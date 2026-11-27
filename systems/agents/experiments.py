"""Cost- and risk-bounded price-strategy experiments for individual businesses."""
from dataclasses import dataclass, field
import math
from typing import Optional

from systems.agents.learning import (
    learning_context, objective_weights, outcome_reward, outcome_snapshot,
    social_contact_count,
)


EXPERIMENT_DAYS = 7
EXPERIMENT_COOLDOWN_DAYS = 90
EXPERIMENT_HISTORY_CAPACITY = 16
PRICE_VARIATION = 0.05
MIN_DEMAND_UNCERTAINTY = 0.15


@dataclass
class PriceExperiment:
    id: int
    business_id: int
    product: str
    hypothesis: str
    baseline_multiplier: float
    treatment_multiplier: float
    uncertainty: float
    expected_value_of_information: float
    estimated_risk: float
    risk_budget: float
    started_day: int
    variable: str = "shop_price_multiplier"
    method: str = "7-day baseline followed by 7-day treatment"
    baseline_days_required: int = EXPERIMENT_DAYS
    treatment_days_required: int = EXPERIMENT_DAYS
    required_stock: float = 1.0
    phase: str = "baseline"
    baseline_days: int = 0
    treatment_days: int = 0
    baseline_cash_flow: float = 0.0
    treatment_cash_flow: float = 0.0
    baseline_units_sold: float = 0.0
    treatment_units_sold: float = 0.0
    baseline_demand: float = 0.0
    treatment_demand: float = 0.0
    daily_phase: str = ""
    daily_cash_start: float = 0.0
    daily_units_sold: float = 0.0
    daily_demand: float = 0.0
    before_state: dict = field(default_factory=dict)
    reward_weights: dict = field(default_factory=dict)
    learning_context: str = ""
    learning_arm: str = ""


@dataclass
class ExperimentResult:
    id: int
    business_id: int
    product: str
    hypothesis: str
    status: str
    baseline_multiplier: float
    treatment_multiplier: float
    expected_value_of_information: float
    risk_budget: float
    risk_used: float
    baseline_profit_per_day: float
    treatment_profit_per_day: float
    profit_change: float
    sales_change: float
    demand_change: float
    started_day: int
    finished_day: int

    @property
    def knowledge_values(self):
        return {
            "price_multiplier_change": self.treatment_multiplier - 1.0,
            "profit_change": self.profit_change,
            "sales_change": self.sales_change,
            "demand_change": self.demand_change,
            "risk_budget_used": min(
                1.0, self.risk_used / max(self.risk_budget, 1.0)
            ),
            "experiment_adopted": float(self.status == "adopted"),
        }

    @property
    def knowledge_context(self):
        return {"product": self.product, "method": "price_strategy"}


@dataclass
class ExperimentState:
    active: Optional[PriceExperiment] = None
    history: list = field(default_factory=list)
    next_experiment_id: int = 1


def _finite(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} eksperimen harus berupa angka.")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} eksperimen harus berupa angka.") from None
    if not math.isfinite(value):
        raise ValueError(f"{label} eksperimen harus terbatas.")
    return value


def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def _recent_duplicate(state, business_id, product, treatment_change, day):
    return any(
        result.business_id == business_id
        and result.product == product
        and abs(result.treatment_multiplier - 1.0 - treatment_change) < 1e-9
        and day - result.finished_day < EXPERIMENT_COOLDOWN_DAYS
        for result in state.history
    )


