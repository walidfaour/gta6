#!/usr/bin/env python3
"""
lurewatch - find newly registered domains that ride a hype keyword (a game launch,
a brand, an event) and flag the ones that behave like lures.

  python3 lurewatch.py                       # GTA 6 themed, last 3 days
  python3 lurewatch.py -p 'black-?friday' -d 7
  python3 lurewatch.py -p 'yourbrand' -d 14 -o yourbrand.csv

Source: the free WhoisDS newly-registered-domains feed (a daily sample).
Probing is read-only: one GET per domain, no redirects followed, body capped,
nothing executed. Run it from a lab VM, not a production workstation.
Report what you find (Google Safe Browsing, registrar abuse, Cloudflare abuse)
and share defanged names only.

Needs: python3 (stdlib only) and curl.
"""
import argparse, base64, concurrent.futures as cf, csv, datetime as dt, html, os, re, subprocess, sys, zipfile

FEED = "https://www.whoisds.com//whois-database/newly-registered-domains/{}/nrd"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

SIGNALS = {
    # name: (weight, regex with ONE capturing group)
    "file_host":   (3, r"((?:mega\.nz|mediafire\.com|gofile\.io|pixeldrain\.com|drive\.google\.com/file|dropbox\.com/s/|anonfiles|workupload|krakenfiles)[^\"'\s<]{0,30})"),
    "executable":  (3, r"href=[\"'][^\"']+\.(exe|msi|apk|scr|zip|rar|7z|iso)[\"']"),
    "dl_bait":     (2, r"(free download|download now|direct download|download for pc|pc download|full version|setup\.exe|installer\.exe|cracked|repack|torrent|steam key|activation key)"),
    "cjk_dl_bait": (3, r"(免费下载|中文版下载|官方下载|下载地址)"),
    "crypto":      (2, r"(airdrop|presale|connect wallet|hold \d+k|\$gta6\w{0,12})"),
    "gambling":    (2, r"(online casino|casino bonus|free spins|slot gacor|jackpot|deposit bonus|sportsbook|judi online)"),
    "community":   (1, r"((?:t\.me|discord\.gg)/\w{1,30})"),
}
NAME_BAIT = re.compile(r"(download|xiazai|apk|crack|free|giveaway|slots?|casino|bet|airdrop|token|beta|leak|early|unlock|keys?)", re.I)


def feed_day(day, cache):
    path = os.path.join(cache, f"{day}.zip")
    if not (os.path.exists(path) and zipfile.is_zipfile(path)):
        token = base64.b64encode(f"{day}.zip".encode()).decode()
        subprocess.run(["curl", "-s", "--max-time", "90", "-o", path, FEED.format(token)], check=False)
    if not zipfile.is_zipfile(path):
        return []
    with zipfile.ZipFile(path) as z:
        return [l.strip() for n in z.namelist() for l in z.read(n).decode("utf-8", "ignore").splitlines() if l.strip()]


def fetch(domain):
    for scheme in ("https://", "http://"):
        p = subprocess.run(["curl", "-s", "--max-time", "8", "--max-filesize", "400000", "-r", "0-80000",
                            "-A", UA, "-o", "-", "-w", "\n__LW__%{http_code}|%{redirect_url}", scheme + domain + "/"],
                           capture_output=True)
        out = p.stdout.decode("utf-8", "ignore")
        if "__LW__" in out:
            body, meta = out.rsplit("\n__LW__", 1)
            code, redirect = (meta.split("|", 1) + [""])[:2]
            if code != "000":
                return code, redirect, body
    return "000", "", ""


def probe(row):
    day, domain = row
    code, redirect, body = fetch(domain)
    t = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    title = re.sub(r"\s+", " ", html.unescape(t.group(1))).strip()[:90] if t else ""
    score, hits = 0, []
    for name, (weight, rx) in SIGNALS.items():
        found = sorted({m if isinstance(m, str) else m[0] for m in re.findall(rx, body, re.I)})
        if found:
            score += weight * min(len(found), 3)
            hits.append(f"{name}:{'/'.join(x.lower()[:28] for x in found[:3])}")
    nb = sorted({m.lower() for m in NAME_BAIT.findall(domain.split(".")[0])})
    if nb:
        score += 2 * len(nb)
        hits.insert(0, f"name:{'/'.join(nb)}")
    if "Just a moment" in body and code == "403":
        hits.append("cf_challenge")
        score += 1
    if code == "000":
        hits.append("no_response")
    return [score, day, domain, domain.replace(".", "[.]"), code, redirect[:80], title, " ".join(hits)]


def main():
    ap = argparse.ArgumentParser(description="Hunt hype-keyword lookalike domains in the daily new-domain feed.")
    ap.add_argument("-p", "--pattern", default=r"gta[-_]?(6|vi)([^0-9]|$)", help="regex matched against new domains")
    ap.add_argument("-d", "--days", type=int, default=3, help="how many feed days to scan (default 3)")
    ap.add_argument("-t", "--threads", type=int, default=12)
    ap.add_argument("-o", "--out", default=f"lurewatch_{dt.date.today()}.csv")
    ap.add_argument("-n", "--top", type=int, default=15, help="rows to print")
    a = ap.parse_args()

    cache = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "lurewatch")
    os.makedirs(cache, exist_ok=True)
    rx = re.compile(a.pattern, re.I)
    today = dt.datetime.now(dt.timezone.utc).date()
    rows, seen = [], set()
    for i in range(1, a.days + 1):                      # yesterday first; a missing day is skipped
        day = (today - dt.timedelta(days=i)).isoformat()
        for d in feed_day(day, cache):
            if rx.search(d) and d not in seen:
                seen.add(d)
                rows.append((day, d))
    print(f"[lurewatch] {len(rows)} new domains match /{a.pattern}/ over {a.days} feed days", file=sys.stderr)
    if not rows:
        return
    with cf.ThreadPoolExecutor(a.threads) as ex:
        res = sorted(ex.map(probe, rows), key=lambda r: (-r[0], r[2]))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "feed_day", "domain", "defanged", "http", "redirect", "title", "signals"])
        w.writerows(res)
    print(f"{'score':>5}  {'feed day':10}  {'domain (defanged)':38}  signals", file=sys.stderr)
    for r in res[:a.top]:
        print(f"{r[0]:>5}  {r[1]:10}  {r[3][:38]:38}  {r[7][:90]}")
    print(f"[lurewatch] full results: {a.out}. Report, don't repost live links.", file=sys.stderr)


if __name__ == "__main__":
    main()
