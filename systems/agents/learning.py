"""Bounded per-citizen contextual bandit learning from simulated outcomes."""
from dataclasses import dataclass, field
import math
from typing import Optional


CONTEXT_CAPACITY = 48
ARM_CAPACITY = 32
LEARNING_STRENGTH = 0.4
EXPLORATION_STRENGTH = 0.25


@dataclass
class ArmStats:
    count: int = 0
    mean_reward: float = 0.0
    last_reward: float = 0.0
    last_updated_day: int = 0


@dataclass
class PendingOutcome:
    context: str
    arm: str
    before: dict
    weights: dict
    decision_day: int


@dataclass
class LearningState:
    contexts: dict = field(default_factory=dict)
    pending: Optional[PendingOutcome] = None
    last_updated_day: int = -1
    last_decision_day: int = -1

    @staticmethod
    def _key(value, label, maximum=120):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} pembelajaran tidak valid.")
        return value.strip()

    @staticmethod
    def _day(day):
        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ValueError("Hari pembelajaran harus bilangan bulat nonnegatif.")

    @staticmethod
    def _reward(reward):
        try:
            reward = float(reward)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Reward pembelajaran harus berupa angka.") from None
        if not math.isfinite(reward) or not -1.0 <= reward <= 1.0:
            raise ValueError("Reward pembelajaran harus terbatas dalam rentang -1..1.")
        return reward

    def _context(self, context, create=False):
        context = self._key(context, "Konteks", 180)
        if context in self.contexts:
            return self.contexts[context]
        if not create:
            return {}
        if len(self.contexts) >= CONTEXT_CAPACITY:
            oldest = min(
                self.contexts,
                key=lambda key: (
                    max(
                        (stats.last_updated_day
                         for stats in self.contexts[key].values()),
                        default=-1,
                    ),
                    sum(stats.count for stats in self.contexts[key].values()),
                ),
            )
            del self.contexts[oldest]
        self.contexts[context] = {}
        return self.contexts[context]

    def update(self, context, arm, reward, day):
        context = self._key(context, "Konteks", 180)
        arm = self._key(arm, "Aksi", 120)
        reward = self._reward(reward)
        self._day(day)
        arms = self._context(context, create=True)
        stats = arms.get(arm)
        if stats is None:
            if len(arms) >= ARM_CAPACITY:
                oldest = min(
                    arms,
                    key=lambda key: (
                        arms[key].last_updated_day, arms[key].count
                    ),
                )
                del arms[oldest]
            stats = ArmStats()
            arms[arm] = stats
        stats.count += 1
        stats.mean_reward += (reward - stats.mean_reward) / stats.count
        stats.last_reward = reward
        stats.last_updated_day = day
        self.last_updated_day = day
        return stats

    def mean_reward(self, context, arm):
        arm = self._key(arm, "Aksi", 120)
        arm_stats = self._context(context).get(arm)
        return arm_stats.mean_reward if arm_stats is not None else 0.0

    def estimate(self, context, arm):
        context = self._key(context, "Konteks", 180)
        arm = self._key(arm, "Aksi", 120)
        arms = self._context(context)
        total = sum(stats.count for stats in arms.values())
        stats = arms.get(arm)
        count = stats.count if stats is not None else 0
        mean = stats.mean_reward if stats is not None else 0.0
        bonus = EXPLORATION_STRENGTH * math.sqrt(
            math.log(total + 2.0) / (count + 1.0)
        )
        return max(-1.0, min(1.0, mean + bonus))

    def score(self, context, arm, base_score):
        try:
            base_score = float(base_score)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Skor dasar strategi harus berupa angka.") from None
        if not math.isfinite(base_score):
            raise ValueError("Skor dasar strategi harus terbatas.")
        return base_score + LEARNING_STRENGTH * self.estimate(context, arm)

    def remember(self, context, arm, before, weights, day):
        context = self._key(context, "Konteks", 180)
        arm = self._key(arm, "Aksi", 120)
        self._day(day)
        if not isinstance(before, dict) or not isinstance(weights, dict):
            raise ValueError("Snapshot dan bobot hasil harus berupa dictionary.")
        self.pending = PendingOutcome(
            context, arm, dict(before), dict(weights), day
        )


def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))


def _finite(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} harus berupa angka terbatas.") from None
    if not math.isfinite(value):
        raise ValueError(f"{label} harus berupa angka terbatas.")
    return value


def learning_context(citizen):
    reserve = max(3.0 * _finite(citizen.est_exp, "Cadangan dana"), 5_000_000.0)
    liquid = max(0.0, _finite(citizen.cash, "Kas warga"))
    liquid += max(0.0, _finite(citizen.savings, "Tabungan warga"))
    liquidity_ratio = liquid / reserve
    liquidity = (
        "short" if liquidity_ratio < 0.5
        else "buffered" if liquidity_ratio < 2.0
        else "strong"
    )
    employment = (
        "business" if citizen.business is not None
        else "employed" if citizen.job is not None
        else "unemployed"
    )
    housing = (
        "owned" if any(house.owner is citizen for house in citizen.houses)
        else "unhoused" if citizen.home is None else "renting"
    )
    risk_profile = _finite(citizen.risk, "Profil risiko")
    risk = (
        "cautious" if risk_profile < 0.35
        else "balanced" if risk_profile < 0.7
        else "risk_tolerant"
    )
    need = "urgent" if citizen.hunger >= 2 else "stable"
    return (
        f"work={employment}|home={housing}|liquidity={liquidity}"
        f"|risk={risk}|need={need}"
    )


