"""Thin figure multiagent counsel — tips world dials only.

Player = collective consciousness / field pressure (not a persona).
No player OCEAN, no persisted player decision dossier — only ephemeral
in-session exchange count until forced close (3–5), then dial tips apply
and the session prompt buffer is wiped.

Narration rails (Odetta): ground per-figure lines in (1) that figure's OCEAN,
(2) period-English aphorism / symbolism soft priors, (3) action-RPG gloss
(Immortals Fenyx Rising × Fire Emblem) — vivid, lightly heroic, not academic.
English only. Offline stub always ends with a decision.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from .figures import FIGURES, figure_available_for_talk, get_figure, talkable_figures
from .nonlinear import clamp, saturating_down, saturating_up
from .trust import get_trust, set_trust

STANCE_HARD = ("contribute", "withhold", "defect")
STANCE_SOFT = ("hedge", "refuse")
STANCE_OK = STANCE_HARD + STANCE_SOFT
STANCE_TO_ENGINE = {
    "contribute": "cooperate",
    "cooperate": "cooperate",
    "withhold": "withhold",
    "defect": "defect",
}
EVENT_TAGS = (
    "patron_rebuke",
    "legalist_probe",
    "isolation_caution",
    "sync_appeal",
    "hedge",
    "refuse",
    "belief_cascade",
    "personal_breakthrough",
    "other",
)
LOYALTY_CAP = 0.25
COUNSEL_LOG_MAX = 40
BELIEF_MAX_PER_FIGURE = 6
BELIEF_WEIGHT_DELTA_CAP = 0.12
BREAKTHROUGH_COOLDOWN = 3
TRUST_FLIP_CAP = 0.08
TECH_KNOWN_BUMP = 0.05
DIALOGUE_MIN = 3
DIALOGUE_MAX = 5

# Ideology/culture-gated dialogue seeds (Odetta).
# Soft priors: vault English notes + period-text paraphrases (Guodian/Dao patronage,
# Qin fa apparatus, Qi Guanzi mercantile caution). Fenyx×FE gloss in delivery only.
# NEVER serve Qin-legalist lines to Chu patronage/tianxia figures.

IDEOLOGY_BY_HOME: dict[str, str] = {
    "chu": "chu_patronage_tianxia",
    "qin": "qin_legalism",
    "qi": "qi_mercantile",
    # Thin scaffolds lean tianxia/lineage, not Qin fa
    "zhao": "chu_patronage_tianxia",
    "han": "qi_mercantile",
    "wei": "chu_patronage_tianxia",
    "yan": "qi_mercantile",
}

# Marker phrases that brand a line as Qin-Legalist — banned for Chu ideology family.
LEGALIST_SEED_MARKERS: tuple[str, ...] = (
    "when laws are clear",
    "orders need few words",
    "clear laws need few words",
    "clear laws cut cleaner",
    "statute is my spear",
    "law before banquet",
    "legalist clarity",
    "fa still drafts",
    "sequential conquest",
    "checklist",
    "guest-expulsion",
    "administrative weather",
    "policy follows the brief",
    "iron follows the mould",
    "obey the sequence",
    "statute versus toast",
    "statute-first",
)

IDEOLOGY_UTTERANCE_BANKS: dict[str, tuple[str, ...]] = {
    # Chu: patronage / lineage / Guodian-Dao soft power / tianxia holding (vault + Guodian paraphrase)
    "chu_patronage_tianxia": (
        "The Way values the weak; force against timing scrapes the court raw.",
        "Patron and client share one face — unpaid ritual debt still bites.",
        "Tianxia holding starts as reciprocity among courts, not a Qin timetable.",
        "Lineage honor is armor; banquet loyalty without grain is empty.",
        "Tai Yi orders the seasons. Haste that ignores timing scrapes courage raw.",
        "Federation talk means the hub still feeds its spokes.",
        "Face first, then spears; Chu does not march as Legalist extras.",
        "A withheld courtesy today is a broken clique tomorrow.",
    ),
    # Qin: fa / administrative apparatus / sequential pressure (vault Legalism cluster paraphrase)
    "qin_legalism": (
        "When laws are clear, orders need few words.",
        "Clear laws cut clean.",
        "Law before banquet loyalty — statute is my spear.",
        "Iron follows the mould; policy follows the minister.",
        "Sequential conquest is a checklist, not a poem.",
        "Guest talent stays if it cuts cleaner than native hesitation.",
        "Administrative weather decides more than toast-logic.",
        "Soft loyalty is fog. Legalist clarity cuts a road.",
    ),
    # Qi: Guanzi mercantile / isolation / grain-workshop caution (vault Guanzi syncretism)
    "qi_mercantile": (
        "Guanzi math first: grain, workshops, then any talk of coalitions.",
        "Isolation is a fortress until the fords are sold.",
        "Markets and grain books price a coalition — they do not hymn it.",
        "Betrayal memory is sticky; Qi will not wash it for a Qin smile.",
        "The frontier eats grain faster than verse can fill it.",
        "Contribute only when the quorum is real — else withhold and watch.",
        "Walls first, speeches later; that is mercantile weather-sense.",
        "A withheld levy today is a broken spear tomorrow — counted twice.",
    ),
}


# Role perspective banks — same event, different vantage (ruler / minister / general / retainer).
ROLE_UTTERANCE_BANKS: dict[str, tuple[str, ...]] = {
    "ruler": (
        "From the throne: the season is weighed in grain, face, and who still answers the levy.",
        "A ruler's counsel is a banner choice — plant it, or the map chooses for you.",
        "I speak as the seal: courts move when the crown names the weather.",
        "Royal vantage: coalition is a tool, not a hymn.",
    ),
    "minister": (
        "From the chancellery: draft the clause before you draft the toast.",
        "A minister's eye counts receipts, guest lists, and which brief still holds.",
        "I advise the apparatus — courage without procedure is theater.",
        "Broker's vantage: sync the spokes, then argue with Heaven.",
    ),
    "general": (
        "From the field edge: fittings and fords decide more than banquet vows.",
        "A general reads the weather in spear-count and supply, not in verse.",
        "March orders first — ideology is the banner over the column, not the road.",
        "Camp vantage: hold the pass or lose the season's grain.",
    ),
    "retainer": (
        "From the client halls: unpaid ritual debt still names who we follow.",
        "Retainers keep lineage armor; we are not statute ink.",
        "Spoke vantage: if the hub goes hungry, so do we.",
        "Noble clients hedge until patronage proves it still feeds its own.",
    ),
}

# Optional figure-color overlays (still ideology-compatible; never cross-family).
FIGURE_UTTERANCE_BANKS: dict[str, tuple[str, ...]] = {
    "kaolie": (
        "The southern hub keeps face only if the clique still answers.",
        "I will not trade Chu's patron web for a Qin timetable.",
        "Latent courage in Chu wakes when the brokers still stand.",
    ),
    "king_you": (
        "The throne feels thin — patrons glance past me.",
        "I inherit a web I can barely hold; Qin weather grows loud.",
        "My seal is new; the guest-houses still ask for Kaolie's name.",
        "Chunshen's ledger weighs more than my word tonight.",
        "I keep Chu face by listening first — fear of Qin already sits here.",
        "Succession is not strength; it is a borrowed hall I must fill.",
    ),
    "chunshen": (
        "Guest-houses remember who paid the last banquet — and who didn't.",
        "I broker coalitions the way others broker steel: carefully, with receipts.",
        "Qin friendship talk is cheap wine. I pour levy math.",
    ),
    "chu_nobility": (
        "We are clients, not statutes — lineage still names the debt.",
        "Abandon the patron and the whole spoke goes hungry.",
        "We hedge until the hub proves it still feeds its own.",
    ),
    "zhaoxiang": (
        "Long reigns are won by patience — staged pressure, not one thunderclap.",
        "I expand like a slow siege: grain, passes, then the map.",
        "Fear of Qin is useful weather — I do not waste it on pageantry.",
    ),
    "ying_zheng": (
        "Unity is scheduled. Banquets wait.",
        "The map closes when courts stop improvising and start obeying.",
        "Plant the banner where the levy already answers — then press.",
    ),
    "li_si": (
        "Huang-Lao garnish or not, fa still drafts the order of the day.",
        "I advise the seal, not the toast; statute is my spear.",
        "My memorials cut guest-expulsion short — law first.",
    ),
    "king_jian": (
        "Qi waits behind walls. The map tightens. Isolation's lesson.",
        "Guanzi math at my threshold. Leave Qin fa outside.",
        "Granaries still answer. Qi refuses rumor-starvation.",
    ),
}

# Flat unique English pool for seed-cap / ASCII tests.
APHORISM_SEEDS: tuple[str, ...] = tuple(
    dict.fromkeys(
        line
        for bank in (
            list(IDEOLOGY_UTTERANCE_BANKS.values())
            + list(ROLE_UTTERANCE_BANKS.values())
            + list(FIGURE_UTTERANCE_BANKS.values())
        )
        for line in bank
    )
)[:20]
assert 1 <= len(APHORISM_SEEDS) <= 20
assert len(set(APHORISM_SEEDS)) == len(APHORISM_SEEDS)

# Ideology gate: Chu family banks must not contain Legalist markers.
for _line in IDEOLOGY_UTTERANCE_BANKS["chu_patronage_tianxia"]:
    _low = _line.lower()
    assert not any(m in _low for m in LEGALIST_SEED_MARKERS), _line
for _fid in ("kaolie", "chunshen", "chu_nobility"):
    for _line in FIGURE_UTTERANCE_BANKS[_fid]:
        _low = _line.lower()
        assert not any(m in _low for m in LEGALIST_SEED_MARKERS), (_fid, _line)
# Qin family must include at least one classic legalist marker line
assert any(
    any(m in line.lower() for m in LEGALIST_SEED_MARKERS)
    for line in IDEOLOGY_UTTERANCE_BANKS["qin_legalism"]
)
del _line, _low, _fid


def counsel_backend_name() -> str:
    from .llm_gate import llm_env_enabled

    return "llm" if llm_env_enabled() and (os.environ.get("WS_COUNSEL_API_KEY") or "").strip() else "stub"


def _seed_int(*parts: Any) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _strip_ui(text: str) -> str:
    t = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+", "", str(text or ""))
    t = re.sub(r"[#*`]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def living_figures(world: Any) -> list[dict[str, Any]]:
    """Living + era-unlocked cast (Zheng / Li Si gated until ≤247 BCE)."""
    out = []
    for fig in FIGURES:
        if figure_available_for_talk(world, fig["id"]):
            out.append(fig)
    return out


def select_figures(world: Any, n: int | None = None, *, focus_id: str | None = None) -> list[dict[str, Any]]:
    living = living_figures(world)
    if not living:
        return []
    # One-on-one: selected talkable figure only
    if focus_id:
        fig = get_figure(focus_id)
        if fig and figure_available_for_talk(world, fig["id"]):
            return [fig]
        return []
    if n is None:
        n = 2 + (_seed_int(world.tick, "n") % 3)
    n = max(2, min(4, int(n), len(living)))
    qin = [f for f in living if world.agents[f["home"]].bloc == "qin"]
    anti = [f for f in living if world.agents[f["home"]].bloc != "qin"]
    picked: list[dict[str, Any]] = []

    def take(pool: list[dict[str, Any]], want: int) -> None:
        for f in sorted(pool, key=lambda x: _seed_int(world.tick, x["id"], "r")):
            if f not in picked:
                picked.append(f)
            if sum(1 for x in picked if x in pool) >= want or len(picked) >= n:
                break

    if qin and anti and n >= 2:
        take(qin, 1)
        take(anti, 1)
        take([f for f in living if f not in picked], n - len(picked))
    else:
        take(living, n)
    return picked[:n]


def _ensure_session(world: Any) -> dict[str, Any]:
    """Ephemeral dialogue session — never a player dossier.

    Stores only exchange count / open flag / last field-pressure line for the
    *current* open talk. Cleared on close; not a cross-session memory of choices.
    """
    sess = getattr(world, "counsel_session", None)
    if not isinstance(sess, dict):
        sess = {"open": False, "exchanges": 0, "cap": DIALOGUE_MAX, "pressure": "", "figure_id": ""}
        world.counsel_session = sess
    sess.setdefault("open", False)
    sess.setdefault("exchanges", 0)
    sess.setdefault("cap", DIALOGUE_MAX)
    sess.setdefault("pressure", "")
    sess.setdefault("figure_id", "")
    # Never attach player ocean / decision history keys
    for ban in ("player_ocean", "player_decisions", "god_view", "choice_dossier"):
        sess.pop(ban, None)
    return sess


def clear_counsel_session(world: Any) -> None:
    world.counsel_session = {"open": False, "exchanges": 0, "cap": DIALOGUE_MAX, "pressure": "", "figure_id": ""}


def _ideology_for(fig: dict[str, Any] | None = None, *, home: str = "", fid: str = "") -> str:
    """Map home court → ideology family (Chu patronage/tianxia vs Qin legalism vs Qi mercantile)."""
    h = str(home or (fig or {}).get("home") or "").strip().lower()
    return IDEOLOGY_BY_HOME.get(h, "chu_patronage_tianxia")


def _speech_role_for(fig: dict[str, Any] | None = None, *, fid: str = "") -> str:
    """ruler | minister | general | retainer — perspective key for same-event speech."""
    if fig and fig.get("speech_role"):
        return str(fig["speech_role"]).strip().lower()
    meta = get_figure(fid) if fid else None
    if meta and meta.get("speech_role"):
        return str(meta["speech_role"]).strip().lower()
    # Heuristic fallback from role_label
    label = str((fig or meta or {}).get("role_label") or "").lower()
    if any(w in label for w in ("king", "ruler", "sovereign")):
        return "ruler"
    if any(w in label for w in ("chancellor", "minister", "advisor", "patron")):
        return "minister"
    if any(w in label for w in ("general", "commander", "marshal")):
        return "general"
    if any(w in label for w in ("nobility", "client", "retainer")):
        return "retainer"
    return "minister"


def _figure_bank(fid: str, *, home: str = "", role: str | None = None) -> tuple[str, ...]:
    """Combine figure overlay + role bank + ideology bank — never cross ideology family."""
    fid = str(fid or "").strip().lower()
    meta = get_figure(fid)
    if meta:
        home = home or str(meta.get("home") or "")
        role = role or _speech_role_for(meta, fid=fid)
    ideo = _ideology_for(meta, home=home, fid=fid)
    role = (role or _speech_role_for(meta, fid=fid) or "minister").strip().lower()
    overlay = list(FIGURE_UTTERANCE_BANKS.get(fid) or ())
    role_bank = list(ROLE_UTTERANCE_BANKS.get(role) or ())
    ideo_bank = list(IDEOLOGY_UTTERANCE_BANKS.get(ideo) or IDEOLOGY_UTTERANCE_BANKS["chu_patronage_tianxia"])
    # Priority: figure-specific → role perspective → ideology soft priors
    bank = tuple(overlay + role_bank + ideo_bank)
    if ideo != "qin_legalism":
        bank = tuple(line for line in bank if not any(m in line.lower() for m in LEGALIST_SEED_MARKERS))
    if not bank:
        bank = (f"{fid or 'figure'} ({role}) keeps counsel with home-court weather.",)
    return bank


def _aphorism(
    world: Any,
    fid: str,
    tag: str,
    *,
    ocean: dict[str, float] | None = None,
    home: str = "",
    role: str | None = None,
) -> str:
    """Pick from role+ideology+figure bank — hashed by figure_id + role + OCEAN + home + tag.

    Prefer figure-specific overlay (~2/3) so King You / Kaolie / Li Si stay distinct.
    """
    meta = get_figure(fid)
    role = role or _speech_role_for(meta, fid=fid)
    home = home or str((meta or {}).get("home") or "")
    overlay = tuple(FIGURE_UTTERANCE_BANKS.get(str(fid or "").strip().lower()) or ())
    bank = _figure_bank(fid, home=home, role=role)
    o = ocean or {}
    # Bias toward figure-unique lines when available
    pick_key = _seed_int(world.tick, fid, tag, "figbias")
    if overlay and (pick_key % 3) != 0:
        bank = overlay
    key = (
        world.tick,
        fid,
        home,
        role,
        _ideology_for(meta, home=home, fid=fid),
        tag,
        f"O{o.get('O', 0):.2f}",
        f"C{o.get('C', 0):.2f}",
        f"E{o.get('E', 0):.2f}",
        f"A{o.get('A', 0):.2f}",
        f"N{o.get('N', 0):.2f}",
        "apo",
    )
    line = bank[_seed_int(*key) % len(bank)]
    ideo = _ideology_for(meta, home=home, fid=fid)
    if ideo != "qin_legalism" and any(m in line.lower() for m in LEGALIST_SEED_MARKERS):
        safe = [x for x in bank if not any(m in x.lower() for m in LEGALIST_SEED_MARKERS)]
        line = safe[_seed_int(*key, "safe") % len(safe)] if safe else f"{fid}: home-court counsel only."
    return line


def _tag_gloss(fid: str, tag: str, lean: str) -> str:
    """Figure-specific tag/lean coda — not a shared suffix across the cast."""
    fid = str(fid or "").strip().lower()
    # Default lean lines still keyed by figure so they cannot collide verbatim
    lean_map = {
        "kaolie": {
            "contribute": "Chu plants its banner with the southern line.",
            "withhold": "Chu holds — no rash charge from the hub.",
            "defect": "Pressure rises; Chu will not pretend otherwise.",
            "hedge": "Kaolie reads the weather before the clique swings.",
            "refuse": "Chu rejects that frame.",
        },
        "chunshen": {
            "contribute": "I pull the spokes into one shield.",
            "withhold": "I stall the toast until the receipts clear.",
            "defect": "I cut a hard bargain — patrons do that.",
            "hedge": "A broker hedges; that is the craft.",
            "refuse": "I refuse Qin-friendship scripts.",
        },
        "chu_nobility": {
            "contribute": "The clients march if the patron still feeds us.",
            "withhold": "We withhold until lineage honor is named aloud.",
            "defect": "Client halls can spoil a campaign as fast as Qin.",
            "hedge": "Nobility hedges — unpaid debt makes cowards and critics.",
            "refuse": "We will not be drafted as Legalist extras.",
        },
        "zhaoxiang": {
            "contribute": "Qin contributes pressure on a long fuse.",
            "withhold": "I withhold the thunderclap; patience is policy.",
            "defect": "I press the passes — staged, not theatrical.",
            "hedge": "Even a long-reign king reads the grain first.",
            "refuse": "I refuse short reigns' panic.",
        },
        "ying_zheng": {
            "contribute": "Contribute means the checklist advances.",
            "withhold": "Withhold only to reload the next decree.",
            "defect": "Hard pressure is the point of the apparatus.",
            "hedge": "Hedge is temporary; schedule resumes at dawn.",
            "refuse": "I refuse banquet politics as strategy.",
        },
        "li_si": {
            "contribute": "My brief contributes statute, not sentiment.",
            "withhold": "Praise withheld. Procedure issued.",
            "defect": "Administrative pressure — sharp as a memorial.",
            "hedge": "A chancellor hedges only to sharpen the next clause.",
            "refuse": "I refuse toast-logic in the chancellery.",
        },
        "king_jian": {
            "contribute": "Qi contributes only to a real quorum.",
            "withhold": "Qi withholds — walls first, speeches later.",
            "defect": "I remember 284. Defect talk stays outside.",
            "hedge": "Isolation is already my hedge.",
            "refuse": "I refuse Qin-smile diplomacy.",
        },
    }
    gloss_tag = {
        "kaolie": {
            "patron_rebuke": "The hub rebukes a slack spoke.",
            "sync_appeal": "Sync the southern court or lose the season.",
            "legalist_probe": "Legalist haste scrapes Chu's Dao raw.",
            "isolation_caution": "Even Chu watches Qi's walls with unease.",
            "belief_cascade": "A patron belief rides Chu's trust edge.",
            "personal_breakthrough": "A quiet flash — Chu courage finds footing.",
        },
        "chunshen": {
            "patron_rebuke": "I rebuke a client who forgets the guest-house ledger.",
            "sync_appeal": "Sync with me or the coalition is theater.",
            "legalist_probe": "Statute talk stops at my threshold unless paid in face.",
            "isolation_caution": "Qi isolation makes my brokerage harder — noted.",
            "belief_cascade": "Belief spreads along my guest list tonight.",
            "personal_breakthrough": "A broker's insight: the clique can still move.",
        },
        "chu_nobility": {
            "patron_rebuke": "We rebuke a hub that forgets its clients.",
            "sync_appeal": "Call us to sync — and bring ritual payment.",
            "legalist_probe": "Fa language does not fit our ancestral armor.",
            "isolation_caution": "If Qi hides, our spoke feels the draft.",
            "belief_cascade": "Client belief ripples when the patron falters.",
            "personal_breakthrough": "Nobility finds a spine — surprising, even to us.",
        },
        "zhaoxiang": {
            "patron_rebuke": "Qin does not rebuke patrons; it outlasts them.",
            "sync_appeal": "Sync under Qin pressure — or scatter.",
            "legalist_probe": "Law advances with the siege engines.",
            "isolation_caution": "Qi isolation is a gift to a patient king.",
            "belief_cascade": "A Legalist belief rides west-to-east trust edges.",
            "personal_breakthrough": "Long-reign clarity: press where grain already answers.",
        },
        "ying_zheng": {
            "patron_rebuke": "I rebuke hesitation disguised as ritual.",
            "sync_appeal": "Sync means obey the sequence.",
            "legalist_probe": "Probe with fa until soft courts crack.",
            "isolation_caution": "Isolationists are calendar entries.",
            "belief_cascade": "Belief in unity spreads as decree.",
            "personal_breakthrough": "Checklist insight: the next court falls on schedule.",
        },
        "li_si": {
            "patron_rebuke": "I rebuke guest-expulsion nostalgia with a memorial.",
            "sync_appeal": "Sync the apparatus; leave the banquet to others.",
            "legalist_probe": "This is the probe: statute versus toast.",
            "isolation_caution": "Isolation is inefficiency — I file it as such.",
            "belief_cascade": "A clerical belief becomes policy when sealed.",
            "personal_breakthrough": "Brief flash: the right clause turns the court.",
        },
        "king_jian": {
            "patron_rebuke": "I rebuke those who forgot Yan's lesson.",
            "sync_appeal": "Sync only for a real quorum.",
            "legalist_probe": "Guanzi math. Qin fa stays elsewhere.",
            "isolation_caution": "Caution is the policy; walls are the proof.",
            "belief_cascade": "Betrayal memory cascades easier than trust.",
            "personal_breakthrough": "Qi insight: survive first, hymn later.",
        },
    }
    by_lean = lean_map.get(fid) or {
        "contribute": f"{fid}: plant a careful banner.",
        "withhold": f"{fid}: hold without spectacle.",
        "defect": f"{fid}: press without apology.",
        "hedge": f"{fid}: read weather before steel.",
        "refuse": f"{fid}: refuse that frame.",
    }
    by_tag = gloss_tag.get(fid) or {}
    if tag in by_tag:
        return by_tag[tag]
    return by_lean.get(lean, f"{fid}: counsel stands.")



def _figure_ocean(fig: dict[str, Any], world: Any) -> dict[str, float]:
    """Soft OCEAN prior for the named figure (JSON row), fallback to home court."""
    from .profiles import profile_by_id

    row = profile_by_id(fig.get("profile_id") or "") or {}
    bf = row.get("big_five") or {}
    home = str(fig.get("home") or "")
    ag = world.agents.get(home) if home else None
    def pick(letter: str, attr: str, default: float = 0.5) -> float:
        if letter in bf:
            try:
                return float(bf[letter])
            except (TypeError, ValueError):
                pass
        if ag is not None:
            return float(getattr(ag.traits, attr, default))
        return default
    return {
        "O": pick("O", "openness"),
        "C": pick("C", "conscientiousness"),
        "E": pick("E", "extraversion"),
        "A": pick("A", "agreeableness"),
        "N": pick("N", "neuroticism"),
    }


def _ocean_color(ocean: dict[str, float]) -> str:
    """Short action-RPG gloss from dominant OCEAN facets — not clinical jargon."""
    O, C, E, A, N = ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"]
    bits = []
    if C >= 0.75:
        bits.append("steel-disciplined")
    elif C <= 0.4:
        bits.append("improvising")
    if E >= 0.7:
        bits.append("court-forward")
    elif E <= 0.4:
        bits.append("quiet-eyed")
    if A <= 0.35:
        bits.append("hard-edged")
    elif A >= 0.65:
        bits.append("bond-loyal")
    if N >= 0.6:
        bits.append("storm-nerved")
    elif N <= 0.35:
        bits.append("steady-handed")
    if O >= 0.7:
        bits.append("curious-forged")
    elif O <= 0.35:
        bits.append("orthodox-lined")
    return ", ".join(bits[:2]) if bits else "field-tested"


_CONTRAST_TURN_RE = (
    re.compile(r"\bnot\b[^.!?;]{0,48}\bbut\b", re.I),
    re.compile(r"\bwhile\b[^.!?;]{0,56}\b(still|yet|nevertheless)\b", re.I),
    re.compile(r"\bdon\'?t\b[^.!?;]{0,40}\b(instead|rather)\b", re.I),
    re.compile(r"\bisn\'?t\b[^.!?;]{0,40}\bit\'?s\b", re.I),
    re.compile(r"\brather\s+than\b", re.I),
)


def has_contrast_turn(text: str) -> bool:
    return any(rx.search(str(text or "")) for rx in _CONTRAST_TURN_RE)


def scrub_contrast_turns(text: str) -> str:
    """Drop contrast-turn stacks; keep the first plain clause."""
    s = str(text or "").strip()
    if not s:
        return s
    s = re.split(r"\s*;\s*", s)[0].strip()
    s = re.split(r"\bnot\b[^.!?]{0,48}\bbut\b", s, maxsplit=1, flags=re.I)[0].strip(" ,—-")
    s = re.split(r"\bwhile\b[^.!?]{0,56}\b(?:still|yet|nevertheless)\b", s, maxsplit=1, flags=re.I)[0].strip(" ,—-")
    s = re.sub(r"\brather\s+than\b[^.!?]*", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,;.—")
    if s and s[-1] not in ".!?":
        s += "."
    return s


def utterance_shape(text: str) -> dict[str, float]:
    """Shape metrics for OCEAN/role regressions (body after speaker tag)."""
    body = str(text or "")
    if "]: " in body:
        body = body.split("]: ", 1)[-1]
    words = [w for w in re.findall(r"[A-Za-z']+", body)]
    hedges = {"maybe", "perhaps", "pulse", "nerves", "flinch", "rumor", "catch", "quiet", "steady", "calm", "tight", "itch"}
    return {
        "words": float(len(words)),
        "chars": float(len(body)),
        "avg_word": (sum(len(w) for w in words) / len(words)) if words else 0.0,
        "hedges": float(sum(1 for w in words if w.lower() in hedges)),
        "questions": float(body.count("?")),
        "clauses": float(body.count(",") + body.count("—") + body.count(";")),
        "frag_ratio": float(sum(1 for w in words if len(w) <= 4) / max(1, len(words))),
    }


def _relationship_bite(world: Any, fig: dict[str, Any], ocean: dict[str, float]) -> str:
    """Trust / betrayal_memory / resentment bite — relationship-colored."""
    home = str(fig.get("home") or "")
    ag = world.agents.get(home)
    if not ag:
        return ""
    peers = [p for p in ("chu", "qi", "qin", "zhao") if p != home and p in world.agents]
    peers = [p for p in peers if not getattr(world.agents[p], "annexed", False)]
    peer = peers[0] if peers else ""
    trust_v = float(get_trust(world.trust, home, peer)) if peer else 0.5
    resent = float(ag.state.resentment)
    betrayal = float(ag.state.betrayal_memory)
    fear = float(ag.state.fear_of_qin)
    N = float(ocean.get("N", 0.5))
    A = float(ocean.get("A", 0.5))
    bits: list[str] = []
    if betrayal >= 0.45:
        bits.append("Betrayal memory still sticky.")
    elif betrayal >= 0.25 and N >= 0.55:
        bits.append("Old betrayal itches.")
    if resent >= 0.55:
        bits.append("Resentment keeps the ink cold.")
    elif resent >= 0.35 and A <= 0.4:
        bits.append("Resentment sharpens the edge.")
    if peer and trust_v <= 0.28:
        bits.append(f"Trust toward {peer} runs thin.")
    elif peer and trust_v >= 0.62 and A >= 0.45:
        bits.append(f"Trust toward {peer} still holds.")
    if fear >= 0.55 and home != "qin":
        bits.append("Fear of Qin sits in the throat.")
    if not bits:
        if N >= 0.6:
            bits.append("The room feels tight.")
        elif N <= 0.35:
            bits.append("The room holds steady.")
        else:
            return ""
    return bits[_seed_int(world.tick, fig.get("id"), peer, "rel") % len(bits)]


def _ocean_micro(ocean: dict[str, float], world: Any, fid: str) -> str:
    """OCEAN micro cadence — high-N clipped vs low-N steady (shape lever)."""
    N, E, A, C, O = ocean["N"], ocean["E"], ocean["A"], ocean["C"], ocean["O"]
    pool: list[str] = []
    if N >= 0.62:
        pool += ["Pulse jumps.", "Nerves catch.", "I flinch at the rumor.", "Tight breath."]
    elif N <= 0.38:
        pool += ["Steady.", "I keep the count calm.", "No panic here.", "Even breath."]
    if E >= 0.7:
        pool += ["Hear me.", "I say it open."]
    elif E <= 0.4:
        pool += ["Quiet counsel.", "Noted."]
    if A <= 0.35:
        pool += ["Hard edge.", "No soft toast."]
    elif A >= 0.65:
        pool += ["Keep the bond.", "Face held."]
    if C >= 0.8:
        pool += ["On schedule.", "Check the levy."]
    if O >= 0.7:
        pool += ["New angle.", "Try another door."]
    if not pool:
        return ""
    return pool[_seed_int(world.tick, fid, f"N{N:.2f}", f"E{E:.2f}", "om") % len(pool)]


def _role_event_gloss(role: str, tag: str) -> str:
    """Same event_tag → different role perspective (short, role-colored)."""
    role = (role or "minister").lower()
    table = {
        "ruler": {
            "patron_rebuke": "The crown names the slack court.",
            "sync_appeal": "The seal calls one banner.",
            "legalist_probe": "Royal pressure. Who still obeys?",
            "isolation_caution": "Thrones notice walls.",
            "belief_cascade": "Seal it. Rumor becomes policy.",
            "personal_breakthrough": "Plant where grain already answers.",
            "hedge": "Count the seasons.",
            "refuse": "The throne refuses.",
            "other": "Royal word stands.",
        },
        "minister": {
            "patron_rebuke": "Ledger first. Guest forgot.",
            "sync_appeal": "Sync the apparatus.",
            "legalist_probe": "Probe the brief.",
            "isolation_caution": "Isolation is inefficiency.",
            "belief_cascade": "Clause rides the trust edge.",
            "personal_breakthrough": "Right memorial. Court turns.",
            "hedge": "Sharpen the next draft.",
            "refuse": "No toast-logic here.",
            "other": "Brief stands.",
        },
        "general": {
            "patron_rebuke": "Late levy. Broken spear.",
            "sync_appeal": "Sync on the ford.",
            "legalist_probe": "Who answers the march?",
            "isolation_caution": "Hold the fords.",
            "belief_cascade": "Belief rides the supply line.",
            "personal_breakthrough": "Fittings decide the odds.",
            "hedge": "Read weather. Then charge.",
            "refuse": "No parade without grain.",
            "other": "Camp word stands.",
        },
        "retainer": {
            "patron_rebuke": "Hub forgot its spokes.",
            "sync_appeal": "Call us. Bring payment.",
            "legalist_probe": "Fa scrapes ancestral armor.",
            "isolation_caution": "Neighbors hide. Draft hits us.",
            "belief_cascade": "Client belief ripples.",
            "personal_breakthrough": "Retainer spine shows.",
            "hedge": "Unpaid debt. We wait.",
            "refuse": "No Legalist draft for us.",
            "other": "Spoke word stands.",
        },
    }
    return (table.get(role) or table["minister"]).get(tag) or (table.get(role) or table["minister"])["other"]


def _utter(
    world: Any,
    fig: dict[str, Any],
    tag: str,
    lean: str,
    *,
    ocean: dict[str, float] | None = None,
) -> str:
    """Short role-colored line shaped by OCEAN + trust/memory — no contrast-turn stacks."""
    fid = str(fig.get("id") or "")
    home = str(fig.get("home") or "")
    role = _speech_role_for(fig, fid=fid)
    # Ideology gate: Chu family never voices Legalist probe vantage
    ideo = _ideology_for(fig, home=home, fid=fid)
    if ideo == "chu_patronage_tianxia" and tag == "legalist_probe":
        tag = "patron_rebuke"
    elif ideo == "qi_mercantile" and tag == "legalist_probe":
        tag = "isolation_caution"
    name = str(fig.get("role_label") or fid)
    short = {
        "zhaoxiang": "Zhaoxiang",
        "ying_zheng": "Ying Zheng",
        "li_si": "Li Si",
        "kaolie": "Kaolie",
        "king_you": "King You",
        "chunshen": "Chunshen",
        "chu_nobility": "Chu nobility",
        "king_jian": "King Jian",
    }.get(fid, name.split("(")[0].strip()[:28])
    ocean = dict(ocean) if ocean is not None else _figure_ocean(fig, world)
    color = _ocean_color(ocean)
    N = float(ocean.get("N", 0.5))

    seed = scrub_contrast_turns(_aphorism(world, fid, tag, ocean=ocean, home=home, role=role))
    # Prefer short seeds for high-N (clipped nerves)
    if N >= 0.62 and len(seed) > 72:
        bank = _figure_bank(fid, home=home, role=role)
        short_bank = [s for s in bank if len(s) <= 72 and not has_contrast_turn(s)]
        if short_bank:
            seed = scrub_contrast_turns(short_bank[_seed_int(world.tick, fid, "shortN", tag) % len(short_bank)])

    role_bit = scrub_contrast_turns(_role_event_gloss(role, tag))
    rel = scrub_contrast_turns(_relationship_bite(world, fig, ocean))
    micro = scrub_contrast_turns(_ocean_micro(ocean, world, fid))
    # Capped memories + rare unusual-event comment (not every tick)
    mem_bit = ""
    event_bit = ""
    try:
        from .figure_memory import memory_bite, maybe_unusual_event_comment
        mem_bit = scrub_contrast_turns(memory_bite(world, fid) or "")
        event_bit = scrub_contrast_turns(maybe_unusual_event_comment(world, fig, role=role) or "")
    except Exception:
        mem_bit, event_bit = "", ""

    # Compose: seed + ONE of (role / rel / memory / event) + optional ocean micro — keep short
    parts = [seed]
    pick = _seed_int(world.tick, fid, tag, lean, role, "comp")
    if event_bit:
        # Unusual event note wins this line (brief, role-colored)
        parts = [event_bit]
        if mem_bit and pick % 3 == 0:
            parts.append(mem_bit.split(".")[0] + ".")
        elif micro and N >= 0.6:
            parts.append(micro)
    elif role == "general":
        # Generals: role bite first, seed clipped
        parts = [role_bit, seed.split(".")[0] + "."]
        if micro:
            parts.append(micro)
    elif role == "ruler":
        parts = [seed, role_bit]
        if mem_bit and pick % 2 == 0:
            parts = [seed, mem_bit]
        elif rel and N >= 0.55:
            parts = [seed, rel]
    else:
        if pick % 3 == 0 and mem_bit:
            parts = [seed, mem_bit]
        elif pick % 2 == 0 and rel:
            parts = [seed, rel]
        else:
            parts = [seed, role_bit]
        if N >= 0.6 and micro:
            parts.append(micro)
        elif N <= 0.38 and micro and pick % 3 == 0:
            parts.append(micro)

    body = scrub_contrast_turns(" ".join(p for p in parts if p))
    # Hard ban pass
    if has_contrast_turn(body):
        body = scrub_contrast_turns(re.split(r"\b(but|while|rather)\b", body, maxsplit=1, flags=re.I)[0])
    # Length: high-N shorter
    cap = 88 if N >= 0.62 else (100 if role == "general" else 110)
    if len(body) > cap:
        # cut at last sentence end within cap
        cut = body[:cap]
        if "." in cut:
            body = cut[: cut.rfind(".") + 1]
        else:
            body = cut.rsplit(" ", 1)[0] + "."
    line = f"{short} [{role}|{color}]: {body}"
    out = _strip_ui(line)[:140]
    if has_contrast_turn(out):
        # last resort: speaker + micro/role only
        fallback = micro or role_bit or "Counsel stands."
        out = _strip_ui(f"{short} [{role}|{color}]: {scrub_contrast_turns(fallback)}")[:140]
    return out




def suggest_prompt_chips(world: Any, n: int = 2, figure_id: str | None = None) -> list[str]:
    """Short field-pressure chips (≤2) keyed to focus figure + live field weather.

    Player speaks as collective field pressure — chips should be plain pressure lines
    the figure can answer, not cryptic slogans or mismatched court jargon.
    """
    sess = _ensure_session(world)
    closing = sess.get("open") and int(sess.get("exchanges", 0)) >= DIALOGUE_MIN - 1
    focus = (figure_id or sess.get("figure_id") or "").strip().lower()
    fig = get_figure(focus) if focus else None
    home = str((fig or {}).get("home") or "")
    role = _speech_role_for(fig, fid=focus) if fig else ""
    ideo = _ideology_for(fig, home=home, fid=focus) if fig else ""
    ag = world.agents.get(home) if home else None
    qin_p = float(getattr(world, "qin_pressure", 0.0) or 0.0)
    cohesion = float(getattr(getattr(world, "meso", None), "cohesion", 50.0) or 50.0)
    fear = float(getattr(getattr(ag, "state", None), "fear_of_qin", 0.0) or 0.0) if ag else 0.0
    resent = float(getattr(getattr(ag, "state", None), "resentment", 0.0) or 0.0) if ag else 0.0

    if closing:
        pool = ["Commit: contribute.", "Commit: withhold.", "Close counsel."]
    elif focus and fig:
        pool = []
        # Role-shaped pressure (what you ask this person to weigh)
        if role == "ruler":
            pool.append("Hold your court's face without rushing the map.")
            pool.append("Tell me what unity costs your people this season.")
        elif role == "minister":
            pool.append("Broker the next move with receipts, not banquet vows.")
            pool.append("Where should the levy and guest-lists lean?")
        elif role == "retainer":
            pool.append("Will your clients still follow if the hub goes hungry?")
            pool.append("Name the unpaid debt that still binds the spoke.")
        else:
            pool.append("Read the field: fittings and fords before banners.")
            pool.append("What march order still makes sense this quarter?")

        # Ideology / home-shaped — never push Legalist framing onto Chu
        if ideo == "chu_patronage_tianxia":
            pool.append("Keep the patron web intact under Qin weather.")
            if fear >= 0.45 or qin_p >= 55:
                pool.append("Qin pressure is loud — how do Chu spokes answer?")
        elif ideo == "qin_legalism":
            pool.append("Press staged pressure — patience over thunder.")
            if cohesion < 45:
                pool.append("Anti-Qin cohesion is soft. Exploit or wait?")
        elif ideo == "qi_mercantile":
            pool.append("Qi walls still hold — trade caution for time?")
            pool.append("Isolation buys a season. What does it cost next?")
        else:
            pool.append("Speak to the field as it stands — no destiny script.")

        if resent >= 0.5:
            pool.append("Resentment is hot here. Cool it, or let it cut?")
        if getattr(ag, "desperate", False):
            pool.append("Your court is desperate — what still can be saved?")
    else:
        # Among-courts / no focus: general field pressure, still plain English
        pool = [
            "Hold the coalition line without forcing a single ending.",
            "Ask what grain and trust still buy this quarter.",
        ]
        if qin_p >= 55:
            pool.append("Qin pressure rises — who still answers the field?")
        if cohesion < 45:
            pool.append("Cohesion frays. Repair the spokes, or accept the split?")
        qi = world.agents.get("qi")
        if qi is not None and not getattr(qi, "annexed", False):
            pool.append("Qi stays behind walls — press them, or leave them?")

    # Dedupe while preserving sense; rank by tick so chips rotate
    seen: list[str] = []
    for s in pool:
        s = _strip_ui(s)[:72]
        if s and s not in seen:
            seen.append(s)
    ranked = sorted(seen, key=lambda s: _seed_int(world.tick, sess.get("exchanges", 0), focus or "-", s))
    return ranked[: max(1, min(2, n))]


def _ensure_beliefs(world: Any) -> dict[str, dict[str, float]]:
    fb = getattr(world, "figure_beliefs", None)
    if not isinstance(fb, dict):
        fb = {}
        world.figure_beliefs = fb
    return fb


def _prune_beliefs(board: dict[str, float]) -> dict[str, float]:
    if len(board) <= BELIEF_MAX_PER_FIGURE:
        return board
    return dict(sorted(board.items(), key=lambda kv: kv[1], reverse=True)[:BELIEF_MAX_PER_FIGURE])


def _pressure_bias(pressure: str | None) -> dict[str, float]:
    """Soft bias from field-pressure text — not a player persona trait."""
    p = (pressure or "").lower()
    return {
        "contribute": 0.12 if any(w in p for w in ("hold", "contribute", "coalition", "unity", "close counsel: lean contribute")) else 0.0,
        "withhold": 0.10 if any(w in p for w in ("withhold", "caution", "wait", "close counsel: lean withhold")) else 0.0,
        "defect": 0.10 if any(w in p for w in ("attack", "raid", "defect", "press", "legalist")) else 0.0,
        "close": 0.15 if any(w in p for w in ("close counsel", "commit:", "accept the hedge")) else 0.0,
    }


def _stub_row(world: Any, fig: dict[str, Any], pressure: str | None = None, *, deciding: bool = False) -> dict[str, Any]:
    fid, home = str(fig["id"]), str(fig["home"])
    ag = world.agents[home]
    weights = dict(getattr(ag, "packet_weights", None) or {})
    bias = dict(fig.get("packet_bias") or {})
    from .ideology import ideology_vector, loyalty_sync_bias, rare_combo_bonus

    ideo_v = ideology_vector(ag)
    legalist = float(weights.get("legalist_fa", 0.0)) + 0.35 * float(bias.get("legalist_fa", 0.0)) + 0.15 * ideo_v["legalist"]
    mohist = float(weights.get("mohist_shangxian", 0.0)) + 0.35 * float(bias.get("mohist_shangxian", 0.0))
    soft = (
        float(weights.get("tianxia_da_yitong", 0.0))
        + float(weights.get("chu_patron_client", 0.0))
        + 0.3 * float(bias.get("tianxia_da_yitong", 0.0))
        + 0.3 * float(bias.get("chu_patron_client", 0.0))
        + 0.55 * mohist
        + 0.2 * ideo_v["tianxia"]
        + 0.15 * ideo_v["patron"]
    )
    guanzi = float(weights.get("guanzi", 0.0)) + 0.4 * float(bias.get("guanzi", 0.0))
    fear, resent = float(ag.state.fear_of_qin), float(ag.state.resentment)
    seed = _seed_int(world.tick, fid, "st", pressure or "", deciding)
    pb = _pressure_bias(pressure)
    fb = _ensure_beliefs(world).get(fid) or {}
    top_b = max(fb.values()) if fb else 0.0

    if not deciding and seed % 11 == 0:
        lean, tag, shift = "hedge", "hedge", 0.0
    elif not deciding and seed % 13 == 0:
        lean, tag, shift = "refuse", "refuse", -0.04
    elif getattr(ag, "desperate", False):
        lean, tag, shift = "defect", "other", -0.12
    elif home == "qi" or guanzi > 0.35:
        lean = "withhold" if fear > 0.28 else "contribute"
        tag, shift = "isolation_caution", -0.05
    elif home == "qin" and legalist >= soft:
        lean = "defect"
        tag, shift = "legalist_probe", 0.05
    elif soft > 0.35 or home == "chu" or mohist >= 0.2:
        lean = "contribute" if float(world.meso.cohesion) >= 45 or mohist >= 0.25 else "withhold"
        if mohist >= 0.22 and resent < 0.45:
            tag = "sync_appeal"
        else:
            tag = "patron_rebuke" if resent > 0.4 else "sync_appeal"
        shift = 0.07 if lean == "contribute" else -0.04
        shift += 0.5 * loyalty_sync_bias(ag)
    else:
        lean = "contribute" if (seed % 3) else "withhold"
        tag, shift = "other", 0.03 * (1 if lean == "contribute" else -1)

    # Ideology gate on tags: Chu never speaks as Qin-fa probe; Qi stays mercantile/isolation
    ideo = _ideology_for(fig, home=home, fid=fid)
    if ideo == "chu_patronage_tianxia" and tag == "legalist_probe":
        tag = "patron_rebuke" if resent > 0.35 else "sync_appeal"
    elif ideo == "qi_mercantile" and tag == "legalist_probe":
        tag = "isolation_caution"

    if deciding and lean in STANCE_SOFT:
        lean = "withhold"
        tag = "other"
    if lean in STANCE_HARD:
        scores = {
            "contribute": (0.35 if lean == "contribute" else 0.15) + pb["contribute"] + (0.08 if top_b >= 0.4 else 0),
            "withhold": (0.35 if lean == "withhold" else 0.15) + pb["withhold"],
            "defect": (0.35 if lean == "defect" else 0.10) + pb["defect"],
        }
        lean = max(scores, key=scores.get)

    # Ideology loyalty tip + rare combo crumb (capped by LOYALTY_CAP)
    shift = float(shift) + 0.35 * loyalty_sync_bias(ag)
    combo = rare_combo_bonus(ag, tick=int(world.tick), sid=home)
    shift += float(combo.get("loyalty") or 0.0)
    shift = float(clamp(shift + 0.02 * pb["contribute"], -LOYALTY_CAP, LOYALTY_CAP))
    row: dict[str, Any] = {
        "figure_id": fid,
        "home": home,
        "stance_lean": lean if lean in STANCE_OK else "withhold",
        "loyalty_shift": round(shift, 3),
        "event_tag": tag if tag in EVENT_TAGS else "other",
        "utterance": _utter(world, fig, tag, lean),
        "belief_seed": None,
        "breakthrough": None,
    }
    if deciding:
        # Forced decision — still ideology-gated bank line
        ocean = _figure_ocean(fig, world)
        row["utterance"] = _strip_ui(
            _utter(world, fig, row["event_tag"], row["stance_lean"])
        )[:140]
        row["event_tag"] = tag if tag in EVENT_TAGS else "other"

    stressed = getattr(ag, "desperate", False) or resent > 0.55 or legalist > 0.5
    if (not deciding) and stressed and (_seed_int(world.tick, fid, "bt") % 100) < 20:
        row["breakthrough"] = {
            "kind": "counsel_insight",
            "stance_tip": lean if lean in STANCE_HARD else None,
            "tech_node": None,
            "trust_edge": None,
            "note": "A quiet insight hardens resolve.",
        }
        row["event_tag"] = "personal_breakthrough"
        row["utterance"] = _utter(world, fig, "personal_breakthrough", lean)
    elif (not deciding) and (world.tick % 2 == 0) and (_seed_int(world.tick, fid, "bs") % 100) < 35:
        row["belief_seed"] = {
            "belief_id": "patron_obligation_over_qin_fear" if soft >= legalist else "legalist_clarity_over_ritual",
            "weight_delta": 0.06,
            "spread_hint": "along_loyalty",
        }
        row["event_tag"] = "belief_cascade"
        row["utterance"] = _utter(world, fig, "belief_cascade", lean)
    return row


def rule_counsel(world: Any, *, n: int | None = None, pressure: str | None = None, deciding: bool = False, focus_id: str | None = None) -> list[dict[str, Any]]:
    try:
        from .figure_memory import ensure_figure_memories
        ensure_figure_memories(world)
    except Exception:
        pass
    return [_stub_row(world, f, pressure, deciding=deciding) for f in select_figures(world, n=n, focus_id=focus_id)]


def _clamp_row(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    fid = str(raw.get("figure_id") or "").strip().lower()
    if not fid:
        return None
    lean = str(raw.get("stance_lean") or "withhold").strip().lower()
    if lean == "cooperate":
        lean = "contribute"
    if lean not in STANCE_OK:
        lean = "withhold"
    try:
        shift = float(raw.get("loyalty_shift", 0.0))
    except (TypeError, ValueError):
        shift = 0.0
    tag = str(raw.get("event_tag") or "other").strip().lower()
    if tag not in EVENT_TAGS:
        tag = "other"
    return {
        "figure_id": fid,
        "home": str(raw.get("home") or "chu").strip().lower(),
        "stance_lean": lean,
        "loyalty_shift": round(float(clamp(shift, -LOYALTY_CAP, LOYALTY_CAP)), 3),
        "event_tag": tag,
        "utterance": _strip_ui(str(raw.get("utterance") or ""))[:140] or f"{fid}: …",
        "belief_seed": raw.get("belief_seed"),
        "breakthrough": raw.get("breakthrough"),
    }


def parse_counsel_payload(raw: Any) -> list[dict[str, Any]]:
    data = raw
    if isinstance(raw, str):
        text = raw.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
            if m:
                text = m.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", text, re.S)
            if not m:
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []
    if isinstance(data, dict):
        data = data.get("rows") or data.get("counsel") or [data]
    if not isinstance(data, list):
        return []
    return [r for r in (_clamp_row(i if isinstance(i, dict) else None) for i in data) if r]


def apply_counsel_tips(world: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "trust_edges": 0,
        "resentment_nudges": 0,
        "fear_nudges": 0,
        "cohesion_delta": 0.0,
        "stance_nudges": 0,
        "skipped_annexed": 0,
        "soft_only": 0,
    }
    hard: list[str] = []
    for row in rows:
        home = str(row.get("home") or "")
        ag = world.agents.get(home)
        if ag is None or getattr(ag, "annexed", False) or float(getattr(ag, "viability", 0)) <= 0:
            summary["skipped_annexed"] += 1
            continue
        lean = str(row.get("stance_lean") or "withhold")
        shift = float(row.get("loyalty_shift") or 0.0)
        if lean in STANCE_SOFT:
            summary["soft_only"] += 1
            ag.state.fear_of_qin = float(clamp(float(ag.state.fear_of_qin) + (0.015 if lean == "hedge" else -0.01), 0, 1))
        elif lean in STANCE_HARD:
            hard.append(lean)
            eng = STANCE_TO_ENGINE[lean]
            if world.tick >= int(getattr(ag.intention, "sticky_until", 0) or 0):
                if ag.bloc != "qin" and ag.intention.current != eng:
                    ag.intention.current = eng
                    summary["stance_nudges"] += 1
                elif ag.bloc == "qin" and eng == "defect":
                    ag.intention.current = "defect"
                    summary["stance_nudges"] += 1
        if ag.bloc == "qin":
            partner = "chu" if "chu" in world.agents and not getattr(world.agents["chu"], "annexed", False) else None
        elif home == "chu":
            partner = "qi" if "qi" in world.agents and not getattr(world.agents["qi"], "annexed", False) else "zhao"
        elif home == "qi":
            partner = "chu" if "chu" in world.agents and not getattr(world.agents["chu"], "annexed", False) else "zhao"
        else:
            partner = "chu" if "chu" in world.agents and not getattr(world.agents["chu"], "annexed", False) else None
        if partner and partner in world.agents and not getattr(world.agents[partner], "annexed", False):
            cur = get_trust(world.trust, home, partner)
            if shift > 0:
                set_trust(world.trust, home, partner, saturating_up(cur, min(0.08, shift * 0.35)))
                ag.state.resentment = max(0.0, saturating_down(float(ag.state.resentment), min(0.06, shift * 0.25)))
            elif shift < 0:
                set_trust(world.trust, home, partner, saturating_down(cur, min(0.10, abs(shift) * 0.4)))
                ag.state.resentment = min(1.0, saturating_up(float(ag.state.resentment), min(0.08, abs(shift) * 0.3)))
                if ag.bloc != "qin":
                    ag.state.fear_of_qin = min(1.0, saturating_up(float(ag.state.fear_of_qin), min(0.05, abs(shift) * 0.2)))
                    summary["fear_nudges"] += 1
            summary["trust_edges"] += 1
            summary["resentment_nudges"] += 1
    uniq = set(hard)
    c_delta = 0.0
    if len(hard) >= 2:
        if uniq == {"contribute"}:
            c_delta = 1.5
        elif "contribute" in uniq and "defect" in uniq:
            c_delta = -2.0
        elif len(uniq) >= 2:
            c_delta = -1.0
    if c_delta:
        world.meso.cohesion = float(clamp(float(world.meso.cohesion) + c_delta, 0, 100))
        summary["cohesion_delta"] = c_delta
    world.clamp()
    return summary


def apply_belief_seeds(world: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    board = _ensure_beliefs(world)
    for row in rows:
        seed = row.get("belief_seed")
        if not isinstance(seed, dict):
            continue
        fid, home = str(row.get("figure_id") or ""), str(row.get("home") or "")
        if not fid or home not in world.agents or getattr(world.agents[home], "annexed", False):
            continue
        bid = str(seed.get("belief_id") or "unnamed_belief")
        try:
            delta = float(seed.get("weight_delta") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        delta = float(clamp(delta, 0, BELIEF_WEIGHT_DELTA_CAP))
        if delta <= 0:
            continue
        fig_b = dict(board.get(fid) or {})
        fig_b[bid] = float(clamp(float(fig_b.get(bid, 0)) + delta, 0, 1))
        board[fid] = _prune_beliefs(fig_b)
        peers = []
        for other in living_figures(world):
            oid, oh = str(other["id"]), str(other["home"])
            if oid == fid:
                continue
            edge = 0.5 * (get_trust(world.trust, home, oh) + get_trust(world.trust, oh, home))
            if edge >= 0.55:
                peers.append((edge, oid))
        peers.sort(reverse=True)
        infected = []
        for edge, oid in peers[:2]:
            ob = dict(board.get(oid) or {})
            ob[bid] = float(clamp(float(ob.get(bid, 0)) + 0.5 * delta * edge, 0, 1))
            board[oid] = _prune_beliefs(ob)
            infected.append(oid)
        ag = world.agents[home]
        pw = dict(getattr(ag, "packet_weights", None) or {})
        mapped = "chu_patron_client" if "patron" in bid else ("legalist_fa" if "legalist" in bid else None)
        if mapped:
            pw[mapped] = float(clamp(float(pw.get(mapped, 0)) + min(0.03, delta * 0.4), 0, 1))
            ag.packet_weights = pw
        world.figure_beliefs = board
        line = f"[t={world.tick}] belief_seed {bid} +{delta:.2f} on {fid}" + (
            f" → {','.join(infected)}" if infected else ""
        )
        _log(world, line)
        world.append_log(line, event_id="belief_cascade", actor=fid, action="belief_seed")
        return {"belief_id": bid, "speaker": fid, "delta": delta, "peers": infected}
    return {}


def apply_breakthrough(world: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    cool = getattr(world, "figure_breakthrough_at", None)
    if not isinstance(cool, dict):
        cool = {}
        world.figure_breakthrough_at = cool
    for row in rows:
        bt = row.get("breakthrough")
        if not isinstance(bt, dict):
            continue
        fid, home = str(row.get("figure_id") or ""), str(row.get("home") or "")
        ag = world.agents.get(home)
        if not fid or ag is None or getattr(ag, "annexed", False):
            continue
        last = int(cool.get(fid, -999))
        if last >= 0 and world.tick - last < BREAKTHROUGH_COOLDOWN:
            continue
        kind = str(bt.get("kind") or "counsel_insight")
        note = _strip_ui(str(bt.get("note") or ""))[:80]
        applied: dict[str, Any] = {"kind": kind, "figure_id": fid, "home": home, "note": note}
        tip = bt.get("stance_tip")
        if tip in STANCE_HARD and ag.bloc != "qin" and world.tick >= int(getattr(ag.intention, "sticky_until", 0) or 0):
            ag.intention.current = STANCE_TO_ENGINE[tip]
        if kind == "loyalty_flip":
            edge = str(bt.get("trust_edge") or "")
            if "->" in edge:
                a, b = [x.strip() for x in edge.split("->", 1)]
                if a in world.agents and b in world.agents:
                    set_trust(world.trust, a, b, float(clamp(get_trust(world.trust, a, b) + TRUST_FLIP_CAP, 0, 1)))
                    applied["trust_edge"] = edge
        if kind in ("tech_flash", "craft_flash"):
            node = str(bt.get("tech_node") or "").strip()
            from .tech import TECH_DAG

            if node in TECH_DAG and getattr(world, "tech", None) is not None:
                st = world.tech.states.get(home)
                if st is not None:
                    st.known[node] = float(clamp(float(st.known.get(node, 0)) + TECH_KNOWN_BUMP, 0, 1))
                    applied["tech_node"] = node
            else:
                applied["tech_invalid"] = node or None
        cool[fid] = int(world.tick)
        world.figure_breakthrough_at = cool
        world.last_breakthrough = applied
        try:
            from .figure_memory import record_breakthrough
            record_breakthrough(world, fid, home, note or kind)
        except Exception:
            pass
        line = f"[t={world.tick}] breakthrough {kind} · {fid}@{home}" + (f" — {note}" if note else "")
        _log(world, line)
        world.append_log(line, event_id="breakthrough", actor=fid, action=kind)
        return applied
    return {}


def _log(world: Any, line: str) -> None:
    if not hasattr(world, "counsel_log") or world.counsel_log is None:
        world.counsel_log = []
    world.counsel_log.append(_strip_ui(line))
    if len(world.counsel_log) > COUNSEL_LOG_MAX:
        world.counsel_log = world.counsel_log[-COUNSEL_LOG_MAX:]


def _field_snapshot(world: Any, figs: list[dict[str, Any]]) -> str:
    lines = [
        f"tick={world.tick} pressure={world.qin_pressure:.0f} cohesion={world.meso.cohesion:.0f} pathway={world.meso.pathway_soft}",
        "Channel = collective consciousness among figures (no player persona; figures do not remember a person).",
        "VOICE: action-RPG gloss (Fenyx Rising x Fire Emblem) — vivid, lightly heroic, not academic essay.",
        "Ground each utterance in that figure's OCEAN + ideology/home bank (Chu patronage/tianxia vs Qin legalism vs Qi mercantile). English only.",
        "Ideology gate: Chu figures must NEVER use Qin-Legalist lines (e.g. clear-laws aphorisms).",
        "Role gate: same event_tag → different vantage for ruler vs minister vs general vs retainer.",
        "Memory: use capped figure memories; comment on unusual events rarely; never invent a player persona.",
    ]
    pr = list(getattr(world, "pattern_reactions", None) or [])[-2:]
    if pr:
        lines.append("patterns: " + " | ".join(str(x)[:60] for x in pr))
    fb = _ensure_beliefs(world)
    for fig in figs:
        ag = world.agents.get(fig["home"])
        if not ag:
            continue
        ocean = _figure_ocean(fig, world)
        color = _ocean_color(ocean)
        top = sorted((fb.get(fig["id"]) or {}).items(), key=lambda kv: -kv[1])[:2]
        ideo = _ideology_for(fig)
        role = _speech_role_for(fig)
        try:
            from .figure_memory import snapshot_lines as _mem_snap
            mem_s = _mem_snap(world, fig["id"])
        except Exception:
            mem_s = "memories=[]"
        lines.append(
            f"{fig['id']}@{fig['home']} role={role} ideo={ideo} [{color}] "
            f"OCEAN O={ocean['O']:.2f} C={ocean['C']:.2f} E={ocean['E']:.2f} A={ocean['A']:.2f} N={ocean['N']:.2f} "
            f"fear={ag.state.fear_of_qin:.2f} resent={ag.state.resentment:.2f} beliefs={top} {mem_s}"
        )
    return "\n".join(lines)[:1800]


def _generate_rows(world: Any, *, pressure: str | None, force_stub: bool, deciding: bool, focus_id: str | None = None) -> tuple[list[dict[str, Any]], str, str | None]:
    figs = select_figures(world, focus_id=focus_id)
    mode, err, rows = "stub", None, []
    min_rows = 1 if focus_id else 2
    use_llm = (not force_stub) and counsel_backend_name() == "llm"
    if use_llm:
        try:
            from .counsel_llm import complete_counsel_json

            snap = _field_snapshot(world, figs)
            if focus_id:
                snap += f"\nONE-ON-ONE with {focus_id}: reply as that figure only."
            if deciding:
                snap += "\nFORCE CLOSE: emit final decision leans (contribute|withhold|defect) for each figure."
            raw = complete_counsel_json(snap, prompt=pressure)
            rows = parse_counsel_payload(raw)
            if focus_id:
                rows = [r for r in rows if str(r.get("figure_id") or "").lower() == str(focus_id).lower()] or rows[:1]
            if len(rows) < min_rows:
                raise ValueError("short")
            mode = "llm"
        except Exception as exc:  # noqa: BLE001
            err = f"llm_fallback:{type(exc).__name__}"
            rows = []
    if not rows:
        rows = rule_counsel(world, pressure=pressure, deciding=deciding, focus_id=focus_id)
        mode = "stub"
    living_ids = {f["id"] for f in living_figures(world)}
    living_homes = {f["home"] for f in living_figures(world)}
    if focus_id:
        rows = [r for r in rows if str(r.get("figure_id") or "").lower() == str(focus_id).lower()][:1]
    else:
        rows = [r for r in rows if r.get("home") in living_homes][:4]
    if len(rows) < min_rows:
        rows = rule_counsel(world, pressure=pressure, deciding=deciding, focus_id=focus_id)
        mode = "stub"
    for r in rows:
        r["utterance"] = _strip_ui(r.get("utterance") or "")[:140]
        if deciding and r.get("stance_lean") in STANCE_SOFT:
            r["stance_lean"] = "withhold"
    return rows, mode, err


def _apply_close(world: Any, rows: list[dict[str, Any]], mode: str, err: str | None, pressure: str | None) -> dict[str, Any]:
    """Apply dial tips + cascade/breakthrough on close; wipe session pressure (no dossier)."""
    tips = apply_counsel_tips(world, rows)
    belief = apply_belief_seeds(world, rows)
    breakthrough = apply_breakthrough(world, rows)
    world.counsel_mode = mode
    world.last_counsel_tips = tips
    for row in rows:
        line = (
            f"[t={world.tick}] DECISION {row['figure_id']}@{row['home']} "
            f"{row['stance_lean']} Δloy={row['loyalty_shift']:+.2f} "
            f"[{row['event_tag']}] {row['utterance']}"
        )
        _log(world, line)
        world.append_log(line, event_id="counsel", actor=str(row["figure_id"]), action="decision")
    _log(world, f"[t={world.tick}] counsel_closed mode={mode} n={len(rows)}" + (f" ({err})" if err else ""))
    clear_counsel_session(world)  # wipe ephemeral pressure text — no player memory
    return {
        "ok": True,
        "mode": mode,
        "closed": True,
        "rows": rows,
        "tips": tips,
        "applied_belief": belief or None,
        "applied_breakthrough": breakthrough or None,
        "prompt_chips": suggest_prompt_chips(world, figure_id=(rows[0].get("figure_id") if rows else None)),
        "exchange": 0,
        "exchanges_left": 0,
        "error": err,
    }


def run_counsel_round(
    world: Any,
    *,
    prompt: str | None = None,
    force_stub: bool = False,
    player_initiated: bool = False,
    commit: bool = False,
    figure_id: str | None = None,
) -> dict[str, Any]:
    """Auto: among-courts one-shot. Player: optional one-on-one via figure_id; close by 3–5."""
    if getattr(world, "run_ended", False):
        return {"ok": False, "mode": "stub", "rows": [], "closed": True, "error": "run_ended", "prompt_chips": suggest_prompt_chips(world)}

    # Auto tick path — among courts (era-gated living cast); never one-on-one
    if not player_initiated:
        if not getattr(world, "counsel_auto", True):
            return {"ok": True, "mode": "stub", "rows": [], "closed": True, "skipped": True, "prompt_chips": suggest_prompt_chips(world)}
        rows, mode, err = _generate_rows(world, pressure=None, force_stub=force_stub, deciding=True, focus_id=None)
        return _apply_close(world, rows, mode, err, None)

    # Player dialogue — optional per-figure focus
    left = int(getattr(world, "counsel_actions_left", 1))
    sess = _ensure_session(world)
    focus = (figure_id or sess.get("figure_id") or "").strip().lower() or None
    if focus and not figure_available_for_talk(world, focus):
        return {
            "ok": False,
            "mode": getattr(world, "counsel_mode", "stub"),
            "rows": [],
            "closed": True,
            "error": "Figure not available (era-locked or home annexed)",
            "figure_id": focus,
            "prompt_chips": suggest_prompt_chips(world, figure_id=focus),
        }

    if not sess.get("open"):
        if left <= 0:
            return {
                "ok": False,
                "mode": getattr(world, "counsel_mode", "stub"),
                "rows": [],
                "closed": True,
                "error": "Counsel budget spent this quarter — Advance to reset",
                "prompt_chips": suggest_prompt_chips(world, figure_id=focus),
            }
        world.counsel_actions_left = max(0, left - 1)
        sess["open"] = True
        sess["exchanges"] = 0
        sess["cap"] = DIALOGUE_MIN + (_seed_int(world.tick, "cap") % (DIALOGUE_MAX - DIALOGUE_MIN + 1))
        sess["pressure"] = ""
        sess["figure_id"] = focus or ""

    # Stick to session focus once open
    focus = (sess.get("figure_id") or focus or "").strip().lower() or None

    pressure = _strip_ui(prompt or "")[:240]
    sess["pressure"] = pressure
    sess["exchanges"] = int(sess.get("exchanges", 0)) + 1
    ex = int(sess["exchanges"])
    cap = int(sess.get("cap", DIALOGUE_MAX))
    pb = _pressure_bias(pressure)
    force_close = bool(commit) or ex >= cap or pb["close"] > 0 or (ex >= DIALOGUE_MIN and ("close counsel" in pressure.lower() or "commit:" in pressure.lower()))

    if force_close:
        rows, mode, err = _generate_rows(world, pressure=pressure, force_stub=force_stub, deciding=True, focus_id=focus)
        out = _apply_close(world, rows, mode, err, pressure)
        out["exchange"] = ex
        out["figure_id"] = focus
        return out

    rows, mode, err = _generate_rows(world, pressure=pressure, force_stub=force_stub, deciding=False, focus_id=focus)
    world.counsel_mode = mode
    for row in rows:
        line = (
            f"[t={world.tick}] x{ex}/{cap} {row['figure_id']}@{row['home']} "
            f"{row['stance_lean']} [{row['event_tag']}] {row['utterance']}"
        )
        _log(world, line)
        world.append_log(line, event_id="counsel", actor=str(row["figure_id"]), action="reply")
    channel = f"talk:{focus}" if focus else "among_courts"
    if pressure:
        _log(world, f"[t={world.tick}] {channel} x{ex}/{cap}: {pressure[:80]}")
    return {
        "ok": True,
        "mode": mode,
        "closed": False,
        "rows": rows,
        "tips": None,
        "applied_belief": None,
        "applied_breakthrough": None,
        "prompt_chips": suggest_prompt_chips(world, figure_id=focus),
        "exchange": ex,
        "exchanges_left": max(0, cap - ex),
        "figure_id": focus,
        "error": err,
    }
