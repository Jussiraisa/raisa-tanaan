#!/usr/bin/env python3
"""Fetch Mea Lianna + Milla Vivida schedules from Google Sheets and merge into shared.json."""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SHARED_PATH = "/workspace/gh-tanaan/shared.json"
TZ = ZoneInfo("Europe/Helsinki")

SHEETS = [
    {
        "key": "mea",
        "who": "mea",
        "title": "Lianna",
        "url": "https://docs.google.com/spreadsheets/d/1NWw7eFqXKeKqKRCwuRY4H-PiyAMa-_LuOMqVmkJUxBg/export?format=csv",
        "fallback": "/workspace/sheet-1NWw7eFqXKeKqKRCwuRY4H-PiyAMa-_LuOMqVmkJUxBg.csv",
    },
    {
        "key": "milla",
        "who": "milla",
        "title": "Vivida",
        "url": "https://docs.google.com/spreadsheets/d/1eEe5XKUp_qncPZ_HpGhZrwn1wTNR_FiB81QMt6gV79o/export?format=csv",
        "fallback": "/workspace/sheet-1eEe5XKUp_qncPZ_HpGhZrwn1wTNR_FiB81QMt6gV79o.csv",
    },
]

TIME_RE = re.compile(
    r"(\d{1,2})(?:[:.](\d{2}))?\s*[-–—]\s*(\d{1,2})(?:[:.](\d{2}))?"
)
WEEK_RE = re.compile(r"^(\d{1,2})\b")

PLACE_RULES = [
    (re.compile(r"@\s*BC\b", re.I), "BellaCenter"),
    (re.compile(r"@\s*Luola\b", re.I), "Luola"),
    (re.compile(r"@\s*Kuoppari\b", re.I), "Kuoppari"),
    (re.compile(r"\bKuoppari\b", re.I), "Kuoppari"),
    (re.compile(r"@\s*Hatsala\b", re.I), "Hatsala"),
    (re.compile(r"@\s*BellaCenter\b", re.I), "BellaCenter"),
]


def fetch_csv(url: str, fallback: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "raisa-tanaan-sync/1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data.decode("utf-8-sig")
    except Exception as exc:
        print(f"fetch failed ({exc}); using fallback {fallback}", file=sys.stderr)
        with open(fallback, "r", encoding="utf-8-sig") as f:
            return f.read()


def pad2(n: int) -> str:
    return f"{n:02d}"


def fmt_hm(h: int, m: int) -> str:
    return f"{pad2(h)}:{pad2(m)}"


def parse_time_range(text: str):
    m = TIME_RE.search(text or "")
    if not m:
        return None
    h1 = int(m.group(1))
    mi1 = int(m.group(2) or 0)
    h2 = int(m.group(3))
    mi2 = int(m.group(4) or 0)
    return fmt_hm(h1, mi1), fmt_hm(h2, mi2)


def parse_place(text: str) -> str:
    for rx, name in PLACE_RULES:
        if rx.search(text or ""):
            return name
    return ""


def cell(row, idx: int) -> str:
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def parse_day_num(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    m = re.match(r"^(\d{1,2})$", raw)
    if not m:
        return None
    n = int(m.group(1))
    if 1 <= n <= 31:
        return n
    return None


def iter_week_blocks(rows):
    """Yield (iso_week, day_nums[7], schedule_cells[7]) for each week block."""
    i = 0
    n = len(rows)
    while i < n:
        c0 = cell(rows[i], 0)
        wm = WEEK_RE.match(c0)
        # Skip header rows like "vko,maanantai,..."
        if c0.lower().startswith("vko"):
            i += 1
            continue
        if wm and any(parse_day_num(cell(rows[i], c)) is not None for c in range(1, 8)):
            week = int(wm.group(1))
            day_nums = [parse_day_num(cell(rows[i], c)) for c in range(1, 8)]
            # Find schedule row: next row that is not blank-only and not Valkku
            j = i + 1
            sched = [""] * 7
            while j < n:
                c0j = cell(rows[j], 0)
                if c0j.lower().startswith("vko"):
                    break
                if WEEK_RE.match(c0j) and any(
                    parse_day_num(cell(rows[j], c)) is not None for c in range(1, 8)
                ):
                    break
                if c0j.lower().startswith("valkku"):
                    j += 1
                    continue
                # Treat as schedule row if any weekday cell has text or times
                cells = [cell(rows[j], c) for c in range(1, 8)]
                if any(cells) or c0j:
                    sched = cells
                    break
                j += 1
            yield week, day_nums, sched
            i += 1
            continue
        i += 1


def schedule_for_date(rows, target: date):
    """Return schedule cell text for target date, or ''."""
    iso = target.isocalendar()
    week = iso.week
    # ISO weekday 1=Mon .. 7=Sun → column index 0..6
    col = iso.weekday - 1
    for w, days, sched in iter_week_blocks(rows):
        if w != week:
            continue
        if days[col] == target.day:
            return sched[col] or ""
    return ""


def event_from_cell(sheet_cfg, target: date, text: str):
    text = (text or "").strip()
    if not text:
        return None
    times = parse_time_range(text)
    if not times:
        return None
    start, end = times
    place = parse_place(text)
    return {
        "id": f"sheet-{sheet_cfg['key']}-{target.isoformat()}",
        "who": sheet_cfg["who"],
        "title": sheet_cfg["title"],
        "date": target.isoformat(),
        "start": start,
        "end": end,
        "place": place,
        "kind": "treeni",
    }


def load_rows(text: str):
    return list(csv.reader(io.StringIO(text)))


def helsinki_today() -> date:
    return datetime.now(TZ).date()


def main():
    today = helsinki_today()
    tomorrow = today + timedelta(days=1)
    targets = [today, tomorrow]

    sheet_events = []
    for cfg in SHEETS:
        raw = fetch_csv(cfg["url"], cfg["fallback"])
        rows = load_rows(raw)
        for d in targets:
            text = schedule_for_date(rows, d)
            ev = event_from_cell(cfg, d, text)
            print(
                f"{cfg['key']} {d.isoformat()} week={d.isocalendar().week} "
                f"cell={text!r} -> {ev}"
            )
            if ev:
                sheet_events.append(ev)

    with open(SHARED_PATH, "r", encoding="utf-8") as f:
        shared = json.load(f)

    old_extras = shared.get("extras") or []
    kept = [
        e
        for e in old_extras
        if not str(e.get("id") or "").startswith("sheet-")
    ]
    # Preserve order: kept (cal/trip/…) then sheet events by date/who
    sheet_events.sort(key=lambda e: (e["date"], e["who"], e.get("start") or ""))
    shared["extras"] = kept + sheet_events
    shared["updated"] = int(datetime.now(timezone.utc).timestamp() * 1000)

    with open(SHARED_PATH, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(sheet_events)} sheet events; total extras={len(shared['extras'])}")
    print("updated=", shared["updated"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
