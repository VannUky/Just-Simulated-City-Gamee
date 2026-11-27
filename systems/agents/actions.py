"""Declarative planning actions and validated execution through World APIs."""
import math

from systems.agents.planner import PlanningAction


def planning_state(world, citizen):
    liquid = max(0.0, citizen.cash) + max(0.0, citizen.savings)
    reserve = max(3.0 * citizen.est_exp, 5_000_000.0)
    buildable_lots = [
        lot for lot in world.lots
        if lot.land_owner is citizen and lot.building is None
        and lot.kind == "biz"
    ]
    available_lots = [
        lot for lot in world.lots
        if lot.kind == "biz" and lot.building is None
        and lot.land_owner is None
    ]
    builders = [
        business for business in world.businesses
        if business.market_product == "construction"
        and business.service_inventory.get("construction", 0.0) >= 1.0
        and business.price > 0
    ]
    has_job = citizen.job is not None
    has_home = any(house.owner is citizen for house in citizen.houses)
    facts = {
        "has_job": has_job,
        "owns_home": has_home,
        "has_buildable_lot": bool(buildable_lots),
        "has_available_lot": bool(available_lots),
        "builder_available": bool(builders),
    }
    for symbol in citizen.hold:
        facts[f"has_asset:{symbol}"] = True
    return {
        "facts": facts,
        "resources": {"money": max(0.0, liquid - reserve)},
    }


def available_actions(world, citizen, state):
    facts = state["facts"]
    actions = []

    if not facts["has_job"] and citizen.age < 60 and citizen.business is None:
        employers = [
            workplace for workplace in world.workplaces()
            if workplace.vacancies > 0 and workplace.can_hire()
        ]
        if employers:
            actions.append(PlanningAction(
                "seek_employment",
                preconditions={"has_job": False},
                effects={"has_job": True},
                duration=1.0,
                risk=0.05,
                base_cost=0.5,
            ))

    if facts["has_available_lot"] and not facts["has_buildable_lot"]:
        actions.append(PlanningAction(
            "buy_land",
            preconditions={
                "has_available_lot": True,
                "has_buildable_lot": False,
            },
            effects={
                "has_available_lot": False,
                "has_buildable_lot": True,
            },
            resource_costs={"money": world.lot_price},
            duration=2.0,
            risk=0.05,
            base_cost=1.0,
        ))

    builders = [
        business for business in world.businesses
        if business.market_product == "construction"
        and business.service_inventory.get("construction", 0.0) >= 1.0
        and business.price > 0
    ]
    if builders:
        builder = min(builders, key=lambda business: business.price)
        contract_cost = builder.price * (1.0 + world.policy.tax_ppn)
        actions.append(PlanningAction(
            "build_house",
            preconditions={
                "has_buildable_lot": True,
                "builder_available": True,
                "owns_home": False,
            },
            effects={
                "has_buildable_lot": False,
                "owns_home": True,
            },
            resource_costs={"money": contract_cost},
            duration=5.0,
            risk=0.08,
            base_cost=1.0,
        ))

    for symbol, position in citizen.hold.items():
        asset = world.market.assets.get(symbol)
        if asset is None or asset.halted:
            continue
        try:
            units = float(position[0])
            tax_rate = (
                world.policy.tax_stock if asset.kind == "stock"
                else world.policy.tax_crypto
            )
            proceeds = units * asset.price * (1.0 - tax_rate)
            volatility = float(asset.vol)
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        if (not math.isfinite(units) or units <= 0
                or not math.isfinite(proceeds) or proceeds <= 0
                or not math.isfinite(volatility) or volatility < 0):
            continue
        actions.append(PlanningAction(
            "sell_asset",
            parameters={"symbol": symbol},
            preconditions={f"has_asset:{symbol}": True},
            effects={f"has_asset:{symbol}": False},
            resource_gains={"money": proceeds},
            duration=1.0,
            risk=volatility,
            base_cost=0.5,
        ))
    return actions


def execute_action(world, citizen, action):
    """Execute one planned step and revalidate it through the economy API."""
    if action.action_id == "seek_employment":
        return world.try_seek_job(citizen)
    if action.action_id == "buy_land":
        return world.buy_land(citizen) is not None
    if action.action_id == "build_house":
        owned = [
            lot for lot in world.lots
            if lot.land_owner is citizen and lot.building is None
            and lot.kind == "biz"
        ]
        return bool(owned and world.build_house(citizen, owned[0]))
    if action.action_id == "sell_asset":
        symbol = action.parameters.get("symbol")
        if not isinstance(symbol, str) or symbol not in citizen.hold:
            return False
        return world.sell_asset(citizen, symbol) > 0
    raise ValueError(f"Aksi planner tidak dikenal: {action.action_id}")
