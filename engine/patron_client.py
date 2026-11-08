"""Chu aristocratic patron–client graph — hub–spoke, not Qin Legalist flat digraph.

Structure (court overlay inside meso field; not extra interstate agents):
  Hubs:  kaolie (royal), chunshen (Four-Lords patron organizer)
  Clients: nobility houses + guest retainers
  Edges: high hub↔client & hub↔hub; weaker lateral client↔client

Sync bonus when a hub's client clique is bonded (high spoke trust + mutual face).
Belief packet: chu_patron_client (packets.py).

Sources:
  docs/big-five-historical-profiles.json (chu-king-kaolie, chu-nobility-faction, chu-lord-chunshen)
  docs/belief-logics-ontologies.md (Chunshen hub)
  docs/primary-texts/shiji.md (春申君 / 楚世家)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import WorldState

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .world import WorldState

# Court-node ids (overlay — not interstate STATE_IDS)
HUB_KAOLIE = "kaolie"
HUB_CHUNSHEN = "chunshen"
CLIENT_NOBILITY = "nobility"
CLIENT_RETAINERS = "retainers"
CLIENT_GUESTS = "guests"

CHU_HUBS = (HUB_KAOLIE, HUB_CHUNSHEN)
CHU_CLIENTS = (CLIENT_NOBILITY, CLIENT_RETAINERS, CLIENT_GUESTS)
CHU_COURT_NODES = CHU_HUBS + CHU_CLIENTS


@dataclass
class PatronClientGraph:
    """Typed hub–spoke graph for Chu romantic/aristocratic court."""

    hubs: list[str] = field(default_factory=lambda: list(CHU_HUBS))
    clients: list[str] = field(default_factory=lambda: list(CHU_CLIENTS))
    # Directed trust on court nodes: "chunshen->nobility"
    edges: dict[str, float] = field(default_factory=dict)
    # Which hub each client primarily attaches to
    primary_hub: dict[str, str] = field(
        default_factory=lambda: {
            CLIENT_NOBILITY: HUB_KAOLIE,  # hereditary houses face the throne
            CLIENT_RETAINERS: HUB_CHUNSHEN,  # guest-retainers of the chancellor
            CLIENT_GUESTS: HUB_CHUNSHEN,
        }
    )
    labels: dict[str, str] = field(
        default_factory=lambda: {
            HUB_KAOLIE: "King Kaolie (royal hub)",
            HUB_CHUNSHEN: "Lord Chunshen (patron hub)",
            CLIENT_NOBILITY: "Chu nobility clients",
            CLIENT_RETAINERS: "Chunshen retainers",
            CLIENT_GUESTS: "Guest clients / 门客",
        }
    )

    def key(self, i: str, j: str) -> str:
        return f"{i}->{j}"

    def get(self, i: str, j: str, default: float = 0.35) -> float:
        return float(self.edges.get(self.key(i, j), default))

    def set(self, i: str, j: str, value: float) -> None:
        self.edges[self.key(i, j)] = max(0.0, min(1.0, float(value)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "hubs": list(self.hubs),
            "clients": list(self.clients),
            "edges": dict(self.edges),
            "primary_hub": dict(self.primary_hub),
            "labels": dict(self.labels),
            "structure": "hub_spoke_patron_client",
            "not": "qin_legalist_flat_digraph",
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "PatronClientGraph":
        if not raw:
            return seed_chu_patron_client()
        g = cls(
            hubs=list(raw.get("hubs") or CHU_HUBS),
            clients=list(raw.get("clients") or CHU_CLIENTS),
            edges=dict(raw.get("edges") or {}),
            primary_hub=dict(raw.get("primary_hub") or {}),
            labels=dict(raw.get("labels") or {}),
        )
        if not g.edges:
            return seed_chu_patron_client()
        return g


def seed_chu_patron_client() -> PatronClientGraph:
    """High hub↔client + hub↔hub; weaker lateral peer edges among clients."""
    g = PatronClientGraph()
    # Hub ↔ hub (Kaolie dyadic trust of Chunshen — profiles JSON A.62 vs organizer)
    g.set(HUB_KAOLIE, HUB_CHUNSHEN, 0.82)
    g.set(HUB_CHUNSHEN, HUB_KAOLIE, 0.78)
    # Spoke trusts: each hub strongly tied to its clients
    for client, hub in g.primary_hub.items():
        g.set(hub, client, 0.80)
        g.set(client, hub, 0.76)
        # Secondary hub still warm but lower (aristocratic hospitality, not fa command)
        other_hub = HUB_CHUNSHEN if hub == HUB_KAOLIE else HUB_KAOLIE
        g.set(other_hub, client, 0.58)
        g.set(client, other_hub, 0.52)
    # Lateral client↔client: weaker peer edges (competition for face/stipend)
    for i, a in enumerate(g.clients):
        for b in g.clients[i + 1 :]:
            g.set(a, b, 0.38)
            g.set(b, a, 0.36)
    return g


def spoke_bond(g: PatronClientGraph, hub: str) -> float:
    """Mean mutual trust on spokes of one hub (order-parameter for that clique)."""
    clients = [c for c in g.clients if g.primary_hub.get(c) == hub]
    if not clients:
        clients = list(g.clients)
    vals = []
    for c in clients:
        vals.append(g.get(hub, c))
        vals.append(g.get(c, hub))
    return sum(vals) / len(vals) if vals else 0.0


def lateral_mean(g: PatronClientGraph) -> float:
    vals = []
    for i, a in enumerate(g.clients):
        for b in g.clients[i + 1 :]:
            vals.append(g.get(a, b))
            vals.append(g.get(b, a))
    return sum(vals) / len(vals) if vals else 0.0


def clique_sync(g: PatronClientGraph) -> dict[str, float]:
    """Bonded client-clique sync scores + overall court order parameter."""
    kaolie_spoke = spoke_bond(g, HUB_KAOLIE)
    chunshen_spoke = spoke_bond(g, HUB_CHUNSHEN)
    hub_dyad = 0.5 * (g.get(HUB_KAOLIE, HUB_CHUNSHEN) + g.get(HUB_CHUNSHEN, HUB_KAOLIE))
    lat = lateral_mean(g)
    # Sync high when spokes strong AND lateral not fractured; hub dyad anchors
    order = 0.4 * chunshen_spoke + 0.25 * kaolie_spoke + 0.25 * hub_dyad + 0.1 * lat
    bonded = chunshen_spoke >= 0.68 and hub_dyad >= 0.70 and lat >= 0.30
    return {
        "kaolie_spoke": round(kaolie_spoke, 3),
        "chunshen_spoke": round(chunshen_spoke, 3),
        "hub_dyad": round(hub_dyad, 3),
        "lateral_mean": round(lat, 3),
        "order_parameter": round(order, 3),
        "bonded": 1.0 if bonded else 0.0,
    }


def sync_bonus(g: PatronClientGraph, world: "WorldState | None" = None) -> dict[str, float]:
    """Bonuses applied to Chu state agent / meso when client cliques are bonded.

    Mohist/patron/tianxia ideology on Chu slightly raises sync ceilings.
    """
    sync = clique_sync(g)
    ideo_pull = 0.0
    combo_coh = 0.0
    if world is not None:
        chu = world.agents.get("chu") if getattr(world, "agents", None) else None
        if chu is not None:
            from .ideology import loyalty_sync_bias, rare_combo_bonus
            ideo_pull = loyalty_sync_bias(chu)
            combo = rare_combo_bonus(chu, tick=int(getattr(world, "tick", 0) or 0), sid="chu")
            combo_coh = float(combo.get("sync_cohesion") or 0.0)
    # Soft ideology can tip near-bond courts over the line (tiny order bump)
    order = float(sync["order_parameter"]) + 0.04 * ideo_pull
    bonded = sync["bonded"] >= 1.0 or (order >= 0.66 and ideo_pull >= 0.18)
    if bonded:
        return {
            "cohesion": 4.0 + min(1.5, 2.0 * ideo_pull) + combo_coh,
            "shared_identity": 3.0 + min(1.0, 1.5 * ideo_pull),
            "chu_threat_relief": 0.04 + 0.02 * ideo_pull,
            "contribute_pull": 0.08 + 0.05 * ideo_pull,
            **{**sync, "order_parameter": round(order, 3), "bonded": 1.0},
        }
    if order >= 0.62:
        return {
            "cohesion": 2.0 + min(1.0, 1.5 * ideo_pull) + 0.5 * combo_coh,
            "shared_identity": 1.5 + min(0.8, ideo_pull),
            "chu_threat_relief": 0.02 + 0.01 * ideo_pull,
            "contribute_pull": 0.04 + 0.03 * ideo_pull,
            **{**sync, "order_parameter": round(order, 3)},
        }
    return {
        "cohesion": combo_coh,
        "shared_identity": 0.0,
        "chu_threat_relief": 0.0,
        "contribute_pull": 0.02 * ideo_pull,
        **{**sync, "order_parameter": round(order, 3)},
    }


def tick_patron_graph(world: "WorldState", actions: dict[str, str]) -> dict[str, float]:
    """Update Chu court edges from Chu interstate action; apply sync bonus to Chu/meso."""
    g = world.chu_court
    chu_act = actions.get("chu", world.agents["chu"].intention.current if "chu" in world.agents else "withhold")
    # Hub dyad tracks Chu sticky Contribute (patron network holding) vs Withhold/Defect (face fracture)
    if chu_act == "cooperate":
        g.set(HUB_KAOLIE, HUB_CHUNSHEN, g.get(HUB_KAOLIE, HUB_CHUNSHEN) + 0.03)
        g.set(HUB_CHUNSHEN, HUB_KAOLIE, g.get(HUB_CHUNSHEN, HUB_KAOLIE) + 0.03)
        for c in g.clients:
            hub = g.primary_hub.get(c, HUB_CHUNSHEN)
            g.set(hub, c, g.get(hub, c) + 0.025)
            g.set(c, hub, g.get(c, hub) + 0.02)
            # slight lateral healing when hub provides
            for other in g.clients:
                if other != c:
                    g.set(c, other, g.get(c, other) + 0.01)
    elif chu_act == "withhold":
        # Nobility clients stiffen laterally (status competition); spokes cool
        g.set(HUB_KAOLIE, CLIENT_NOBILITY, g.get(HUB_KAOLIE, CLIENT_NOBILITY) - 0.04)
        g.set(CLIENT_NOBILITY, HUB_KAOLIE, g.get(CLIENT_NOBILITY, HUB_KAOLIE) - 0.05)
        for i, a in enumerate(g.clients):
            for b in g.clients[i + 1 :]:
                g.set(a, b, g.get(a, b) - 0.03)
                g.set(b, a, g.get(b, a) - 0.03)
    else:  # defect
        g.set(HUB_KAOLIE, HUB_CHUNSHEN, g.get(HUB_KAOLIE, HUB_CHUNSHEN) - 0.08)
        g.set(HUB_CHUNSHEN, HUB_KAOLIE, g.get(HUB_CHUNSHEN, HUB_KAOLIE) - 0.1)
        for c in g.clients:
            for hub in g.hubs:
                g.set(hub, c, g.get(hub, c) - 0.06)
                g.set(c, hub, g.get(c, hub) - 0.07)

    bonus = sync_bonus(g, world)
    chu = world.agents.get("chu")
    if chu and bonus["contribute_pull"] > 0:
        chu.state.perceived_threat = max(0.0, chu.state.perceived_threat - bonus["chu_threat_relief"])
        chu.state.status_threat = max(0.0, chu.state.status_threat - 0.5 * bonus["chu_threat_relief"])
        # Soft pull toward Cooperate via sticky if bonded
        if bonus["bonded"] >= 1.0 and chu.intention.current != "defect":
            chu.intention.current = "cooperate"
            chu.intention.sticky_until = max(chu.intention.sticky_until, world.tick + 1)
    if bonus["cohesion"] > 0:
        world.meso.cohesion = min(100.0, world.meso.cohesion + bonus["cohesion"])
        world.meso.shared_identity = min(
            100.0, world.meso.shared_identity + bonus["shared_identity"]
        )
    # Mirror hub strength into interstate chu↔wei / chu↔yan (patron export)
    from .trust import set_trust, get_trust

    spoke = bonus["chunshen_spoke"]
    if "wei" in world.agents:
        set_trust(world.trust, "chu", "wei", max(get_trust(world.trust, "chu", "wei"), 0.45 + 0.35 * spoke))
        set_trust(world.trust, "wei", "chu", max(get_trust(world.trust, "wei", "chu"), 0.42 + 0.32 * spoke))
    if "yan" in world.agents:
        set_trust(world.trust, "chu", "yan", max(get_trust(world.trust, "chu", "yan"), 0.40 + 0.30 * spoke))
    return bonus
