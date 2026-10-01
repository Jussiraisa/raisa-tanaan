#!/usr/bin/env python3
"""Build loppuvuosi.html year-end board from calendar JSON + shared.json."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_JSON = Path("/workspace/loppuvuosi-events.json")
SHARED = ROOT / "shared.json"
OUT = ROOT / "loppuvuosi.html"
OUT_COPY = ROOT / "loppuvuosi-2026.html"

TODAY = date(2026, 10, 1)
RANGE_START = date(2026, 10, 1)
RANGE_END = date(2026, 12, 31)  # inclusive

MONTHS = {
    10: ("Lokakuu", "m10"),
    11: ("Marraskuu", "m11"),
    12: ("Joulukuu", "m12"),
}
DOW_SHORT = ["ma", "ti", "ke", "to", "pe", "la", "su"]

CAT = {
    "kisa": ("#e11d48", "Kisat", "kisa"),
    "matka": ("#7c3aed", "Matka / leiri", "matka"),
    "koulu": ("#2563eb", "Koulu", "koulu"),
    "perhe": ("#db2777", "Perhe", "perhe"),
    "terveys": ("#059669", "Terveys", "terveys"),
    "harrastus": ("#ea580c", "Harrastus", "harrastus"),
}

# ---- helpers ----

def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def parse_iso_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def event_bounds(e: dict) -> tuple[date, date, bool, str | None]:
    s, en = e.get("start") or {}, e.get("end") or {}
    if "date" in s:
        sd = date.fromisoformat(s["date"][:10])
        ed = date.fromisoformat(en["date"][:10]) - timedelta(days=1)
        return sd, ed, True, None
    sdt = parse_iso_dt(s["dateTime"])
    edt = parse_iso_dt(en["dateTime"])
    # keep local calendar date from the offset-aware datetime as-is
    return sdt.date(), edt.date(), False, sdt.strftime("%H:%M")


def is_routine(title: str) -> bool:
    t = title.lower().strip()
    # Keep competitions/camps even if title contains treeni-ish words
    keep_markers = (
        "turnaus", "kisa", "cup", "leiri", "mestik", "testit",
        "päättärit", "näytös", "harkkakisa", "hionta",
    )
    if any(m in t for m in keep_markers):
        return False
    # Weekly practices
    routines = (
        r"\blianna treeni\b",
        r"\bvivida treeni\b",
        r"\bvivida oheinen\b",
        r"\blianna voima\b",
        r"\blianna laji\b",
        r"\bliannan voimat\b",
        r"\bmea · liannan voimat\b",
        r"\bmea valmennus\b",
        r"\bmilla · valmennus\b",
        r"\bsamuel treeni",
        r"\bsamuel treenit",
        r"\bwelhot 2018:\s*\d",  # timed weekly slots
        r"\bambrosia \(ellen\) treeni",
        r"\bpadel\b",
    )
    for pat in routines:
        if re.search(pat, t):
            return True
    return False


def categorize(title: str, detail: str = "") -> str:
    t = (title + " " + detail).lower()
    if any(x in t for x in (
        "turnaus", "kisa", "cup", "mestik", "harkkakisa", "testit",
        "näytös", "elixiria", "illusion", "ttnv",
    )):
        return "kisa"
    if any(x in t for x in (
        "leiri", "lontoo", "oulu", "matka", "reissu", "vierumäki",
        "kisakallio", "hionta",
    )):
        return "matka"
    if any(x in t for x in (
        "terapia", "siedätys", "arja",
    )):
        return "terveys"
    if any(x in t for x in (
        "koe", "koulukuvaus", "vanhempain", "pelipassi", "välitesti",
        "hakemus", "kemian opetus", "kemia", "wilma", "maa03", "rub",
    )):
        return "koulu"
    if any(x in t for x in (
        "synttär", "40v", "hautajais", "ainon", "riikka",
    )) and "oulu" not in t and "padel" not in t:
        # Riikka birthday etc — but Riikka Oulu already matka
        if "oulu" in t:
            return "matka"
        return "perhe"
    if any(x in t for x in ("tesla", "päättärit")):
        return "harrastus"
    if "oulu" in t or "koulupäiv" in t:
        return "matka"
    return "harrastus"


def shorten(title: str, n: int = 14) -> str:
    t = title.strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def fmt_day(d: date) -> str:
    return f"{d.day}.{d.month}."


def fmt_range(a: date, b: date) -> str:
    if a == b:
        return fmt_day(a)
    return f"{fmt_day(a)}–{fmt_day(b)}"


def normalize_cal_event(e: dict, cal: str) -> dict | None:
    title_raw = (e.get("summary") or "").strip()
    if not title_raw:
        return None
    if is_routine(title_raw):
        return None
    # Skip duplicate Welhot generic turnaus if Perhe has better Samuel titled one
    # (handled later in dedupe) — keep for now
    sd, ed, all_day, tm = event_bounds(e)
    if ed < RANGE_START or sd > RANGE_END:
        return None
    # Clamp display to window
    disp_s = max(sd, RANGE_START)
    disp_e = min(ed, RANGE_END)

    loc = (e.get("location") or "").strip()
    desc = (e.get("description") or "").strip()
    desc_one = re.sub(r"\s+", " ", desc)

    title, detail, cat_hint = polish_title(title_raw, loc, desc_one, tm, all_day, cal)

    cat = cat_hint or categorize(title, detail)
    color, label, cat_key = CAT[cat]

    # Multi-day trips: never show a clock time on the board
    show_time = None if all_day else tm
    if disp_s != disp_e and cat_key == "matka":
        show_time = None
    if title in ("Riikka Oulu", "Lontoo"):
        show_time = None

    return {
        "title": title,
        "detail": detail,
        "start": disp_s,
        "end": disp_e,
        "time": show_time,
        "cat": cat_key,
        "color": color,
        "label": label,
        "source": f"cal:{cal}",
        "raw": title_raw,
    }


def polish_title(title: str, loc: str, desc: str, tm: str | None, all_day: bool, cal: str):
    t = title.strip()
    detail_parts = []

    # London trips
    if t.lower().startswith("lontoon reissu"):
        detail = desc or t
        if loc:
            detail = f"{detail} · {loc}" if detail else loc
        return "Lontoo", detail.strip(" ·"), "matka"

    # Riikka Oulu / koulupäivät → Riikka Oulu
    if re.search(r"riikka\s*oulu", t, re.I) or re.search(r"riikan\s*koulupäiv", t, re.I):
        detail = desc or t
        return "Riikka Oulu", detail, "matka"

    # Samuel Welhot tournaments
    m = re.search(r"Welhot P9 turnaus\s+(.+)", t, re.I)
    if m:
        place = m.group(1).strip()
        # normalize "Kuopio Studentia" etc
        short_place = place
        short_place = short_place.replace("Kuopio Studentia", "Studentia")
        short_place = short_place.replace("Kuopio Luola", "Luola")
        short_place = short_place.replace("(Studentia · kotiturnaus)", "Studentia")
        short_place = short_place.replace("(Luola · kotiturnaus)", "Luola")
        title_out = f"Samuel turnaus · {short_place}"
        detail = desc or t
        if loc and loc not in detail:
            detail = f"{detail} · {loc}"
        return title_out, detail, "kisa"

    if re.search(r"Welhot Joensuu", t, re.I):
        detail = desc or t
        return "Samuel turnaus · Joensuu", detail, "kisa"

    # Generic Welhot 2018: Turnaus — keep as fallback (may dedupe)
    if re.match(r"Welhot 2018:\s*Turnaus", t, re.I):
        place = loc.split(",")[0].strip() if loc else ""
        # map known places
        place_map = {
            "Nepenmäen Koulu": "Joensuu",
            "Lippumäen uima- ja liikuntahalli": "Lippumäki",
            "Studentia": "Studentia",
            "Lintharjun Liikuntakeskus": "Suonenjoki",
            "Ahmon koulu": "Siilinjärvi",
            "Luola- savilahden liikunta ja tapahtumakeskus": "Luola",
        }
        for k, v in place_map.items():
            if k.lower() in (loc or "").lower() or k.lower() in place.lower():
                place = v
                break
        title_out = f"Samuel turnaus · {place}" if place else "Samuel turnaus"
        detail = desc or t
        if loc:
            detail = f"{detail} · {loc}" if detail else loc
        # Junnuliiga Lippumäki
        if "junnuliiga" in t.lower():
            title_out = "Samuel turnaus · Lippumäki"
            detail = desc or t
            if loc:
                detail = f"{detail} · {loc}"
        return title_out, detail, "kisa"

    # Vivida / Lianna competitions & camps
    mapping = [
        (r"Vivida aluerinkileiri", "Vivida leiri · Kisakallio", "matka"),
        (r"Vivida KISAT @TTNV", "Vivida TTNV Cup", "kisa"),
        (r"Vivida KRV", "Vivida KRV-näytös", "kisa"),
        (r"Vivida kisaviikonloppu", "Vivida kisat · Espoo/TRE", "kisa"),
        (r"Vivida Elixiria", "Vivida Elixiria Cup", "kisa"),
        (r"Vivida Mestikset", "Vivida Mestikset · JKL", "kisa"),
        (r"Vivida päättärit", "Vivida päättärit", "harrastus"),
        (r"Lianna Illusion Cup", "Lianna Illusion Cup (?)", "kisa"),
        (r"Lianna Elixiria", "Lianna Elixiria (?)", "kisa"),
        (r"Lianna Mestikset", "Lianna Mestikset · JKL", "kisa"),
        (r"Lianna Liiton testit", "Lianna Liiton testit", "kisa"),
        (r"Lianna päättärit", "Lianna päättärit", "harrastus"),
        (r"Vivida hiontaleiri|Milla · Vivida hiontaleiri", "Vivida hiontaleiri", "matka"),
    ]
    for pat, out, cat in mapping:
        if re.search(pat, t, re.I):
            detail = desc or t
            if loc and loc not in detail:
                detail = f"{detail} · {loc}"
            return out, detail, cat

    # School / health / family polish
    polish = [
        (r"Ellen · UE-koe", "Ellen koe · UE", "koulu"),
        (r"Ellen · Äidinkielen koe", "Ellen koe · äidinkieli", "koulu"),
        (r"Ellen · Matematiikan koe", "Ellen koe · matematiikka", "koulu"),
        (r"Mea · kemia koe", "Mea KE-koe", "koulu"),
        (r"Mea · kemian opetus", "Mea + Jussi kemian opetus", "koulu"),
        (r"Ellen · Ambrosia vanhempainilta", "Ellen vanhempainilta", "koulu"),
        (r"Samuel · Welhot P9 pelipassi", "Samuel pelipassi", "koulu"),
        (r"Mea terapia · Minna", "Mea terapia", "terveys"),
        (r"Mea terapia · Tarja", "Mea terapia", "terveys"),
        (r"Mea Arja", "Mea Arja", "terveys"),
        (r"Mea siedätys", "Mea siedätys", "terveys"),
        (r"Riikka 40V", "Riikka 40V", "perhe"),
        (r"Riikka synttärit sukulaiset", "Riikka synttärit · sukulaiset", "perhe"),
        (r"Riikka synttärit", "Riikka synttärit", "perhe"),
        (r"Ellin hautajaiset", "Ellin hautajaiset", "perhe"),
        (r"Ainon synttärit", "Ainon synttärit", "perhe"),
        (r"Tesla kotihuolto", "Tesla kotihuolto", "harrastus"),
        (r"Milla · MAA03", "Milla · MAA03 välitesti (geometria)", "koulu"),
    ]
    for pat, out, cat in polish:
        if re.search(pat, t, re.I):
            detail = desc or t
            if loc and loc not in detail:
                detail = f"{detail} · {loc}"
            return out, detail, cat

    detail = desc or t
    if loc and loc not in detail:
        detail = f"{detail} · {loc}"
    return t, detail, None


def extras_to_events(shared: dict) -> list[dict]:
    out = []
    for ex in shared.get("extras") or []:
        eid = ex.get("id") or ""
        # Prefer info-* ; also allow cal-* that add unique info not in calendar
        # Task: Include shared.json extras with info-* ids that fall in range.
        if not eid.startswith("info-"):
            continue
        d = ex.get("date")
        if not d:
            continue
        sd = date.fromisoformat(d[:10])
        ed = date.fromisoformat((ex.get("dateEnd") or d)[:10])
        if ed < RANGE_START or sd > RANGE_END:
            continue
        # Skip routine treeni extras (Liannan voimat weekly)
        title = (ex.get("title") or "").strip()
        kind = ex.get("kind") or ""
        if kind == "treeni" and is_routine(title) or (
            kind == "treeni" and re.search(r"voimat|treeni|oheinen|valmennus", title, re.I)
            and not re.search(r"hionta|leiri|kisa|cup|turnaus", title, re.I)
        ):
            # Keep hiontaleiri (kind treeni in shared but it's a camp)
            if "hionta" not in title.lower() and "leiri" not in title.lower():
                continue

        who = (ex.get("who") or "").strip()
        place = (ex.get("place") or "").strip()
        note = (ex.get("note") or "").strip()
        start_t = (ex.get("start") or "").strip() or None
        if start_t and len(start_t) == 5:
            pass
        elif start_t:
            start_t = start_t[:5]

        # Build display title matching previous board
        title_out, detail, cat = polish_extra(eid, title, who, place, note)

        color, label, cat_key = CAT[cat]
        disp_s = max(sd, RANGE_START)
        disp_e = min(ed, RANGE_END)
        if title_out in ("Riikka Oulu", "Lontoo") or disp_s != disp_e and cat_key == "matka":
            start_t = None
        out.append({
            "title": title_out,
            "detail": detail,
            "start": disp_s,
            "end": disp_e,
            "time": start_t,
            "cat": cat_key,
            "color": color,
            "label": label,
            "source": f"extra:{eid}",
            "raw": title,
        })
    return out


def polish_extra(eid: str, title: str, who: str, place: str, note: str):
    t = title
    detail_bits = [t]
    if note:
        detail_bits.append(note)
    if place:
        detail_bits.append(place)
    detail = " · ".join(dict.fromkeys(detail_bits))  # dedupe order-preserving

    # Specific id/title mappings to match previous board
    if "koulukuvaus-samuel" in eid:
        return "Samuel koulukuvaus", detail, "koulu"
    if "koulukuvaus-ellen" in eid:
        return "Ellen koulukuvaus", detail, "koulu"
    if "samuel-pelipassi" in eid:
        return "Samuel pelipassi", (
            "WhatsApp Welhot P9 Info: hanki pelipassi mielellään 1.10. mennessä"
            if not note else detail
        ), "koulu"
    if "ellen-vanhempainilta" in eid:
        return "Ellen vanhempainilta", detail, "koulu"
    if "mea-ke-koe" in eid:
        return "Mea KE-koe", detail, "koulu"
    if "rooma-hakemus" in eid:
        return "Rooman hakemus", detail, "koulu"
    if "samuel-turnaus" in eid:
        # prefer place-based short title
        place_l = place.lower()
        if "joensuu" in place_l or "joensuu" in t.lower():
            return "Samuel turnaus · Joensuu", detail, "kisa"
        if "studentia" in place_l or "studentia" in t.lower():
            return "Samuel turnaus · Studentia", detail, "kisa"
        if "suonenjoki" in place_l:
            return "Samuel turnaus · Suonenjoki", detail, "kisa"
        if "siilinjärvi" in place_l or "siilinjarvi" in place_l:
            return "Samuel turnaus · Siilinjärvi", detail, "kisa"
        if "luola" in place_l:
            return "Samuel turnaus · Luola", detail, "kisa"
        return f"Samuel turnaus · {place or t}", detail, "kisa"
    if "milla-hionta" in eid or "hiontaleiri" in t.lower():
        return "Vivida hiontaleiri", detail, "matka"
    if "lianna-harkkakisa" in eid:
        return "Lianna harkkakisa · Ylä-Pyörö", detail, "kisa"
    if "riikka-oulu" in eid:
        return "Riikka Oulu", detail, "matka"
    if "mea-terapia" in eid:
        return "Mea terapia", detail, "terveys"
    if "ellen-koe-aidinkieli" in eid:
        return "Ellen koe · äidinkieli", detail, "koulu"
    if "ellen-koe-matematiikka" in eid:
        return "Ellen koe · matematiikka", detail, "koulu"
    if "ambrosia" in eid:
        if "leiri" in t.lower() or "vierumäki" in t.lower():
            return title if title.startswith("Ambrosia") else f"Ambrosia leiri · {place}", detail, "matka"
        return title if title.startswith("Ambrosia") else f"Ambrosia kisat · {place}", detail, "kisa"

    cat = categorize(title, detail)
    # who-prefix for school exams if not already
    if cat == "koulu" and who and who.lower() not in t.lower():
        who_cap = who[:1].upper() + who[1:]
        t = f"{who_cap} · {t}"
    return t, detail, cat


def dedupe_key(ev: dict) -> str:
    """Same title+start day (normalized)."""
    # Normalize title for dedupe of near-duplicates
    t = ev["title"].lower()
    t = t.replace("(?)", "").strip()
    t = re.sub(r"\s+", " ", t)
    # Map aliases
    aliases = [
        (r"riikka oulu|riikan koulupäiv", "riikka oulu"),
        (r"samuel turnaus · joensuu|samuel · welhot joensuu", "samuel turnaus joensuu"),
        (r"samuel turnaus · studentia", "samuel turnaus studentia"),
        (r"samuel turnaus · suonenjoki", "samuel turnaus suonenjoki"),
        (r"samuel turnaus · siilinjärvi", "samuel turnaus siilinjarvi"),
        (r"samuel turnaus · luola", "samuel turnaus luola"),
        (r"samuel turnaus · lippumäki", "samuel turnaus lippumaki"),
        (r"samuel pelipassi", "samuel pelipassi"),
        (r"ellen vanhempainilta", "ellen vanhempainilta"),
        (r"ellen koulukuvaus", "ellen koulukuvaus"),
        (r"samuel koulukuvaus", "samuel koulukuvaus"),
        (r"mea ke-koe|mea · kemia", "mea ke-koe"),
        (r"vivida hiontaleiri", "vivida hiontaleiri"),
        (r"lontoo", "lontoo"),
        (r"lianna \+ vivida päättärit|lianna päättärit|vivida päättärit", "paattarit"),
    ]
    norm = t
    for pat, rep in aliases:
        if re.search(pat, t):
            norm = rep
            break
    return f"{norm}|{ev['start'].isoformat()}"


def merge_events(events: list[dict]) -> list[dict]:
    """Dedupe; prefer richer detail / better time / preferred source."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        buckets[dedupe_key(ev)].append(ev)

    merged = []
    for key, group in buckets.items():
        # Special: combine Lianna + Vivida päättärit
        if key.startswith("paattarit|"):
            d = group[0]["start"]
            merged.append({
                "title": "Lianna + Vivida päättärit",
                "detail": "Vivida päättärit" if len(group) == 1 else "Lianna + Vivida päättärit",
                "start": d,
                "end": group[0]["end"],
                "time": None,
                "cat": "harrastus",
                "color": CAT["harrastus"][0],
                "label": CAT["harrastus"][1],
                "source": "merge:paattarit",
                "raw": "päättärit",
            })
            continue

        def score(ev: dict) -> tuple:
            # Prefer extras for Ambrosia (only in extras), prefer timed, longer detail,
            # prefer Perhe over Jussi Welhot generic, prefer non-generic titles
            src = ev.get("source", "")
            s = 0
            if src.startswith("extra:"):
                s += 5
            if src.startswith("cal:perhe"):
                s += 3
            if src.startswith("cal:voimistelu"):
                s += 2
            if src.startswith("cal:jussi"):
                s += 1
            if ev.get("time"):
                s += 2
            s += min(len(ev.get("detail") or ""), 80) / 80
            # Prefer nicer titles without "Welhot 2018"
            if "Welhot 2018" not in (ev.get("raw") or ""):
                s += 1
            return (s, len(ev.get("detail") or ""))

        best = max(group, key=score)
        # Expand end to max of group if same event multi-source
        best = dict(best)
        best["end"] = max(g["end"] for g in group)
        best["start"] = min(g["start"] for g in group)
        # Prefer a time if any has it (not for multi-day matka)
        best_start = min(g["start"] for g in group)
        best_end = max(g["end"] for g in group)
        if best_start != best_end and best.get("cat") == "matka":
            best["time"] = None
        elif best.get("title") in ("Riikka Oulu", "Lontoo"):
            best["time"] = None
        else:
            for g in sorted(group, key=score, reverse=True):
                if g.get("time"):
                    best["time"] = g["time"]
                    break
        merged.append(best)

    # Second pass: drop Joensuu Welhot 2018 duplicate if Samuel turnaus Joensuu exists same day
    # (already covered by alias). Also drop second Samuel koulukuvaus single-day if range exists.
    return merged


