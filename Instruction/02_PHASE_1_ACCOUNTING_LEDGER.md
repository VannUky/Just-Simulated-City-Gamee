# PHASE 1: Centralized Accounting Ledger [STATUS: COMPLETED / VERIFICATION REFERENCE]

## 1. Purpose & Status
Phase 1 established the financial backbone of the simulation (`systems/accounting.py` integrated into `systems/ekonomi_core.py`).
**If you are starting Phase 2 or later:** Do NOT re-implement Phase 1 from scratch. Instead, verify all invariants below hold and route every new economic mechanic in Phase 2+ through this ledger.

---

## 2. Core Architecture & Rules
1. **Double-Entry Transaction Model (`systems/accounting.py`)**:
   - Every financial event is recorded via `post_transaction(tx_type, entries, tick, reason, metadata)` where `sum(debits) == sum(credits)` (within floating-point tolerance or integer cents/rupiah).
   - **Atomic Execution**: If any account lacks sufficient funds (and overdraft/credit is not explicitly permitted for that account type), the transaction fails atomically with **zero partial balance mutations**.
   - **Typed Chart of Accounts**: Distinguishes Households (`citizen`), Businesses (`business`), Commercial Banks (`bank`), Central Bank / Monetary Authority (`central_bank`), Government Treasury (`government`), Equity Market Clearing (`market_clearing`), and Player Intervention (`player_intervention`).
2. **Explicit Transaction Categories**:
   - `wage`, `tax_income`, `tax_corporate`, `tax_vat`, `welfare`, `deposit`, `withdrawal`, `interest_deposit`, `interest_loan`, `loan_disbursement`, `loan_repayment`, `retail_sale`, `b2b_supply`, `rent`, `real_estate_trade`, `construction`, `equity_trade`, `dividend`, `seizure_fine`, `inheritance`, `player_intervention`, and `legacy_opening_balance`.
3. **Money Creation Discipline**:
   - Standard transfers redistribute existing money (`total_money_supply` unchanged).
   - Money supply may expand/contract **only** through explicit monetary mechanisms (e.g., central bank liquidity injection or fractional-reserve bank credit creation creating matched `loan_receivable` asset + `deposit_liability`) or logged `player_intervention`.
   - Bank initial capital is transferred/recorded from a valid funding account—never duplicated out of thin air alongside city treasury.
4. **Object Balance Synchronization & Pickle Compatibility**:
   - Legacy attributes (`citizen.cash`, `citizen.savings`, `world.treasury`, `bank.cash`, etc.) are synchronized projections of ledger accounts so existing UI and tests continue working.
   - Legacy pickle saves migrate idempotently via `World.migrate_save()` by generating `legacy_opening_balance` entries without fabricating historical transactions.
   - Bounded transaction history retention (rolling window / summary snapshots) prevents unbounded pickle file bloat over multi-decade simulations.

---

## 3. Mandatory Verification Checklist (Run Before Phase 2)
Before writing Phase 2 code, confirm via `pytest`:
- [ ] Every posted transaction satisfies `total_debit == total_credit`.
- [ ] Failed transactions leave all account balances and entity attributes unchanged.
- [ ] Sum of ledger account balances reconciles with entity balance projections across citizens, businesses, banks, and government.
- [ ] Player cash-set / debug tools log `player_intervention` transactions.
- [ ] Loading an old pickle save and re-saving preserves exact balances and passes idempotent migration twice.