def social_contact_count(citizen):
    contacts = set()

    def add_members(members):
        for member in members:
            if member is not citizen:
                contacts.add(member.id)

    if citizen.home is not None:
        add_members(citizen.home.occupants)
    if citizen.job is not None:
        add_members(getattr(citizen.job, "workers", ()))
        owner = getattr(citizen.job, "owner", None)
        if owner is not None and owner is not citizen:
            contacts.add(owner.id)
    if citizen.business is not None:
        add_members(citizen.business.workers)
        owner = citizen.business.owner
        if owner is not None and owner is not citizen:
            contacts.add(owner.id)
    return len(contacts)


def outcome_snapshot(world, citizen):
    reserve = max(3.0 * _finite(citizen.est_exp, "Cadangan dana"), 5_000_000.0)
    liquid = max(0.0, _finite(citizen.cash, "Kas warga"))
    liquid += max(0.0, _finite(citizen.savings, "Tabungan warga"))
    net_worth = _finite(citizen.networth, "Kekayaan bersih")
    holdings_value = 0.0
    risk_exposure = 0.0
    for symbol, position in citizen.hold.items():
        asset = world.market.assets.get(symbol)
        if asset is None:
            continue
        try:
            units = _finite(position[0], "Jumlah unit aset")
            price = _finite(asset.price, "Harga aset")
            volatility = _finite(asset.vol, "Volatilitas aset")
        except (TypeError, ValueError, IndexError, OverflowError):
            raise ValueError("Posisi investasi tidak valid untuk evaluasi hasil.") from None
        if units < 0 or price < 0 or volatility < 0:
            raise ValueError("Posisi investasi negatif tidak dapat dievaluasi.")
        value = units * price
        if not math.isfinite(value):
            raise ValueError("Nilai posisi investasi tidak terbatas.")
        holdings_value += value
        risk_exposure += value * volatility
    financial_security = (
        0.65 * (_clamp(liquid / reserve, 0.0, 2.0) / 2.0)
        + 0.35 * _clamp(0.5 + net_worth / (6.0 * reserve))
    )
    survival = (
        0.7 * _clamp(_finite(citizen.health, "Kesehatan warga") / 100.0)
        + 0.3 * (1.0 - _clamp(
            _finite(citizen.hunger, "Kebutuhan warga") / 3.0
        ))
    )
    wellbeing = (
        0.45 * _clamp(_finite(citizen.happy, "Kebahagiaan warga") / 100.0)
        + 0.55 * (
            1.0
            - 0.45 * _clamp(_finite(citizen.stress, "Stres warga"))
            - 0.25 * _clamp(_finite(citizen.fear, "Ketakutan warga"))
            - 0.30 * _clamp(_finite(citizen.depression, "Depresi warga"))
        )
    )
    stability = 0.5 * float(any(
        house.owner is citizen for house in citizen.houses
    )) + 0.5 * float(citizen.job is not None or citizen.business is not None)
    skill = (
        0.5 * _clamp(_finite(citizen.skill, "Keterampilan warga"))
        + 0.5 * _clamp(
            _finite(citizen.financial_literacy, "Literasi finansial")
        )
    )
    risk_ratio = risk_exposure / max(
        reserve, liquid + holdings_value, 1.0
    )
    if not math.isfinite(risk_ratio):
        raise ValueError("Eksposur risiko aset tidak terbatas.")
    risk = _clamp(
        risk_ratio * max(0.0, 1.0 - _finite(citizen.risk, "Profil risiko"))
    )
    return {
        "survival": survival,
        "wellbeing": wellbeing,
        "financial_security": financial_security,
        "stability": stability,
        "skill": skill,
        "social": _clamp(social_contact_count(citizen) / 5.0),
        "risk": risk,
    }


def objective_weights(motivations, social_need=0.0):
    social_need = _clamp(_finite(social_need, "Kebutuhan sosial"))
    weights = {
        "survival": 0.2 + 0.2 * motivations.get("survival", 0.0),
        "wellbeing": 0.18,
        "financial_security": (
            0.16 + 0.16 * motivations.get("financial_security", 0.0)
        ),
        "stability": (
            0.14 + 0.12 * motivations.get("housing_safety", 0.0)
        ),
        "skill": (
            0.08 + 0.08 * motivations.get("skill_development", 0.0)
        ),
        "social": 0.08 + 0.12 * social_need,
        "risk": (
            0.08 + 0.16 * motivations.get("risk_reduction", 0.0)
        ),
    }
    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def outcome_reward(before, after, weights):
    reward = 0.0
    for objective, weight in weights.items():
        if objective == "risk":
            change = (
                _finite(before[objective], "Hasil awal")
                - _finite(after[objective], "Hasil akhir")
            )
        else:
            change = (
                _finite(after[objective], "Hasil akhir")
                - _finite(before[objective], "Hasil awal")
            )
        weight = _finite(weight, "Bobot tujuan")
        if weight < 0:
            raise ValueError("Bobot tujuan tidak boleh negatif.")
        reward += weight * change
    if not math.isfinite(reward):
        raise ValueError("Reward hasil simulasi tidak valid.")
    return max(-1.0, min(1.0, reward))


def settle_pending(policy, world, citizen):
    pending = policy.pending
    if pending is None or world.day <= pending.decision_day:
        return None
    after = outcome_snapshot(world, citizen)
    reward = outcome_reward(pending.before, after, pending.weights)
    policy.update(pending.context, pending.arm, reward, world.day)
    policy.pending = None
    return reward