def build_days(events: list[dict]) -> dict[str, list[dict]]:
    days: dict[str, list[dict]] = defaultdict(list)
    # stable order: by time then title
    events_sorted = sorted(events, key=lambda e: (e["start"], e.get("time") or "99:99", e["title"]))
    for ev in events_sorted:
        for d in daterange(ev["start"], ev["end"]):
            if d < RANGE_START or d > RANGE_END:
                continue
            iso = d.isoformat()
            range_s = (
                iso if ev["start"] == ev["end"]
                else f"{ev['start'].isoformat()}…{ev['end'].isoformat()}"
            )
            days[iso].append({
                "title": ev["title"],
                "time": ev.get("time"),
                "cat": ev["cat"],
                "detail": ev["detail"],
                "range": range_s,
                "color": ev["color"],
                "label": ev["label"],
                "_start": ev["start"],
                "_end": ev["end"],
            })
    return days


def agenda_for_month(events: list[dict], month: int) -> list[dict]:
    """One row per event that starts in month (or overlaps and starts before — show once at start)."""
    rows = []
    for ev in sorted(events, key=lambda e: (e["start"], e.get("time") or "99:99", e["title"])):
        # show if event intersects month and agenda anchor (start) is in month,
        # OR start before month but still ongoing in month → show only if start in window months
        if ev["end"].month < month and ev["end"].year == 2026:
            continue
        if ev["start"].month > month and ev["start"].year == 2026:
            continue
        # Anchor: use start day; if start before RANGE_START but event continues, use RANGE_START
        anchor = max(ev["start"], RANGE_START)
        if anchor.month != month:
            # multi-month: show in the month where it starts (within window)
            if ev["start"] < RANGE_START and RANGE_START.month == month:
                pass
            else:
                continue
        rows.append(ev)
    return rows


