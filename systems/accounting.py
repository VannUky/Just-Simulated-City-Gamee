"""Double-entry journal used to audit the existing economy during migration."""

from collections import deque
from dataclasses import dataclass
from functools import wraps
import math


DEBIT = "debit"
CREDIT = "credit"
_EPSILON = 1e-7
_BROAD_TRANSACTION_FIELDS = {
    "weekly_start": {
        "Citizen": ("cash", "job", "thoughts"),
        "Business": (),
        "Hall": ("max_workers", "workers"),
    },
    "payroll": {
        "Citizen": (
            "cash", "job", "missed_pay", "learning", "financial_literacy",
            "thoughts",
        ),
        "Business": ("cash", "exp", "workers"),
        "Hall": ("workers",),
    },
    "gig_market": {
        "Citizen": (
            "cash", "gigs_done", "last_gig", "learning",
            "construction_skill", "repair_skill", "thoughts",
        ),
        "Business": ("cash", "rev", "exp"),
    },
    "crime_daily": {
        "Citizen": ("cash", "crimes", "stress", "fear", "thoughts"),
        "Business": (),
    },
    "buy_goods": {
        "Citizen": ("cash", "savings", "exp_acc"),
        "Business": (
            "cash", "stock", "rev", "sold_today", "demand_today",
        ),
    },
    "showroom_daily": {
        "Business": ("cash", "exp", "rev", "car_stock"),
    },
    "shop_restock": {
        "Business": (
            "age_days", "cash", "exp", "stock", "cost_avg", "rev",
        ),
    },
    "random_event": {
        "Business": ("stock", "cash"),
        "Asset": ("price", "hist"),
    },
    "yearly": {
        "Citizen": ("cash", "savings", "exp_acc"),
        "Business": ("cash", "exp"),
    },
    "production_cycle": {
        "Business": (
            "cash", "input_inventory", "input_costs", "service_inventory",
            "service_costs", "production_progress", "production_failed",
            "prod", "unit_cost", "quality", "stock", "car_stock", "exp",
            "age_days",
        ),
    },
    "adjust_prices": {
        "Business": (
            "price", "markup", "stock", "demand_today", "sold_today", "daily_demand",
            "soldout_hist", "over_hist", "age_days",
        ),
    },
}


