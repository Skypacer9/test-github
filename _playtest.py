"""Agent playtest: Advance, Intervene multi, Profile, New Run, long run."""
from __future__ import annotations

from app import build_ui, render_field, render_profile
from backend import (
    advance_quarter,
    character_choices,
    character_profile,
    fresh_run,
    initial_state,
    intervene_targets,
)
from engine.packets import COURT_MIXES, PACKET_CATALOG
from engine.tick import tick
from engine.world import new_world

bugs: list[str] = []
notes: list[str] = []

s = initial_state()
html = render_field(s)
if "M2 TECH" not in html and "Adoption Meter" not in html:
    bugs.append("Field missing M2 Adoption Meter panel")
else:
    notes.append("Field M2 panel present")
if "ws-meters" not in html:
    bugs.append("Equal court meters missing")
else:
    notes.append("Equal Qin/Chu/Qi meters present")

s2, _msgs = advance_quarter(s)
tick2 = (s2.get("_engine") or s2).get("tick", 0)
if int(tick2) < 1:
    bugs.append("Advance did not increment tick")
else:
    notes.append(f"Advance ok tick={tick2}")

s3, m3, e3 = intervene_targets(s2, ["qin", "chu", "qi"])
if e3:
    bugs.append(f"Intervene multi budget err: {e3}")
elif len(m3) < 1:
    bugs.append("Intervene multi produced no messages")
else:
    notes.append(f"Intervene multi msgs={len(m3)}")
# Second intervene same tick should be budget-blocked (not an exception)
s4, m4, e4 = intervene_targets(s3, ["chu"])
if e4 and "already used" in str(e4).lower():
    notes.append("Intervene budget gate ok")
else:
    notes.append(f"Intervene second click: err={e4!r}")

choices = character_choices(None)
if len(choices) != 6:
    bugs.append(f"choices={len(choices)} want 6")
for _lab, vid in choices:
    prof = character_profile(s3, vid)
    if prof.get("error"):
        bugs.append(f"profile {vid}: {prof['error']}")
    rh = render_profile(s3, vid)
    if not rh:
        bugs.append(f"render_profile empty for {vid}")
notes.append("Profile switch 6 checked")

fr = fresh_run()
eng = fr.get("_engine") or fr
if int(eng.get("tick", 99)) != 0:
    bugs.append(f"New Run tick={eng.get('tick')}")
else:
    notes.append("New Run resets tick=0")
if eng.get("run_ended"):
    bugs.append("New Run left run_ended True")

w = new_world()
for _ in range(20):
    tick(w)
notes.append(
    f"Long 20Q: tick={w.tick} pressure={w.qin_pressure:.1f} "
    f"pathway={w.meso.pathway_soft} ended={w.run_ended} "
    f"mil_qin={w.world.military_qin:.2f} adopt={w.world.adoption_meter:.2f}"
)
if w.run_ended and (w.end_screen or {}).get("lock_kind") != "mechanism":
    bugs.append("Long run locked without mechanism kind")

w8 = new_world()
for _ in range(8):
    tick(w8)
if w8.run_ended and "Q8" in str((w8.end_screen or {}).get("reason", "")):
    bugs.append("Calendar Q8 soft-lock still present")
else:
    notes.append(f"No calendar lock at Q8 (ended={w8.run_ended})")

try:
    build_ui()
    notes.append("build_ui ok")
except Exception as e:  # noqa: BLE001
    bugs.append(f"build_ui FAIL: {e}")

need = [
    "legalist_fa",
    "dao_guodian",
    "huang_lao",
    "guanzi",
    "chu_patron_client",
    "tianxia_da_yitong",
    "lineage_shi",
    "ru_li",
    "mohist_shangxian",
]
miss = [x for x in need if x not in PACKET_CATALOG]
if miss:
    bugs.append(f"missing packets {miss}")
else:
    notes.append("vault schools catalog ok")
if any("tianxia_da_yitong" not in COURT_MIXES[k] for k in COURT_MIXES):
    bugs.append("some court missing tianxia")
else:
    notes.append("all courts have tianxia_da_yitong")

print("NOTES:")
for n in notes:
    print(" -", n)
print("BUGS:")
if not bugs:
    print(" - none")
else:
    for b in bugs:
        print(" -", b)
raise SystemExit(1 if bugs else 0)