def month_grid_html(year: int, month: int, days: dict) -> str:
    # ISO week grid Mon-Sun
    first = date(year, month, 1)
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    # Monday=0
    start_pad = first.weekday()  # Mon=0
    cells = []
    for _ in range(start_pad):
        cells.append('<div class="cell empty" aria-hidden="true"></div>')
    d = first
    while d <= last:
        iso = d.isoformat()
        evs = days.get(iso) or []
        classes = ["cell"]
        if d < TODAY:
            classes.append("past")
        if d == TODAY:
            classes.append("today")
        if evs:
            classes.append("has")
        # pills: unique titles max 3 (first occurrence order)
        seen = []
        for e in evs:
            if e["title"] not in seen:
                seen.append(e["title"])
        pills = seen[:3]
        aria = f"{d.day}.{d.month}."
        if evs:
            aria += f" {len(evs)} tapahtumaa"
        disabled = " disabled" if not evs else ""
        inner = [f'<div class="n">{d.day}</div>']
        for title in pills:
            # find color of first matching
            color = next(e["color"] for e in evs if e["title"] == title)
            inner.append(
                f'<span class="pill" style="background:{color}">{esc(shorten(title))}</span>'
            )
        cells.append(
            f'<button type="button" class="{" ".join(classes)}" data-day="{iso}"'
            f'{disabled} aria-label="{esc(aria)}">{"".join(inner)}</button>'
        )
        d += timedelta(days=1)
    # trailing empties to complete week
    while len(cells) % 7 != 0:
        cells.append('<div class="cell empty" aria-hidden="true"></div>')
    dow = "".join(f'<div class="dow">{x}</div>' for x in DOW_SHORT)
    return f'<div class="cal">{dow}{"".join(cells)}</div>'


