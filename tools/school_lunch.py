#!/usr/bin/env python3
"""Fetch the Kuopio school lunch (Servica, Aromi eMenus) and update fiilis/schedule.json -> schoolLunch.

Source: https://menu.servica.fi/  (Servica ruokalistat -> "Kuopio koulut", diner group "Peruskoulu")
API (public, no auth):
  GET  .../api/Common/Page/GetPageInfo?currentpage=...          -> restaurant list
  GET  .../api/GetRestaurantPublicDinerGroups?id=..&startDate=..&endDate=..
  POST .../api/Common/Restaurant/RestaurantMeals?Id=..&StartDate=..&EndDate=..   (body = diner group object)

Usage:
  python3 tools/school_lunch.py                      # today .. +14 days, print only (dry run)
  python3 tools/school_lunch.py --write              # also write fiilis/schedule.json
  python3 tools/school_lunch.py --start 2026-09-30 --end 2026-10-09 --write
  python3 tools/school_lunch.py --restaurant "Kuopion lukiot"   # lukio menu instead
Entries from --start onward that the source does not return are removed (never guessed).
"""
import argparse, datetime as dt, json, os, re, sys, urllib.parse, urllib.request

BASE = "https://menu.servica.fi/ServicaAromieMenus/FI/Default/SERVICA/_/api"
PAGE = "/ServicaAromieMenus/FI/Default/SERVICA/_/Page/home"
SCHEDULE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fiilis", "schedule.json")


def _req(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                               headers={"Accept": "application/json", "Content-Type": "application/json",
                                        "User-Agent": "raisa-tanaan-fiilis/1.0"})
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else None


def _iso(d):
    return d.strftime("%Y-%m-%dT00:00:00.000Z")


def restaurant_id(name):
    info = _req(f"{BASE}/Common/Page/GetPageInfo?currentpage={urllib.parse.quote(PAGE, safe='')}")
    for r in info["Restaurants"]:
        if r["NameOrUniqueCode"].strip().lower() == name.lower():
            return r["Id"]
    raise SystemExit(f"Restaurant '{name}' not found")


def clean(s):
    s = re.sub(r"\s*★\s*", " ", s).strip()
    s = re.sub(r"(\s+(L|M|G|VG|VL|K))+$", "", s).strip()  # stray diet codes in the name
    return s[:1].upper() + s[1:]


def fetch(name, start, end, diner=None):
    rid = restaurant_id(name)
    q = f"id={rid}&startDate={_iso(start)}&endDate={_iso(end)}"
    groups = _req(f"{BASE}/GetRestaurantPublicDinerGroups?{q}") or []
    if diner:
        groups = [g for g in groups if g["Name"].lower() == diner.lower()] or groups
    if not groups:
        raise SystemExit("No diner groups")
    body = dict(groups[0])
    body["SuitabilityDietIds"] = body.get("SuitabilityDietIds") or []  # null -> HTTP 400
    days = _req(f"{BASE}/Common/Restaurant/RestaurantMeals?Id={rid}&StartDate={_iso(start)}&EndDate={_iso(end)}",
                body) or []
    out = {}
    for day in days:
        date = day["Date"][:10]
        meals = {m["MealName"]: m.get("Dishes") or [] for m in day.get("Meals") or []}
        main = meals.get("Lounas 1") or meals.get("Lounas") or []
        veg = meals.get("Lounas 2") or []
        mains = [clean(x["DishName"]) for x in main if x.get("PartOfMealIndexNumber") == 1]
        sides = [clean(x["DishName"]).lower() for x in main if x.get("PartOfMealIndexNumber") == 3]
        vegs = [clean(x["DishName"]) for x in veg if x.get("PartOfMealIndexNumber") == 1]
        if not mains:
            continue
        parts = mains + sides
        text = " + ".join([parts[0]] + [p[:1].lower() + p[1:] for p in parts[1:]])
        if vegs and [v.lower() for v in vegs] != [m.lower() for m in mains]:
            text += " (kasvis: " + " + ".join(v[:1].lower() + v[1:] for v in vegs) + ")"
        out[date] = text
    return out


def main():
    ap = argparse.ArgumentParser()
    today = dt.date.today()
    ap.add_argument("--start", default=today.isoformat())
    ap.add_argument("--end", default=(today + dt.timedelta(days=14)).isoformat())
    ap.add_argument("--restaurant", default="Kuopio koulut")
    ap.add_argument("--diner", default="Peruskoulu")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    menu = fetch(a.restaurant, start, end, a.diner)
    for k, v in sorted(menu.items()):
        print(k, v)
    if a.write:
        with open(SCHEDULE, encoding="utf-8") as f:
            sched = json.load(f)
        sl = {k: v for k, v in sched.get("schoolLunch", {}).items() if k < a.start or k > a.end}
        sl.update(menu)
        sched["schoolLunch"] = dict(sorted(sl.items()))
        with open(SCHEDULE, "w", encoding="utf-8") as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {len(menu)} entries to {os.path.normpath(SCHEDULE)}", file=sys.stderr)


if __name__ == "__main__":
    main()
