# Visual assets — sources & licenses

**Rule:** Open-source / Creative Commons only for portraits, map tiles, icons. Cite every file here before shipping binaries. Placeholders are OK until downloads land.

## Art direction

| Cue | Direction |
|-----|-----------|
| Tactical chrome | Fire Emblem–style meters, panel borders, clear faction strips |
| Vibrancy | Immortals Fenyx–like saturated accents on gold/bronze frames (not neon glow spam) |
| Context | Chinese late Warring States — states as panels, ink/paper field, not European fantasy |
| Palette note | *The Apothecary Diaries* lean: muted sage greens, soft mauves, ink blacks, warm paper & gold |

### CSS variables (live in `app.py`)

| Token | Hex | Role |
|-------|-----|------|
| `--ws-ink` | `#1A1512` | Ink black field |
| `--ws-paper` | `#E8DCC8` | Warm paper text / rules |
| `--ws-sage` | `#6B7F6A` | Muted green (Chu / calm) |
| `--ws-mauve` | `#8B6B7A` | Soft mauve accent |
| `--ws-gold` | `#C4A35A` | Warm gold frames |
| `--ws-bronze` | `#A67C52` | Bronze panel edge |
| `--ws-qin` | `#8B3A3A` | Qin deep red (desaturated) |
| `--ws-trust` | `#4A7C8C` | Trust / Qi cool teal-ink |
| `--ws-pressure` | `#8B3A3A` | Pressure meter |

## Placeholders (current)

| Slot | Path / markup | Status |
|------|---------------|--------|
| Qin portrait | CSS `.ws-portrait.qin` monogram | Placeholder — no binary yet |
| Chu portrait | CSS `.ws-portrait.chu` monogram | Placeholder |
| Qi portrait | CSS `.ws-portrait.qi` monogram | Placeholder |
| Map tiles | none | Deferred |
| Icons | none | Deferred |

Suggested on-disk layout when assets arrive:

```text
sim/assets/
  portraits/   # qin.png chu.png qi.png …
  tiles/       # optional hex/square map
  icons/       # UI glyphs
  LICENSE.txt  # bundled third-party notices
```

## Candidate sources (download later — verify license page at fetch time)

| Source | License (typical) | Use |
|--------|-------------------|-----|
| [Kenney](https://kenney.nl/assets) | CC0 | UI icons, simple frames |
| [OpenGameArt](https://opengameart.org/) | CC0 / CC-BY / OGA-BY (per pack) | Portraits adjacent, tiles |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Varies — prefer CC BY-SA / public domain historical art | Period atmosphere (bronzes, maps); **check each file** |
| [game-icons.net](https://game-icons.net/) | CC BY 3.0 | Small action icons |

**Do not use:** commercial FE/Fenyx ripped sprites, unpaid stock, unlicensed anime stills, or Apothecary Diaries official art.

## Attribution template (copy when a file is added)

```text
filename — Title — Author — License — URL — Date fetched
```

## Fiction vs historical art

Portraits for Qin / Chu / Qi / Zhao / Han / Wei / Yan = historical-scaffold states.  
Do **not** commission or label Ling / Silkworm / Nightingale assets as historical.

## Character Profile / Field meters (engine 1:1)

UI meters map only to live WorldState fields — no orphan dials:

| UI | Engine field |
|----|--------------|
| OCEAN bars | gent.traits.openness/conscientiousness/extraversion/agreeableness/neuroticism |
| resentment / fear_of_qin / betrayal_memory / status_threat | gent.state.* |
| withholding_threshold | gent.state.withholding_threshold |
| sticky intention | gent.intention.current + sticky_until + hysteresis_mu |
| belief packets | gent.active_packets |
| dyadic trust rows | world.trust[i->j] |
| alliance_cohesion | world.meso.cohesion |
| qin_pressure | world.qin_pressure |
| cascade_armed | world.meso.cascade_armed |
| shared_identity | world.meso.shared_identity |

Portrait slots remain CSS monogram placeholders until CC assets land under ssets/portraits/{qin,chu,qi}.png.

## Figure portraits (WS-57)

Human bust JPGs in `static/portraits/<id>.jpg` — original playtest art.

**Hue by allegiance (not per-person):**
- Chu court (kaolie, king_you, chunshen, chu_nobility): sage `--ws-chu` / `#6B7F6A`
- Qin court (zhaoxiang, ying_zheng, li_si): Qin red `--ws-qin` / `#8B3A3A`
- Qi court (king_jian): teal `--ws-qi` / `#4A7C8C`

Within a court, value/ornament differ; base hue stays with home allegiance. UI portrait-card borders use the same allegiance tokens.
