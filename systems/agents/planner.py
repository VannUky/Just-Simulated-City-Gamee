"""Bounded, side-effect-free GOAP-style planning over declarative actions."""
from dataclasses import dataclass, field
import heapq
import itertools
import math


@dataclass(frozen=True)
class PlanningAction:
    action_id: str
    preconditions: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)
    resource_costs: dict = field(default_factory=dict)
    resource_gains: dict = field(default_factory=dict)
    duration: float = 1.0
    risk: float = 0.0
    base_cost: float = 1.0
    parameters: dict = field(default_factory=dict)

    @property
    def token(self):
        if not self.parameters:
            return self.action_id
        values = ",".join(
            f"{key}={self.parameters[key]}"
            for key in sorted(self.parameters)
        )
        return f"{self.action_id}[{values}]"


@dataclass
class Plan:
    actions: list
    cost: float
    final_state: dict
    expanded: int


class BoundedPlanner:
    def __init__(self, max_depth=4, max_expansions=96):
        if (isinstance(max_depth, bool) or not isinstance(max_depth, int)
                or max_depth < 1):
            raise ValueError("Kedalaman rencana harus bilangan bulat positif.")
        if (isinstance(max_expansions, bool)
                or not isinstance(max_expansions, int)
                or max_expansions < 1):
            raise ValueError("Batas ekspansi planner harus bilangan bulat positif.")
        self.max_depth = max_depth
        self.max_expansions = max_expansions

    @staticmethod
    def _copy_state(state):
        if not isinstance(state, dict):
            raise ValueError("State planner harus berupa dictionary.")
        facts = state.get("facts", {})
        resources = state.get("resources", {})
        if not isinstance(facts, dict) or not isinstance(resources, dict):
            raise ValueError("Facts dan resources planner harus berupa dictionary.")
        copied_resources = {}
        for name, value in resources.items():
            if not isinstance(name, str) or not name:
                raise ValueError("Nama resource planner tidak valid.")
            try:
                amount = float(value)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Nilai resource planner harus berupa angka.") from None
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Nilai resource planner harus terbatas dan nonnegatif.")
            copied_resources[name] = amount
        return {"facts": dict(facts), "resources": copied_resources}

    @staticmethod
    def _condition_met(state, goal):
        facts = state["facts"]
        resources = state["resources"]
        if any(facts.get(key) != value for key, value in goal.conditions.items()):
            return False
        return all(
            resources.get(key, 0.0) >= amount
            for key, amount in goal.resource_targets.items()
        )

    @staticmethod
    def _key(state):
        facts = tuple(sorted(
            (key, type(value).__name__, repr(value))
            for key, value in state["facts"].items()
        ))
        resources = tuple(sorted(
            (key, round(value, 6))
            for key, value in state["resources"].items()
        ))
        return facts, resources

    @staticmethod
    def _valid_number(value, name):
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{name} action harus berupa angka.") from None
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} action harus terbatas dan nonnegatif.")
        return value

    def _apply(self, state, action):
        if any(
                state["facts"].get(key) != value
                for key, value in action.preconditions.items()):
            return None
        next_state = {
            "facts": dict(state["facts"]),
            "resources": dict(state["resources"]),
        }
        for key, raw_cost in action.resource_costs.items():
            cost = self._valid_number(raw_cost, "Biaya resource")
            available = next_state["resources"].get(key, 0.0)
            if available + 1e-9 < cost:
                return None
            next_state["resources"][key] = max(0.0, available - cost)
        for key, effect in action.effects.items():
            next_state["facts"][key] = effect
        for key, raw_gain in action.resource_gains.items():
            gain = self._valid_number(raw_gain, "Perolehan resource")
            amount = next_state["resources"].get(key, 0.0) + gain
            if not math.isfinite(amount):
                raise ValueError("Hasil resource action tidak valid.")
            next_state["resources"][key] = amount
        return next_state

    def _action_cost(self, action, state):
        base = self._valid_number(action.base_cost, "Biaya dasar")
        duration = self._valid_number(action.duration, "Durasi")
        risk = self._valid_number(action.risk, "Risiko")
        spend = sum(
            self._valid_number(value, "Biaya resource")
            for value in action.resource_costs.values()
        )
        budget = max(1_000_000.0, sum(state["resources"].values()))
        return base + duration * 0.1 + risk * 2.0 + spend / budget * 0.25

    def plan(self, initial_state, goal, actions):
        state = self._copy_state(initial_state)
        if self._condition_met(state, goal):
            return Plan([], 0.0, state, 0)
        action_list = tuple(actions)
        queue = []
        sequence = itertools.count()
        heapq.heappush(queue, (0.0, next(sequence), 0.0, state, ()))
        best_cost = {self._key(state): 0.0}
        expanded = 0

        while queue and expanded < self.max_expansions:
            _, _, cost, current, steps = heapq.heappop(queue)
            current_key = self._key(current)
            if cost > best_cost.get(current_key, math.inf) + 1e-12:
                continue
            expanded += 1
            if self._condition_met(current, goal):
                return Plan(list(steps), cost, current, expanded)
            if len(steps) >= self.max_depth:
                continue

            for action in action_list:
                next_state = self._apply(current, action)
                if next_state is None:
                    continue
                next_cost = cost + self._action_cost(action, current)
                next_key = self._key(next_state)
                if next_cost >= best_cost.get(next_key, math.inf) - 1e-12:
                    continue
                best_cost[next_key] = next_cost
                heapq.heappush(
                    queue,
                    (
                        next_cost,
                        next(sequence),
                        next_cost,
                        next_state,
                        steps + (action,),
                    ),
                )
        return None
