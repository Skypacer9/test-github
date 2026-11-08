"""Public-corpus dossiers for state agents + named figures.

Shiji / primary-texts packs only. No private-chat grafts.
Design-fiction cast (Ling etc.) excluded.
Sources: docs/primary-texts/shiji.md + docs/big-five-historical-profiles.json anchors.
"""

from __future__ import annotations

from .profiles import advisor_brief, profile_by_id, profile_meta_for_state

# Prose grounded in public Shiji / OA packs (Wikisource). Numbers stay in WorldState.
DOSSIERS: dict[str, str] = {
    "qin": (
        "Qin (Zhaoxiang early face → Ying Zheng later) — Legalist war-admin apparatus on the western passes. "
        "Shiji 秦始皇本紀: Wei Liao on 少恩而虎狼心; guest expulsion reversed after Li Si's "
        "《谏逐客书》; sequential conquest doctrine. Design prior from historiography, "
        "not a clinical psych score. Packets: 法家/法 + light Huang-Lao syncretism."
    ),
    "chu": (
        "Chu — Daoist-leaning aristocratic court (郭店楚简 Dao strand + romantic patron–client), "
        "NOT Qin Legalist fa. Weighted mix: dao_guodian + chu_patron_client + lineage_shi + "
        "light Huang-Lao syncretism. Kaolie trusts Chunshen hub; nobility are clients. "
        "Shiji: Ying fall 278; 春申君合纵. Dials: response_latency, status_threat."
    ),
    "qi": (
        "Qi (King Jian isolationist court) — post-284 Yan trauma memory_bias plus "
        "Guanzi-weighted statecraft memory (法+道综摄, distinct from Huang-Lao). "
        "Shiji 秦始皇本紀 二十六年: 齐王建…不通秦; vault Legalism cluster names 《管子》. "
        "High betrayal_memory; quorum leans on Contribute. Not design-fiction."
    ),
    "zhao": (
        "Zhao — northern militarized court; Changping trauma lean (白起王翦列傳 scaffold). "
        "Mix: tianxia holding + lineage + light Mohism/Huang-Lao. Thin OCEAN scaffold "
        "(no dedicated JSON row). Historical state, not fiction cast."
    ),
    "han": (
        "Han — buffer on Qin approaches; archaeology prior for iron/weapons niche "
        "(西平酒店冶铁 — see archaeology survey). Mohist + Legalist weight in court mix. "
        "High fear_of_qin. Scaffold OCEAN."
    ),
    "wei": (
        "Wei — central plain; Xinling tradition pairs with Chunshen in Shiji relief "
        "episodes. Ru-leaning + tianxia mix; cynical treaty memory; needs credible "
        "guarantees. Scaffold OCEAN."
    ),
    "yan": (
        "Yan — northern flank; 284 invasion of Qi is memory source for Qi isolationism. "
        "兴隆铁范 as M2 mould niche prior. Tianxia + Mohist lean. Scaffold OCEAN. "
        "Historical state agent."
    ),
}