def agenda_html(events: list[dict], month: int) -> str:
    rows = agenda_for_month(events, month)
    if not rows:
        return '<ul class="agenda"></ul>'
    items = []
    for ev in rows:
        when = fmt_range(ev["start"], ev["end"])
        tm = f'<span class="tm">klo {ev["time"]}</span>' if ev.get("time") else ""
        items.append(
            f'<li style="border-left-color:{ev["color"]}" data-day="{ev["start"].isoformat()}">'
            f'<span class="when">{esc(when)}</span>'
            f'<span class="what">{esc(ev["title"])}{tm}</span></li>'
        )
    return f'<ul class="agenda">{"".join(items)}</ul>'


def days_json(days: dict) -> str:
    out = {}
    for iso, evs in sorted(days.items()):
        out[iso] = [
            {
                "title": e["title"],
                "time": e["time"],
                "cat": e["cat"],
                "detail": e["detail"],
                "range": e["range"],
                "color": e["color"],
                "label": e["label"],
            }
            for e in evs
        ]
    return json.dumps(out, ensure_ascii=False, separators=(",", ": "))


CSS = r'''
:root {
  --bg: #0b1220; --card: #152033; --card2: #1c2a42; --text: #f1f5f9;
  --muted: #94a3b8; --line: #243247; --today: #38bdf8;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
body { padding: 12px 12px 40px; max-width: 720px; margin: 0 auto; }
h1 { font-size: 1.55rem; margin: 4px 0 2px; font-weight: 800; letter-spacing: -.02em; }
.sub { color: var(--muted); font-size: .9rem; margin: 0 0 14px; }
.jumps { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 10px; margin-bottom: 8px;
  -webkit-overflow-scrolling: touch; scrollbar-width: none; }
.jumps::-webkit-scrollbar { display: none; }
.jumps a { flex: 0 0 auto; text-decoration: none; color: var(--text); background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 8px 14px; font-weight: 700; font-size: .9rem; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 12px; margin: 0 0 18px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: .8rem; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.month { margin-bottom: 28px; scroll-margin-top: 12px; }
.month h2 { font-size: 1.2rem; margin: 0 0 10px; padding-bottom: 6px; border-bottom: 2px solid var(--line); }
.cal { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; margin-bottom: 12px; }
.dow { text-align: center; font-size: .68rem; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: .04em; padding: 4px 0; }
.cell {
  background: var(--card); border-radius: 10px; min-height: 64px;
  padding: 5px 4px 4px; display: flex; flex-direction: column; gap: 2px;
  border: 0; color: inherit; text-align: left; width: 100%; font: inherit;
  -webkit-tap-highlight-color: transparent;
}
.cell:not(.empty):not(:disabled) { cursor: pointer; }
.cell:not(.empty):not(:disabled):active { transform: scale(.97); background: var(--card2); }
.cell.has { box-shadow: inset 0 0 0 1px rgba(148,163,184,.25); }
.cell.empty { background: transparent; min-height: 0; padding: 0; }
.cell.past { opacity: .42; }
.cell.today { outline: 2px solid var(--today); outline-offset: -1px; background: var(--card2); }
.cell .n { font-size: .85rem; font-weight: 800; color: var(--muted); line-height: 1; margin-bottom: 2px; }
.cell.today .n { color: var(--today); }
.pill {
  display: block; font-size: .58rem; font-weight: 700; line-height: 1.15;
  padding: 2px 3px; border-radius: 4px; color: #fff;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.agenda { list-style: none; margin: 0; padding: 0; }
.agenda li {
  display: grid; grid-template-columns: 4.8rem 1fr; gap: 10px; align-items: start;
  background: var(--card); border-radius: 12px; padding: 10px 12px; margin-bottom: 6px;
  border-left: 4px solid #64748b; width: 100%; border-top:0; border-right:0; border-bottom:0;
  color: inherit; font: inherit; text-align: left; cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.agenda li:active { background: var(--card2); }
.agenda .when { font-weight: 800; font-size: .95rem; font-variant-numeric: tabular-nums; }
.agenda .what { font-size: .98rem; font-weight: 600; }
.agenda .tm { display: block; font-size: .78rem; color: var(--muted); font-weight: 600; margin-top: 2px; }
.note { color: var(--muted); font-size: .8rem; margin-top: 8px; }
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 40;
  display: none; align-items: flex-end; justify-content: center;
}
.overlay.open { display: flex; }
.sheet {
  width: 100%; max-width: 720px; max-height: min(78vh, 640px);
  background: #121a2b; border-radius: 18px 18px 0 0;
  padding: 10px 16px 28px; overflow: auto;
  box-shadow: 0 -8px 40px rgba(0,0,0,.45);
}
.handle { width: 42px; height: 4px; border-radius: 999px; background: #334155; margin: 4px auto 12px; }
.sheet h3 { margin: 0 0 4px; font-size: 1.25rem; font-weight: 800; }
.sheet .dowline { color: var(--muted); font-size: .9rem; margin: 0 0 14px; text-transform: capitalize; }
.ev {
  background: var(--card); border-radius: 14px; padding: 12px 14px; margin-bottom: 10px;
  border-left: 4px solid #64748b;
}
.ev .ttl { font-size: 1.05rem; font-weight: 800; margin: 0 0 4px; }
.ev .meta { font-size: .82rem; color: var(--muted); font-weight: 600; margin-bottom: 8px; }
.ev .body { font-size: .95rem; line-height: 1.4; color: #e2e8f0; }
.closebtn {
  display: block; width: 100%; margin-top: 8px; padding: 14px;
  border: 0; border-radius: 12px; background: #243247; color: var(--text);
  font: inherit; font-weight: 800; font-size: 1rem; cursor: pointer;
}
.empty-msg { color: var(--muted); padding: 8px 0 16px; }
@media (min-width: 560px) {
  .cell { min-height: 78px; }
  .pill { font-size: .65rem; }
  .overlay { align-items: center; padding: 24px; }
  .sheet { border-radius: 18px; max-height: 80vh; }
}
'''

