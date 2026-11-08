"""Thin cultural chronicle — English flavor gloss, not historical inevitability.

Infers an **emergent cultural state** from event patterns + pivotal dials
(cohesion, trust, annex shocks, counsel tags, tech bursts, mean resentment).
Renaissance / syncretism only when the pattern earns it — never a fixed Chu line.
Resentment colors tone: high → hard realism / bitter; low + warm trust → generative.

Narrator voice (Odetta): Shiji-like — wry, dry, slightly ironic historiographer.
NOT awe-laden epic praise. (Figure dialogue keeps Fenyx×FE gloss elsewhere; this
module does not.) English only; no Chinese UI.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

CHRONICLE_LOG_MAX = 30
# Every Advance writes a wry Shiji-style line (was 3 → felt like skips on most quarters).
CHRONICLE_EVERY_N = 1

_READING_NOTE = "One cultural reading among several — not a locked destiny."

# Emergent states (assessed, not pathway hardcodes)
CULTURAL_STATES = (
    "bitter_realism",
    "legalist_consolidation",
    "mercantile_caution",
    "exhausted_stalemate",
    "fractured_survival",
    "syncretic_bloom",  # earned only
    "craft_renaissance",  # earned only
    "plural_contest",
)


def chronicle_backend_name() -> str:
    from .llm_gate import llm_env_enabled

    key = (os.environ.get("WS_CHRONICLE_API_KEY") or os.environ.get("WS_COUNSEL_API_KEY") or "").strip()
    return "llm" if llm_env_enabled() and key else "stub"


def _seed_int(*parts: Any) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _strip_cjk(text: str) -> str:
    t = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+", "", str(text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _mean_resentment(world: Any) -> float:
    vals = [float(ag.state.resentment) for ag in world.agents.values() if not getattr(ag, "annexed", False)]
    return sum(vals) / max(1, len(vals))


def _featured_trust(world: Any) -> float:
    from .trust import get_trust

    edges = []
    for a, b in (("chu", "qi"), ("qi", "chu"), ("chu", "zhao"), ("qi", "zhao")):
        if a in world.agents and b in world.agents:
            if getattr(world.agents[a], "annexed", False) or getattr(world.agents[b], "annexed", False):
                continue
            edges.append(get_trust(world.trust, a, b))
    return sum(edges) / max(1, len(edges)) if edges else 0.4


def _recent_counsel_tags(world: Any, n: int = 8) -> list[str]:
    tags = []
    for rec in (world.episode or [])[-50:]:
        if rec.get("event_id") == "counsel":
            tags.append(str(rec.get("action") or "other"))
    return tags[-n:]


def _annex_count(world: Any) -> int:
    return sum(1 for ag in world.agents.values() if getattr(ag, "annexed", False))


def _tech_burst(world: Any) -> bool:
    for rec in (world.episode or [])[-30:]:
        if rec.get("event_id") in ("m2_breakthrough", "breakthrough"):
            return True
    return False


def _count_tags(tags: list[str], *names: str) -> int:
    return sum(1 for t in tags if t in names)


def assess_cultural_pattern(world: Any, *, reason: str | None = None) -> dict[str, Any]:
    """Score emergent cultural state from dials + recent event pattern.

    Returns dict with state id, tone (bitter|hard|neutral|warm|generative),
    scores, and feature flags — used by stub + LLM context.
    """
    path = str(getattr(world.meso, "pathway_soft", None) or "other")
    coh = float(world.meso.cohesion)
    sid = float(world.meso.shared_identity)
    pressure = float(world.qin_pressure)
    resent = _mean_resentment(world)
    trust = _featured_trust(world)
    tags = _recent_counsel_tags(world)
    annex_n = _annex_count(world)
    tech = _tech_burst(world)
    reason = (reason or "cadence").lower()

    from .ideology import bloc_ideology_means

    ideo_m = bloc_ideology_means(world)
    sync_n = _count_tags(tags, "sync_appeal", "patron_rebuke")
    legalist_n = _count_tags(tags, "legalist_probe")
    isol_n = _count_tags(tags, "isolation_caution")
    belief_n = _count_tags(tags, "belief_cascade")
    break_n = _count_tags(tags, "personal_breakthrough")

    # Feature flags that must be earned for bloom/renaissance
    warm_social = coh >= 68 and trust >= 0.52 and resent <= 0.38
    # Mohism / tianxia soft priors make warm tone slightly easier to earn
    if ideo_m["mohist"] + ideo_m["tianxia"] >= 0.45 and resent <= 0.45 and trust >= 0.48:
        warm_social = True if coh >= 62 else warm_social
    generative_room = warm_social and sid >= 48 and annex_n == 0
    syncretic_earned = (
        generative_room
        and (sync_n + belief_n) >= 1
        and path in ("chu_fiction", "other", "stalemate")
        and pressure < 75
    )
    renaissance_earned = (
        syncretic_earned
        and (tech or break_n >= 1)
        and coh >= 72
        and resent <= 0.32
    )

    scores: dict[str, float] = {
        "bitter_realism": 0.15 + 0.55 * resent + 0.12 * min(1.0, annex_n / 2) + (0.2 if reason.startswith("annex") else 0),
        "legalist_consolidation": 0.1
        + (0.35 if path == "qin_path" else 0.05)
        + 0.2 * (pressure / 100.0)
        + 0.15 * legalist_n
        + 0.1 * resent
        + 0.22 * ideo_m["legalist"],
        # Mercantile/Qi-Linzi caution only when Qin force is not already dominating the board
        "mercantile_caution": (
            0.12
            + 0.25 * isol_n
            + (0.2 if path == "other" else 0.05)
            + 0.1 * (1.0 - trust)
            + 0.18 * ideo_m["guanzi"]
            - (0.35 if path == "qin_path" else 0.0)
            - (0.2 if pressure >= 75 else 0.0)
        ),
        "exhausted_stalemate": 0.1
        + (0.4 if path == "stalemate" else 0.05)
        + 0.15 * (1.0 if 40 <= coh < 70 else 0)
        + 0.1 * (pressure / 100.0),
        "fractured_survival": 0.1 + 0.35 * (1.0 if coh < 42 else 0) + 0.2 * min(1.0, annex_n / 2) + 0.15 * resent,
        "plural_contest": 0.2 + 0.1 * (1.0 if path == "other" else 0) + 0.05 * (legalist_n + sync_n + isol_n)
        + 0.12 * ideo_m["mohist"] + 0.08 * ideo_m["dao"],
        "syncretic_bloom": 0.0,
        "craft_renaissance": 0.0,
    }
    if syncretic_earned:
        scores["syncretic_bloom"] = 0.45 + 0.15 * sync_n + 0.1 * belief_n + 0.1 * (trust - 0.5)
    if renaissance_earned:
        scores["craft_renaissance"] = 0.55 + 0.15 * (1.0 if tech else 0) + 0.1 * break_n

    # High resentment suppresses bloom/renaissance hard
    if resent >= 0.55:
        scores["syncretic_bloom"] *= 0.15
        scores["craft_renaissance"] *= 0.1
        scores["bitter_realism"] += 0.25
    elif resent >= 0.42:
        scores["syncretic_bloom"] *= 0.45
        scores["craft_renaissance"] *= 0.35

    state = max(scores, key=scores.get)
    # Stricter earned states win when flagged (renaissance ⊂ bloom)
    if renaissance_earned and scores.get("craft_renaissance", 0) > 0:
        state = "craft_renaissance"
    elif syncretic_earned and scores.get("syncretic_bloom", 0) > 0 and state not in (
        "craft_renaissance",
        "bitter_realism",
    ):
        # Prefer bloom over weaker plural/stalemate when earned and not bitter
        if state in ("plural_contest", "exhausted_stalemate", "mercantile_caution", "syncretic_bloom"):
            state = "syncretic_bloom"

    # Tone from resentment (+ warmth modifiers)
    if resent >= 0.55:
        tone = "bitter"
    elif resent >= 0.42:
        tone = "hard"
    elif generative_room and state in ("syncretic_bloom", "craft_renaissance"):
        tone = "generative"
    elif warm_social:
        tone = "warm"
    else:
        tone = "neutral"

    return {
        "state": state,
        "tone": tone,
        "scores": scores,
        "path": path,
        "cohesion": coh,
        "shared_identity": sid,
        "pressure": pressure,
        "resentment": resent,
        "trust": trust,
        "annex_n": annex_n,
        "tags": tags,
        "tech_burst": tech,
        "syncretic_earned": syncretic_earned,
        "renaissance_earned": renaissance_earned,
        "ideology": ideo_m,
        "reason": reason,
    }


# English gloss for packet ids — vault/primary-text grounded, narrator-safe (no CJK).
_PACKET_EN_GLOSS: dict[str, str] = {
    "legalist_fa": "fa and ranks: order by statute and reward, not blood",
    "mohist_shangxian": "elevate the worthy; condemn wasteful offensive war",
    "dao_guodian": "Guodian Dao color — weak use, timing, receptivity",
    "ru_li": "li and ren: ritual names that bind power",
    "huang_lao": "Huang-Lao mix — Dao as frame, xingming/fa as tools",
    # "Qi hegemonic" = Guanzi/Linzi mercantile–fiscal pattern (NOT a Qin typo).
    # Prefer "Linzi mercantile" wording so high Qin force is never miscited as Qi hegemony.
    "guanzi": "Guanzi technics — Linzi grain, workshops, Qi mercantile–fiscal order",
    "lineage_shi": "lineage honor and ancestral precedent",
    "tianxia_da_yitong": "da-yitong ideal — credible unity without one court swallowing all",
    "chu_patron_client": "Chu patron–client web: hospitality and spokes over central fa",
}


def _packet_symbol_bits(world: Any, *, pick: int, limit: int = 2) -> list[str]:
    """Pull short English symbol bites from active belief packets (catalog + vault gloss)."""
    try:
        from .packets import PACKET_CATALOG, normalize_packet_list
    except Exception:
        return []
    scored: list[tuple[float, str, str]] = []
    for ag in world.agents.values():
        if getattr(ag, "annexed", False):
            continue
        weights = dict(getattr(ag, "packet_weights", None) or {})
        pids = normalize_packet_list(getattr(ag, "active_packets", None) or list(weights.keys()))
        for pid in pids:
            pkt = PACKET_CATALOG.get(pid)
            if not pkt:
                continue
            w = float(weights.get(pid, pkt.strength or 0.4))
            gloss = _PACKET_EN_GLOSS.get(pid, "")
            anchor = _strip_cjk(getattr(pkt, "anchor", "") or "")
            # Drop leftover punctuation after CJK strip
            anchor = re.sub(r"\s*[—\-]\s*$", "", anchor).strip()
            tags = []
            ont = getattr(pkt, "ontology", None)
            if ont is not None:
                tags.extend(list(getattr(ont, "legitimacy_source", None) or [])[:2])
            bit = gloss or anchor
            if not bit and tags:
                # Never surface bare "qi hegemonic order" under Qin-path — that reads as a Qin typo
                safe_tags = [
                    t for t in tags
                    if not (
                        t == "qi_hegemonic_order"
                        and str(getattr(getattr(world, "meso", None), "pathway_soft", "") or "") == "qin_path"
                    )
                ]
                if safe_tags:
                    bit = "legitimacy via " + ", ".join(t.replace("_", " ") for t in safe_tags[:2])
            # Under Qin domination, rephrase Guanzi as Linzi mercantile caution (not Qi conquest hegemony)
            path = str(getattr(getattr(world, "meso", None), "pathway_soft", "") or "")
            press = float(getattr(world, "qin_pressure", 0) or 0)
            if pid == "guanzi" and bit and (path == "qin_path" or press >= 75):
                bit = "Guanzi residue — Linzi mercantile caution under Qin pressure"
            if bit:
                scored.append((w, pid, bit))
    if not scored:
        return []
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = scored[:6]
    out: list[str] = []
    seen: set[str] = set()
    for i in range(len(top)):
        _, pid, bit = top[(pick + i) % len(top)]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(f"{pid.replace('_', ' ')} — {bit}")
        if len(out) >= limit:
            break
    return out


def _body_for_state(pattern: dict[str, Any], pick: int, *, world: Any | None = None) -> str:
    state = pattern["state"]
    tone = pattern["tone"]
    path = pattern["path"]

    # Tone varnish — wry Shiji historiographer (dry, ironic); never epic praise
    if tone == "bitter":
        varnish = (
            "The brush turns cold: resentment keeps the accounts honest, if not kind.",
            "One notes the debts first; ideals, as usual, arrive late if at all.",
        )[pick % 2]
    elif tone == "hard":
        varnish = (
            "A dry reading: hope is measured out with the grain, not sung.",
            "The season admits little romance — which, historically, is rarely a loss.",
        )[pick % 2]
    elif tone == "generative":
        varnish = (
            "Where trust holds and resentment thins, invention creeps in — quietly, without parade.",
            "A generative register, contingent as ever; the record declines to call it destiny.",
        )[pick % 2]
    elif tone == "warm":
        varnish = (
            "Cohesion softens the prose a degree — not utopia, merely less clenched teeth.",
            "The field sounds almost civil; the chronicler withholds applause.",
        )[pick % 2]
    else:
        varnish = "The season remains contested and unfinished; the record declines a moral."

    bodies = {
        "bitter_realism": (
            "Annex scars and raised resentment push culture toward hard accounting: levy math, betrayal memory, fewer banquet metaphors.",
            "Shared stories thin; what remains is realist talk of spoils, fear, and who eats next.",
        ),
        "legalist_consolidation": (
            "Pattern leans legalist: statute-first speech, harder edges, less patience for soft loyalty rituals.",
            "Administrative clarity crowds out plural experiment — a consolidation reading, not a final empire.",
        ),
        "mercantile_caution": (
            "Mercantile caution colors the field: isolationist counsel and mid trust keep romance of federation at arm's length.",
            "Markets and grain books set the tone more than salons; coalitions are priced, not hymned.",
        ),
        "exhausted_stalemate": (
            "Stalemate weather: courts conserve grain and metaphors; culture turns tired, careful, administrative.",
            "Neither bloom nor purge — a long season of withheld levies and clipped speech.",
        ),
        "fractured_survival": (
            "Low cohesion fragments culture into court-by-court survival stories.",
            "Shared identity frays; each capital keeps its own dialect of fear.",
        ),
        "plural_contest": (
            "No orthodoxy crowns the season: legalist probes, patron appeals, and mercantile caution compete without a winner.",
            f"Soft pathway label '{path.replace('_', ' ')}' is only a meter reading — the culture stays plural.",
        ),
        "syncretic_bloom": (
            "Earned pattern: warm trust, contained resentment, and sync/belief counsel let syncretic habits surface — mixed packets without a single orthodoxy.",
            "Patron–client and plural speech find listeners; syncretism appears because the meters allow it, not because a path name requires it.",
        ),
        "craft_renaissance": (
            "Earned pattern — if one insists: workshops and counsel flashes coincide with warm trust; a craft bloom, provisional, and already looking over its shoulder.",
            "Breakthroughs meet low bitterness; courts trade methods like grain. Call it renaissance if you must — the pattern holds only while nobody counts the spoils.",
        ),
    }
    opts = bodies.get(state) or bodies["plural_contest"]
    body = opts[pick % len(opts)]
    symbol = ""
    if world is not None:
        bits = _packet_symbol_bits(world, pick=pick, limit=2)
        if bits:
            symbol = " Symbols in play — " + "; ".join(bits) + "."
    return f"{body} {varnish}{symbol}"


def stub_chronicle(world: Any, *, reason: str | None = None) -> str:
    """1–3 English sentences from assessed cultural pattern (not fixed path slogans)."""
    pattern = assess_cultural_pattern(world, reason=reason)
    reason = pattern["reason"]
    pick = _seed_int(
        world.tick,
        pattern["state"],
        pattern["tone"],
        reason,
        f"{pattern['resentment']:.2f}",
    )

    if reason.startswith("annex"):
        lead = (
            "Another annexation: workshops and grain change hands, "
            "and bystanders discover fresh reasons for resentment."
        )
    elif reason.startswith("alliance"):
        lead = (
            "A joint campaign briefly aligns the courts — then, as ever, "
            "trust and resentment compete to write the next line."
        )
    elif reason.startswith("pathway"):
        lead = (
            f"Meters nudge the soft pathway toward '{pattern['path'].replace('_', ' ')}'; "
            "the chronicle reassesses cultural weather from the whole pattern."
        )
    else:
        lead = (
            f"Quarter {world.tick}: pressure {pattern['pressure']:.0f}, cohesion {pattern['cohesion']:.0f}, "
            f"mean resentment {pattern['resentment']:.2f}, featured trust {pattern['trust']:.2f}."
        )

    body = _body_for_state(pattern, pick, world=world)
    state_tag = f" Cultural state reading: {pattern['state'].replace('_', ' ')} ({pattern['tone']} tone)."

    # Light event spice (not path slogans)
    spice = ""
    tags = pattern["tags"]
    if pattern["annex_n"] >= 2 and "annex" not in reason:
        spice += " Multiple annexations already scar cultural memory."
    if "belief_cascade" in tags and pattern["state"] in ("syncretic_bloom", "plural_contest"):
        spice += " Beliefs still ride trust edges in recent counsel."
    if pattern["tech_burst"] and pattern["state"] != "craft_renaissance":
        spice += " A tech flash registered, but bitterness or thin trust kept bloom from locking in."

    text = f"{lead} {body}{state_tag}{spice} {_READING_NOTE}"
    return _strip_cjk(text)


def _llm_polish(draft: str, world: Any, pattern: dict[str, Any]) -> str | None:
    from .llm_gate import admit_llm_call

    if chronicle_backend_name() != "llm":
        return None
    # Same global+session budget as counsel — deny ⇒ keep stub draft.
    if not admit_llm_call():
        return None
    try:
        import json
        import urllib.request

        api_key = (os.environ.get("WS_CHRONICLE_API_KEY") or os.environ.get("WS_COUNSEL_API_KEY") or "").strip()
        base = (os.environ.get("WS_COUNSEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        model = (os.environ.get("WS_CHRONICLE_MODEL") or os.environ.get("WS_COUNSEL_MODEL") or "gpt-4o-mini").strip()
        body = {
            "model": model,
            "temperature": 0.55,
            "max_tokens": 240,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Polish a Warring States cultural chronicle into 1–3 English sentences. VOICE: Shiji-like historiographer — wry, dry, slightly ironic. NOT awe-laden epic praise; NOT action-RPG heroic gloss (that voice is for figure dialogue only). Assess the given emergent cultural state; do NOT invent a renaissance or syncretism unless state is syncretic_bloom or craft_renaissance. High resentment → hard/bitter realist tone. English only — no Chinese. Keep 'one reading among several — not destiny'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"state={pattern['state']} tone={pattern['tone']} "
                        f"resentment={pattern['resentment']:.2f} cohesion={pattern['cohesion']:.0f} "
                        f"trust={pattern['trust']:.2f} pathway={pattern['path']} "
                        f"syncretic_earned={pattern['syncretic_earned']} "
                        f"renaissance_earned={pattern['renaissance_earned']}\n"
                        "Keep any 'Symbols in play' packet anchors/claims from the draft — "
                        "they are vault-grounded belief-packet gloss, not decoration.\n"
                        f"Draft:\n{draft}"
                    ),
                },
            ],
        }
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        out = _strip_cjk(content)
        return out[:600] if out else None
    except Exception:  # noqa: BLE001
        return None


def _append(world: Any, line: str, *, reason: str, mode: str) -> None:
    if not hasattr(world, "chronicle_log") or world.chronicle_log is None:
        world.chronicle_log = []
    world.chronicle_log.append(line)
    if len(world.chronicle_log) > CHRONICLE_LOG_MAX:
        world.chronicle_log = world.chronicle_log[-CHRONICLE_LOG_MAX:]
    world.chronicle_mode = mode
    world.append_log(
        line,
        event_id="chronicle",
        actor="chronicler",
        action=reason or "cadence",
        dials_fired=["pathway", "cohesion", "resentment", "culture"],
    )


def should_chronicle(world: Any, *, reason: str | None = None) -> bool:
    if getattr(world, "run_ended", False):
        return False
    if reason:
        return True
    if world.tick > 0 and world.tick % CHRONICLE_EVERY_N == 0:
        return True
    last = getattr(world, "last_chronicle_pathway", None)
    path = str(world.meso.pathway_soft or "other")
    if last is not None and last != path:
        return True
    return False


def maybe_write_chronicle(world: Any, *, reason: str | None = None, force: bool = False) -> dict[str, Any] | None:
    path = str(getattr(world.meso, "pathway_soft", None) or "other")
    why = reason
    if not why:
        last = getattr(world, "last_chronicle_pathway", None)
        if last is not None and last != path:
            why = "pathway_change"
        elif world.tick > 0 and world.tick % CHRONICLE_EVERY_N == 0:
            why = "cadence"
        else:
            why = "manual"
    if not force and not should_chronicle(world, reason=reason):
        return None

    pattern = assess_cultural_pattern(world, reason=why)
    draft = stub_chronicle(world, reason=why)
    mode = "stub"
    text = draft
    polished = _llm_polish(draft, world, pattern)
    if polished:
        text = polished
        mode = "llm"
        # Guard: LLM must not smuggle renaissance if not earned
        if not pattern["renaissance_earned"]:
            text = re.sub(r"(?i)\brenaissance\b", "craft stir", text)
        if not pattern["syncretic_earned"]:
            text = re.sub(r"(?i)\bsyncretism\b", "mixed habits", text)
            text = re.sub(r"(?i)\bsyncretic\b", "mixed", text)
        if _READING_NOTE.lower() not in text.lower():
            text = f"{text.rstrip()} {_READING_NOTE}"

    text = _strip_cjk(text)
    world.last_cultural_state = pattern["state"]
    world.last_cultural_tone = pattern["tone"]
    _append(world, f"[t={world.tick}] {text}", reason=why, mode=mode)
    world.last_chronicle_pathway = path
    return {
        "ok": True,
        "mode": mode,
        "reason": why,
        "text": text,
        "cultural_state": pattern["state"],
        "tone": pattern["tone"],
        "pattern": pattern,
    }