# Named figures (Character Profile) — one dossier each, Shiji-grounded.
FIGURE_DOSSIERS: dict[str, str] = {
    "kaolie": (
        "楚考烈王 Kaolie — Chu royal hub. Daoist–aristocratic syncretism "
        "(郭店楚简 Dao + lineage honor), not Qin fa. Relies on Chunshen as patron "
        "broker for合纵. Status-threat dial high; latency slows Contribute. "
        "Home meters on state agent 'chu'."
    ),
    "king_you": (
        "楚幽王 King You of Chu — weak successor after Kaolie (~238 BCE). "
        "High neuroticism scaffold; patronage web frays; not Qin fa. "
        "Talkable when Kaolie exits (BCE year ≤ 238). Home meters on state agent 'chu'."
    ),
    "chunshen": (
        "春申君黄歇 Lord Chunshen — Chu patron hub. Shiji 春申君列傳: guest-house "
        "politics +合纵 brokerage. Packet lean: chu_patron_client + tianxia + Dao. "
        "Hub–spoke sync with Kaolie/nobility is bonded-coalition mechanic, not "
        "Qin friendship. Fiction cast excluded."
    ),
    "chu_nobility": (
        "Chu nobility clients (aggregate) — lineage_shi-heavy spoke under Chunshen "
        "patronage. Face / unpaid ritual debt ontologies; abandon_patron tags "
        "betrayal. Syncretic Dao light; resists exclusive Legalist label."
    ),
    "zhaoxiang": (
        "King Zhaoxiang of Qin — long-reign sovereign prior to Ying Zheng. "
        "Scaffold: expansive yet patient consolidation; guest talent and staged pressure "
        "without First-Emperor radicalism. Packets lean legalist_fa with tianxia / Huang-Lao "
        "garnish. Early-era talkable Qin face while Zheng / Li Si remain era-gated "
        "(unlock when BCE year ≤ 247). Design prior — not a clinical psych score."
    ),
    "ying_zheng": (
        "秦王政 Ying Zheng — Qin king prior. Shiji 秦始皇本紀 scaffold: sequential "
        "conquest, guest-minister apparatus, Legalist centralism (legalist_fa dominant) "
        "with light Huang-Lao / Ru garnish. Design prior — not a clinical psych score."
    ),
    "li_si": (
        "李斯 Li Si — Qin chancellor / Legalist advisor. 《谏逐客书》 reverses guest "
        "expulsion; fa + Huang-Lao (Dao>Fa garnish) weighted mix. Advisor brief for "
        "Qin court; not a separate interstate agent."
    ),
    "king_jian": (
        "齐王建 King Jian — isolationist Qi court. Shiji: 不通秦 after 284 Yan trauma. "
        "Guanzi syncretism (Fa>Dao, distinct from Huang-Lao Dao>Fa) + lineage + "
        "memory_bias. Quorum often gated by Contribute; betrayal_memory sticky."
    ),
}

PACK_CITATIONS = (
    "docs/primary-texts/shiji.md (Wikisource 公有领域)",
    "docs/big-five-historical-profiles.json (design priors + shiji_anchors)",
    "docs/primary-texts-index.md (OA portal map)",
)


def dossier_for(agent_id: str) -> str:
    base = DOSSIERS.get(agent_id, f"{agent_id.title()} — meso field state agent.")
    meta = profile_meta_for_state(agent_id)
    anchors = meta.get("shiji_anchors") or []
    if anchors:
        base += " Anchors: " + "; ".join(anchors[:2]) + "."
    base += f" Confidence={meta.get('confidence', 'scaffold')}."
    return base


def dossier_for_figure(figure_id: str) -> str:
    """Named-figure dossier for Character Profile (cast figures)."""
    fid = str(figure_id or "").strip().lower()
    prose = FIGURE_DOSSIERS.get(fid)
    if not prose:
        return f"{fid or 'figure'} — named court figure (scaffold)."
    # Pull profile row anchors when present
    from .figures import get_figure

    meta = get_figure(fid) or {}
    row = profile_by_id(meta.get("profile_id") or "") or {}
    anchors = list(row.get("shiji_anchors") or [])[:2]
    conf = row.get("confidence") or "low"
    out = prose
    if anchors:
        out += " Anchors: " + "; ".join(str(a) for a in anchors) + "."
    out += (
        f" Confidence={conf}. Speculative design prior from Shiji — "
        "not a clinical score. Four bases + syncretic mixes; no fiction cast."
    )
    return out


def dossier_bundle(agent_id: str) -> dict:
    meta = profile_meta_for_state(agent_id)
    advisors = []
    if agent_id == "qin":
        a = advisor_brief("qin-li-si")
        if a:
            advisors.append(a)
    if agent_id == "chu":
        a = advisor_brief("chu-lord-chunshen")
        if a:
            advisors.append(a)
    return {
        "text": dossier_for(agent_id),
        "profile_ids": meta.get("profile_ids") or [],
        "shiji_anchors": meta.get("shiji_anchors") or [],
        "confidence": meta.get("confidence"),
        "disclaimer": meta.get("disclaimer"),
        "fiction": False,
        "advisors": advisors,
        "corpora": list(PACK_CITATIONS),
    }
