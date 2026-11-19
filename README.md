# lurewatch

Every big launch gets its own crop of new domains: fake "PC downloads", fake giveaways, crypto tokens, gambling pages. lurewatch finds the ones riding a keyword and scores how lure-like they are, so you can report them before they get traffic.

```
$ python3 lurewatch.py -d 7
[lurewatch] 83 new domains match /gta[-_]?(6|vi)([^0-9]|$)/ over 7 feed days
score  feed day    domain (defanged)                       signals
   11  2026-11-14  gta6zwenbanxiazai[.]com[.]cn            name:xiazai cjk_dl_bait:下载地址/中文版下载/免费下载
    8  2026-11-18  gta6giveaway[.]fun                      name:giveaway crypto:$gta6/connect wallet/hold 25k
    4  2026-11-15  gta6download[.]cloud                    name:download dl_bait:pc download
```

## How it works

1. Pulls the free WhoisDS newly-registered-domains feed (a daily sample) for the last N days and caches it.
2. Keeps the domains that match your regex.
3. Probes each one read-only: one GET, no redirects followed, body capped, nothing executed.
4. Scores signals: bait words in the domain name, file-host links, executable links, download bait text (including Chinese), crypto wallet bait, gambling bait, Cloudflare bot challenges.
5. Prints the top hits defanged and writes everything to CSV.

## Usage

```
python3 lurewatch.py                          # GTA 6 themed, last 3 days
python3 lurewatch.py -p 'black-?friday' -d 7  # any hype keyword
python3 lurewatch.py -p 'yourbrand' -d 14 -o yourbrand.csv
```

Needs python3 (standard library only) and curl.

## Rules

- Run it from a lab VM, not a production workstation.
- A match is not a verdict. Most hits are SEO content farms. Check the high scores by hand in a sandbox.
- Report, don't repost: Google Safe Browsing, Microsoft's unsafe-site report, the registrar's abuse contact (RDAP lists it) and Cloudflare abuse for proxied sites.
- Share defanged names only.

## License

MIT