JS = r'''
const WD = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"];
function openDay(iso) {
  const evs = DAYS[iso] || [];
  if (!evs.length) return;
  const [y,m,d] = iso.split('-').map(Number);
  const dt = new Date(y, m-1, d);
  document.getElementById('sheet-title').textContent = d + '.' + m + '.' + y;
  document.getElementById('sheet-dow').textContent = WD[dt.getDay() === 0 ? 6 : dt.getDay()-1];
  document.getElementById('sheet-body').innerHTML = evs.map(e => {
    const meta = [e.label, e.time ? ('klo ' + e.time) : null].filter(Boolean).join(' · ');
    return '<div class="ev" style="border-left-color:' + e.color + '">'
      + '<div class="ttl">' + escapeHtml(e.title) + '</div>'
      + (meta ? '<div class="meta">' + escapeHtml(meta) + '</div>' : '')
      + '<div class="body">' + escapeHtml(e.detail) + '</div></div>';
  }).join('');
  const ov = document.getElementById('overlay');
  ov.hidden = false; ov.classList.add('open');
}
function closeSheet() {
  const ov = document.getElementById('overlay');
  ov.classList.remove('open'); ov.hidden = true;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-day]');
  if (btn && btn.dataset.day) { openDay(btn.dataset.day); return; }
  if (e.target.id === 'sheet-close') { closeSheet(); return; }
  if (e.target.id === 'overlay') closeSheet();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
'''


