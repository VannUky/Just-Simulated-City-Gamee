import unittest

from systems.agents.learning import (
    LearningState, objective_weights, outcome_reward, outcome_snapshot,
    settle_pending,
)
from systems.ekonomi_core import World


class AdaptiveLearningTests(unittest.TestCase):
    def test_bad_experience_changes_strategy_from_rule_based_baseline(self):
        learning = LearningState()
        context = "unemployed|low_liquidity|risk_tolerant"
        baseline_scores = {"risky": 0.65, "safe": 0.55}
        baseline_choice = max(baseline_scores, key=baseline_scores.get)

        for day in range(12):
            learning.update(context, "risky", -0.8, day)

        learned_choice = max(
            baseline_scores,
            key=lambda arm: learning.score(
                context, arm, baseline_scores[arm]
            ),
        )

        self.assertEqual(baseline_choice, "risky")
        self.assertEqual(learned_choice, "safe")

    def test_individual_policies_develop_different_strategies(self):
        context = "employed|buffered|balanced"
        scores = {"save": 0.5, "invest": 0.5}
        cautious, growth_seeking = LearningState(), LearningState()
        for day in range(10):
            cautious.update(context, "invest", -0.7, day)
            growth_seeking.update(context, "save", -0.7, day)

        cautious_choice = max(
            scores,
            key=lambda arm: cautious.score(context, arm, scores[arm]),
        )
        growth_choice = max(
            scores,
            key=lambda arm: growth_seeking.score(
                context, arm, scores[arm]
            ),
        )

        self.assertNotEqual(cautious_choice, growth_choice)

    def test_learning_is_contextual_and_beats_static_rule_baseline(self):
        learning = LearningState()
        context = "renting|short_liquidity|balanced"
        scores = {"risky": 0.65, "safe": 0.55}
        baseline_total = 0.0
        learned_total = 0.0

        for day in range(30):
            baseline_total += -0.8
            arm = max(
                scores,
                key=lambda candidate: learning.score(
                    context, candidate, scores[candidate]
                ),
            )
            reward = -0.8 if arm == "risky" else 0.5
            learning.update(context, arm, reward, day)
            learned_total += reward

        self.assertGreater(learned_total, baseline_total)
        self.assertEqual(
            learning.mean_reward("different-context", "risky"), 0.0
        )

    def test_reward_balances_survival_wellbeing_finance_and_risk(self):
        before = {
            "survival": 0.8,
            "wellbeing": 0.8,
            "financial_security": 0.2,
            "stability": 0.4,
            "skill": 0.3,
            "social": 0.4,
            "risk": 0.1,
        }
        after = {
            "survival": 0.2,
            "wellbeing": 0.2,
            "financial_security": 0.8,
            "stability": 0.4,
            "skill": 0.3,
            "social": 0.4,
            "risk": 0.9,
        }
        weights = objective_weights({
            "survival": 1.0,
            "financial_security": 0.0,
            "housing_safety": 0.0,
            "skill_development": 0.0,
            "risk_reduction": 1.0,
        })

        self.assertLess(outcome_reward(before, after, weights), 0.0)

    def test_delayed_outcome_updates_policy_once_from_world_state(self):
        world = World(seed=71, n_pop=1)
        citizen = world.citizens[0]
        learning = LearningState()
        before = outcome_snapshot(world, citizen)
        weights = objective_weights({"survival": 1.0})
        learning.remember("context", "action", before, weights, world.day)

        world.day += 1
        citizen.health -= 30.0
        citizen.hunger = 3
        reward = settle_pending(learning, world, citizen)

        self.assertLess(reward, 0.0)
        self.assertEqual(learning.contexts["context"]["action"].count, 1)
        self.assertIsNone(learning.pending)
        self.assertIsNone(settle_pending(learning, world, citizen))


if __name__ == "__main__":
    unittest.main()
