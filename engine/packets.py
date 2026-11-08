"""Belief packets = ontology schemas (logics), not scalar ideology labels.

Four *base* schools (vault classical cluster):
  Legalism · Mohism · Daoism · Confucianism
Syncretisms (Huang-Lao, Guanzi, …) = weighted combos of those bases.
Institutional overlays (lineage, tianxia holding, Chu patron–client) may mix in too.
Many mixes allowed — courts hold syncretic weight vectors, not exclusive labels.

Grounded in retrieved public corpora + vault ideology notes. Fiction cast excluded.
Docs: belief-logics-ontologies.md · daoscape-sources-check.md · primary-texts/*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .world import WorldState


@dataclass
class OntologyTags:
    """What counts as betrayal / ally / legitimacy under this logic."""

    betrayal_criteria: list[str] = field(default_factory=list)
    ally_criteria: list[str] = field(default_factory=list)
    legitimacy_source: list[str] = field(default_factory=list)

    def as_flat(self) -> list[str]:
        return (
            [f"betrayal:{t}" for t in self.betrayal_criteria]
            + [f"ally:{t}" for t in self.ally_criteria]
            + [f"legit:{t}" for t in self.legitimacy_source]
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "betrayal_criteria": list(self.betrayal_criteria),
            "ally_criteria": list(self.ally_criteria),
            "legitimacy_source": list(self.legitimacy_source),
        }


# Four classical base schools → packet ids
BASE_SCHOOLS: dict[str, str] = {
    "legalism": "legalist_fa",
    "mohism": "mohist_shangxian",
    "daoism": "dao_guodian",
    "confucianism": "ru_li",
}
BASE_PACKET_IDS: frozenset[str] = frozenset(BASE_SCHOOLS.values())
BASE_SCHOOL_ORDER: tuple[str, ...] = (
    "legalism",
    "mohism",
    "daoism",
    "confucianism",
)


@dataclass
class BeliefPacket:
    """Structured belief ontology — schema + claim + strength + text anchors.

    kind:
      base — one of the four schools
      syncretism — weighted combo of bases (blend_weights)
      institutional — political/network overlay (may mix with any)
    """

    id: str
    logic_id: str
    name_zh: str
    claim: str
    strength: float = 0.5
    ontology: OntologyTags = field(default_factory=OntologyTags)
    # legacy flat tags (UI chips); derived from ontology if empty
    ontology_tags: list[str] = field(default_factory=list)
    # soft allow-list of other logic_ids this packet can travel with
    compatibility: list[str] = field(default_factory=list)
    blend_of: list[str] = field(default_factory=list)  # packet ids in the blend
    # school-key weights for syncretisms, e.g. {"daoism": 0.55, "legalism": 0.45}
    blend_weights: dict[str, float] = field(default_factory=dict)
    kind: str = "institutional"  # base | syncretism | institutional
    fiction: bool = False
    sources: list[str] = field(default_factory=list)
    anchor: str = ""

    def tags(self) -> list[str]:
        return self.ontology_tags or self.ontology.as_flat()

    def is_base(self) -> bool:
        return self.kind == "base" or self.id in BASE_PACKET_IDS

    def is_syncretism(self) -> bool:
        return self.kind == "syncretism" or bool(self.blend_weights) or bool(self.blend_of)


# Static compatibility in [-1, 1] — docs/belief-logics-ontologies.md §3.1 + Mohist/Huang-Lao
COMPAT_MATRIX: dict[tuple[str, str], float] = {
    ("legalist_fa", "legalist_fa"): 1.0,
    ("legalist_fa", "lineage_shi"): -0.6,
    ("legalist_fa", "tianxia_da_yitong"): -0.35,
    ("legalist_fa", "mohist_shangxian"): 0.35,  # merit/elevation affinity; not identity
    ("legalist_fa", "huang_lao"): 0.55,  # fa strand inside Huang-Lao
    ("legalist_fa", "guanzi"): 0.5,  # shared fa tools; Guanzi != Qin harsh fa
    ("legalist_fa", "ru_li"): -0.45,
    ("legalist_fa", "chu_patron_client"): -0.7,  # central fa vs aristocratic patronage
    ("lineage_shi", "lineage_shi"): 1.0,
    ("lineage_shi", "tianxia_da_yitong"): 0.15,  # honorable Contribute can align
    ("lineage_shi", "mohist_shangxian"): -0.55,  # blood vs elevate-the-worthy
    ("lineage_shi", "huang_lao"): -0.25,
    ("lineage_shi", "guanzi"): 0.1,  # Qi wealth/house interest can coexist with Guanzi tech
    ("lineage_shi", "ru_li"): 0.45,  # ritual/rank overlap
    ("lineage_shi", "chu_patron_client"): 0.75,  # Chu aristocratic spine
    ("tianxia_da_yitong", "tianxia_da_yitong"): 1.0,
    ("tianxia_da_yitong", "mohist_shangxian"): 0.25,
    ("tianxia_da_yitong", "huang_lao"): 0.2,
    ("tianxia_da_yitong", "guanzi"): 0.15,  # hegemonic order, not horizontal holding
    ("tianxia_da_yitong", "ru_li"): 0.3,
    ("tianxia_da_yitong", "chu_patron_client"): 0.4,  # Chunshen hub as horizontal organizer
    ("mohist_shangxian", "mohist_shangxian"): 1.0,
    ("mohist_shangxian", "huang_lao"): 0.1,
    ("mohist_shangxian", "guanzi"): 0.2,
    ("mohist_shangxian", "ru_li"): -0.2,
    ("mohist_shangxian", "chu_patron_client"): -0.2,
    ("huang_lao", "huang_lao"): 1.0,
    ("huang_lao", "guanzi"): 0.35,  # related fa+dao mixes but DISTINCT logics
    ("huang_lao", "ru_li"): -0.15,
    ("huang_lao", "chu_patron_client"): 0.25,  # syncretic Chu can hold both
    ("huang_lao", "dao_guodian"): 0.85,  # Dao strand inside Huang-Lao
    ("guanzi", "guanzi"): 1.0,
    ("guanzi", "dao_guodian"): 0.4,  # Dao-tinged cosmology/economy, not Guodian quietism
    ("guanzi", "ru_li"): 0.05,
    ("guanzi", "chu_patron_client"): -0.25,
    ("dao_guodian", "dao_guodian"): 1.0,
    ("dao_guodian", "chu_patron_client"): 0.55,
    ("dao_guodian", "lineage_shi"): 0.35,
    ("dao_guodian", "tianxia_da_yitong"): 0.3,
    ("dao_guodian", "legalist_fa"): -0.4,
    ("dao_guodian", "ru_li"): 0.25,
    ("dao_guodian", "mohist_shangxian"): 0.1,
    ("ru_li", "ru_li"): 1.0,
    ("ru_li", "chu_patron_client"): 0.35,
    ("chu_patron_client", "chu_patron_client"): 1.0,
}


def compat(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if (a, b) in COMPAT_MATRIX:
        return COMPAT_MATRIX[(a, b)]
    if (b, a) in COMPAT_MATRIX:
        return COMPAT_MATRIX[(b, a)]
    return 0.0


PACKET_CATALOG: dict[str, BeliefPacket] = {
    "legalist_fa": BeliefPacket(
        id="legalist_fa",
        logic_id="legalist_fa",
        name_zh="法家·法",
        claim="法、令、赏罚一统于上；能力与军功重于血缘世卿。",
        strength=0.78,
        kind="base",
        ontology=OntologyTags(
            betrayal_criteria=["defy_center", "leak_capacity", "fail_assigned_role"],
            ally_criteria=["useful_instrument", "talent_that_strengthens_machine"],
            legitimacy_source=["effective_order", "fa_and_ranks", "force_success"],
        ),
        compatibility=["legalist_fa", "huang_lao", "guanzi", "mohist_shangxian"],
        sources=[
            "docs/belief-logics-ontologies.md §3–4",
            "docs/daoscape-sources-check.md (Shang Yang / fa)",
            "docs/primary-texts/shiji.md (商君列傳 / 秦始皇本紀)",
            "docs/big-five-historical-profiles.json (qin-ying-zheng, qin-li-si)",
        ],
        anchor="BASE Legalism — Shiji 商君列傳 + 始皇本紀",
    ),
    "mohist_shangxian": BeliefPacket(
        id="mohist_shangxian",
        logic_id="mohist_shangxian",
        name_zh="墨家·尚贤",
        claim="尚贤尚同：举用贤能、兼爱非攻色彩；可与军功制部分共振，非楚世卿礼。",
        strength=0.55,
        kind="base",
        ontology=OntologyTags(
            betrayal_criteria=["nepotism_over_worth", "offensive_war_for_glory", "waste_common_benefit"],
            ally_criteria=["worthy_regardless_of_birth", "defensive_cooperation"],
            legitimacy_source=["worth_shangxian", "jian_ai_utility", "condemn_offensive_war"],
        ),
        compatibility=["mohist_shangxian", "legalist_fa", "tianxia_da_yitong"],
        sources=[
            "docs/daoscape-sources-check.md (Mozi 尚贤 parallel)",
            "docs/primary-texts/mozi-open-editions.md (尚贤/兼爱/非攻)",
            "docs/primary-texts-index.md (Mozi OA map)",
        ],
        anchor="BASE Mohism — Mozi 尚贤 / 非攻",
    ),
    "dao_guodian": BeliefPacket(
        id="dao_guodian",
        logic_id="dao_guodian",
        name_zh="道家·郭店（楚简）",
        claim=(
            "楚地道家：太一/弱用、因循、贵柔——郭店老子甲乙丙与太一生水气质。"
            "与贵族门客网可并存，不是秦法的对立标签，而是可加权的宇宙—政治感受。"
        ),
        strength=0.7,
        kind="base",
        ontology=OntologyTags(
            betrayal_criteria=["force_against_timing", "crush_weak_for_show", "ignore_dao_pattern"],
            ally_criteria=["quiet_partners", "non_coercive_hubs", "ritual_soft_power"],
            legitimacy_source=["dao_pattern", "tai_yi_order", "wuwei_receptivity"],
        ),
        compatibility=[
            "dao_guodian",
            "chu_patron_client",
            "huang_lao",
            "lineage_shi",
            "tianxia_da_yitong",
            "ru_li",
        ],
        sources=[
            "docs/primary-texts/guodian.md (老子甲乙丙 / 太一生水)",
            "docs/primary-texts/zhuangzi.md (non-coercion color)",
            "docs/daoscape-sources-check.md (paradigm / syncretism notes)",
        ],
        anchor="BASE Daoism — Guodian Chu slips",
    ),
    "ru_li": BeliefPacket(
        id="ru_li",
        logic_id="ru_li",
        name_zh="儒家·礼",
        claim="礼、仁、名分与教化约束权力；可缓世族苛索，亦可非峻法。",
        strength=0.45,
        kind="base",
        ontology=OntologyTags(
            betrayal_criteria=["break_li", "inhumane_punishment", "name_not_rectified"],
            ally_criteria=["ritual_peers", "ren_reciprocity"],
            legitimacy_source=["li", "ren", "virtue_example"],
        ),
        compatibility=["ru_li", "lineage_shi", "tianxia_da_yitong", "chu_patron_client"],
        sources=[
            "docs/primary-texts/analects.md",
            "docs/primary-texts/mencius.md",
            "docs/primary-texts/xunzi.md (礼/性恶 — Li Si teacher strand)",
            "docs/primary-texts/liji.md",
        ],
        anchor="BASE Confucianism — Analects/Mencius/Xunzi/Liji",
    ),
    # --- Syncretisms = weighted combos of the four bases ---
    "huang_lao": BeliefPacket(
        id="huang_lao",
        logic_id="huang_lao",
        name_zh="黄老（道+法综摄）",
        claim=(
            "黄老式综摄：道为纲、刑名为用——Daoism+Legalism weighted mix，不是互斥单标签。"
            "Distinct from Guanzi: Huang-Lao leans xingming/wuwei; Guanzi leans Qi fiscal-hegemony."
        ),
        strength=0.55,
        kind="syncretism",
        ontology=OntologyTags(
            betrayal_criteria=["disrupt_natural_order", "arbitrary_cruelty_without_xingming", "ignore_timing"],
            ally_criteria=["quiet_efficacy", "xingming_aligners"],
            legitimacy_source=["dao_pattern", "xingming_fa", "wuwei_governance"],
        ),
        compatibility=["huang_lao", "legalist_fa", "dao_guodian", "guanzi", "tianxia_da_yitong", "chu_patron_client"],
        blend_of=["dao_guodian", "legalist_fa"],
        blend_weights={"daoism": 0.55, "legalism": 0.45},
        sources=[
            "docs/primary-texts/guodian.md (Dao strand)",
            "docs/daoscape-sources-check.md (paradigms; Ternary syncretism)",
            "docs/belief-logics-ontologies.md (courts are mixed)",
        ],
        anchor="SYNCRETISM Daoism+Legalism (Huang-Lao weights)",
    ),
    "guanzi": BeliefPacket(
        id="guanzi",
        logic_id="guanzi",
        name_zh="管子（齐·法+道综摄）",
        claim=(
            "《管子》式齐国霸政综摄：Legalism+Daoism weighted mix（富国强兵、轻重、因时），"
            "不是黄老刑名清静，也不是秦商鞅峻法。"
        ),
        strength=0.62,
        kind="syncretism",
        ontology=OntologyTags(
            betrayal_criteria=[
                "waste_state_wealth",
                "ignore_seasonal_qi",
                "sabotage_hegemonic_order",
                "starve_levy_for_private_house",
            ],
            ally_criteria=["fiscal_administrators", "hegemonic_partners", "seasonal_planners"],
            legitimacy_source=["qi_hegemonic_order", "wealth_and_arms", "guanzi_technics", "timely_dao_of_qi"],
        ),
        compatibility=["guanzi", "legalist_fa", "dao_guodian", "huang_lao", "lineage_shi", "tianxia_da_yitong"],
        blend_of=["legalist_fa", "dao_guodian"],
        blend_weights={"legalism": 0.58, "daoism": 0.42},
        sources=[
            "docs/daoscape-sources-check.md (Legalism.md — Guanzi)",
            "docs/primary-texts-index.md (管子)",
            "docs/primary-texts/xunzi.md (管仲為政者也)",
            "docs/primary-texts/shiji.md (齐管仲)",
        ],
        anchor="SYNCRETISM Legalism+Daoism (Guanzi / Qi weights — distinct from Huang-Lao)",
    ),
    # --- Institutional overlays (may mix with bases/syncretisms) ---
    "lineage_shi": BeliefPacket(
        id="lineage_shi",
        logic_id="lineage_shi",
        name_zh="士/世族",
        claim="世卿、礼与血缘义务约束精英；地位稀释即本体论威胁。",
        strength=0.7,
        kind="institutional",
        ontology=OntologyTags(
            betrayal_criteria=["demotion", "outsider_elevation", "unpaid_ritual_debt", "shame_house"],
            ally_criteria=["kin_rank_peers", "marriage_patron_ties"],
            legitimacy_source=["heredity", "ritual_correctness", "ancestral_precedent"],
        ),
        compatibility=["lineage_shi", "tianxia_da_yitong", "ru_li"],
        sources=[
            "docs/belief-logics-ontologies.md §2.2–4",
            "docs/big-five-historical-profiles.json (chu-nobility-faction)",
            "docs/primary-texts/liji.md",
            "docs/primary-texts/shiji.md (楚世家)",
        ],
        anchor="INSTITUTIONAL lineage overlay — often mixes with Confucianism",
    ),
    "tianxia_da_yitong": BeliefPacket(
        id="tianxia_da_yitong",
        logic_id="tianxia_da_yitong",
        name_zh="天下/大一统（共持读）",
        claim="天下秩序可求；晚战国共持读=水平合纵抑霸，非必然秦式郡县独断。",
        strength=0.68,
        kind="institutional",
        ontology=OntologyTags(
            betrayal_criteria=["free_ride_bloc", "secret_qin_side_deal", "break_public_contribute"],
            ally_criteria=["anti_qin_co_contributors", "horizontal_trust"],
            legitimacy_source=["credible_unity", "shared_power_holding", "da_yitong_ideal"],
        ),
        compatibility=["tianxia_da_yitong", "lineage_shi", "mohist_shangxian", "ru_li"],
        sources=[
            "docs/daoscape-vault-overview.md (The unifying ideal / da yitong)",
            "docs/belief-logics-ontologies.md (tianxia_shared_power)",
            "docs/primary-texts/zhanguoce.md",
            "docs/primary-texts/shiji.md",
        ],
        anchor="INSTITUTIONAL order-claim overlay — mixes across schools",
    ),
    "chu_patron_client": BeliefPacket(
        id="chu_patron_client",
        logic_id="chu_patron_client",
        name_zh="楚·贵族门客网",
        claim=(
            "楚政是浪漫贵族式门客—恩主网络（春申君式四公子 hub），"
            "不是秦式以法赏罚一统的中央集权。恩义、面子与庇护链条约束行动。"
        ),
        strength=0.72,
        kind="institutional",
        ontology=OntologyTags(
            betrayal_criteria=[
                "abandon_patron",
                "cut_client_stipend",
                "public_loss_of_face",
                "side_deal_past_hub",
            ],
            ally_criteria=[
                "patron_client_dyad",
                "four_lords_style_hub",
                "guest_retainers",
                "marriage_fief_ties",
            ],
            legitimacy_source=[
                "charismatic_patronage",
                "aristocratic_generosity",
                "ritual_hospitality",
                "personal_en_yi",
            ],
        ),
        compatibility=["chu_patron_client", "lineage_shi", "tianxia_da_yitong", "ru_li", "dao_guodian"],
        # Soft affinity: patronage often rides with Daoist Chu color + Confucian ritual face
        blend_of=["dao_guodian", "ru_li"],
        blend_weights={"daoism": 0.55, "confucianism": 0.45},
        sources=[
            "docs/belief-logics-ontologies.md (Chu nobility / Chunshen hub)",
            "docs/big-five-historical-profiles.json",
            "docs/primary-texts/shiji.md (春申君列傳 / 楚世家)",
            "docs/daoscape-sources-check.md (Four Lords)",
        ],
        anchor="INSTITUTIONAL Chu patronage — optional Dao+Ru affinity weights",
    ),
}

# Legacy / school-name aliases → canonical packet ids
ALIAS_TO_CANONICAL: dict[str, str] = {
    "legalist_centralism": "legalist_fa",
    "legalism": "legalist_fa",
    "fa": "legalist_fa",
    "mohism": "mohist_shangxian",
    "mozi": "mohist_shangxian",
    "daoism": "dao_guodian",
    "dao": "dao_guodian",
    "confucianism": "ru_li",
    "ru": "ru_li",
    "confucian": "ru_li",
    "lineage_honor": "lineage_shi",
    "tianxia_unity": "tianxia_da_yitong",
    "tianxia_shared_power": "tianxia_da_yitong",
}


def resolve_packet_id(pid: str) -> str:
    return ALIAS_TO_CANONICAL.get(pid, pid)


def get_packet(pid: str) -> BeliefPacket | None:
    return PACKET_CATALOG.get(resolve_packet_id(pid))


def normalize_packet_list(ids: list[str]) -> list[str]:
    out: list[str] = []
    for pid in ids:
        canon = resolve_packet_id(pid)
        if canon in PACKET_CATALOG and canon not in out:
            out.append(canon)
    return out


def syncretism_ids() -> list[str]:
    return [pid for pid, p in PACKET_CATALOG.items() if p.kind == "syncretism"]


def institutional_ids() -> list[str]:
    return [pid for pid, p in PACKET_CATALOG.items() if p.kind == "institutional"]


# Weighted ontology mixes per court — docs/packet-mix-proposal.md §2.2.
# Four bases + syncretisms (Huang-Lao ≠ Guanzi) + institutional overlays.
# Soft weights only — dynamics stay emergent (no hard coexistence rules).
COURT_MIXES: dict[str, dict[str, float]] = {
    "qin": {
        "legalist_fa": 0.55,  # base Legalism
        "tianxia_da_yitong": 0.22,
        "huang_lao": 0.18,  # syncretism Dao>Fa
        "ru_li": 0.05,  # light Xunzi residue
    },
    "chu": {
        "dao_guodian": 0.28,  # Guodian Chu Dao
        "chu_patron_client": 0.26,
        "lineage_shi": 0.18,
        "tianxia_da_yitong": 0.14,
        "huang_lao": 0.10,
        "ru_li": 0.04,  # ritual face (below active threshold alone)
    },
    "qi": {
        "guanzi": 0.34,  # Fa>Dao technics — distinct from Huang-Lao
        "lineage_shi": 0.26,
        "tianxia_da_yitong": 0.14,
        "dao_guodian": 0.12,
        "ru_li": 0.10,
        "huang_lao": 0.04,  # trace only; Guanzi stays dominant
    },
    "zhao": {
        "tianxia_da_yitong": 0.38,
        "lineage_shi": 0.32,
        "huang_lao": 0.15,
        "mohist_shangxian": 0.10,
        "legalist_fa": 0.05,  # military reform discipline adjacency
    },
    "han": {
        "mohist_shangxian": 0.36,
        "legalist_fa": 0.30,
        "huang_lao": 0.14,
        "tianxia_da_yitong": 0.12,
        "guanzi": 0.08,
    },
    "wei": {
        "tianxia_da_yitong": 0.36,
        "ru_li": 0.26,
        "lineage_shi": 0.14,
        "huang_lao": 0.12,
        "guanzi": 0.12,
    },
    "yan": {
        "tianxia_da_yitong": 0.40,
        "mohist_shangxian": 0.22,
        "dao_guodian": 0.14,
        "ru_li": 0.14,
        "guanzi": 0.10,
    },
}


def starting_weights(state_id: str) -> dict[str, float]:
    mix = dict(COURT_MIXES.get(state_id, {"tianxia_da_yitong": 1.0}))
    s = sum(mix.values()) or 1.0
    return {k: round(v / s, 4) for k, v in mix.items()}


def starting_packets(state_id: str) -> list[str]:
    """Active set = all logics with weight ≥ 0.08 (many mixes; not exclusive)."""
    w = starting_weights(state_id)
    return [pid for pid, wt in sorted(w.items(), key=lambda x: -x[1]) if wt >= 0.08]


def expand_to_base_schools(weights: dict[str, float] | None) -> dict[str, float]:
    """Roll packet mix into the four base-school dials (syncretisms expand via blend_weights).

    Institutional packets without blend_weights do not add to school dials
    (they remain separate overlays). Institutional with blend_weights (Chu patronage)
    contribute their affinity share.
    """
    bases = {k: 0.0 for k in BASE_SCHOOL_ORDER}
    w = {resolve_packet_id(k): float(v) for k, v in (weights or {}).items()}
    for pid, wt in w.items():
        if wt <= 0:
            continue
        pkt = PACKET_CATALOG.get(pid)
        if pkt is None:
            continue
        if pkt.id in BASE_PACKET_IDS:
            school = next(s for s, bid in BASE_SCHOOLS.items() if bid == pkt.id)
            bases[school] += wt
            continue
        if pkt.blend_weights:
            bw = pkt.blend_weights
            bsum = sum(float(v) for v in bw.values()) or 1.0
            for school, sw in bw.items():
                if school in bases:
                    bases[school] += wt * (float(sw) / bsum)
            continue
        # pure institutional overlay — skip school rollup
    total = sum(bases.values()) or 1.0
    return {k: round(v / total, 4) for k, v in bases.items()}


def court_base_mix(state_id: str) -> dict[str, float]:
    return expand_to_base_schools(starting_weights(state_id))


# Backward alias
DEFAULT_ACTIVE = {k: starting_packets(k) for k in COURT_MIXES}


def conflict_score(
    agent_packet_ids: list[str],
    weights: dict[str, float] | None = None,
) -> float:
    """Σ w_p·w_q·strength_p·strength_q·(1-compat)/2 — weighted syncretic mix.

    High-compat blends (Dao+patron, Huang-Lao) score low conflict; fa vs lineage stays high.
    """
    ids = normalize_packet_list(agent_packet_ids)
    pkts = [PACKET_CATALOG[i] for i in ids if i in PACKET_CATALOG]
    w = {resolve_packet_id(k): float(v) for k, v in (weights or {}).items()}
    total = 0.0
    n = 0
    for i, p in enumerate(pkts):
        for q in pkts[i + 1 :]:
            c = compat(p.logic_id, q.logic_id)
            wp = w.get(p.id, 1.0 / max(1, len(pkts)))
            wq = w.get(q.id, 1.0 / max(1, len(pkts)))
            total += wp * wq * p.strength * q.strength * (1.0 - c) / 2.0
            n += 1
    return float(total) if n else 0.0


def logic_conflict(
    agent_packet_ids: list[str],
    weights: dict[str, float] | None = None,
) -> bool:
    # Syncretic high-compat mixes (Chu Dao+patron) should rarely trip this
    return conflict_score(agent_packet_ids, weights) >= 0.08


def ontology_tags_act_as_betrayal(packet_ids: list[str], act: str) -> bool:
    """Gate betrayal_memory spikes — only if an active ontology tags the act."""
    act = act.lower()
    tag_map = {
        "defect": {
            "break_public_contribute",
            "free_ride_bloc",
            "secret_qin_side_deal",
            "defy_center",
            "fail_assigned_role",
            "shame_house",
            "unpaid_ritual_debt",
            "abandon_patron",
            "side_deal_past_hub",
            "public_loss_of_face",
        },
        "withhold": {
            "free_ride_bloc",
            "break_public_contribute",
            "unpaid_ritual_debt",
            "leak_capacity",
            "waste_common_benefit",
            "cut_client_stipend",
            "abandon_patron",
            "public_loss_of_face",
        },
    }
    relevant = tag_map.get(act, set())
    for pid in normalize_packet_list(packet_ids):
        pkt = PACKET_CATALOG.get(pid)
        if not pkt:
            continue
        if set(pkt.ontology.betrayal_criteria) & relevant:
            return True
    return False


def shared_identity(world: "WorldState") -> float:
    """Derived meso stock from tianxia / patron / Dao-soft unity on anti-Qin bloc."""
    anti = [a for a in world.agents.values() if a.bloc == "anti_qin"]
    if not anti:
        return 0.0
    scores = []
    unity_ids = {"tianxia_da_yitong", "chu_patron_client", "dao_guodian", "huang_lao"}
    for ag in anti:
        local = 0.0
        weights = getattr(ag, "packet_weights", None) or {}
        for pid in normalize_packet_list(ag.active_packets):
            pkt = PACKET_CATALOG.get(pid)
            if not pkt:
                continue
            if pkt.logic_id in unity_ids or "tianxia_da_yitong" in pkt.compatibility:
                w = float(weights.get(pid, 0.25))
                # Dao/patron soften into holding stock; tianxia strongest
                kind_w = {
                    "tianxia_da_yitong": 1.0,
                    "chu_patron_client": 0.7,
                    "dao_guodian": 0.55,
                    "huang_lao": 0.45,
                }.get(pkt.logic_id, 0.4)
                local += w * kind_w * pkt.strength * (1.0 - 0.5 * ag.state.betrayal_memory)
        scores.append(min(1.0, local))
    return 100.0 * (sum(scores) / len(scores))


# Contagious logics: bases + syncretisms + holding overlay (not sticky local lineage)
_CONTAGIOUS = frozenset(
    {
        "tianxia_da_yitong",
        "mohist_shangxian",
        "ru_li",
        "dao_guodian",
        "huang_lao",
        "guanzi",
        "chu_patron_client",  # Chu romantic patronage can travel along trust
        "legalist_fa",  # listed but filtered out of anti-Qin outbound below
    }
)


def renormalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    w = {resolve_packet_id(k): max(0.0, float(v)) for k, v in (weights or {}).items()}
    w = {k: v for k, v in w.items() if k in PACKET_CATALOG and v > 0}
    s = sum(w.values()) or 1.0
    return {k: round(v / s, 4) for k, v in w.items()}


def _bump_weight(ag: Any, pid: str, amount: float) -> None:
    weights = dict(getattr(ag, "packet_weights", None) or {})
    pid = resolve_packet_id(pid)
    weights[pid] = float(weights.get(pid, 0.0)) + amount
    ag.packet_weights = renormalize_weights(weights)
    # Keep active set = top weights (≥0.08), max 5
    ranked = [k for k, v in sorted(ag.packet_weights.items(), key=lambda x: -x[1]) if v >= 0.08]
    ag.active_packets = ranked[:5]


def propagate_packets(world: "WorldState") -> list[dict[str, Any]]:
    """M3 contagion: frequency-dependent / soft-threshold adoption along trust edges.

    Not a linear blend-only copy. Granovetter-style: personal threshold θ from
    openness/memory_bias; exposure blends local packet frequency with source trust.
    Soft gate σ(k·(exposure−θ)) multiplies receptivity; weight bump saturates
    toward remaining mix room. Conflict may still reject.
    docs/belief-logics-ontologies.md §6.
    """
    from .nonlinear import saturating_up, soft_threshold
    from .trust import get_trust

    events: list[dict[str, Any]] = []
    anti = [a for a in world.agents.values() if a.bloc == "anti_qin"]
    if len(anti) < 2:
        return events
    pairs = 0
    strong = 0
    for i, a in enumerate(anti):
        for b in anti[i + 1 :]:
            pairs += 1
            if get_trust(world.trust, a.id, b.id) >= 0.5 and get_trust(world.trust, b.id, a.id) >= 0.5:
                strong += 1
    density = (strong / pairs) if pairs else 0.0
    evo = float(getattr(world.world, "evo_dial", 0.4))

    def _holder_freq(pid: str) -> float:
        n = 0
        for a in anti:
            w = float((getattr(a, "packet_weights", None) or {}).get(pid, 0.0))
            if pid in normalize_packet_list(a.active_packets) or w >= 0.08:
                n += 1
        return n / max(1, len(anti))

    for source in anti:
        src_w = renormalize_weights(getattr(source, "packet_weights", None) or {})
        if not src_w and source.active_packets:
            src_w = {p: 1.0 / len(source.active_packets) for p in normalize_packet_list(source.active_packets)}
        # Seed = highest-weight contagious packet (lineage sticky stays local)
        candidates = [
            (pid, wt)
            for pid, wt in src_w.items()
            if pid in _CONTAGIOUS and pid != "legalist_fa"
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda x: -x[1])
        seed, seed_w = candidates[0]
        seed_pkt = PACKET_CATALOG[seed]
        freq = _holder_freq(seed)
        for target in anti:
            if target.id == source.id:
                continue
            trust_st = get_trust(world.trust, source.id, target.id)
            if trust_st < 0.45:
                continue
            # Linear affinity features (still used) × frequency soft gate
            receptivity = 0.35 * target.traits.openness + 0.4 * trust_st + 0.25 * density
            receptivity *= 0.5 + 0.5 * evo
            receptivity *= 0.7 + 0.3 * min(1.0, seed_w)
            if target.traits.memory_bias > 0.55 and seed_pkt.logic_id == "tianxia_da_yitong":
                receptivity *= 0.45  # Qi trauma damping
            # Dao/Guanzi easier into Chu; Mohist harder into lineage-heavy courts
            tgt_base = expand_to_base_schools(getattr(target, "packet_weights", None) or {})
            if seed_pkt.logic_id == "mohist_shangxian" and tgt_base.get("confucianism", 0) > 0.35:
                receptivity *= 0.75

            # Granovetter personal threshold: low openness / high trauma → higher θ
            theta = (
                0.18
                + 0.32 * (1.0 - float(target.traits.openness))
                + 0.12 * float(target.traits.memory_bias)
            )
            # Exposure: global holder frequency + trusted source strength
            exposure = 0.50 * freq + 0.50 * trust_st * min(1.0, seed_w)
            freq_gate = soft_threshold(exposure, theta, k=10.0)
            # Dual path: high receptivity innovators OR frequency cascade
            effective = receptivity * (0.30 + 0.70 * freq_gate)
            if effective < 0.28 and receptivity < 0.42:
                continue

            cur_w = float((getattr(target, "packet_weights", None) or {}).get(seed, 0.0))
            # Saturating bump toward remaining mix room (not unbounded linear add)
            bump = 0.12 * effective * max(0.0, 1.0 - cur_w)
            trial_ids = normalize_packet_list(list(target.active_packets) + [seed])
            trial_w = dict(getattr(target, "packet_weights", None) or {})
            trial_w[seed] = cur_w + bump
            if (
                conflict_score(trial_ids, trial_w) > 0.22
                and seed not in normalize_packet_list(target.active_packets)
            ):
                target.state.perceived_threat = min(
                    1.0, saturating_up(target.state.perceived_threat, 0.03)
                )
                events.append(
                    {
                        "from": source.id,
                        "to": target.id,
                        "packet": seed,
                        "result": "rejected_conflict",
                        "conflict": round(conflict_score(trial_ids, trial_w), 3),
                        "freq": round(freq, 3),
                        "freq_gate": round(freq_gate, 3),
                    }
                )
                continue
            had = seed in normalize_packet_list(target.active_packets)
            if bump > 1e-6:
                _bump_weight(target, seed, bump)
            events.append(
                {
                    "from": source.id,
                    "to": target.id,
                    "packet": seed,
                    "result": "reinforced" if had else "adopted",
                    "receptivity": round(receptivity, 3),
                    "effective": round(effective, 3),
                    "freq": round(freq, 3),
                    "freq_gate": round(freq_gate, 3),
                    "weight": float((target.packet_weights or {}).get(seed, 0.0)),
                }
            )
    return events


def packet_public_view(pid: str) -> dict[str, Any]:
    pkt = get_packet(pid)
    if not pkt:
        return {"id": pid, "error": "unknown"}
    return {
        "id": pkt.id,
        "logic_id": pkt.logic_id,
        "name_zh": pkt.name_zh,
        "claim": pkt.claim,
        "strength": pkt.strength,
        "kind": pkt.kind,
        "ontology": pkt.ontology.to_dict(),
        "tags": pkt.tags(),
        "blend_of": list(pkt.blend_of),
        "blend_weights": dict(pkt.blend_weights),
        "fiction": pkt.fiction,
        "sources": list(pkt.sources),
        "anchor": pkt.anchor,
    }