def main():
    cal_data = json.loads(EVENTS_JSON.read_text())
    shared = json.loads(SHARED.read_text())

    events: list[dict] = []
    counts = {}
    for cal, blob in cal_data.items():
        n_keep = 0
        for e in blob.get("events") or []:
            ev = normalize_cal_event(e, cal)
            if ev:
                events.append(ev)
                n_keep += 1
        counts[cal] = {"raw": len(blob.get("events") or []), "kept": n_keep}

    extras = extras_to_events(shared)
    events.extend(extras)
    counts["extras_info"] = len(extras)

    events = merge_events(events)
    # Fix Riikka Oulu end dates: timed jussi event may end same calendar day evening
    # Prefer all-day span when both exist — already merged by alias with max end

    days = build_days(events)

    # Month sections
    jumps = "".join(f'<a href="#{mid}">{name}</a>' for m, (name, mid) in MONTHS.items())
    legend = (
        '<div class="legend">'
        '<span><i class="dot" style="background:#e11d48"></i>Kisat</span>'
        '<span><i class="dot" style="background:#7c3aed"></i>Matka / leiri</span>'
        '<span><i class="dot" style="background:#2563eb"></i>Koulu</span>'
        '<span><i class="dot" style="background:#db2777"></i>Perhe</span>'
        '<span><i class="dot" style="background:#059669"></i>Terveys</span>'
        '<span><i class="dot" style="background:#ea580c"></i>Harrastus</span>'
        "</div>"
    )
    sections = []
    for m, (name, mid) in MONTHS.items():
        sections.append(
            f'<section class="month" id="{mid}"><h2>{name}</h2>'
            + month_grid_html(2026, m, days)
            + agenda_html(events, m)
            + "</section>"
        )

    sub = (
        f"Karkea kalenteri · napauta päivää → lisätieto · "
        f"{RANGE_START.day}.{RANGE_START.month}.–{RANGE_END.day}.{RANGE_END.month}.{RANGE_END.year}"
    )

    html = f"""<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="color-scheme" content="dark"/>
<title>Räisä · loppuvuosi</title>
<style>
{CSS}
</style>
</head>
<body>
<h1>Loppuvuosi</h1>
<p class="sub">{esc(sub)}</p>
<nav class="jumps">
{jumps}</nav>{legend}{"".join(sections)}
<p class="note">Päivittyy aamuisin. Viikottaiset treenit eivät näy tässä. Napauta päivää tai listariviä.</p>

<div class="overlay" id="overlay" hidden>
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
    <div class="handle"></div>
    <h3 id="sheet-title"></h3>
    <p class="dowline" id="sheet-dow"></p>
    <div id="sheet-body"></div>
    <button type="button" class="closebtn" id="sheet-close">Sulje</button>
  </div>
</div>

<script>
const DAYS = {days_json(days)};
{JS}
</script>
</body></html>
"""
    OUT.write_text(html)
    shutil.copyfile(OUT, OUT_COPY)

    # Summary for stdout
    print("COUNTS", json.dumps(counts))
    print("MERGED_EVENTS", len(events))
    print("DAYS_WITH_EVENTS", len(days))
    for ev in sorted(events, key=lambda e: (e["start"], e["title"])):
        print(f"  {ev['start']}..{ev['end']} {ev.get('time') or 'ALL':5} [{ev['cat']}] {ev['title']}  ← {ev['source']}")


if __name__ == "__main__":
    main()
