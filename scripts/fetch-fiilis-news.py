#!/usr/bin/env python3
"""Fetch Yle headlines + X trends into fiilis/news.json for Fiilis Tesla."""
import urllib.request, re, json, datetime, xml.etree.ElementTree as ET, pathlib, sys
UA = "Mozilla/5.0 (compatible; FiilisNews/1.0)"
SKIP = re.compile(
    r"kuol|murha|ampu|hyökkäys|väkival|onnettomuu|terrori|pommi|raisk|itsemurha|sota\b|massacre|killed|shooting|rape|\bdead\b",
    re.I,
)
LATIN = re.compile(r"^[\w\s#@\'\-\.&!:?+/]+$", re.UNICODE)
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "fiilis" / "news.json"

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def yle_items():
    out = []
    feeds = [
        "https://feeds.yle.fi/uutiset/v1/majorHeadlines/YLE_UUTISET.rss",
        "https://yle.fi/rss/uutiset/tuoreimmat",
    ]
    for feed in feeds:
        try:
            root = ET.fromstring(get(feed))
            for it in root.findall(".//item"):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                if not title or title.lower().startswith("svenska"):
                    continue
                if SKIP.search(title):
                    continue
                out.append({"title": title, "url": link, "source": "Yle"})
                if len(out) >= 3:
                    return out
            if out:
                return out
        except Exception as e:
            print("yle fail", feed, e, file=sys.stderr)
    return out

def trends(url, limit=8):
    html = get(url).decode("utf-8", "replace")
    pairs = re.findall(r'href="(https://twitter\.com/search\?q=[^"]+)"[^>]*>([^<]+)<', html)
    seen, out = set(), []
    for href, name in pairs:
        name = " ".join(name.split())
        if not name or name.lower() in seen:
            continue
        if SKIP.search(name):
            continue
        seen.add(name.lower())
        out.append({"title": name, "url": href.replace("twitter.com", "x.com"), "source": "X"})
        if len(out) >= limit:
            break
    return out

def main():
    yle = yle_items()
    x = trends("https://trends24.in/united-states/", 6)
    seen = {i["title"].lower() for i in x}
    for it in trends("https://trends24.in/", 12):
        if it["title"].lower() in seen:
            continue
        if not LATIN.match(it["title"].replace("#", "")):
            continue
        x.append(it)
        seen.add(it["title"].lower())
        if len(x) >= 5:
            break
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "yle": yle[:3],
        "x": x[:4],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT, "yle", len(payload["yle"]), "x", len(payload["x"]))

if __name__ == "__main__":
    main()