def propose_price_experiment(world, citizen):
    """Return a pure proposal only when uncertainty makes a real test worthwhile."""
    state = getattr(citizen, "experiments", None)
    business = citizen.business
    if (citizen not in world.citizens or state is None
            or state.active is not None or business not in world.businesses
            or business.owner is not citizen or business.kind != "shop"
            or len(business.daily_demand) < 7 or len(business.soldout_hist) < 7
            or len(business.over_hist) < 7):
        return None

    demand = [
        _finite(sample, "Permintaan historis")
        for sample in list(business.daily_demand)[-7:]
    ]
    if any(sample < 0 for sample in demand):
        raise ValueError("Permintaan historis eksperimen tidak boleh negatif.")
    mean_demand = sum(demand) / len(demand)
    variance = sum((sample - mean_demand) ** 2 for sample in demand) / len(demand)
    uncertainty = _clamp(math.sqrt(variance) / max(mean_demand, 1.0), 0.0, 1.0)
    if uncertainty < MIN_DEMAND_UNCERTAINTY or mean_demand <= 0:
        return None
    required_stock = max(1.0, mean_demand * 0.5)
    if _finite(business.stock, "Persediaan usaha") < required_stock:
        return None

    price = _finite(business.price, "Harga")
    unit_cost = _finite(business.cost_avg, "Harga pokok")
    cash = _finite(business.cash, "Kas usaha")
    if price <= max(unit_cost, 1_000.0) or cash <= 0:
        return None

    stockouts = sum(bool(value) for value in business.soldout_hist)
    overstock = sum(bool(value) for value in business.over_hist)
    if stockouts > overstock:
        direction = 1.0
        direction_text = "kenaikan harga"
    elif overstock > stockouts:
        direction = -1.0
        direction_text = "penurunan harga"
    else:
        direction = 1.0 if business.stock < mean_demand * 1.5 else -1.0
        direction_text = (
            "kenaikan harga" if direction > 0 else "penurunan harga"
        )

    baseline_multiplier = _finite(
        getattr(business, "innovation_price_multiplier", 1.0),
        "Strategi harga saat ini",
    )
    if not 0.8 <= baseline_multiplier <= 1.2:
        return None
    treatment_multiplier = 1.0 + direction * PRICE_VARIATION
    if not 0.8 <= baseline_multiplier * treatment_multiplier <= 1.2:
        return None
    if price * treatment_multiplier < 1_000.0:
        return None
    if _recent_duplicate(
            state, business.ledger_id, business.market_product,
            direction * PRICE_VARIATION, world.day):
        return None

    gross_week = price * mean_demand * EXPERIMENT_DAYS
    margin = _clamp((price - unit_cost) / price)
    expected_profit = max(
        0.0,
        _finite(business.last_profit, "Laba terakhir"),
        gross_week * margin,
    )
    expected_value = expected_profit * uncertainty * 0.5
    estimated_risk = (
        gross_week * abs(treatment_multiplier - 1.0)
        * max(0.25, uncertainty)
    )
    risk_budget = max(estimated_risk * 1.5, gross_week * 0.002)
    if expected_value <= estimated_risk or cash < risk_budget:
        return None

    hypothesis = (
        f"Strategi {direction_text} 5% meningkatkan hasil bersih "
        f"{business.market_product} tanpa melewati batas risiko."
    )
    return PriceExperiment(
        id=state.next_experiment_id,
        business_id=business.ledger_id,
        product=business.market_product,
        hypothesis=hypothesis,
        baseline_multiplier=baseline_multiplier,
        treatment_multiplier=treatment_multiplier,
        uncertainty=uncertainty,
        expected_value_of_information=expected_value,
        estimated_risk=estimated_risk,
        risk_budget=risk_budget,
        started_day=world.day,
        required_stock=required_stock,
    )


