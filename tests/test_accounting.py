import copy
import pickle
import math
import unittest
from collections import deque
from unittest.mock import patch

from systems.accounting import AccountingLedger
from systems.ekonomi_core import World


class AccountingLedgerTests(unittest.TestCase):
    def test_journal_rejects_unbalanced_postings_without_mutating_accounts(self):
        ledger = AccountingLedger()

        with self.assertRaises(ValueError):
            ledger.post(0, "test", "unbalanced", {"cash": 10}, {"revenue": 9})

        self.assertFalse(ledger.entries)
        self.assertEqual(ledger.accounts, {})

    def test_journal_validates_account_normals_before_committing_any_posting(self):
        ledger = AccountingLedger()
        conflict = ledger.ensure_account("conflict", "credit")

        with self.assertRaises(ValueError):
            ledger.post(
                0, "test", "normal balance conflict",
                {"cash": 10}, {"conflict": 10},
                normal_balances={"cash": "debit", "conflict": "debit"},
            )

        self.assertEqual(set(ledger.accounts), {"conflict"})
        self.assertEqual(conflict.balance, 0)
        self.assertEqual(ledger.next_sequence, 1)
        self.assertFalse(ledger.entries)

    def test_journal_posts_balanced_entries(self):
        ledger = AccountingLedger()
        entry = ledger.post(3, "test", "cash transfer", {"recipient:cash": 10},
                            {"payer:cash": 10})

        self.assertEqual(entry.debits, 10)
        self.assertEqual(entry.credits, 10)
        self.assertEqual(ledger.accounts["recipient:cash"].balance, 10)
        self.assertEqual(ledger.accounts["payer:cash"].balance, -10)

    def test_world_transactions_reconcile_cash_and_bank_accounts(self):
        world = World(seed=31, n_pop=12)
        citizen = world.citizens[0]
        world.set_cash(citizen, 8_000_000)
        world.deposit(citizen, 2_000_000)
        world.withdraw(citizen, 500_000)
        world.make_loan(citizen, 1_000_000, 0.1, 12, "personal")
        world.buy_asset(citizen, "KOTA", 500_000)
        world.sell_asset(citizen, "KOTA")

        self.assertEqual(world.reconcile_ledger(), {})
        self.assertTrue(all(
            abs(entry.debits - entry.credits) < 1e-7
            for entry in world.ledger.entries
        ))
        categories = {entry.category for entry in world.ledger.entries}
        self.assertIn("loan_disbursement", categories)
        self.assertIn("asset_purchase", categories)
        self.assertIn("asset_sale", categories)

    def test_deposit_rolls_back_when_journal_recording_fails(self):
        world = World(seed=41, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        before = (
            citizen.cash, citizen.savings, world.bank.cash,
            world.bank.deposits, len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.deposit(citizen, 500_000)

        self.assertEqual(
            (citizen.cash, citizen.savings, world.bank.cash,
             world.bank.deposits, len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_loan_disbursement_rolls_back_when_journal_recording_fails(self):
        world = World(seed=42, n_pop=1)
        citizen = world.citizens[0]
        before = (
            citizen.cash, world.bank.cash, world.bank.loan_book,
            tuple(citizen.loans), tuple(world.loans),
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.make_loan(citizen, 500_000, 0.1, 12, "personal")

        self.assertEqual(
            (citizen.cash, world.bank.cash, world.bank.loan_book,
             tuple(citizen.loans), tuple(world.loans),
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_house_purchase_rolls_back_when_journal_recording_fails(self):
        world = World(seed=43, n_pop=2)
        seller, buyer = world.citizens
        house = world.houses[0]
        house.owner = seller
        seller.houses.append(house)
        mortgage = world.make_loan(seller, 10_000_000, 0.1, 240, "mortgage", house)
        world.edit_cash(seller, -mortgage.balance)
        price = house.value
        fee = price * 0.01
        world.set_cash(buyer, price + fee)
        before = (
            buyer.cash, seller.cash, world.bank.cash, world.bank.loan_book,
            world.treasury, house.owner, tuple(buyer.houses),
            tuple(seller.houses), tuple(world.loans), tuple(house.occupants),
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.buy_house(buyer, house)

        self.assertEqual(
            (buyer.cash, seller.cash, world.bank.cash, world.bank.loan_book,
             world.treasury, house.owner, tuple(buyer.houses),
             tuple(seller.houses), tuple(world.loans), tuple(house.occupants),
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_monthly_settlement_rolls_back_when_journal_recording_fails(self):
        world = World(seed=44, n_pop=2)
        citizen = world.citizens[0]
        world.set_cash(citizen, 2_000_000)
        world.deposit(citizen, 1_000_000)
        before = (
            tuple((c.cash, c.savings, c.exp_acc, c.est_exp, c.credit_score,
                   c.learning, c.missed_rent) for c in world.citizens),
            tuple((loan.balance, loan.months, loan.missed) for loan in world.loans),
            (world.bank.cash, world.bank.deposits, world.bank.loan_book,
             world.bank.equity, world.bank.profit, world.bank.loss),
            tuple((house.condition, house.bank_value, tuple(house.occupants))
                  for house in world.houses),
            world.rng.getstate(),
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.monthly()

        self.assertEqual(
            (tuple((c.cash, c.savings, c.exp_acc, c.est_exp, c.credit_score,
                    c.learning, c.missed_rent) for c in world.citizens),
             tuple((loan.balance, loan.months, loan.missed) for loan in world.loans),
             (world.bank.cash, world.bank.deposits, world.bank.loan_book,
              world.bank.equity, world.bank.profit, world.bank.loss),
             tuple((house.condition, house.bank_value, tuple(house.occupants))
                   for house in world.houses),
             world.rng.getstate(),
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_production_cycle_rolls_back_when_journal_recording_fails(self):
        world = World(seed=47, n_pop=1)
        owner = world.citizens[0]
        world.set_cash(owner, 20_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        farm.input_inventory["seeds"] = 0.05
        farm.input_costs["seeds"] = 20_000.0
        world._initialize_ledger()
        before = (
            farm.cash, farm.stock, farm.prod, farm.production_progress,
            farm.production_failed, dict(farm.input_inventory),
            dict(farm.input_costs), dict(world.import_supply_remaining),
            tuple(world.trade_contracts), world.rng.getstate(),
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.production_cycle(farm)

        self.assertEqual(
            (farm.cash, farm.stock, farm.prod, farm.production_progress,
             farm.production_failed, dict(farm.input_inventory),
             dict(farm.input_costs), dict(world.import_supply_remaining),
             tuple(world.trade_contracts), world.rng.getstate(),
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_goods_purchase_from_savings_rolls_back_when_journal_fails(self):
        world = World(seed=49, n_pop=2)
        buyer, owner = world.citizens
        world.set_cash(buyer, 1_000_000)
        world.deposit(buyer, 1_000_000)
        world.set_cash(owner, 100_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        farm.stock = 5.0
        world._initialize_ledger()
        before = (
            buyer.cash, buyer.savings, buyer.exp_acc,
            world.bank.cash, world.bank.deposits,
            farm.cash, farm.stock, world.treasury,
            tuple(world.trade_contracts), world.next_trade_id,
            copy.deepcopy(world.social_state), len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.buy_goods(buyer, 1.0)

        self.assertEqual(
            (buyer.cash, buyer.savings, buyer.exp_acc,
             world.bank.cash, world.bank.deposits,
             farm.cash, farm.stock, world.treasury,
             tuple(world.trade_contracts), world.next_trade_id,
             world.social_state, len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_world_migrates_v1_ledger_with_opening_business_inventory(self):
        world = World(seed=48, n_pop=1)
        owner = world.citizens[0]
        world.set_cash(owner, 20_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        business = owner.business
        business.input_inventory.clear()
        business.input_costs.clear()
        business.stock = 2.0
        world._initialize_ledger()
        clone = pickle.loads(pickle.dumps(world, protocol=4))
        legacy_snapshot = {
            name: value
            for name, value in clone._ledger_snapshot().items()
            if not name.endswith(":inventory")
        }
        clone.ledger = AccountingLedger()
        clone.ledger.seed_opening_balances(clone.day, legacy_snapshot)
        clone.ledger.schema_version = 1
        legacy_business = clone.businesses[0]
        for attribute in (
                "input_inventory", "input_costs", "service_inventory",
                "service_costs", "production_progress", "production_failed",
                "work_hours", "unit_cost", "quality", "market_product"):
            delattr(legacy_business, attribute)

        clone.migrate_save()

        inventory_account = f"business:{legacy_business.ledger_id}:inventory"
        self.assertEqual(clone.ledger.schema_version, AccountingLedger.SCHEMA_VERSION)
        self.assertAlmostEqual(
            clone.ledger.accounts[inventory_account].balance,
            legacy_business.inventory_value,
        )
        self.assertEqual(clone.reconcile_ledger(), {})

    def test_pay_from_rejects_negative_and_nonfinite_amounts(self):
        world = World(seed=45, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        before = (
            citizen.cash, citizen.savings, world.bank.cash,
            world.bank.deposits, citizen.exp_acc, len(world.ledger.entries),
        )

        for amount in (-1, float("nan"), float("inf")):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    world.pay_from(citizen, amount)
                self.assertEqual(
                    (citizen.cash, citizen.savings, world.bank.cash,
                     world.bank.deposits, citizen.exp_acc,
                     len(world.ledger.entries)),
                    before,
                )

        self.assertTrue(world.pay_from(citizen, 0))
        self.assertEqual(
            (citizen.cash, citizen.savings, world.bank.cash,
             world.bank.deposits, citizen.exp_acc, len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_direct_pay_from_is_ledgered_and_rolls_back_on_failure(self):
        world = World(seed=46, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        before = (citizen.cash, citizen.exp_acc, len(world.ledger.entries))

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.pay_from(citizen, 250_000)

        self.assertEqual(
            (citizen.cash, citizen.exp_acc, len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

        self.assertTrue(world.pay_from(citizen, 250_000))
        self.assertEqual(citizen.cash, 750_000)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_asset_sale_rejects_oversell_and_nonfinite_fractions_atomically(self):
        for fraction in (1.01, -0.01, float("nan"), float("inf")):
            with self.subTest(fraction=fraction):
                world = World(seed=35, n_pop=1)
                citizen = world.citizens[0]
                world.set_cash(citizen, 1_000_000)
                world.buy_asset(citizen, "KOTA", 1_000_000)
                units_before = citizen.hold["KOTA"][0]
                cash_before = citizen.cash
                flow_before = world.market.assets["KOTA"].flow
                entries_before = len(world.ledger.entries)

                with self.assertRaises(ValueError):
                    world.sell_asset(citizen, "KOTA", fraction)

                self.assertEqual(citizen.hold["KOTA"][0], units_before)
                self.assertEqual(citizen.cash, cash_before)
                self.assertEqual(world.market.assets["KOTA"].flow, flow_before)
                self.assertEqual(len(world.ledger.entries), entries_before)
                self.assertEqual(world.reconcile_ledger(), {})

    def test_asset_sale_rejects_unknown_symbol_without_mutation(self):
        world = World(seed=36, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        before = citizen.cash

        with self.assertRaises(ValueError):
            world.sell_asset(citizen, "MISSING")

        self.assertEqual(citizen.cash, before)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_asset_purchase_rejects_invalid_amounts_without_mutation(self):
        for amount in (-1, float("nan"), float("inf")):
            with self.subTest(amount=amount):
                world = World(seed=39, n_pop=1)
                citizen = world.citizens[0]
                world.set_cash(citizen, 1_000_000)
                before = (
                    citizen.cash,
                    dict(citizen.hold),
                    world.market.assets["KOTA"].flow,
                    len(world.ledger.entries),
                )

                with self.assertRaises(ValueError):
                    world.buy_asset(citizen, "KOTA", amount)

                self.assertEqual(
                    (citizen.cash, dict(citizen.hold),
                     world.market.assets["KOTA"].flow,
                     len(world.ledger.entries)),
                    before,
                )
                self.assertEqual(world.reconcile_ledger(), {})

    def test_asset_purchase_preflights_journal_before_changing_domain_state(self):
        world = World(seed=40, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        before = (
            citizen.cash,
            dict(citizen.hold),
            world.market.assets["KOTA"].flow,
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.buy_asset(citizen, "KOTA", 500_000)

        self.assertEqual(
            (citizen.cash, dict(citizen.hold),
             world.market.assets["KOTA"].flow,
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_asset_sale_preflights_journal_before_changing_domain_state(self):
        world = World(seed=37, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 1_000_000)
        world.buy_asset(citizen, "KOTA", 1_000_000)
        before = (citizen.cash, list(citizen.hold["KOTA"]),
                  world.treasury, len(world.ledger.entries))

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.sell_asset(citizen, "KOTA", 0.5)

        self.assertEqual(
            (citizen.cash, citizen.hold["KOTA"], world.treasury,
             len(world.ledger.entries)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_treasury_editor_commands_are_ledgered(self):
        world = World(seed=38, n_pop=1)
        initial = world.treasury

        world.adjust_treasury(-500_000_000)
        world.set_treasury(2_000_000_000)

        self.assertEqual(world.treasury, 2_000_000_000)
        self.assertEqual(world.reconcile_ledger(), {})
        self.assertEqual(
            sum(entry.category == "player_treasury_adjustment"
                for entry in world.ledger.entries),
            2,
        )
        self.assertEqual(initial, 3_000_000_000)

    def test_monthly_interest_uses_a_named_accrual_account(self):
        world = World(seed=33, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 2_000_000)
        world.deposit(citizen, 2_000_000)
        for house in world.houses:
            house.occupants.clear()
        citizen.home = None
        world.policy.deposit_rate = 0.12
        expected_interest = citizen.savings * world.policy.deposit_rate / 12

        world.monthly()

        self.assertAlmostEqual(citizen.savings, 2_000_000 + expected_interest)
        self.assertNotIn("bank:profit", world.ledger.accounts)
        self.assertNotIn("bank:loss", world.ledger.accounts)
        self.assertAlmostEqual(
            world.ledger.counterpart_balances["counterpart:interest_and_rent_accruals"],
            -expected_interest,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_legacy_pickle_save_is_seeded_and_migration_is_idempotent(self):
        world = World(seed=32, n_pop=12)
        citizen = world.citizens[0]
        world.set_cash(citizen, 4_000_000)
        self.assertTrue(world.found_business(citizen, "farm", force=True))
        saved_cash = citizen.cash
        saved_treasury = world.treasury

        del world.ledger
        del world._ledger_capture_depth
        del world.next_business_id
        for business in world.businesses:
            del business.ledger_id
        clone = pickle.loads(pickle.dumps(world, protocol=4))
        clone.migrate_save()

        self.assertEqual(clone.citizens[0].cash, saved_cash)
        self.assertEqual(clone.treasury, saved_treasury)
        self.assertEqual(clone.businesses[0].ledger_id, 1)
        self.assertEqual(clone.reconcile_ledger(), {})
        opening_count = len(clone.ledger.entries)
        self.assertGreater(opening_count, 0)

        clone.migrate_save()

        self.assertEqual(len(clone.ledger.entries), opening_count)
        self.assertEqual(clone.reconcile_ledger(), {})

    def test_legacy_bank_metrics_do_not_break_reconciliation(self):
        world = World(seed=34, n_pop=1)
        world.ledger.ensure_account("bank:profit", "credit")
        world.ledger.post(
            world.day, "legacy_metric", "legacy bank profit memo",
            {"opening_source:legacy_metric": 10}, {"bank:profit": 10},
        )

        self.assertEqual(world.reconcile_ledger(), {})

    def test_legacy_list_journal_is_migrated_to_bounded_history_on_unpickle(self):
        ledger = AccountingLedger()
        ledger.post(0, "test", "opening", {"cash": 10}, {"source": 10})
        ledger.entries = list(ledger.entries)

        restored = pickle.loads(pickle.dumps(ledger, protocol=4))

        self.assertIsInstance(restored.entries, deque)
        self.assertEqual(len(restored.entries), 1)
        self.assertEqual(restored.archived_entry_count, 0)

    def test_long_simulation_keeps_journal_balanced_and_reconciled(self):
        world = World(seed=42, n_pop=40)
        world.advance(24 * 1100)

        self.assertEqual(world.reconcile_ledger(), {})
        self.assertTrue(all(
            abs(entry.debits - entry.credits) < 1e-7
            for entry in world.ledger.entries
        ))
        self.assertEqual(
            len(world.ledger.entries),
            world.ledger.MAX_RETAINED_ENTRIES,
        )
        self.assertGreater(world.ledger.archived_entry_count, 0)
        self.assertEqual(
            world.ledger.archived_entry_count + len(world.ledger.entries),
            world.ledger.next_sequence - 1,
        )
        self.assertTrue(math.isclose(
            sum(totals["debits"] for totals in world.ledger.archived_totals.values()),
            sum(totals["credits"] for totals in world.ledger.archived_totals.values()),
            rel_tol=1e-12,
            abs_tol=1e-7,
        ))
        self.assertTrue(world.ledger.counterpart_balances)


if __name__ == "__main__":
    unittest.main()
