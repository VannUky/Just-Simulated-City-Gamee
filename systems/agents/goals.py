"""Dynamic beliefs, motivations, desires, and active intentions for citizens."""
from dataclasses import dataclass, field
import math
from typing import Optional


@dataclass
class Belief:
    key: str
    value: object
    confidence: float
    source: str
    source_refs: tuple = ()
    observed_day: int = 0


@dataclass
class Goal:
    id: str
    conditions: dict = field(default_factory=dict)
    resource_targets: dict = field(default_factory=dict)
    priority: float = 0.0
    expected_benefit: float = 1.0
    horizon: str = "short"
    motivation: str = ""
    created_day: int = 0


@dataclass
class Intention:
    goal_id: str
    action_ids: tuple
    planned_day: int
    next_step: int = 0
    last_action_day: int = -1
    status: str = "active"


@dataclass
class BDIState:
    beliefs: dict = field(default_factory=dict)
    motivations: dict = field(default_factory=dict)
    desires: list = field(default_factory=list)
    intention: Optional[Intention] = None
    last_updated_day: int = -1


def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def update_beliefs(world, citizen, state):
    """Refresh personal beliefs from current facts, memory, and validated claims."""
    liquid = max(0.0, citizen.cash) + max(0.0, citizen.savings)
    reserve = max(3.0 * citizen.est_exp, 5_000_000.0)
    beliefs = {
        "liquid_funds": Belief(
            "liquid_funds", liquid, 1.0, "world_state", observed_day=world.day
        ),
        "has_job": Belief(
            "has_job", citizen.job is not None, 1.0, "world_state",
            observed_day=world.day,
        ),
        "owns_home": Belief(
            "owns_home", bool(citizen.houses), 1.0, "world_state",
            observed_day=world.day,
        ),
        "financial_reserve": Belief(
            "financial_reserve", reserve, 1.0, "personal_estimate",
            observed_day=world.day,
        ),
    }

    memory = getattr(citizen, "memory", None)
    if memory is not None:
        recent_sales = memory.retrieve(
            domain="investment", action="sale", current_day=world.day, limit=1
        )
        if recent_sales:
            sale = recent_sales[0]
            beliefs["recent_investment_outcome"] = Belief(
                "recent_investment_outcome",
                sale.mean_value,
                min(1.0, sale.source_count / 3.0),
                "personal_memory",
                tuple(str(item) for item in sale.source_ids),
                sale.last_day,
            )

    knowledge = getattr(citizen, "knowledge", None)
    if knowledge is not None:
        claims = knowledge.query(
            status="validated", current_day=world.day, limit=16
        )
        for claim in claims:
            key = f"knowledge:{claim.id}"
            beliefs[key] = Belief(
                key,
                {
                    "concept_a": claim.concept_a,
                    "relation": claim.relation,
                    "concept_b": claim.concept_b,
                },
                claim.confidence,
                "knowledge_graph",
                tuple(claim.evidence_refs),
                claim.last_day,
            )

    financial_pressure = _clamp((reserve - liquid) / reserve)
    home_pressure = 1.0 if citizen.home is None else (
        0.55 if citizen.home.owner is not citizen else 0.0
    )
    learning_drive = _clamp(0.35 + (1.0 - citizen.financial_literacy) * 0.65)
    recent_outcome = beliefs.get("recent_investment_outcome")
    if recent_outcome and recent_outcome.value < 0:
        financial_pressure = _clamp(
            financial_pressure + abs(recent_outcome.value) * 0.2
        )
    risk_pressure = (
        _clamp(abs(recent_outcome.value))
        if recent_outcome and recent_outcome.value < 0 else 0.0
    )
    state.beliefs = beliefs
    state.motivations = {
        "survival": _clamp(citizen.hunger / 3.0),
        "financial_security": financial_pressure,
        "housing_safety": home_pressure,
        "autonomy": _clamp(citizen.entre),
        "learning": learning_drive,
        "skill_development": _clamp(1.0 - citizen.skill),
        "wealth_growth": _clamp((liquid - reserve) / (3.0 * reserve)),
        "risk_reduction": risk_pressure,
    }
    state.last_updated_day = world.day
    return beliefs


def form_goals(world, citizen, state):
    """Create desires from current needs and evidence-backed risk signals."""
    liquid = max(0.0, citizen.cash) + max(0.0, citizen.savings)
    reserve = max(3.0 * citizen.est_exp, 5_000_000.0)
    goals = []

    if citizen.job is None and citizen.business is None and citizen.age < 60:
        priority = (
            0.48
            + 0.24 * state.motivations.get("financial_security", 0.0)
            + min(0.2, max(0, citizen.unemp_days) / 900.0)
        )
        goals.append(Goal(
            "find_employment",
            conditions={"has_job": True},
            priority=_clamp(priority),
            expected_benefit=1.0 + state.motivations.get("financial_security", 0.0),
            horizon="short",
            motivation="financial_security",
            created_day=world.day,
        ))

    if liquid < reserve and citizen.hold:
        deficit = reserve - liquid
        goals.append(Goal(
            "restore_financial_reserve",
            resource_targets={"money": deficit},
            priority=_clamp(
                0.45 + 0.4 * state.motivations.get("financial_security", 0.0)
            ),
            expected_benefit=1.0 + deficit / reserve,
            horizon="medium",
            motivation="financial_security",
            created_day=world.day,
        ))

    owns_home = any(house.owner is citizen for house in citizen.houses)
    if not owns_home and citizen.age < 60:
        priority = (
            0.28
            + 0.38 * state.motivations.get("housing_safety", 0.0)
            + 0.14 * state.motivations.get("financial_security", 0.0)
        )
        goals.append(Goal(
            "own_a_home",
            conditions={"owns_home": True},
            priority=_clamp(priority),
            expected_benefit=1.0 + state.motivations.get("housing_safety", 0.0),
            horizon="long",
            motivation="housing_safety",
            created_day=world.day,
        ))

    for symbol, position in citizen.hold.items():
        asset = world.market.assets.get(symbol)
        if asset is None or asset.halted:
            continue
        try:
            units = float(position[0])
            momentum = max(
                -1.0, min(1.0, asset.momentum() * 4 + asset.change(10) * 2)
            )
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        if not math.isfinite(units) or units <= 0:
            continue
        adjustment = citizen.knowledge.prediction_adjustment(
            "market_momentum",
            "realized_return",
            momentum,
            context={"asset": symbol},
            current_day=world.day,
        )
        if adjustment < -0.003:
            goals.append(Goal(
                f"reduce_exposure:{symbol}",
                conditions={f"has_asset:{symbol}": False},
                priority=_clamp(0.42 + abs(adjustment) * 20.0),
                expected_benefit=1.0 + abs(adjustment) * 10.0,
                horizon="short",
                motivation="financial_security",
                created_day=world.day,
            ))

    state.desires = sorted(
        goals, key=lambda goal: (-goal.priority, goal.id)
    )
    return state.desires
