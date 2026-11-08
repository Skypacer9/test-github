"""WorldState — single JSON-serializable owner of sim memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .agents import Agent, default_agents
from .demographics import DemographicsBoard, seed_demographics
from .packets import shared_identity
from .patron_client import PatronClientGraph, seed_chu_patron_client
from .tech import TechBoard, seed_tech_board
from .trust import default_trust_matrix, mean_bloc_trust


@dataclass
class MesoField:
    cohesion: float = 62.0
    shared_identity: float = 55.0
    cascade_armed: int = 0
    quorum_ok: bool = True
    pathway_soft: str = "other"  # qin_path | stalemate | chu_fiction | other (soft label only)


@dataclass
class WorldMods:
    """Coarse M1–M4 + M2 military mirrors + global dials."""

    levy_capacity: float = 0.6
    famine_shock: float = 0.0
    siege_mod: float = 0.1
    defense_mod: float = 0.5
    march_cost: float = 0.5
    extraction_mod: float = 0.5
    qin_projection: float = 0.4
    thermo_dial: float = 0.5  # stress sensitivity
    evo_dial: float = 0.4  # strategy copy speed
    # M2 live mirrors (from tech.tick_tech)
    military_qin: float = 0.0
    military_coalition: float = 0.0
    qin_mil_advantage: float = 0.0
    adoption_meter: float = 0.0


@dataclass
class DecisionRecord:
    tick: int
    event_id: str
    actor: str
    action: str
    dials_fired: list[str]
    text: str
    anchor: str = ""
    unknown: bool = False
    state_snapshot: dict[str, float] = field(default_factory=dict)


FEATURED_FACTIONS = ("qin", "chu", "qi")


def _coerce_flag(val: object, default: bool = False) -> bool:
    """Bool coerce that treats string 'false'/'0' as False."""
    if val is None:
        return default
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(val)


def _agent_meters(ag: Agent) -> dict[str, float]:
    return {
        "resentment": float(ag.state.resentment),
        "fear_of_qin": float(ag.state.fear_of_qin),
        "betrayal_memory": float(ag.state.betrayal_memory),
        "status_threat": float(ag.state.status_threat),
        "perceived_threat": float(ag.state.perceived_threat),
    }


@dataclass
class WorldState:
    tick: int = 0
    year: int = -260
    quarter_in_year: int = 1
    qin_pressure: float = 20.0  # early-game pacing: start ~20 (was 38)
    agents: dict[str, Agent] = field(default_factory=dict)
    trust: dict[str, float] = field(default_factory=dict)
    meso: MesoField = field(default_factory=MesoField)
    world: WorldMods = field(default_factory=WorldMods)
    episode: list[dict[str, Any]] = field(default_factory=list)
    pending_trigger: str | None = None
    last_actions: dict[str, str] = field(default_factory=dict)
    # Player soft-lock action consequence lines (Fund Military / Send Grain / Broker Mediation)
    player_log: list[str] = field(default_factory=list)
    # Player purse — invest actions spend these (not a court agent)
    player_political_capital: float = 100.0
    player_treasury: float = 100.0
    # Joint alliance fund — pooled on quorum success; spend on tech/agri/build/mil
    alliance_fund_grain: float = 0.0
    alliance_fund_treasury: float = 0.0
    alliance_fund_log: list[str] = field(default_factory=list)
    # Last invest attempt error (None on success) — for Flask/CLI without parsing logs
    last_player_action_error: str | None = None
    last_player_offensive_error: str | None = None
    last_alliance_fund_error: str | None = None
    last_alliance_attempt_error: str | None = None
    last_intervene_error: str | None = None
    # Demo play-feel: 1 invest + 1 Attempt Alliance + 1 Intervene;
    # player offensives soft-cap 3/quarter; per-court fronts tracked separately
    # alliance fund: each purpose (tech/agri/build/mil) once per tick
    player_invest_actions_left: int = 1
    alliance_attempt_actions_left: int = 1
    intervene_actions_left: int = 1
    player_offensive_actions_left: int = 3  # soft player-initiated cap ~2–3/quarter
    player_offensive_fronts: dict[str, int] = field(default_factory=dict)  # attacker→fronts this quarter
    last_player_offensive: dict[str, Any] | None = None
    alliance_fund_spent_purposes: list[str] = field(default_factory=list)
    # Run-start baselines + append-only per-event faction deltas (Field dashboard)
    faction_baseline: dict[str, dict[str, float]] = field(default_factory=dict)
    meso_baseline: dict[str, float] = field(default_factory=dict)
    faction_delta_log: list[dict[str, Any]] = field(default_factory=list)
    # Chu aristocratic hub–spoke court (Kaolie/Chunshen hubs, nobility clients)
    chu_court: PatronClientGraph = field(default_factory=seed_chu_patron_client)
    # M2 tech DAG + Adoption Meter (military / levy / siege)
    tech: TechBoard = field(default_factory=seed_tech_board)
    # PLACEHOLDER demographics / satisfaction / manpower (uncalibrated stubs)
    demographics: DemographicsBoard = field(default_factory=seed_demographics)
    # Soft-lock is mechanism-only (no calendar). demo_horizon kept for serialize compat.
    demo_mode: str = "full"  # full | short (short = UI flavor only)
    demo_horizon: int = 0  # unused for locking
    soft_lock_enabled: bool = True  # evaluates natural conditions only
    run_ended: bool = False
    opening_seen: bool = False
    pathway_stable_count: int = 0
    last_pathway: str = "other"
    dead_edges: list[str] = field(default_factory=list)
    end_screen: dict[str, Any] | None = None
    # Figure counsel (tips dials only). No player OCEAN / decision dossier.
    counsel_auto: bool = True
    counsel_mode: str = "stub"
    counsel_log: list[str] = field(default_factory=list)
    counsel_actions_left: int = 6  # Speak→Decide episodes / quarter (soft cap)
    counsel_session: dict[str, Any] = field(default_factory=dict)  # ephemeral open talk only
    figure_beliefs: dict[str, dict[str, float]] = field(default_factory=dict)
    figure_breakthrough_at: dict[str, int] = field(default_factory=dict)
    # Figure memories (historical priors + in-run events). No player dossier.
    figure_memories: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    figure_memory_pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    figure_memory_comment_at: dict[str, int] = field(default_factory=dict)
    pattern_reactions: list[str] = field(default_factory=list)  # thin WS-54 pattern notes
    last_counsel_tips: dict[str, Any] | None = None
    last_breakthrough: dict[str, Any] | None = None
    # Cultural chronicle (English flavor gloss — not inevitability)
    chronicle_log: list[str] = field(default_factory=list)
    chronicle_mode: str = "stub"
    last_chronicle_pathway: str | None = None

    def ensure_baselines(self) -> None:
        if not self.faction_baseline:
            self.faction_baseline = {
                aid: _agent_meters(ag)
                for aid, ag in self.agents.items()
                if aid in FEATURED_FACTIONS
            }
        if not self.meso_baseline:
            self.meso_baseline = {
                "qin_pressure": float(self.qin_pressure),
                "cohesion": float(self.meso.cohesion),
                "shared_identity": float(self.meso.shared_identity),
                "cascade_armed": float(self.meso.cascade_armed),
            }

    def run_deltas(self) -> dict[str, Any]:
        """Cumulative deltas vs run start for featured factions + meso."""
        self.ensure_baselines()
        factions: dict[str, dict[str, float]] = {}
        for aid in FEATURED_FACTIONS:
            ag = self.agents.get(aid)
            if not ag:
                continue
            cur = _agent_meters(ag)
            base = self.faction_baseline.get(aid) or cur
            factions[aid] = {k: round(cur[k] - float(base.get(k, cur[k])), 3) for k in cur}
        meso_now = {
            "qin_pressure": float(self.qin_pressure),
            "cohesion": float(self.meso.cohesion),
            "shared_identity": float(self.meso.shared_identity),
            "cascade_armed": float(self.meso.cascade_armed),
        }
        meso_d = {
            k: round(meso_now[k] - float(self.meso_baseline.get(k, meso_now[k])), 3)
            for k in meso_now
        }
        return {"factions": factions, "meso": meso_d, "intentions": {
            aid: self.agents[aid].intention.current
            for aid in FEATURED_FACTIONS
            if aid in self.agents
        }}

    def record_faction_deltas(
        self,
        *,
        event_id: str,
        actor: str,
        action: str,
        per_faction: dict[str, dict[str, float]],
        note: str = "",
    ) -> None:
        self.faction_delta_log.append(
            {
                "tick": self.tick,
                "event_id": event_id,
                "actor": actor,
                "action": action,
                "note": note,
                "per_faction": per_faction,
                "run_deltas": self.run_deltas(),
            }
        )

    def clamp(self) -> None:
        self.qin_pressure = max(0.0, min(100.0, float(self.qin_pressure)))
        self.meso.cohesion = max(0.0, min(100.0, float(self.meso.cohesion)))
        self.meso.shared_identity = max(0.0, min(100.0, float(self.meso.shared_identity)))
        self.player_political_capital = max(0.0, min(100.0, float(getattr(self, "player_political_capital", 100.0))))
        self.player_treasury = max(0.0, min(100.0, float(getattr(self, "player_treasury", 100.0))))
        self.alliance_fund_grain = max(0.0, float(getattr(self, "alliance_fund_grain", 0.0)))
        self.alliance_fund_treasury = max(0.0, float(getattr(self, "alliance_fund_treasury", 0.0)))
        self.player_invest_actions_left = max(
            0, min(1, int(getattr(self, "player_invest_actions_left", 1)))
        )
        self.alliance_attempt_actions_left = max(
            0, min(1, int(getattr(self, "alliance_attempt_actions_left", 1)))
        )
        self.intervene_actions_left = max(
            0, min(1, int(getattr(self, "intervene_actions_left", 1)))
        )
        self.player_offensive_actions_left = max(
            0, min(3, int(getattr(self, "player_offensive_actions_left", 3)))
        )
        fronts = getattr(self, "player_offensive_fronts", None) or {}
        if not isinstance(fronts, dict):
            fronts = {}
        self.player_offensive_fronts = {
            str(k): max(0, int(v)) for k, v in fronts.items()
        }
        spent = getattr(self, "alliance_fund_spent_purposes", None) or []
        if not isinstance(spent, list):
            spent = list(spent)
        # normalize + dedupe
        clean: list[str] = []
        for p in spent:
            s = str(p).strip().lower()
            if s and s not in clean:
                clean.append(s)
        self.alliance_fund_spent_purposes = clean
        for ag in self.agents.values():
            ag.clamp()

    def recompute_meso(self) -> None:
        self.meso.cohesion = mean_bloc_trust(self)
        self.meso.shared_identity = shared_identity(self)
        # Cascade arming as threshold process with exit hysteresis (margin 0.06).
        # Evidence: Granovetter / threshold cascade literature — latch until clear drop.
        CASCADE_EXIT_MARGIN = 0.06
        armed = 0
        for ag in self.agents.values():
            if ag.bloc != "anti_qin" or getattr(ag, "annexed", False):
                continue
            thr = float(ag.state.withholding_threshold)
            threat = float(ag.state.perceived_threat)
            if threat >= thr:
                ag.state.cascade_latched = True
                armed += 1
            elif ag.state.cascade_latched and threat >= thr - CASCADE_EXIT_MARGIN:
                armed += 1  # still armed until clear disarm
            else:
                ag.state.cascade_latched = False
        self.meso.cascade_armed = armed
        # Quorum: enough cooperate among living anti-Qin
        anti = [a for a in self.agents.values() if a.bloc == "anti_qin" and not getattr(a, "annexed", False)]
        coop = sum(1 for a in anti if a.intention.current == "cooperate")
        self.meso.quorum_ok = coop >= max(3, (len(anti) + 1) // 2) if anti else False
        self.player_political_capital = max(0.0, min(100.0, float(self.player_political_capital)))
        self.player_treasury = max(0.0, min(100.0, float(self.player_treasury)))
        self.clamp()

    def append_log(
        self,
        text: str,
        *,
        event_id: str = "tick",
        actor: str = "world",
        action: str = "note",
        dials_fired: list[str] | None = None,
        anchor: str = "",
        unknown: bool = False,
    ) -> dict[str, Any]:
        rec = {
            "tick": self.tick,
            "event_id": event_id,
            "actor": actor,
            "action": action,
            "dials_fired": dials_fired or [],
            "text": text,
            "anchor": anchor,
            "unknown": unknown,
            "state_snapshot": {
                "qin_pressure": self.qin_pressure,
                "cohesion": self.meso.cohesion,
                "shared_identity": self.meso.shared_identity,
            },
        }
        self.episode.append(rec)
        return rec

    def to_dict(self) -> dict[str, Any]:
        self.clamp()
        self.ensure_baselines()
        return {
            "tick": self.tick,
            "year": self.year,
            "quarter_in_year": self.quarter_in_year,
            "qin_pressure": self.qin_pressure,
            "agents": {k: asdict(v) for k, v in self.agents.items()},
            "trust": dict(self.trust),
            "meso": asdict(self.meso),
            "world": asdict(self.world),
            "episode": list(self.episode),
            "pending_trigger": self.pending_trigger,
            "last_actions": dict(self.last_actions),
            "player_log": list(self.player_log),
            "player_political_capital": float(self.player_political_capital),
            "player_treasury": float(self.player_treasury),
            "alliance_fund_grain": float(self.alliance_fund_grain),
            "alliance_fund_treasury": float(self.alliance_fund_treasury),
            "alliance_fund_log": list(self.alliance_fund_log),
            "player_invest_actions_left": int(self.player_invest_actions_left),
            "alliance_attempt_actions_left": int(self.alliance_attempt_actions_left),
            "intervene_actions_left": int(self.intervene_actions_left),
            "player_offensive_actions_left": int(self.player_offensive_actions_left),
            "player_offensive_fronts": {
                str(k): int(v) for k, v in (self.player_offensive_fronts or {}).items()
            },
            "last_player_offensive": (
                dict(self.last_player_offensive)
                if isinstance(self.last_player_offensive, dict)
                else None
            ),
            "alliance_fund_spent_purposes": list(self.alliance_fund_spent_purposes),
            "faction_baseline": dict(self.faction_baseline),
            "meso_baseline": dict(self.meso_baseline),
            "faction_delta_log": list(self.faction_delta_log),
            "chu_court": self.chu_court.to_dict(),
            "tech": self.tech.to_dict(),
            "demographics": self.demographics.to_dict(),
            "demo_mode": self.demo_mode,
            "demo_horizon": self.demo_horizon,
            "run_ended": self.run_ended,
            "opening_seen": self.opening_seen,
            "pathway_stable_count": self.pathway_stable_count,
            "last_pathway": self.last_pathway,
            "dead_edges": list(self.dead_edges),
            "end_screen": self.end_screen,
            "counsel_auto": bool(self.counsel_auto),
            "counsel_mode": str(self.counsel_mode or "stub"),
            "counsel_log": list(self.counsel_log or []),
            "counsel_actions_left": int(self.counsel_actions_left),
            # Persist open-session exchange count only — never player choice dossier
            "counsel_session": {
                "open": bool((self.counsel_session or {}).get("open")),
                "exchanges": int((self.counsel_session or {}).get("exchanges") or 0),
                "cap": int((self.counsel_session or {}).get("cap") or 5),
                # pressure text intentionally omitted from durable save
            },
            "figure_beliefs": {k: dict(v) for k, v in (self.figure_beliefs or {}).items()},
            "figure_breakthrough_at": {k: int(v) for k, v in (self.figure_breakthrough_at or {}).items()},
            "figure_memories": {
                str(k): [dict(x) for x in (v or [])]
                for k, v in (self.figure_memories or {}).items()
            },
            "figure_memory_pending": {str(k): dict(v) for k, v in (self.figure_memory_pending or {}).items()},
            "figure_memory_comment_at": {str(k): int(v) for k, v in (self.figure_memory_comment_at or {}).items()},
            "pattern_reactions": list(self.pattern_reactions or [])[-8:],
            "last_counsel_tips": self.last_counsel_tips,
            "last_breakthrough": self.last_breakthrough,
            "chronicle_log": list(self.chronicle_log or []),
            "chronicle_mode": str(self.chronicle_mode or "stub"),
            "last_chronicle_pathway": self.last_chronicle_pathway,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "WorldState":
        if not raw:
            return new_world()
        from .agents import AffectiveState, Intention, Traits

        agents: dict[str, Agent] = {}
        for aid, payload in (raw.get("agents") or {}).items():
            traits = Traits(**{k: v for k, v in (payload.get("traits") or {}).items() if k in Traits.__dataclass_fields__})
            state = AffectiveState(
                **{k: v for k, v in (payload.get("state") or {}).items() if k in AffectiveState.__dataclass_fields__}
            )
            intention_raw = payload.get("intention") or {}
            intention = Intention(
                current=intention_raw.get("current", "cooperate"),
                sticky_until=int(intention_raw.get("sticky_until", 0)),
                hysteresis_mu=float(intention_raw.get("hysteresis_mu", 0.08)),
            )
            agents[aid] = Agent(
                id=payload.get("id", aid),
                name=payload.get("name", aid.title()),
                bloc=payload.get("bloc", "anti_qin"),
                traits=traits,
                state=state,
                intention=intention,
                active_packets=list(payload.get("active_packets") or []),
                packet_weights=dict(payload.get("packet_weights") or {}),
                profile_ids=list(payload.get("profile_ids") or []),
                profile_confidence=str(payload.get("profile_confidence") or "scaffold"),
                viability=float(payload.get("viability", 100.0)),
                grain=float(payload.get("grain", 60.0)),
                treasury=float(payload.get("treasury", 60.0)),
                geographic_yield=float(payload.get("geographic_yield", 0.6)),
                annexed=_coerce_flag(payload.get("annexed", False)),
                annexed_by=payload.get("annexed_by"),
                stance_mode=str(payload.get("stance_mode") or "coalition"),
                desperate=_coerce_flag(payload.get("desperate", False)),
            )

        meso_raw = raw.get("meso") or {}
        world_raw = raw.get("world") or {}
        ws = cls(
            tick=int(raw.get("tick", 0)),
            year=int(raw.get("year", -260)),
            quarter_in_year=int(raw.get("quarter_in_year", 1)),
            qin_pressure=float(raw.get("qin_pressure", 20.0)),
            agents=agents or default_agents(),
            trust=dict(raw.get("trust") or {}),
            meso=MesoField(**{k: v for k, v in meso_raw.items() if k in MesoField.__dataclass_fields__}),
            world=WorldMods(**{k: v for k, v in world_raw.items() if k in WorldMods.__dataclass_fields__}),
            episode=list(raw.get("episode") or []),
            pending_trigger=raw.get("pending_trigger"),
            last_actions=dict(raw.get("last_actions") or {}),
            player_log=list(raw.get("player_log") or []),
            player_political_capital=float(raw.get("player_political_capital", 100.0)),
            player_treasury=float(raw.get("player_treasury", 100.0)),
            alliance_fund_grain=float(raw.get("alliance_fund_grain", 0.0)),
            alliance_fund_treasury=float(raw.get("alliance_fund_treasury", 0.0)),
            alliance_fund_log=list(raw.get("alliance_fund_log") or []),
            player_invest_actions_left=int(
                raw["player_invest_actions_left"]
                if raw.get("player_invest_actions_left") is not None
                else 1
            ),
            alliance_attempt_actions_left=int(
                raw["alliance_attempt_actions_left"]
                if raw.get("alliance_attempt_actions_left") is not None
                else 1
            ),
            intervene_actions_left=int(
                raw["intervene_actions_left"]
                if raw.get("intervene_actions_left") is not None
                else 1
            ),
            player_offensive_actions_left=int(
                raw["player_offensive_actions_left"]
                if raw.get("player_offensive_actions_left") is not None
                else 3
            ),
            player_offensive_fronts={
                str(k): int(v)
                for k, v in (raw.get("player_offensive_fronts") or {}).items()
            },
            last_player_offensive=(
                dict(raw["last_player_offensive"])
                if isinstance(raw.get("last_player_offensive"), dict)
                else None
            ),
            alliance_fund_spent_purposes=list(raw.get("alliance_fund_spent_purposes") or []),
            faction_baseline=dict(raw.get("faction_baseline") or {}),
            meso_baseline=dict(raw.get("meso_baseline") or {}),
            faction_delta_log=list(raw.get("faction_delta_log") or []),
            chu_court=PatronClientGraph.from_dict(raw.get("chu_court")),
            tech=TechBoard.from_dict(raw.get("tech")),
            demographics=DemographicsBoard.from_dict(raw.get("demographics")),
            demo_mode=str(raw.get("demo_mode") or "full"),
            demo_horizon=int(raw["demo_horizon"]) if raw.get("demo_horizon") is not None else 0,
            soft_lock_enabled=True,
            run_ended=bool(raw.get("run_ended") or False),
            opening_seen=bool(raw.get("opening_seen") or False),
            pathway_stable_count=int(raw.get("pathway_stable_count") or 0),
            last_pathway=str(raw.get("last_pathway") or "other"),
            dead_edges=list(raw.get("dead_edges") or []),
            end_screen=raw.get("end_screen"),
            counsel_auto=_coerce_flag(raw.get("counsel_auto", True), True),
            counsel_mode=str(raw.get("counsel_mode") or "stub"),
            counsel_log=list(raw.get("counsel_log") or []),
            counsel_actions_left=int(
                raw["counsel_actions_left"] if raw.get("counsel_actions_left") is not None else 6
            ),
            counsel_session=dict(raw.get("counsel_session") or {}),
            figure_beliefs={
                str(k): {str(kk): float(vv) for kk, vv in (v or {}).items()}
                for k, v in (raw.get("figure_beliefs") or {}).items()
            },
            figure_breakthrough_at={
                str(k): int(v) for k, v in (raw.get("figure_breakthrough_at") or {}).items()
            },
            figure_memories={
                str(k): [dict(x) for x in (v or []) if isinstance(x, dict)]
                for k, v in (raw.get("figure_memories") or {}).items()
            },
            figure_memory_pending={
                str(k): dict(v) for k, v in (raw.get("figure_memory_pending") or {}).items()
                if isinstance(v, dict)
            },
            figure_memory_comment_at={
                str(k): int(v) for k, v in (raw.get("figure_memory_comment_at") or {}).items()
            },
            pattern_reactions=list(raw.get("pattern_reactions") or [])[-8:],
            last_counsel_tips=raw.get("last_counsel_tips"),
            last_breakthrough=raw.get("last_breakthrough"),
            chronicle_log=list(raw.get("chronicle_log") or []),
            chronicle_mode=str(raw.get("chronicle_mode") or "stub"),
            last_chronicle_pathway=raw.get("last_chronicle_pathway"),
        )
        if not ws.trust:
            ws.trust = default_trust_matrix(list(ws.agents.keys()))
        from .packets import starting_packets, starting_weights
        from .tech_hooks import recompute_tech, tick_tech

        for aid, ag in ws.agents.items():
            if not ag.packet_weights:
                ag.packet_weights = starting_weights(aid)
            if not ag.active_packets:
                ag.active_packets = starting_packets(aid)
        recompute_tech(ws.tech, levy_capacity=float(ws.world.levy_capacity))
        tick_tech(ws)  # mirror military scalars onto WorldMods (Tech worker)
        ws.recompute_meso()
        ws.ensure_baselines()
        return ws


def new_world() -> WorldState:
    """Fresh run; seed figure historical memory priors (no player dossier)."""
    from .demo_flow import ensure_demo_fields
    from .demographics import apply_placeholder_hooks, tick_demographics
    from .geo import apply_m4_to_world
    from .tech_hooks import tick_tech

    agents = default_agents()
    ws = WorldState(
        agents=agents,
        trust=default_trust_matrix(list(agents.keys())),
        tech=seed_tech_board(),
        demographics=seed_demographics(),
    )
    apply_m4_to_world(ws)
    tick_tech(ws)  # Tech worker owns tech.py; hooks soft-fail
    tick_demographics(ws)
    apply_placeholder_hooks(ws)  # tiny soft hooks — placeholder only
    ws.recompute_meso()
    ws.ensure_baselines()
    ensure_demo_fields(ws)
    return ws