def _copy_containers(value):
    if isinstance(value, dict):
        return {
            _copy_containers(key): _copy_containers(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_copy_containers(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_containers(item) for item in value)
    if isinstance(value, set):
        return {_copy_containers(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(_copy_containers(item) for item in value)
    if isinstance(value, deque):
        return deque(
            (_copy_containers(item) for item in value),
            maxlen=value.maxlen,
        )
    return value


def _capture_transaction_state(root, args, citizen_ids, business_ids,
                               include_all, include_businesses,
                               track_world_collections, method_name):
    domain_module = type(root).__module__
    random_states = []
    objects = {id(root): root}

    def add_domain_objects(value):
        if isinstance(value, dict):
            for key, item in value.items():
                add_domain_objects(key)
                add_domain_objects(item)
        elif isinstance(value, (list, tuple, set, frozenset, deque)):
            for item in value:
                add_domain_objects(item)
        elif type(value).__module__ == domain_module:
            if hasattr(value, "__dict__"):
                objects[id(value)] = value

    if include_all:
        add_domain_objects(root.citizens)
        add_domain_objects(root.businesses)
        add_domain_objects(root.hall)
        if method_name in ("monthly", "remove_citizen",
                           "migration_daily"):
            add_domain_objects(root.houses)
            add_domain_objects(root.loans)
        if method_name in (
                "remove_citizen", "migration_daily"):
            add_domain_objects(root.lots)
    else:
        if method_name == "migration_daily":
            add_domain_objects(root.citizens)
            add_domain_objects(root.businesses)
            add_domain_objects(root.houses)
            add_domain_objects(root.lots)
        for citizen in root.citizens:
            if citizen_ids is None or citizen.id in citizen_ids:
                objects[id(citizen)] = citizen
        for business in root.businesses:
            if (business_ids is None or include_businesses
                    or business.ledger_id in business_ids):
                objects[id(business)] = business
        for value in args:
            add_domain_objects(value)
        if method_name in ("found_business", "buy_land", "build_house"):
            add_domain_objects(root.lots)
        if method_name == "random_event":
            add_domain_objects(root.market.assets)

    objects[id(root.bank)] = root.bank
    if method_name == "government_cycle":
        objects[id(root.policy)] = root.policy

    related_fields = (
        "owner", "borrower", "ref", "home", "business", "job",
        "lot", "building", "land_owner",
    )
    if method_name not in _BROAD_TRANSACTION_FIELDS:
        for value in tuple(objects.values()):
            if value is root:
                continue
            for name in related_fields:
                add_domain_objects(getattr(value, name, None))

    generator = getattr(root, "rng", None)
    if type(generator).__module__ == "random" and hasattr(generator, "getstate"):
        random_states.append((generator, generator.getstate()))

    snapshots = []
    world_collections = {"citizens", "businesses", "houses", "loans"}
    for value in objects.values():
        fields = _BROAD_TRANSACTION_FIELDS.get(method_name, {}).get(
            type(value).__name__
        )
        if fields is not None:
            state = {
                name: _copy_containers(getattr(value, name))
                for name in fields
            }
            snapshots.append((value, state, fields))
            continue
        state = {}
        for name, item in value.__dict__.items():
            if value is root and name in (
                    "series", "ledger", "lots", "vroads", "hroads", "sales_hist"):
                state[name] = item
            elif (value is root and name in world_collections
                  and not track_world_collections):
                state[name] = item
            elif name in ("hist", "ticks") and method_name != "random_event":
                state[name] = item
            else:
                state[name] = _copy_containers(item)
        snapshots.append((value, state, None))
    return snapshots, random_states


def _restore_transaction_state(snapshot):
    object_states, random_states = snapshot
    for value, state, fields in object_states:
        if fields is None:
            value.__dict__.clear()
            value.__dict__.update(state)
        else:
            for name, item in state.items():
                setattr(value, name, item)
    for generator, state in random_states:
        generator.setstate(state)


@dataclass
class LedgerAccount:
    name: str
    normal_balance: str
    balance: float = 0.0


@dataclass(frozen=True)
class Posting:
    account: str
    side: str
    amount: float


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    day: int
    category: str
    description: str
    postings: tuple
    counterpart: str = ""

    @property
    def debits(self):
        return sum(p.amount for p in self.postings if p.side == DEBIT)

    @property
    def credits(self):
        return sum(p.amount for p in self.postings if p.side == CREDIT)


class AccountingLedger:
    SCHEMA_VERSION = 2
    MAX_RETAINED_ENTRIES = 10_000
    # Legacy journals included these UI metrics separately from bank equity.
    RECONCILIATION_IGNORED_ACCOUNTS = frozenset(("bank:profit", "bank:loss"))

    def __init__(self):
        self.schema_version = self.SCHEMA_VERSION
        self.accounts = {}
        self.entries = deque(maxlen=self.MAX_RETAINED_ENTRIES)
        self.archived_entry_count = 0
        self.archived_totals = {}
        self.next_sequence = 1

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.archived_entry_count = getattr(self, "archived_entry_count", 0)
        self.archived_totals = getattr(self, "archived_totals", {})
        old_entries = getattr(self, "entries", ())
        if (isinstance(old_entries, deque)
                and old_entries.maxlen == self.MAX_RETAINED_ENTRIES):
            return

        self.entries = deque(maxlen=self.MAX_RETAINED_ENTRIES)
        for entry in old_entries:
            if len(self.entries) == self.MAX_RETAINED_ENTRIES:
                self._archive_entry(self.entries.popleft())
            self.entries.append(entry)

    def _archive_entry(self, entry):
        summary = self.archived_totals.setdefault(entry.category, {
            "count": 0,
            "debits": 0.0,
            "credits": 0.0,
            "first_day": entry.day,
            "last_day": entry.day,
        })
        summary["count"] += 1
        summary["debits"] += entry.debits
        summary["credits"] += entry.credits
        summary["first_day"] = min(summary["first_day"], entry.day)
        summary["last_day"] = max(summary["last_day"], entry.day)
        self.archived_entry_count += 1

    def ensure_account(self, name, normal_balance=DEBIT):
        if normal_balance not in (DEBIT, CREDIT):
            raise ValueError("Saldo normal akun harus debit atau kredit.")
        account = self.accounts.get(name)
        if account is None:
            account = LedgerAccount(name, normal_balance)
            self.accounts[name] = account
        elif account.normal_balance != normal_balance:
            raise ValueError(f"Saldo normal akun {name!r} tidak konsisten.")
        return account

    def post(self, day, category, description, debits, credits, counterpart="",
             normal_balances=None):
        normalized_debits = self._normalize_side(debits, DEBIT)
        normalized_credits = self._normalize_side(credits, CREDIT)
        debit_total = sum(normalized_debits.values())
        credit_total = sum(normalized_credits.values())
        if not math.isclose(debit_total, credit_total, rel_tol=1e-12, abs_tol=_EPSILON):
            raise ValueError(
                f"Jurnal tidak seimbang: debit {debit_total:.8f}, "
                f"kredit {credit_total:.8f}."
            )
        if not normalized_debits and not normalized_credits:
            return None

        day = int(day)
        category = str(category)
        description = str(description)
        counterpart = str(counterpart)
        normal_balances = normal_balances or {}
        account_names = set(normalized_debits) | set(normalized_credits)
        new_accounts = {}
        balance_updates = {}
        for name in account_names:
            normal_balance = normal_balances.get(name, DEBIT)
            if normal_balance not in (DEBIT, CREDIT):
                raise ValueError(f"Saldo normal akun {name!r} tidak valid.")
            account = self.accounts.get(name)
            if account is not None:
                if (name in normal_balances
                        and account.normal_balance != normal_balance):
                    raise ValueError(f"Saldo normal akun {name!r} tidak konsisten.")
            else:
                account = LedgerAccount(name, normal_balance)
                new_accounts[name] = account
            amount = normalized_debits.get(name, 0.0) - normalized_credits.get(name, 0.0)
            next_balance = account.balance + amount
            if not math.isfinite(next_balance):
                raise ValueError(f"Saldo akun {name!r} menjadi tidak valid.")
            balance_updates[name] = next_balance

        postings = []
        for side, amounts in ((DEBIT, normalized_debits), (CREDIT, normalized_credits)):
            for name, amount in amounts.items():
                postings.append(Posting(name, side, amount))

        entry = JournalEntry(
            sequence=self.next_sequence,
            day=day,
            category=category,
            description=description,
            postings=tuple(postings),
            counterpart=counterpart,
        )

        archive_update = None
        if len(self.entries) >= self.MAX_RETAINED_ENTRIES:
            if not isinstance(self.entries, deque):
                raise ValueError("Riwayat jurnal tidak memiliki struktur yang valid.")
            old_entry = self.entries[0]
            old_summary = self.archived_totals.get(old_entry.category)
            if old_summary is None:
                archive_update = {
                    "count": 1,
                    "debits": old_entry.debits,
                    "credits": old_entry.credits,
                    "first_day": old_entry.day,
                    "last_day": old_entry.day,
                }
            else:
                archive_update = {
                    "count": old_summary["count"] + 1,
                    "debits": old_summary["debits"] + old_entry.debits,
                    "credits": old_summary["credits"] + old_entry.credits,
                    "first_day": min(old_summary["first_day"], old_entry.day),
                    "last_day": max(old_summary["last_day"], old_entry.day),
                }

        self.accounts.update(new_accounts)
        for name, balance in balance_updates.items():
            self.accounts[name].balance = balance
        self.next_sequence += 1
        if archive_update is not None:
            self.archived_totals[old_entry.category] = archive_update
            self.archived_entry_count += 1
            self.entries.popleft()
        self.entries.append(entry)
        return entry

    def seed_opening_balances(self, day, snapshot, source_prefix="opening_source"):
        for name, (amount, normal_balance) in sorted(snapshot.items()):
            amount = float(amount)
            if not math.isfinite(amount):
                raise ValueError(f"Saldo awal akun {name!r} tidak valid.")
            if abs(amount) <= _EPSILON:
                self.ensure_account(name, normal_balance)
                continue
            self.ensure_account(name, normal_balance)
            side = normal_balance if amount > 0 else (
                CREDIT if normal_balance == DEBIT else DEBIT
            )
            source = f"{source_prefix}:{name}"
            if side == DEBIT:
                self.post(day, "opening_balance", f"Saldo awal {name}",
                          {name: abs(amount)}, {source: abs(amount)}, source)
            else:
                self.post(day, "opening_balance", f"Saldo awal {name}",
                          {source: abs(amount)}, {name: abs(amount)}, source)

    def migrate_schema(self, day, snapshot):
        if self.schema_version == self.SCHEMA_VERSION:
            return
        if self.schema_version != 1 or self.SCHEMA_VERSION != 2:
            raise ValueError(
                f"Versi ledger {self.schema_version!r} tidak didukung."
            )

        missing_inventory = {}
        normals = {}
        for name, (amount, normal_balance) in snapshot.items():
            if not (name.startswith("business:") and name.endswith(":inventory")):
                continue
            if name in self.accounts:
                continue
            value = float(amount)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Saldo migrasi akun {name!r} tidak valid.")
            missing_inventory[name] = value
            normals[name] = normal_balance

        total = sum(missing_inventory.values())
        if total > _EPSILON:
            self.post(
                day, "ledger_schema_migration",
                "Saldo pembukaan inventaris usaha",
                missing_inventory,
                {"opening_source:business_inventory_v2": total},
                "opening_source:business_inventory_v2",
                normal_balances={
                    **normals,
                    "opening_source:business_inventory_v2": CREDIT,
                },
            )
        for name, normal_balance in normals.items():
            self.ensure_account(name, normal_balance)
        self.schema_version = self.SCHEMA_VERSION

    def record_snapshot_change(self, day, category, description, before, after,
                               counterpart):
        names = set(before) | set(after)
        debits = {}
        credits = {}
        normal_balances = {}
        for name in sorted(names):
            old_amount, old_normal = before.get(name, (0.0, after.get(name, (0.0, DEBIT))[1]))
            new_amount, new_normal = after.get(name, (0.0, old_normal))
            if old_normal != new_normal:
                raise ValueError(f"Saldo normal akun {name!r} berubah saat transaksi.")
            account = self.accounts.get(name)
            if account is not None and account.normal_balance != new_normal:
                raise ValueError(f"Saldo normal akun {name!r} tidak konsisten.")
            normal_balances[name] = new_normal
            delta = float(new_amount) - float(old_amount)
            if not math.isfinite(delta):
                raise ValueError(f"Perubahan saldo akun {name!r} tidak valid.")
            if abs(delta) <= _EPSILON:
                continue
            side = old_normal if delta > 0 else (
                CREDIT if old_normal == DEBIT else DEBIT
            )
            target = debits if side == DEBIT else credits
            target[name] = target.get(name, 0.0) + abs(delta)

        debit_total = sum(debits.values())
        credit_total = sum(credits.values())
        imbalance = debit_total - credit_total
        if abs(imbalance) <= _EPSILON:
            return self.post(
                day, category, description, debits, credits,
                normal_balances=normal_balances,
            )

        if not counterpart:
            raise ValueError(f"Transaksi {category!r} membutuhkan akun lawan.")
        counterpart_account = self.accounts.get(counterpart)
        if (counterpart_account is not None
                and counterpart_account.normal_balance != DEBIT):
            raise ValueError(f"Saldo normal akun {counterpart!r} tidak konsisten.")
        normal_balances[counterpart] = DEBIT
        if imbalance > 0:
            credits[counterpart] = credits.get(counterpart, 0.0) + imbalance
        else:
            debits[counterpart] = debits.get(counterpart, 0.0) - imbalance
        return self.post(
            day, category, description, debits, credits, counterpart,
            normal_balances,
        )

    def reconcile(self, snapshot, tolerance=0.01):
        discrepancies = {}
        for name, (actual, normal_balance) in snapshot.items():
            account = self.accounts.get(name)
            if account is None:
                expected_signed = float(actual) if normal_balance == DEBIT else -float(actual)
                if abs(expected_signed) > tolerance:
                    discrepancies[name] = (0.0, expected_signed)
                continue
            if account.normal_balance != normal_balance:
                discrepancies[name] = (account.balance, float("nan"))
                continue
            expected_signed = float(actual) if normal_balance == DEBIT else -float(actual)
            if not math.isclose(account.balance, expected_signed,
                                rel_tol=1e-12, abs_tol=tolerance):
                discrepancies[name] = (account.balance, expected_signed)
        for name, account in self.accounts.items():
            if name in self.RECONCILIATION_IGNORED_ACCOUNTS:
                continue
            if name.startswith(("counterpart:", "opening_source:")):
                continue
            if name not in snapshot and abs(account.balance) > tolerance:
                discrepancies[name] = (account.balance, 0.0)
        return discrepancies

    @property
    def counterpart_balances(self):
        prefixes = ("counterpart:", "opening_source:")
        return {
            name: account.balance
            for name, account in self.accounts.items()
            if name.startswith(prefixes) and abs(account.balance) > _EPSILON
        }

    @staticmethod
    def _normalize_side(amounts, side):
        normalized = {}
        for name, raw_amount in amounts.items():
            amount = float(raw_amount)
            if not name or not math.isfinite(amount) or amount < 0:
                raise ValueError(f"Posting {side} tidak valid untuk akun {name!r}.")
            if amount > _EPSILON:
                normalized[name] = normalized.get(name, 0.0) + amount
        return normalized


def ledgered_transaction(category, counterpart="", include_all=False,
                         include_businesses=False,
                         track_world_collections=False,
                         business_selector=None):
    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            ledger = getattr(self, "ledger", None)
            if ledger is None or getattr(self, "_ledger_capture_depth", 0):
                return method(self, *args, **kwargs)

            citizen_ids = set()
            business_ids = set()
            for value in args:
                if hasattr(value, "loans") and hasattr(value, "cash") and hasattr(value, "id"):
                    citizen_ids.add(value.id)
                elif hasattr(value, "ledger_id") and hasattr(value, "cash"):
                    business_ids.add(value.ledger_id)
                elif hasattr(value, "borrower"):
                    citizen_ids.add(value.borrower.id)
                    reference = getattr(value, "ref", None)
                    owner = getattr(reference, "owner", None)
                    if owner is not None and hasattr(owner, "id"):
                        citizen_ids.add(owner.id)
                    if hasattr(reference, "ledger_id"):
                        business_ids.add(reference.ledger_id)
                else:
                    owner = getattr(value, "owner", None)
                    if owner is not None and hasattr(owner, "id"):
                        citizen_ids.add(owner.id)
            if include_all:
                scoped_citizens = None
                scoped_businesses = None
            else:
                scoped_citizens = citizen_ids
                if business_selector is not None:
                    scoped_businesses = {
                        business.ledger_id
                        for business in business_selector(self, *args, **kwargs)
                    }
                else:
                    scoped_businesses = None if include_businesses else business_ids
            before = self._ledger_snapshot(scoped_citizens, scoped_businesses)
            transaction_state = _capture_transaction_state(
                self, args, scoped_citizens, scoped_businesses,
                include_all, include_businesses, track_world_collections,
                method.__name__,
            )
            self._ledger_capture_depth = 1
            try:
                result = method(self, *args, **kwargs)
                after = self._ledger_snapshot(scoped_citizens, scoped_businesses)
                ledger.record_snapshot_change(
                    self.day, category, method.__name__, before, after, counterpart
                )
                return result
            except Exception:
                _restore_transaction_state(transaction_state)
                raise
            finally:
                self._ledger_capture_depth = 0

        return wrapped
    return decorate
