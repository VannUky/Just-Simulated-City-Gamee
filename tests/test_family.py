import pickle
import unittest
from unittest.mock import patch

from systems.agents.family import teach_knowledge
from systems.agents.lifecycle import advance_age, consider_births, food_payer
from systems.ekonomi_core import World


class FamilyLifecycleTests(unittest.TestCase):
    def make_couple(self):
        world = World(seed=922, n_pop=2)
        mother, father = world.citizens
        mother.female = True
        father.female = False
        mother.age = 25.0
        father.age = 28.0
        mother.happy = father.happy = 75.0
        mother.health = father.health = 95.0
        mother.cash = 1_000_000.0
        father.cash = 1_000_000.0
        home = world.houses[0]
        for house in world.houses:
            house.occupants = [
                occupant for occupant in house.occupants
                if occupant not in (mother, father)
            ]
        mother.home = father.home = home
        home.occupants = [mother, father]
        world._initialize_ledger()
        for _ in range(12):
            world.record_social_interaction(
                mother, father, "shared_work", True, "worked together"
            )
        proposal_id = world.propose_partnership(mother, father)
        self.assertTrue(world.respond_partnership(father, proposal_id, True))
        return world, mother, father

    def test_birth_builds_family_links_and_children_develop_as_dependents(self):
        world, mother, father = self.make_couple()
        starting_cash = mother.cash + father.cash

        first_child = world.birth_child(mother, father)
        second_child = world.birth_child(mother, father)

        self.assertIsNotNone(first_child)
        self.assertIsNotNone(second_child)
        self.assertEqual(first_child.age, 0.0)
        self.assertLess(first_child.skill, 0.2)
        self.assertEqual(first_child.knowledge.observations, [])
        self.assertEqual(world.family_parents(first_child), [mother, father])
        self.assertEqual(world.family_guardians(first_child), [mother, father])
        self.assertEqual(world.family_siblings(first_child), [second_child])
        self.assertEqual(world.family_partner(mother), father)
        self.assertAlmostEqual(
            starting_cash - mother.cash - father.cash, 500_000.0
        )
        self.assertEqual(world.reconcile_ledger(), {})

        for _ in range(6 * world.days_per_year):
            advance_age(world, first_child)

        self.assertGreaterEqual(first_child.age, 6.0)
        self.assertGreater(first_child.school_days, 0)
        self.assertGreater(first_child.education_level, 0.0)
        self.assertIn(food_payer(world, first_child), (mother, father))
        self.assertFalse(world.credit_ok(
            first_child, 100_000.0, 12, "personal", world.policy.loan_rate
        ))
        with self.assertRaises(ValueError):
            world.buy_asset(first_child, "KOTA", 100_000.0)

    def test_natural_birth_requires_funding_and_readiness(self):
        world, mother, father = self.make_couple()
        mother.parenting_desire = father.parenting_desire = 1.0
        mother.cash = father.cash = 0.0
        world._initialize_ledger()

        self.assertFalse(consider_births(world))
        self.assertEqual(len(world.citizens), 2)

        mother.cash = father.cash = 1_000_000.0
        world._initialize_ledger()
        original_random = world.rng.random
        first_draw = True

        def deterministic_first_draw():
            nonlocal first_draw
            if first_draw:
                first_draw = False
                return 0.0
            return original_random()

        with patch.object(world.rng, "random", side_effect=deterministic_first_draw):
            self.assertTrue(consider_births(world))

        self.assertEqual(len(world.citizens), 3)
        child = world.citizens[-1]
        self.assertEqual(world.family_parents(child), [mother, father])
        self.assertEqual(world.reconcile_ledger(), {})

    def test_teaching_is_explicit_imperfect_and_not_inherited_on_birth(self):
        world, mother, father = self.make_couple()
        child = world.birth_child(mother, father)
        source = mother.knowledge.observe(
            world.day, "personal_experience", "family-business",
            {"business_quality": 0.8, "market_risk": 0.2},
            context={"sector": "retail"},
        )
        self.assertEqual(child.knowledge.observations, [])

        with patch.object(world.rng, "random", return_value=0.01), patch.object(
                world.rng, "normalvariate", return_value=0.0):
            self.assertTrue(teach_knowledge(
                world, mother, child, source.id, "teaching"
            ))

        inherited = child.knowledge.observations[-1]
        self.assertEqual(inherited.source_type, "social_information")
        self.assertTrue(inherited.context["family_transfer"])
        self.assertNotEqual(inherited.source_id, source.source_id)
        self.assertEqual(father.knowledge.observations, [])

    def test_death_prefers_family_heir_and_reassigns_guardianship(self):
        world, mother, father = self.make_couple()
        child = world.birth_child(mother, father)
        adult_sibling = world.birth_child(mother, father)
        adult_sibling.age = 18.0
        world.appoint_family_guardian(child, adult_sibling)
        private_knowledge = mother.knowledge.observe(
            world.day, "personal_experience", "private-knowledge",
            {"market_risk": 0.9},
        )
        mother.cash = 700_000.0
        world._initialize_ledger()
        father_cash = father.cash

        self.assertTrue(world.remove_citizen(mother, cause="meninggal"))

        self.assertNotIn(mother, world.citizens)
        self.assertAlmostEqual(father.cash, father_cash + 700_000.0)
        self.assertEqual(world.family_partner(father), None)
        self.assertEqual(
            world.family_guardians(child), [father, adult_sibling]
        )
        self.assertEqual(world.family_parents(child), [father])
        self.assertEqual(child.knowledge.observations, [])
        self.assertEqual(world.reconcile_ledger(), {})

        self.assertTrue(world.remove_citizen(father, cause="meninggal"))

        self.assertEqual(world.family_guardians(child), [adult_sibling])
        self.assertEqual(world.family_parents(child), [])
        self.assertEqual(adult_sibling.cash, father_cash + 700_000.0)
        self.assertFalse(any(
            item.id == private_knowledge.id for item in child.knowledge.observations
        ))
        self.assertEqual(world.reconcile_ledger(), {})

    def test_child_death_settles_estate_but_cannot_depart(self):
        world, mother, father = self.make_couple()
        child = world.birth_child(mother, father)
        mother_cash = mother.cash
        child.cash = 100_000.0
        world._initialize_ledger()

        self.assertFalse(world.remove_citizen(
            child, inherit=False, cause="pindah"
        ))
        self.assertTrue(world.remove_citizen(child, cause="meninggal"))

        self.assertNotIn(child, world.citizens)
        self.assertAlmostEqual(mother.cash, mother_cash + 100_000.0)
        self.assertNotIn(str(child.id), world.family_state["guardians"])
        self.assertEqual(world.reconcile_ledger(), {})

    def test_family_state_round_trips_and_legacy_saves_migrate(self):
        world, mother, father = self.make_couple()
        child = world.birth_child(mother, father)
        restored = pickle.loads(pickle.dumps(world))
        restored.migrate_save()

        restored_child = next(
            citizen for citizen in restored.citizens
            if citizen.id == child.id
        )
        self.assertEqual(
            [parent.id for parent in restored.family_parents(restored_child)],
            [mother.id, father.id],
        )
        del restored.family_state["partners"]
        restored.migrate_save()
        self.assertEqual(
            restored.family_partner(
                next(c for c in restored.citizens if c.id == mother.id)
            ).id,
            father.id,
        )

        del restored.family_state
        del restored.citizens[0].parenting_desire
        restored.migrate_save()
        self.assertEqual(restored.family_state["relationships"], {})
        for citizen in restored.citizens:
            for attribute in (
                    "parenting_desire", "education_level", "school_days",
                    "adult_since_day"):
                if hasattr(citizen, attribute):
                    delattr(citizen, attribute)
        del restored.max_population
        del restored.days_per_year
        restored.migrate_save()
        self.assertTrue(hasattr(restored.citizens[0], "parenting_desire"))
        self.assertEqual(restored.max_population, 140)
        self.assertEqual(restored.days_per_year, 360)


if __name__ == "__main__":
    unittest.main()