def start_price_experiment(world, citizen, proposal, motivations=None):
    if citizen not in world.citizens:
        raise ValueError("Pemilik eksperimen tidak ditemukan.")
    if not isinstance(proposal, PriceExperiment):
        raise ValueError("Proposal eksperimen harga tidak valid.")
    baseline_multiplier = _finite(
        proposal.baseline_multiplier, "Strategi dasar eksperimen"
    )
    treatment_multiplier = _finite(
        proposal.treatment_multiplier, "Strategi uji eksperimen"
    )
    expected_value = _finite(
        proposal.expected_value_of_information, "Nilai informasi eksperimen"
    )
    estimated_risk = _finite(
        proposal.estimated_risk, "Risiko perkiraan eksperimen"
    )
    risk_budget = _finite(proposal.risk_budget, "Batas risiko eksperimen")
    required_stock = _finite(
        proposal.required_stock, "Persediaan eksperimen"
    )
    uncertainty = _finite(proposal.uncertainty, "Ketidakpastian eksperimen")
    state = getattr(citizen, "experiments", None)
    business = citizen.business
    if (state is None or state.active is not None
            or business not in world.businesses
            or business.owner is not citizen
            or business.ledger_id != proposal.business_id
            or business.kind != "shop"
            or state.next_experiment_id != proposal.id
            or proposal.started_day != world.day
            or proposal.baseline_days_required != EXPERIMENT_DAYS
            or proposal.treatment_days_required != EXPERIMENT_DAYS
            or _recent_duplicate(
                state, business.ledger_id, business.market_product,
                treatment_multiplier - 1.0,
                world.day)):
        return False
    current_multiplier = _finite(
        getattr(business, "innovation_price_multiplier", 1.0),
        "Strategi harga saat ini",
    )
    if (baseline_multiplier <= 0 or treatment_multiplier <= 0
            or not 0.0 <= uncertainty <= 1.0
            or estimated_risk < 0
            or risk_budget < estimated_risk
            or not math.isclose(
                abs(treatment_multiplier - 1.0),
                PRICE_VARIATION,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            or abs(current_multiplier - baseline_multiplier) > 1e-9
            or not 0.8 <= treatment_multiplier <= 1.2
            or not 0.8 <= current_multiplier * treatment_multiplier <= 1.2
            or _finite(business.stock, "Persediaan usaha")
            < required_stock
            or _finite(business.cash, "Kas usaha") < risk_budget
            or expected_value <= estimated_risk
            or risk_budget <= 0):
        return False

    motivations = motivations or {}
    social_need = 1.0 / (1.0 + social_contact_count(citizen))
    state.active = proposal
    proposal.before_state = outcome_snapshot(world, citizen)
    proposal.reward_weights = objective_weights(motivations, social_need)
    proposal.learning_context = learning_context(citizen)
    proposal.learning_arm = (
        f"experiment:price:{proposal.product}:"
        f"{'up' if proposal.treatment_multiplier > 1.0 else 'down'}"
    )
    state.next_experiment_id += 1
    citizen.think(f"Mulai eksperimen: {proposal.hypothesis}")
    world.log(
        "info", "EKSPERIMEN USAHA DIMULAI",
        f"{citizen.first} menguji strategi harga {proposal.product}.",
    )
    return True


def consider_price_experiment(world, citizen, curiosity, motivations=None):
    if _finite(curiosity, "Motivasi belajar") < 0.55:
        return False
    proposal = propose_price_experiment(world, citizen)
    return bool(
        proposal is not None
        and start_price_experiment(world, citizen, proposal, motivations)
    )


def begin_experiment_day(world):
    for citizen in world.citizens:
        state = getattr(citizen, "experiments", None)
        experiment = state.active if state is not None else None
        if experiment is None:
            continue
        business = next(
            (item for item in world.businesses
             if item.ledger_id == experiment.business_id),
            None,
        )
        if business is None:
            continue
        experiment.daily_phase = experiment.phase
        experiment.daily_cash_start = _finite(
            business.cash, "Kas awal harian"
        )
        experiment.daily_units_sold = 0.0
        experiment.daily_demand = 0.0


def capture_experiment_market(world):
    for citizen in world.citizens:
        state = getattr(citizen, "experiments", None)
        experiment = state.active if state is not None else None
        if experiment is None or experiment.daily_phase not in (
                "baseline", "treatment"):
            continue
        business = next(
            (item for item in world.businesses
             if item.ledger_id == experiment.business_id),
            None,
        )
        if business is None:
            continue
        experiment.daily_units_sold = _finite(
            business.sold_today, "Penjualan harian"
        )
        experiment.daily_demand = _finite(
            business.demand_today, "Permintaan harian"
        )


def _store_result(world, citizen, experiment, business, status):
    baseline_days = max(experiment.baseline_days, 1)
    treatment_days = max(experiment.treatment_days, 1)
    baseline_profit = experiment.baseline_cash_flow / baseline_days
    treatment_profit = experiment.treatment_cash_flow / treatment_days
    baseline_sales = experiment.baseline_units_sold / baseline_days
    treatment_sales = experiment.treatment_units_sold / treatment_days
    baseline_demand = experiment.baseline_demand / baseline_days
    treatment_demand = experiment.treatment_demand / treatment_days
    profit_change = _clamp(
        (treatment_profit - baseline_profit)
        / max(abs(baseline_profit), 1.0),
        -1.0,
        1.0,
    )
    sales_change = _clamp(
        (treatment_sales - baseline_sales) / max(baseline_sales, 1.0),
        -1.0,
        1.0,
    )
    demand_change = _clamp(
        (treatment_demand - baseline_demand) / max(baseline_demand, 1.0),
        -1.0,
        1.0,
    )
    risk_used = max(
        0.0,
        baseline_profit * experiment.treatment_days
        - experiment.treatment_cash_flow,
    )
    if status == "completed":
        improvement_threshold = max(1.0, abs(baseline_profit) * 0.02)
        adopted = (
            treatment_profit > baseline_profit + improvement_threshold
            and treatment_sales >= baseline_sales * 0.9
            and risk_used <= experiment.risk_budget
        )
        status = "adopted" if adopted else "rejected"

    if business is not None and status != "adopted":
        effective = business.innovation_price_multiplier
        business.innovation_price_multiplier = experiment.baseline_multiplier
        if effective > 0:
            business.price *= experiment.baseline_multiplier / effective

    result = ExperimentResult(
        id=experiment.id,
        business_id=experiment.business_id,
        product=experiment.product,
        hypothesis=experiment.hypothesis,
        status=status,
        baseline_multiplier=experiment.baseline_multiplier,
        treatment_multiplier=experiment.treatment_multiplier,
        expected_value_of_information=experiment.expected_value_of_information,
        risk_budget=experiment.risk_budget,
        risk_used=risk_used,
        baseline_profit_per_day=baseline_profit,
        treatment_profit_per_day=treatment_profit,
        profit_change=profit_change,
        sales_change=sales_change,
        demand_change=demand_change,
        started_day=experiment.started_day,
        finished_day=world.day,
    )
    state = citizen.experiments
    state.history.append(result)
    if len(state.history) > EXPERIMENT_HISTORY_CAPACITY:
        del state.history[:-EXPERIMENT_HISTORY_CAPACITY]
    citizen.memory.record(
        world.day,
        "experimentation",
        "price_test",
        {"product": result.product, "method": "price_strategy"},
        f"Experiment {result.status}: profit change {profit_change:+.1%}",
        result.status == "adopted" if status != "cancelled" else None,
        impact=min(1.0, abs(profit_change)),
        value=profit_change,
    )
    citizen.knowledge.observe(
        world.day,
        "personal_experience",
        f"experiment:{result.id}:{result.status}",
        result.knowledge_values,
        context=result.knowledge_context,
    )
    after_state = outcome_snapshot(world, citizen)
    reward = outcome_reward(
        experiment.before_state, after_state, experiment.reward_weights
    )
    citizen.adaptive_learning.update(
        experiment.learning_context,
        experiment.learning_arm,
        reward,
        world.day,
    )
    citizen.think(f"Hasil eksperimen harga: {result.status}.")
    world.log(
        "good" if result.status == "adopted" else "info",
        "HASIL EKSPERIMEN USAHA",
        f"{citizen.first}: {result.status}, perubahan hasil {profit_change:+.1%}.",
    )
    state.active = None


def finish_experiment_day(world):
    for citizen in list(world.citizens):
        state = getattr(citizen, "experiments", None)
        experiment = state.active if state is not None else None
        if experiment is None:
            continue
        business = next(
            (item for item in world.businesses
             if item.ledger_id == experiment.business_id),
            None,
        )
        if business is None or business.owner is not citizen:
            _store_result(world, citizen, experiment, None, "cancelled")
            continue
        if experiment.daily_phase not in ("baseline", "treatment"):
            continue
        cash_delta = (
            _finite(business.cash, "Kas akhir harian")
            - experiment.daily_cash_start
        )
        if experiment.daily_phase == "baseline":
            experiment.baseline_cash_flow += cash_delta
            experiment.baseline_units_sold += experiment.daily_units_sold
            experiment.baseline_demand += experiment.daily_demand
            experiment.baseline_days += 1
            if experiment.baseline_days >= experiment.baseline_days_required:
                if (business.cash < experiment.risk_budget
                        or business.stock < experiment.required_stock):
                    _store_result(
                        world, citizen, experiment, business, "aborted"
                    )
                    continue
                experiment.phase = "treatment"
                business.innovation_price_multiplier = (
                    experiment.baseline_multiplier
                    * experiment.treatment_multiplier
                )
                business.price *= experiment.treatment_multiplier
        else:
            experiment.treatment_cash_flow += cash_delta
            experiment.treatment_units_sold += experiment.daily_units_sold
            experiment.treatment_demand += experiment.daily_demand
            experiment.treatment_days += 1
            baseline_average = (
                experiment.baseline_cash_flow
                / max(experiment.baseline_days, 1)
            )
            expected_cash_flow = baseline_average * experiment.treatment_days
            shortfall = expected_cash_flow - experiment.treatment_cash_flow
            if shortfall > experiment.risk_budget:
                _store_result(world, citizen, experiment, business, "aborted")
            elif experiment.treatment_days >= experiment.treatment_days_required:
                _store_result(world, citizen, experiment, business, "completed")


def share_experiment_result(world, sender, receiver, result_id):
    if sender not in world.citizens or receiver not in world.citizens:
        raise ValueError("Pengirim dan penerima harus warga kota.")
    if sender is receiver:
        raise ValueError("Hasil eksperimen harus dibagikan kepada warga lain.")
    result = next(
        (item for item in sender.experiments.history if item.id == result_id),
        None,
    )
    if result is None:
        raise ValueError("Hasil eksperimen tidak ditemukan.")
    receiver.knowledge.observe(
        world.day,
        "social_information",
        f"shared-experiment:{sender.id}:{result.id}",
        result.knowledge_values,
        context=result.knowledge_context,
    )
    receiver.memory.record(
        world.day,
        "experimentation",
        "shared_result",
        {"product": result.product, "method": "price_strategy"},
        f"Received shared experiment result: {result.status}",
        None,
        impact=min(1.0, abs(result.profit_change)),
        value=result.profit_change,
    )
    return result
