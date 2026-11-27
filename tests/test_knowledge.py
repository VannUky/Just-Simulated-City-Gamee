import pickle
import unittest
from unittest.mock import patch

from systems.agents.knowledge import KnowledgeGraph
from systems.ekonomi_core import World


class KnowledgeGraphTests(unittest.TestCase):
    def test_patterns_form_from_observations_with_provenance(self):
        graph = KnowledgeGraph()
        context = {"sector": "food"}
        for day, supply in enumerate((-2, -1, 0, 1, 2)):
            graph.observe(
                day, "personal_experience", f"market:{day}",
                {"available_supply": supply, "observed_price": -supply},
                context=context,
            )

        claims = graph.query(
            concept="available_supply",
            other_concept="observed_price",
            context=context,
            current_day=4,
        )

        self.assertIn("available_supply", graph.concepts)
        self.assertIn("observed_price", graph.concepts)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].relation, "negative")
        self.assertEqual(claims[0].status, "validated")
        self.assertTrue(all(
            reference.startswith("personal_experience:market:")
            for reference in claims[0].evidence_refs
        ))

    def test_contradictory_observations_reduce_claim_confidence(self):
        graph = KnowledgeGraph()
        context = {"sector": "food"}
        for day, value in enumerate((-2, -1, 0, 1, 2)):
            graph.observe(
                day, "direct_observation", f"first:{day}",
                {"supply": value, "price": value}, context=context,
            )
        claim = graph.query(
            concept="supply", other_concept="price", context=context,
            current_day=4,
        )[0]
        confidence_before = claim.confidence

        for offset, value in enumerate((-2, -1, 0, 1, 2), start=5):
            graph.observe(
                offset, "personal_experience", f"counter:{offset}",
                {"supply": value, "price": -value}, context=context,
            )

        self.assertLess(claim.confidence, confidence_before)
        self.assertNotEqual(claim.status, "validated")

    def test_composed_relations_remain_hypotheses_without_direct_evidence(self):
        graph = KnowledgeGraph()
        context = {"sector": "farm"}
        for day, value in enumerate((-2, -1, 0, 1, 2)):
            graph.observe(
                day, "personal_experience", f"supply:{day}",
                {"raw_stock": value, "input_price": -value},
                context=context,
            )
            graph.observe(
                day, "personal_experience", f"profit:{day}",
                {"input_price": value, "business_profit": value},
                context=context,
            )

        hypotheses = graph.query(
            concept="raw_stock",
            other_concept="business_profit",
            kind="hypothesis",
            context=context,
        )

        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0].relation, "negative")
        self.assertEqual(hypotheses[0].status, "hypothesis")
        self.assertEqual(len(hypotheses[0].derived_from), 2)
        self.assertFalse(graph.query(
            concept="raw_stock",
            other_concept="business_profit",
            status="validated",
            context=context,
        ))

    def test_only_validated_patterns_change_investment_decisions(self):
        worlds = [World(seed=61, n_pop=1), World(seed=61, n_pop=1)]
        for index, world in enumerate(worlds):
            citizen = world.citizens[0]
            asset = next(
                item for item in world.market.assets.values()
                if item.kind == "stock"
            )
            world.market.assets = {asset.sym: asset}
            world.policy.deposit_rate = 0.09
            asset.vol = 0.0
            citizen.risk = 0.0
            citizen.herd = 0.0
            citizen.optimism = 0.5
            citizen.frugal = 0.0
            citizen.financial_literacy = 1.0
            citizen.est_exp = 1_000_000.0
            world.set_cash(citizen, 100_000_000.0)
            if index:
                for value in (-1, -0.5, 0, 0.5, 1):
                    citizen.knowledge.observe(
                        world.day, "personal_experience", f"sale:{value}",
                        {
                            "market_momentum": value,
                            "realized_return": value,
                        },
                        context={"asset": asset.sym},
                    )

        for world in worlds:
            asset = next(iter(world.market.assets.values()))
            with patch.object(world.rng, "random", return_value=0.0):
                with patch.object(world.rng, "gauss", return_value=0.0):
                    with patch.object(asset, "momentum", return_value=0.25):
                        with patch.object(asset, "change", return_value=0.0):
                            world.finance(world.citizens[0])

        self.assertFalse(worlds[0].citizens[0].hold)
        self.assertIn(
            next(iter(worlds[1].market.assets)),
            worlds[1].citizens[0].hold,
        )

    def test_knowledge_is_personal_and_persists_through_pickle(self):
        world = World(seed=62, n_pop=2)
        graph = world.citizens[0].knowledge
        for day, value in enumerate((-2, -1, 0, 1, 2)):
            graph.observe(
                day, "personal_experience", f"sale:{day}",
                {"momentum": value, "return": value},
                context={"asset": "KOTA"},
            )

        restored = pickle.loads(pickle.dumps(world, protocol=4))
        restored.migrate_save()

        self.assertEqual(
            restored.citizens[0].knowledge.query(
                concept="momentum", other_concept="return",
                status="validated", context={"asset": "KOTA"},
            )[0].confidence,
            graph.query(
                concept="momentum", other_concept="return",
                status="validated", context={"asset": "KOTA"},
            )[0].confidence,
        )
        self.assertFalse(restored.citizens[1].knowledge.claims)

    def test_legacy_citizen_gets_knowledge_graph_idempotently(self):
        world = World(seed=63, n_pop=1)
        del world.citizens[0].knowledge
        restored = pickle.loads(pickle.dumps(world, protocol=4))

        restored.migrate_save()
        knowledge = restored.citizens[0].knowledge
        restored.migrate_save()

        self.assertIs(restored.citizens[0].knowledge, knowledge)
        self.assertIsInstance(knowledge, KnowledgeGraph)


if __name__ == "__main__":
    unittest.main()
