import pickle
import sys
import unittest
from unittest.mock import patch

from systems.ekonomi_core import (
    BUILD_COST, DPY, SECURED_LOAN_MAX, STARTUP, UNSECURED_LOAN_MAX,
    UNSECURED_LOAN_MIN, World, TICKS_PER_DAY,
)


class EconomyCoreTests(unittest.TestCase):
    def test_residents_start_with_zero_rupiah(self):
        world = World(seed=7, n_pop=12)
        self.assertTrue(world.citizens)
        self.assertTrue(all(c.cash == 0 and c.savings == 0 for c in world.citizens))

    def test_world_advances_a_day(self):
        world = World(seed=7, n_pop=12)
        world.advance(24)
        self.assertEqual(world.day, 1)

    def test_editor_controls_change_cash_tax_and_market_price(self):
        world = World(seed=7, n_pop=12)
        citizen = world.citizens[0]
        old_price = world.market.assets["KOTA"].price
        world.set_cash(citizen, 2_500_000)
        world.policy.tax_pph = 0.125
        world.set_price("KOTA", 1_500_000)
        self.assertEqual(citizen.cash, 2_500_000)
        self.assertEqual(world.policy.tax_pph, 0.125)
        self.assertNotEqual(world.market.assets["KOTA"].price, old_price)

    def test_city_has_exchange_and_hall(self):
        world = World(seed=3, n_pop=12)
        kinds = [l.kind for l in world.lots]
        self.assertEqual(kinds.count("exchange"), 1)
        self.assertEqual(kinds.count("hall"), 1)
        self.assertEqual(kinds.count("house"), 1)

    def test_candles_are_valid_ohlc(self):
        world = World(seed=3, n_pop=12)
        for tf in (1, 7, 30):
            for sym in world.market.assets:
                for o, h, l, c, v in world.market.candles(sym, tf, 40):
                    self.assertLessEqual(l, min(o, c) + 1e-9)
                    self.assertGreaterEqual(h, max(o, c) - 1e-9)
                    self.assertGreaterEqual(v, 0)

    def test_new_day_adds_ticks(self):
        world = World(seed=3, n_pop=12)
        a = world.market.assets["TEKA"]
        n = len(a.ticks)
        world.advance(24)
        self.assertEqual(len(a.ticks), n + TICKS_PER_DAY)

    def test_halt_freezes_price_and_blocks_trading(self):
        world = World(seed=3, n_pop=12)
        a = world.market.assets["BITO"]
        world.toggle_halt("BITO")
        p = a.price
        c = world.citizens[0]
        c.cash = 10_000_000
        self.assertEqual(world.buy_asset(c, "BITO", 5_000_000), 0.0)
        world.advance(24 * 5)
        self.assertEqual(a.price, p)
        world.toggle_halt("BITO")
        self.assertFalse(a.halted)

    def test_market_controls_clamp(self):
        world = World(seed=3, n_pop=12)
        world.set_vol_mult("KOTA", 99)
        world.set_bias("KOTA", -9)
        world.set_sentiment(5)
        a = world.market.assets["KOTA"]
        self.assertEqual(a.vol_mult, 4.0)
        self.assertEqual(a.bias, -1.0)
        self.assertEqual(world.market.sent, 0.12)
        world.reset_market_controls()
        self.assertEqual((a.vol_mult, a.bias, world.market.sent), (1.0, 0.0, 0.0))

    def test_push_price_moves_price_up(self):
        world = World(seed=3, n_pop=12)
        a = world.market.assets["KOTA"]
        world.push_price("KOTA", 5e9)
        self.assertGreater(a.flow, 0)

    def test_same_seed_same_city(self):
        a, b = World(seed=42, n_pop=20), World(seed=42, n_pop=20)
        self.assertEqual([c.name for c in a.citizens], [c.name for c in b.citizens])

    def test_business_equity_counts_land_equipment_inventory_and_debt_once(self):
        world = World(seed=7, n_pop=12)
        citizen = world.citizens[0]
        citizen.cash = 10_000_000
        initial_wealth = citizen.networth

        self.assertTrue(world.found_business(citizen, "farm", force=True))
        business = citizen.business

        self.assertAlmostEqual(business.asset_value, world.lot_price + STARTUP["farm"])
        self.assertAlmostEqual(citizen.networth, initial_wealth)
        self.assertAlmostEqual(citizen.networth,
                               citizen.cash + business.asset_value - citizen.debt)

    def test_negative_net_worth_includes_unsecured_debt(self):
        world = World(seed=7, n_pop=12)
        citizen = world.citizens[0]
        citizen.persuasion = citizen.skill = 1.0
        citizen.credit_score = 850
        citizen.cash = 5_000_000
        world.make_loan(citizen, 10_000_000, 0.1, 12, "personal")
        citizen.cash -= 10_000_000

        self.assertEqual(citizen.networth, -5_000_000)

    def test_building_and_business_assets_depreciate(self):
        world = World(seed=7, n_pop=12)
        citizen = world.citizens[0]
        citizen.cash = 10_000_000
        self.assertTrue(world.found_business(citizen, "farm", force=True))
        house_value = world.houses[0].value
        equipment_value = citizen.business.equipment_value

        world.monthly()

        self.assertLess(world.houses[0].value, house_value)
        self.assertLess(citizen.business.equipment_value, equipment_value)

    def test_startup_ai_is_inexperienced_and_learns_from_paid_work(self):
        world = World(seed=7, n_pop=20)
        worker = world.hall.workers[0]
        initial_learning = worker.learning

        for _ in range(20):
            world.payroll()

        self.assertLess(initial_learning, 0.05)
        self.assertGreater(worker.learning, initial_learning)

    def test_migration_is_not_guaranteed_when_city_conditions_are_bad(self):
        world = World(seed=7, n_pop=12)
        for citizen in world.citizens:
            if citizen.job:
                citizen.job.workers.remove(citizen)
                citizen.job = None
        population = len(world.citizens)

        world.migration_daily()

        self.assertEqual(len(world.citizens), population)

    def test_random_events_are_seeded_and_reproducible(self):
        def event_titles(seed):
            world = World(seed=seed, n_pop=12)
            titles = []
            for day in range(1, 1501):
                world.day = day
                previous = world._ev
                world.random_event()
                if world._ev > previous:
                    titles.append(world.events[-1][2])
            return titles

        first = event_titles(17)
        self.assertTrue(first)
        self.assertEqual(first, event_titles(17))

    def test_elected_mayor_can_adjust_policy_from_city_conditions(self):
        world = World(seed=7, n_pop=12)
        world.day = DPY
        world.treasury = 100_000_000
        starting_tax = world.policy.tax_pph
        starting_welfare = world.policy.welfare

        world.government_cycle()

        self.assertIsNotNone(world.mayor_id)
        self.assertGreater(world.government_learning, 0.02)
        self.assertLess(world.policy.tax_pph, starting_tax)
        self.assertGreater(world.policy.welfare, starting_welfare)
        self.assertIn("KEBIJAKAN PEMERINTAH BERUBAH", [event[2] for event in world.events])

    def test_vehicle_purchase_uses_showroom_stock_and_financed_net_worth(self):
        world = World(seed=21, n_pop=20)
        buyer = world.hall.workers[0]
        owner = next(c for c in world.citizens if c is not buyer and c.business is None)
        owner.cash = 20_000_000
        self.assertTrue(world.found_business(owner, "showroom", force=True))
        self.assertGreaterEqual(owner.business.car_stock, 1.0)
        buyer.cash = 10_000_000
        before = buyer.networth

        self.assertTrue(world.buy_car(buyer))

        self.assertIsNotNone(buyer.vehicle_color)
        self.assertGreater(buyer.vehicle_value, 0)
        self.assertAlmostEqual(buyer.networth, before)

    def test_bank_balance_sheet_reconciles_after_deposit_interest(self):
        world = World(seed=9, n_pop=12)
        citizen = world.citizens[0]
        citizen.cash = 10_000_000
        world.deposit(citizen, citizen.cash)

        world.monthly()

        assets_minus_liabilities = (
            world.bank.cash + world.bank.loan_book + world.bank.repossessed_assets
            - world.bank.deposits
        )
        self.assertAlmostEqual(world.bank.equity, assets_minus_liabilities, places=2)

    def test_insolvent_bank_does_not_issue_new_credit(self):
        world = World(seed=10, n_pop=12)
        citizen = world.citizens[0]
        citizen.cash = 100_000_000
        world.bank.equity = 0

        self.assertFalse(world.credit_ok(citizen, 1_000_000, 12, "vehicle", 0.1))

    def test_unsecured_credit_limit_depends_on_character_and_has_a_cap(self):
        world = World(seed=10, n_pop=12)
        citizen = world.hall.workers[0]
        citizen.persuasion = citizen.skill = 0.0
        citizen.credit_score = 300
        self.assertAlmostEqual(world.unsecured_limit(citizen), UNSECURED_LOAN_MIN)

        citizen.persuasion = citizen.skill = 1.0
        citizen.credit_score = 850
        self.assertAlmostEqual(world.unsecured_limit(citizen), UNSECURED_LOAN_MAX)
        self.assertIsNone(world.apply_personal_loan(citizen, UNSECURED_LOAN_MAX + 1))
        self.assertIsNotNone(world.apply_personal_loan(citizen, UNSECURED_LOAN_MIN))

    def test_secured_credit_limit_is_capped(self):
        world = World(seed=10, n_pop=12)
        citizen = world.hall.workers[0]
        self.assertFalse(world.credit_ok(citizen, SECURED_LOAN_MAX + 1, 240,
                                         "mortgage", world.policy.loan_rate))
        with self.assertRaises(ValueError):
            world.make_loan(citizen, SECURED_LOAN_MAX + 1, 0.1, 240, "mortgage")

    def test_gigs_pay_workers_from_the_city_budget(self):
        world = World(seed=12, n_pop=20)
        before = world.treasury
        world.gig_market()
        workers = [c for c in world.citizens if c.gigs_done]

        self.assertTrue(workers)
        self.assertLess(world.treasury, before)
        self.assertTrue(all(c.last_gig for c in workers))

    def test_employment_stats_do_not_count_never_worked_citizens_as_gig_workers(self):
        world = World(seed=13, n_pop=12)
        for citizen in world.citizens:
            if citizen.job is not None:
                citizen.job.workers.remove(citizen)
                citizen.job = None

        self.assertEqual(world.employment_stats()["informal"], 0)
        self.assertEqual(world.employment_stats()["unemployed"], len(world.citizens))

        world.citizens[0].last_gig_day = world.day
        world.day += 3
        self.assertEqual(world.employment_stats()["informal"], 1)

    def test_employment_market_separates_full_and_part_time_hours(self):
        world = World(seed=14, n_pop=12)
        owner, worker = world.citizens[:2]
        world.set_cash(owner, 100_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        business = owner.business
        for citizen in world.citizens:
            if citizen.job is not None:
                citizen.job.workers.remove(citizen)
                citizen.job = None
        worker.job = business
        business.workers.append(worker)
        business.work_hours = 20.0

        counts = world.employment_stats()

        self.assertEqual(counts["part_time"], 1)
        self.assertEqual(counts["full_time"], 0)
        part_time_pay = business.pay_for(worker)
        business.work_hours = 40.0
        self.assertGreater(business.pay_for(worker), part_time_pay)

    def test_crime_transfers_money_and_records_city_incident(self):
        class CrimeRandom:
            def random(self):
                return 0.0

            def choice(self, values):
                return values[0]

            def uniform(self, low, high):
                return low

        world = World(seed=14, n_pop=12)
        offender, victim = world.citizens[:2]
        world.hall.workers.clear()
        for citizen in world.citizens[1:]:
            citizen.job = world.hall
            world.hall.workers.append(citizen)
        offender.job = None
        victim.cash = 1_000_000
        world.rng = CrimeRandom()
        total_cash = sum(c.cash for c in world.citizens)

        world.crime_daily()

        self.assertEqual(victim.cash, 950_000)
        self.assertEqual(offender.cash, 50_000)
        self.assertGreater(victim.fear, 0)
        self.assertAlmostEqual(sum(c.cash for c in world.citizens), total_cash)
        self.assertGreater(world.crime_rate, 0)

    def test_land_purchase_and_home_construction_are_separate_transactions(self):
        world = World(seed=15, n_pop=12)
        buyer, contractor_owner = world.citizens[:2]
        world.set_cash(buyer, 50_000_000)
        world.set_cash(contractor_owner, 100_000_000)
        treasury = world.treasury

        lot = world.buy_land(buyer)
        self.assertIsNotNone(lot)
        self.assertEqual(world.treasury, treasury + world.lot_price)
        self.assertAlmostEqual(buyer.networth, 50_000_000)

        self.assertTrue(world.found_business(contractor_owner, "builder", force=True))
        builder = contractor_owner.business
        for _ in range(30):
            world.production_cycle(builder)
        home = world.build_house(buyer, lot)

        self.assertIsNotNone(home)
        self.assertIs(home.owner, buyer)
        self.assertAlmostEqual(home.land_value, world.lot_price)
        self.assertAlmostEqual(home.base_structure_value, BUILD_COST)
        self.assertIn(home, buyer.houses)
        self.assertEqual(lot.kind, "house")

    def test_business_creation_has_no_year_based_unlock(self):
        world = World(seed=16, n_pop=12)
        founder = world.citizens[0]
        founder.entre = 1.0
        founder.risk = 1.0
        founder.learning = 1.0
        with patch.object(world.rng, "random", return_value=0.0):
            with patch.object(world, "found_business", return_value=True) as start:
                world.day = 0
                world.maybe_start_business(founder)
                world.day = DPY * 5
                world.maybe_start_business(founder)
        self.assertEqual(start.call_count, 2)

    def test_daily_cycle_does_not_inject_a_construction_company(self):
        world = World(seed=17, n_pop=12)
        world.day = DPY * 2
        for citizen in world.citizens:
            citizen.entre = 0.0

        world.daily()

        self.assertFalse(any(b.kind == "builder" for b in world.businesses))

    def test_generic_production_consumes_inputs_and_records_contracts(self):
        world = World(seed=18, n_pop=12)
        owner = world.citizens[0]
        world.set_cash(owner, 20_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        initial_stock = farm.stock
        farm.input_inventory["seeds"] = 0.05
        farm.input_costs["seeds"] = 20_000.0
        world._initialize_ledger()
        initial_inputs = farm.input_inventory["seeds"]
        world.import_supply_remaining["seeds"] = 0.1

        world.production_cycle(farm)

        self.assertGreater(farm.stock, initial_stock)
        self.assertLess(farm.input_inventory.get("seeds", 0.0), initial_inputs)
        self.assertGreater(farm.prod, 0)
        self.assertTrue(world.trade_contracts)
        self.assertEqual(world.reconcile_ledger(), {})
        self.assertTrue(all(
            abs(entry.debits - entry.credits) < 1e-7
            for entry in world.ledger.entries
        ))

    def test_production_fails_without_inputs_or_operating_cash(self):
        world = World(seed=19, n_pop=12)
        owner = world.citizens[0]
        world.set_cash(owner, 20_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        farm.cash = 0
        farm.input_inventory.clear()
        farm.input_costs.clear()
        farm.stock = 0
        world._initialize_ledger()

        world.production_cycle(farm)

        self.assertEqual(farm.stock, 0)
        self.assertEqual(farm.production_failed, "inputs_or_cash")
        self.assertEqual(world.reconcile_ledger(), {})

    def test_service_contract_records_tax_and_settlement_amount(self):
        world = World(seed=20, n_pop=12)
        provider_owner, buyer = world.citizens[:2]
        world.set_cash(provider_owner, 100_000_000)
        world.set_cash(buyer, 2_000_000)
        self.assertTrue(world.found_business(provider_owner, "repair", force=True))
        provider = provider_owner.business
        provider.service_inventory["repair"] = 1.0
        provider.service_costs["repair"] = 20_000.0
        world._initialize_ledger()
        price = provider.price
        tax = price * world.policy.tax_ppn
        buyer_cash = buyer.cash
        provider_cash = provider.cash
        treasury = world.treasury

        bought = world.buy_service(buyer, "repair", 1.0)

        self.assertAlmostEqual(bought, 1.0)
        self.assertAlmostEqual(buyer.cash, buyer_cash - price - tax)
        self.assertAlmostEqual(provider.cash, provider_cash + price)
        self.assertAlmostEqual(world.treasury, treasury + tax)
        contract = world.trade_contracts[-1]
        self.assertEqual(contract["buyer"], f"citizen:{buyer.id}")
        self.assertEqual(contract["seller"], f"business:{provider.ledger_id}")
        self.assertAlmostEqual(contract["tax_amount"], tax)
        self.assertAlmostEqual(contract["gross_amount"], price + tax)
        self.assertEqual(contract["status"], "settled")
        self.assertEqual(world.reconcile_ledger(), {})

    def test_service_contract_can_be_paid_entirely_from_savings(self):
        world = World(seed=24, n_pop=12)
        provider_owner, buyer = world.citizens[:2]
        world.set_cash(provider_owner, 100_000_000)
        world.set_cash(buyer, 2_000_000)
        self.assertTrue(world.found_business(provider_owner, "repair", force=True))
        provider = provider_owner.business
        provider.service_inventory["repair"] = 1.0
        provider.service_costs["repair"] = 20_000.0
        world._initialize_ledger()
        world.deposit(buyer, buyer.cash)
        price = provider.price
        gross = price * (1 + world.policy.tax_ppn)
        savings_before = buyer.savings

        bought = world.buy_service(buyer, "repair", 1.0)

        self.assertAlmostEqual(bought, 1.0)
        self.assertEqual(buyer.cash, 0)
        self.assertAlmostEqual(buyer.savings, savings_before - gross)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_goods_market_contract_records_tax_and_inventory_settlement(self):
        world = World(seed=22, n_pop=12)
        buyer, owner = world.citizens[:2]
        world.set_cash(owner, 100_000_000)
        world.set_cash(buyer, 1_000_000)
        world.deposit(buyer, 1_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        farm.stock = 5.0
        world._initialize_ledger()
        price = farm.price
        tax = price * world.policy.tax_ppn
        cash_before = buyer.cash
        savings_before = buyer.savings

        bought = world.buy_goods(buyer, 1.0)

        self.assertAlmostEqual(bought, 1.0)
        self.assertAlmostEqual(buyer.cash, cash_before)
        self.assertAlmostEqual(buyer.savings, savings_before - price - tax)
        contract = world.trade_contracts[-1]
        self.assertEqual(contract["product"], "food")
        self.assertAlmostEqual(contract["tax_amount"], tax)
        self.assertAlmostEqual(contract["gross_amount"], price + tax)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_goods_purchase_rounding_never_exceeds_available_funds(self):
        world = World(seed=23, n_pop=12)
        buyer, owner = world.citizens[:2]
        available = 3_149_403.3271747134
        world.set_cash(owner, 100_000_000.0)
        world.set_cash(buyer, available)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business
        farm.stock = 100.0
        farm.price = 96_431.24081723612
        world.policy.tax_ppn = 0.11
        world._initialize_ledger()

        bought = world.buy_goods(buyer, 100.0)

        self.assertGreater(bought, 0.0)
        self.assertGreaterEqual(buyer.cash, 0.0)
        self.assertLess(buyer.cash, available * 2e-14)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_market_prices_respond_to_observed_shortage_and_surplus(self):
        world = World(seed=23, n_pop=12)
        owner = world.citizens[0]
        world.set_cash(owner, 100_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        farm = owner.business

        farm.stock = 0.0
        farm.demand_today = 5.0
        farm.sold_today = 0.0
        world._initialize_ledger()
        shortage_price = farm.price
        world.adjust_prices({})
        self.assertGreater(farm.price, shortage_price)

        farm.stock = 200.0
        farm.demand_today = 0.0
        farm.sold_today = 0.0
        world._initialize_ledger()
        surplus_price = farm.price
        world.adjust_prices({})
        self.assertLess(farm.price, surplus_price)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_house_construction_does_not_partially_settle_service(self):
        world = World(seed=21, n_pop=12)
        buyer, contractor_owner = world.citizens[:2]
        world.set_cash(buyer, 50_000_000)
        world.set_cash(contractor_owner, 100_000_000)
        lot = world.buy_land(buyer)
        self.assertIsNotNone(lot)
        self.assertTrue(world.found_business(contractor_owner, "builder", force=True))
        builder = contractor_owner.business
        builder.service_inventory["construction"] = 1.0
        builder.service_costs["construction"] = 1_000_000.0
        world._initialize_ledger()
        world.set_cash(buyer, BUILD_COST * 1.05)
        before = (
            buyer.cash, dict(builder.service_inventory), tuple(world.trade_contracts),
            len(world.houses),
        )

        self.assertIsNone(world.build_house(buyer, lot))

        self.assertEqual(
            (buyer.cash, dict(builder.service_inventory), tuple(world.trade_contracts),
             len(world.houses)),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_house_construction_can_be_paid_from_savings(self):
        world = World(seed=25, n_pop=12)
        buyer, contractor_owner = world.citizens[:2]
        world.set_cash(buyer, 50_000_000)
        world.set_cash(contractor_owner, 100_000_000)
        lot = world.buy_land(buyer)
        self.assertIsNotNone(lot)
        self.assertTrue(world.found_business(contractor_owner, "builder", force=True))
        builder = contractor_owner.business
        builder.service_inventory["construction"] = 1.0
        builder.service_costs["construction"] = 1_000_000.0
        world._initialize_ledger()
        world.deposit(buyer, buyer.cash)
        self.assertEqual(buyer.cash, 0)
        self.assertGreater(buyer.savings, builder.price * (1 + world.policy.tax_ppn))

        home = world.build_house(buyer, lot)

        self.assertIsNotNone(home)
        self.assertEqual(buyer.cash, 0)
        self.assertGreater(buyer.savings, 0)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_service_purchase_from_savings_rolls_back_on_ledger_failure(self):
        world = World(seed=26, n_pop=12)
        provider_owner, buyer = world.citizens[:2]
        world.set_cash(provider_owner, 100_000_000)
        world.set_cash(buyer, 2_000_000)
        self.assertTrue(world.found_business(provider_owner, "repair", force=True))
        provider = provider_owner.business
        provider.service_inventory["repair"] = 1.0
        provider.service_costs["repair"] = 20_000.0
        world._initialize_ledger()
        world.deposit(buyer, buyer.cash)
        before = (
            buyer.cash, buyer.savings, world.bank.cash, world.bank.deposits,
            provider.cash, provider.rev, dict(provider.service_inventory),
            world.treasury, world.sales_today, tuple(world.trade_contracts),
            len(world.ledger.entries),
        )

        with patch.object(world.ledger, "record_snapshot_change",
                          side_effect=ValueError("injected ledger failure")):
            with self.assertRaisesRegex(ValueError, "injected ledger failure"):
                world.buy_service(buyer, "repair", 1.0)

        self.assertEqual(
            (
                buyer.cash, buyer.savings, world.bank.cash, world.bank.deposits,
                provider.cash, provider.rev, dict(provider.service_inventory),
                world.treasury, world.sales_today, tuple(world.trade_contracts),
                len(world.ledger.entries),
            ),
            before,
        )
        self.assertEqual(world.reconcile_ledger(), {})

    def test_house_sale_pays_the_seller_and_city_transfer_fee(self):
        world = World(seed=19, n_pop=12)
        seller, buyer = world.citizens[:2]
        home = world.houses[0]
        home.owner = seller
        seller.houses.append(home)
        mortgage = world.make_loan(seller, 10_000_000, 0.1, 240, "mortgage", home)
        seller.cash -= mortgage.balance
        price = home.value
        fee = price * 0.01
        buyer.cash = price + fee
        treasury = world.treasury

        self.assertTrue(world.buy_house(buyer, home))

        self.assertIs(home.owner, buyer)
        self.assertAlmostEqual(seller.cash, price - mortgage.balance)
        self.assertNotIn(mortgage, world.loans)
        self.assertAlmostEqual(world.bank.loan_book, 0)
        self.assertAlmostEqual(world.treasury, treasury + fee)

    def test_emotional_strain_reduces_work_capacity(self):
        world = World(seed=18, n_pop=12)
        citizen = world.citizens[0]
        baseline = citizen.work_capacity
        citizen.happy = 10
        citizen.stress = 1
        citizen.depression = 1

        self.assertEqual(citizen.emotion, "depresi")
        self.assertLess(citizen.work_capacity, baseline)

    def test_government_recapitalizes_bank_without_spending_city_reserve(self):
        world = World(seed=13, n_pop=12)
        world.day = DPY
        world.treasury = 1_000_000_000
        world.bank.loan_book = 100_000_000
        world.bank.equity = -10_000_000

        world.government_cycle()

        self.assertAlmostEqual(world.bank.equity, 8_000_000)
        self.assertAlmostEqual(world.treasury, 982_000_000)
        self.assertIn("BANK DIREKAPITALISASI PEMERINTAH", [event[2] for event in world.events])

    def test_business_foreclosure_recovers_collateral_before_owner_gets_assets(self):
        world = World(seed=11, n_pop=12)
        owner = world.citizens[0]
        self.assertTrue(world.found_business(owner, "farm", force=True))
        business = owner.business
        loan_balance = business.loan.balance
        expected_recovery = min(loan_balance, business.asset_value * 0.65)

        world.close_business(business)

        self.assertIsNone(owner.business)
        self.assertEqual(owner.cash, 0)
        self.assertAlmostEqual(world.bank.repossessed_assets, expected_recovery)
        self.assertAlmostEqual(world.bank.loan_book, 0, places=2)
        self.assertAlmostEqual(world.bank.loss, loan_balance - expected_recovery)

    def test_legacy_save_state_is_migrated(self):
        world = World(seed=7, n_pop=12)
        citizen = world.citizens[0]
        for attr in ("learning", "financial_literacy", "credit_score", "vehicle_value", "vehicle_color"):
            delattr(citizen, attr)
        for attr in ("persuasion", "construction_skill", "repair_skill", "stress",
                     "fear", "sadness", "depression", "gigs_done", "last_gig", "crimes"):
            delattr(citizen, attr)
        for lot in world.lots:
            delattr(lot, "land_owner")
        for house in world.houses:
            delattr(house, "base_structure_value")
        del world.bank.equity
        del world.bank.loan_book
        del world.bank.repossessed_assets
        del world.auto_policy
        del world.crime_history
        del world.gig_count
        del world.series["emosi"]
        del world.series["kriminal"]

        clone = pickle.loads(pickle.dumps(world, protocol=4))
        clone.migrate_save()

        self.assertEqual(clone.citizens[0].learning, 0.02)
        self.assertTrue(clone.auto_policy)
        self.assertEqual(clone.bank.loan_book, 0)
        self.assertEqual(len(clone.series["emosi"]), 0)
        self.assertIsNone(clone.lots[0].land_owner)

    def test_speed_controls_match_requested_values(self):
        from game.scene_game import SPEEDS

        self.assertEqual(SPEEDS, [0, 1, 2, 5, 10, 100])

    def test_save_roundtrip_and_long_run(self):
        sys.setrecursionlimit(20000)
        world = World(seed=9, n_pop=30)
        for _ in range(120):
            world.advance(24)
        clone = pickle.loads(pickle.dumps(world, protocol=4))
        self.assertEqual(clone.day, world.day)
        self.assertEqual(len(clone.citizens), len(world.citizens))
        clone.advance(24 * 10)

    def test_long_run_uses_production_and_market_contracts(self):
        world = World(seed=42, n_pop=40)
        world.advance(24 * 1100)

        self.assertTrue(any(b.kind == "farm" for b in world.businesses))
        self.assertTrue(world.trade_contracts)
        self.assertEqual(world.reconcile_ledger(), {})
        self.assertGreater(world.gig_count, 0)


if __name__ == "__main__":
    unittest.main()
