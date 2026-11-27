"""Age progression, dependent development, and condition-based birth decisions."""

from systems.agents.family import active_partner, children_of, guardians_of


ADULT_AGE = 18.0
CHILD_SUPPORT_COST = 50_000.0
MAX_DEPENDENT_CHILDREN = 2


def is_adult(citizen):
    return citizen.age >= ADULT_AGE


def advance_age(world, citizen):
    previous_age = citizen.age
    citizen.age += 1.0 / world.days_per_year
    if previous_age >= ADULT_AGE or citizen.age >= ADULT_AGE:
        if previous_age < ADULT_AGE:
            citizen.adult_since_day = world.day
        return

    guardians = guardians_of(world, citizen)
    caregiver_skill = (
        sum(guardian.skill for guardian in guardians) / len(guardians)
        if guardians else 0.0
    )
    school_attendance = (
        citizen.home is not None
        and 6.0 <= citizen.age < ADULT_AGE
        and citizen.health > 20.0
    )
    if school_attendance:
        citizen.school_days += 1
        citizen.education_level = min(
            1.0, citizen.education_level + 0.0002
        )
    citizen.skill = min(
        1.0, citizen.skill + 0.000012 + caregiver_skill * 0.000008
    )
    citizen.construction_skill = min(
        1.0,
        citizen.construction_skill + 0.000006 + caregiver_skill * 0.000003,
    )
    citizen.repair_skill = min(
        1.0, citizen.repair_skill + 0.000006 + caregiver_skill * 0.000003
    )
    citizen.learning = min(
        1.0, citizen.learning + 0.00004 * (1.0 - citizen.learning)
    )


def food_payer(world, citizen):
    if is_adult(citizen):
        return citizen
    guardians = guardians_of(world, citizen)
    if not guardians:
        return citizen
    return max(
        guardians,
        key=lambda guardian: (
            guardian.cash + guardian.savings,
            -guardian.id,
        ),
    )


def daily_mortality_probability(world, citizen):
    if citizen.age < 5.0:
        return 0.00002 if guardians_of(world, citizen) else 0.00012
    if citizen.age <= 65.0:
        return 0.0
    return min(0.8, (citizen.age - 65.0) * 0.015 + 0.005) / world.days_per_year


def consider_births(world):
    if len(world.citizens) >= world.max_population:
        return False
    for parent in world.citizens:
        if not parent.female or not 20.0 <= parent.age <= 40.0:
            continue
        partner = active_partner(world, parent)
        if (partner is None or partner.age < ADULT_AGE
                or parent.home is None or partner.home is not parent.home
                or parent.home.free <= 0):
            continue
        existing_children = [
            child for child in children_of(world, parent)
            if child.age < ADULT_AGE
        ]
        if len(existing_children) >= MAX_DEPENDENT_CHILDREN:
            continue
        edge = world.social_relationship(parent, partner)
        trust = (
            edge["trust"]
            if edge is not None and edge["status"] == "active"
            else 0.5
        )
        liquid = parent.cash + parent.savings + partner.cash + partner.savings
        stability = min(1.0, liquid / 5_000_000.0)
        health = min(parent.health, partner.health) / 100.0
        desire = (parent.parenting_desire + partner.parenting_desire) / 2.0
        readiness = (
            trust * 0.3
            + min(1.0, (parent.happy + partner.happy) / 200.0) * 0.25
            + stability * 0.25
            + health * 0.2
        )
        probability = 0.0015 * desire * readiness
        if (readiness >= 0.55 and liquid >= 250_000.0
                and world.rng.random() < probability):
            if world.birth_child(parent, partner):
                return True
    return False
