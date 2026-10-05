#!/usr/bin/env python3
"""Fetch Mea Lianna + Milla Vivida schedules and Ellen Ambrosia leirit/kisat from Google Sheets and merge into shared.json."""

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
        # Fallback: single time like "klo 18 (paikalle klo 17)" -> start at arrival, end +2h from main time
        singles = re.findall(r"klo\s*(\d{1,2})(?:[.:](\d{2}))?", text or "", re.I)
        if not singles:
            return None
        mh, mm = int(singles[0][0]), int(singles[0][1] or 0)
        arr = re.search(r"paikalle\s*klo\s*(\d{1,2})(?:[.:](\d{2}))?", text or "", re.I)
        sh, sm = (int(arr.group(1)), int(arr.group(2) or 0)) if arr else (mh, mm)
        if not (0 <= mh <= 23 and 0 <= sh <= 23):
            return None
        return fmt_hm(sh, sm), fmt_hm(min(mh + 2, 23), mm)
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


def _parse_iso_date(value):
    """Parse the date portion of an extra's date field, if present."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_end_time(value):
    """Parse HH:MM (or HH.MM) end times used by shared.json extras."""
    raw = str(value or "").strip().replace(".", ":")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        return None


def is_expired_extra(extra, now: datetime) -> bool:
    """Return whether an extra is over and should leave the board display."""
    start = _parse_iso_date(extra.get("date"))
    end_date = _parse_iso_date(extra.get("dateEnd")) or start
    if not start or not end_date:
        return False

    today = now.date()
    if end_date < today:
        return True

    # A multi-day extra remains visible until its final date.  For a
    # same-day extra, remove it once its explicit end time has passed.
    if start == today and end_date == today:
        end_time = _parse_end_time(extra.get("end"))
        return end_time is not None and now.time() >= end_time
    return False


def drop_expired_extras(extras, now: datetime):
    return [extra for extra in extras if not is_expired_extra(extra, now)]


AMBROSIA = {
    "url": "https://docs.google.com/spreadsheets/d/16me62qlQyhhczEd_9H08DJw_5w4On9uUSIpa-21mEF0/export?format=csv",
    "fallback": "/workspace/sheet-16me62qlQyhhczEd_9H08DJw_5w4On9uUSIpa-21mEF0.csv",
}
AMB_PREFIX = "info-ambrosia-"
AMB_DATE_RE = re.compile(r"(\d{1,2})\.?(?:(\d{1,2})\.)?\s*[-–—]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})")
AMB_ONE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def ambrosia_events():
    """Column-per-event sheet: rows Mikä/Milloin/Paikka/Kulkuväline/Huoltaja/Kuski/Valmentaja."""
    try:
        raw = fetch_csv(AMBROSIA["url"], AMBROSIA["fallback"])
        try:
            with open(AMBROSIA["fallback"], "w", encoding="utf-8") as f:
                f.write(raw)
        except OSError:
            pass
    except Exception as exc:  # noqa: BLE001
        print("ambrosia fetch failed:", exc)
        return None
    rows = load_rows(raw)
    lab = {}
    kuskit = []
    for r in rows:
        if not r:
            continue
        k = (r[0] or "").strip().lower()
        if k.startswith("kuski"):
            kuskit.append(r)
        elif k and k not in lab:
            lab[k] = r
    what = lab.get("mikä")
    when = lab.get("milloin")
    if not what or not when:
        return []
    out = []
    for i in range(1, len(what)):
        kind = cell(what, i)
        w = cell(when, i).replace(" ", "")
        if not kind or not w:
            continue
        m = AMB_DATE_RE.search(w)
        if m:
            d1, m1, d2, m2, y = m.groups()
            m1 = m1 or m2
            try:
                sd = date(int(y), int(m1), int(d1))
                ed = date(int(y), int(m2), int(d2))
            except ValueError:
                continue
        else:
            m = AMB_ONE_RE.match(w)
            if not m:
                continue  # "Tarkentuu myöh."
            sd = ed = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        place = cell(lab.get("paikka") or [], i).strip()
        if place.lower().startswith("tarkentuu"):
            place = ""
        notes = []
        for key, label in (("kulkuväline", "kulku"), ("huoltaja", "huoltaja"), ("yöpaikka", "yö")):
            v = cell(lab.get(key) or [], i).strip()
            if v and v != "?":
                notes.append(f"{label} {v}")
        ks = [cell(r, i).strip() for r in kuskit if cell(r, i).strip()]
        if ks:
            notes.append("kuski " + ", ".join(ks))
        title = f"Ambrosia {kind.lower()}"
        if place:
            title += f" · {place}"
        ev = {
            "id": f"{AMB_PREFIX}{sd.isoformat()}",
            "who": "ellen",
            "title": title,
            "date": sd.isoformat(),
            "kind": "info",
            "place": place,
        }
        if ed != sd:
            ev["dateEnd"] = ed.isoformat()
        if notes:
            ev["note"] = "; ".join(notes)
        out.append(ev)
    return out


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
    amb = ambrosia_events()
    print(f"ambrosia events: {amb}")
    kept = [
        e
        for e in old_extras
        if not str(e.get("id") or "").startswith("sheet-")
        and not (amb is not None and str(e.get("id") or "").startswith(AMB_PREFIX))
    ]
    if amb:
        kept += amb
    # Preserve order: kept (cal/trip/…) then sheet events by date/who
    sheet_events.sort(key=lambda e: (e["date"], e["who"], e.get("start") or ""))
    merged_extras = kept + sheet_events
    shared["extras"] = drop_expired_extras(merged_extras, datetime.now(TZ))
    shared["updated"] = int(datetime.now(timezone.utc).timestamp() * 1000)

    with open(SHARED_PATH, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(sheet_events)} sheet events; total extras={len(shared['extras'])}")
    print("updated=", shared["updated"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
