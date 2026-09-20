# Räisä · Fiilis

Mood layer for the Räisä family **kitchen** portrait TV wall (Kuopio).  
**Raises mood, lowers stress** — gallery / editorial quality, not a logistics dashboard.

Complements the daily board: [Räisä · Tänään](https://jussiraisa.github.io/raisa-tanaan/) (rides, meals). This screen is fiilis + a calm glance at **today’s times**.

## Kitchen placement

- **Hardware:** Cepter 50″ Google TV (CR50EU7002A), **physically rotated to portrait (9:16)** on the kitchen wall.
- **Audience:** morning glance from across the kitchen — large clock, warm light, calm motion only.
- Family: Jussi, Riikka, Ellen·Ambrosia, Samuel·Welhot, Milla·Vivida, Mea·Lianna.

## Open on the TV

1. On the Google TV, open **Browser** → load this page (`http://…/family-life-screen/`). Prefer `http://` so photos load reliably.
2. Fullscreen the tab; leave it ambient.
3. **Portrait rotate is opt-in** (see below) — not automatic on landscape.

Local preview:

```bash
cd /workspace/family-life-screen
python3 -m http.server 8765
# open http://localhost:8765/
```

## Portrait rotate (opt-in)

Physical panel is portrait; Google TV browser may still report landscape.  
**Default: off.** Enable only when needed:

| Query | Effect |
|--------|--------|
| *(none)* | No CSS rotate |
| `?rotate=cw` / `?rotate=1` | Clockwise stage rotate |
| `?rotate=ccw` | Counter-clockwise |
| `?rotate=0` | Force off |

## Live themes (Europe/Helsinki)

| Mode | Hours | Mood |
|------|-------|------|
| `morning` | 05–11 | Cream / soft gold |
| `afternoon` | 11–17 | Warm-neutral gallery |
| `evening` | 17–22 | Amber, dimmer, larger photo |
| `night` | 22–05 | Candlelit |

Palette tokens morph over **~3.2s** (`--theme-dur`) — no snap.

## Layout

1. Clock + date + weather hint  
2. Greeting  
3. **Tänään** — big times, soft labels (school + treenit from `schedule.json`)  
4. Memory hero (ken-burns, slow carousel, 84 travel photos)  
5. Countdowns · family chips · season · hyvät jutut · footer  

Empty days: *“Rauhallinen päivä kotona”*. Sundays show weekend practices + Monday school preview. School times are placeholders until Perhe confirms.

## Photos

- `photos-web/matka-*.jpg` — 84 web-sized frames from *Meidän matkat 2018–2026*
- Manifest: `photos-from-matkat.json` (`src`, `place`, `year`)
- Captions: soft “Muistatko…” + place · year
- Orientation: EXIF transpose + manual upright fixes (PIL)

## Schedule

- `schedule.json` — preferred live source (fetched every 5 min; embedded fallback in `index.html`)
- Fields: `schoolStarts[]`, `events[]` (date, time, who, title, place, kind)

## Files

- `index.html` — self-contained UI
- `schedule.json` — today / week glance data
- `photos-web/` — carousel images
- `photos-from-matkat.json` — caption manifest
- `README.md` — this file
