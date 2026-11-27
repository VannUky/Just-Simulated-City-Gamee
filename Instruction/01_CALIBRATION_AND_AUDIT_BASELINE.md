# Reference: Codebase Audit Baseline & Macro Calibration Data

## 1. Existing Repository Architecture (Audit Summary)
- **`main.py`**: Pygame main loop, UI rendering dispatch, and full `World` state persistence via `pickle`. User settings are saved separately as JSON. No SQLite or external AI modules exist in the active game.
- **`systems/ekonomi_core.py`**: Core simulation engine. `World.daily()` drives daily economic ticks (wages, shops/farms/factories, taxes, savings, loans, real estate, synthetic stock market, gigs, crime, government actions).
  - **Time Base**: `HPD = 24` hours/day, `30` days/month, `360` days/year (note: price charts sample 8 ticks/day).
  - **Agent State (`Citizen`)**: Has personality traits, needs, credit score, emotions, and short thought history. `Citizen.learn()` currently caps literacy/learning at `0..1` without altering decision policies.
  - **Demographics**: Supports aging, death, immigration (`young=True` spawns ages 18–26), and asset inheritance (currently picks a random living adult, **not** kinship). Births and parent-child trees do not exist yet.
- **`game/` (`scene_game.py`, `windows.py`, `city_view.py`, `settings.py`)**: UI views, inspection windows, and player policy/intervention controls.
- **`tests/` (`test_ekonomi_core.py`, `test_main.py`)**: Existing test suite (44 tests passing at baseline).

### Key Economic Gaps Identified in Audit
1. **Macro Metrics**: CPI currently averages raw shop prices (unweighted); GDP currently measures 30-day retail turnover rather than value-added production (`World.record()`).
2. **Stock Market**: Prices follow synthetic paths decoupled from corporate net profit, P/E ratios, or actual dividend payouts.
3. **Scripted Bootstrapping**: Early businesses and first contractors can receive hardcoded government subsidies/triggers instead of emerging purely from capital, credit, and contracts.
4. **Disconnected Flows**: Food rations deduct government treasury without paying food producers; construction routes 75% of cost to treasury without an underlying building-materials market; bank initial capital and city treasury were initialized separately.

---

## 2. Draft Calibration & Causal Knowledge Reference (DO NOT BLINDLY IMPORT)
The developer provided a standalone prototype script (`calibration_data` & `causal_knowledge`) intended as economic reference parameters.

> **CRITICAL WARNING FOR CLINE:**
> - **Do NOT** run the standalone SQLite generator (`economy_sim.db`) as a second source of truth alongside `pickle` saves.
> - **Unit Mismatch:** The active engine uses Rupiah-scale values (`Citizen` starts at `Rp 0`, houses ~`Rp 330M`), whereas the draft data uses abstract `"Coin"` units (`minimum_daily_wage = 100.0`, `daily_rent_cost = 30.0`). Define an explicit `COIN_TO_IDR` conversion constant and unify daily vs. monthly wage periods before applying these ratios.

### A. Macro Calibration Ratios (`calibration_data`)
- **Meta**: `currency_unit="Coin"`, `ticks_per_day=24`, `days_per_year=360`
- **Baseline Prices & Wages**:
  - `basic_food_price`: `15.0` (2 meals/day = 30 Coin = 30% of minimum daily wage)
  - `luxury_good_price`: `80.0`
  - `raw_material_price`: `8.0`
  - `daily_rent_cost`: `30.0`
  - `minimum_daily_wage`: `100.0` | `skilled_daily_wage`: `220.0`
  - `startup_shop_capital`: `1500.0` | `startup_factory_capital`: `8000.0`
- **Monetary & Banking**:
  - `target_annual_inflation`: `0.03` (3%)
  - `central_bank_base_rate`: `0.06` (6%)
  - `bank_loan_spread`: `+0.045` (loan rate 10.5%) | `bank_deposit_spread`: `-0.015` (deposit rate 4.5%)
  - `bank_reserve_ratio`: `0.10` (10% reserve, 90% lendable)
  - `max_debt_to_income_ratio`: `0.35` (max installment 35% of income)
  - `default_penalty_credit_score`: `-150`
- **Fiscal & Taxes**:
  - `income_tax_rate_low`: `0.05` (wage < 150) | `income_tax_rate_high`: `0.15` (wage >= 150)
  - `corporate_tax_rate`: `0.22` (22% net profit)
  - `sales_tax_vat_rate`: `0.11` (11% PPN)
  - `unemployment_welfare_daily`: `25.0`
- **Market Elasticity & Physics**:
  - `food_price_elasticity`: `-0.30` (inelastic) | `luxury_price_elasticity`: `-1.50` (elastic)
  - `price_adjustment_speed`: `0.05` | `wage_adjustment_speed`: `0.02` (sticky wages)
  - `bankruptcy_threshold_cash`: `-500.0`
  - `base_crime_catch_probability`: `0.40`
- **Stock Market**:
  - `pe_ratio_baseline`: `12.0` | `sentiment_volatility`: `0.08` | `dividend_payout_ratio`: `0.30`

### B. Causal Domain Rules (`KB_01` – `KB_12`)
These 12 cause-effect chains define expected macro/micro feedback loops that the simulation mechanics (Phase 2+) and agent knowledge system (Phase 4+) should support naturally:
- **`KB_01` (Market — Excess Demand)**: Low stock + high demand -> price rises -> higher seller margin -> attracts new producers/sellers -> stock recovers.
- **`KB_02` (Market — Excess Supply)**: Full warehouse + unsold goods -> price discounts -> thinner margins -> inefficient firms cut output or lay off workers.
- **`KB_03` (Labor — Tight Labor Market)**: Low unemployment + open vacancies -> wage bidding -> higher operating costs -> cost-push price inflation.
- **`KB_04` (Monetary — High Inflation)**: Money supply outpaces goods output -> falling real wage purchasing power -> luxury spending drops -> Central Bank raises base rate.
- **`KB_05` (Banking — Rate Hike)**: Central Bank raises rate -> loan interest rises -> firms delay expansion loans -> hiring slows, saving rises -> inflation cools.
- **`KB_06` (Banking — Rate Cut)**: Central Bank lowers rate -> cheap credit -> entrepreneurs borrow for shops/factories -> jobs & consumption grow -> equities rise.
- **`KB_07` (Banking — Liquidity Crisis / Bank Run)**: High NPLs + depositor panic -> bank depletes 10% cash reserve -> lending freezes -> working capital crunch -> recession.
- **`KB_08` (Government — Corporate Tax Hike)**: Net profit taxed -> lower business investment -> wage cuts/layoffs -> potential Laffer contraction in long-term tax revenue.
- **`KB_09` (Government — Income/VAT Hike)**: Lower disposable income -> luxury demand drops first -> consumption shifts toward basic food & rent.
- **`KB_10` (Crime — Economic Desperation)**: High unemployment + expensive food + zero cash -> honesty threshold weakens (`Food Value > Catch Prob * Penalty`) -> theft rises -> shops raise prices or hire security.
- **`KB_11` (Finance — Equity Valuation)**: Rising corporate net profit + low deposit rates -> capital flows to stocks -> P/E > 25 risks bubble correction; P/E < 12 with profit growth attracts value buyers.
- **`KB_12` (Agriculture — Food Supply Shock)**: Crop failure / raw material spike -> inelastic food absorbs household budgets -> non-food sectors suffer sharp revenue drop.
