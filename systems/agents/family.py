"""Persistent family ties, guardianship, and consent-based partnerships."""

from systems.agents.social import relationship


MAX_FAMILY_EVENTS = 2_000
MAX_PARTNERSHIP_PROPOSALS = 256


def new_family_state():
    return {
        "relationships": {},
        "partners": {},
        "guardians": {},
        "proposals": {},
        "events": [],
        "next_proposal_id": 1,
    }


def ensure_family_state(world):
    if not isinstance(getattr(world, "family_state", None), dict):
        world.family_state = new_family_state()
    state = world.family_state
    partner_index_missing = "partners" not in state
    for key, value in new_family_state().items():
        if key not in state:
            state[key] = value
    if partner_index_missing:
        state["partners"] = {
            str(edge["source_id"]): edge["target_id"]
            for edge in state["relationships"].values()
            if edge["kind"] == "partner" and edge["status"] == "active"
        }
    return state


def _event(world, kind, source_id, target_id, outcome):
    events = ensure_family_state(world)["events"]
    events.append({
        "day": world.day,
        "kind": kind,
        "source_id": source_id,
        "target_id": target_id,
        "outcome": outcome,
    })
    if len(events) > MAX_FAMILY_EVENTS:
        del events[:-MAX_FAMILY_EVENTS]


def _edge_key(kind, source_id, target_id):
    return f"{kind}:{source_id}:{target_id}"


def _set_relation(world, kind, source_id, target_id, status="active"):
    state = ensure_family_state(world)
    key = _edge_key(kind, source_id, target_id)
    edge = state["relationships"].get(key)
    if edge is None:
        edge = {
            "kind": kind,
            "source_id": source_id,
            "target_id": target_id,
            "status": status,
            "since_day": world.day,
            "history": [{"day": world.day, "status": status}],
        }
        state["relationships"][key] = edge
    elif edge["status"] != status:
        edge["status"] = status
        edge["history"].append({"day": world.day, "status": status})
    if kind == "partner":
        source_key = str(source_id)
        if status == "active":
            state["partners"][source_key] = target_id
        elif state["partners"].get(source_key) == target_id:
            del state["partners"][source_key]
    return edge


def _citizen(world, citizen_id):
    return next(
        (citizen for citizen in world.citizens if citizen.id == citizen_id),
        None,
    )


def active_partner(world, citizen):
    state = ensure_family_state(world)
    partner_id = state["partners"].get(str(citizen.id))
    if partner_id is None:
        return None
    partner = _citizen(world, partner_id)
    if partner is None:
        del state["partners"][str(citizen.id)]
    return partner


def parents_of(world, child):
    state = ensure_family_state(world)
    parent_ids = {
        edge["source_id"]
        for edge in state["relationships"].values()
        if edge["kind"] == "parent" and edge["target_id"] == child.id
    }
    return [
        citizen for citizen_id in sorted(parent_ids)
        if (citizen := _citizen(world, citizen_id)) is not None
    ]


def children_of(world, parent):
    state = ensure_family_state(world)
    child_ids = {
        edge["target_id"]
        for edge in state["relationships"].values()
        if edge["kind"] == "parent" and edge["source_id"] == parent.id
    }
    return [
        citizen for citizen_id in sorted(child_ids)
        if (citizen := _citizen(world, citizen_id)) is not None
    ]


def siblings_of(world, citizen):
    state = ensure_family_state(world)
    sibling_ids = {
        edge["target_id"]
        for edge in state["relationships"].values()
        if edge["kind"] == "sibling" and edge["source_id"] == citizen.id
    }
    return [
        sibling for sibling_id in sorted(sibling_ids)
        if (sibling := _citizen(world, sibling_id)) is not None
    ]


def guardians_of(world, child):
    state = ensure_family_state(world)
    guardian_ids = state["guardians"].get(str(child.id), [])
    guardians = [
        guardian for guardian_id in guardian_ids
        if (guardian := _citizen(world, guardian_id)) is not None
        and guardian.age >= 18
    ]
    if guardians:
        return guardians
    return [
        parent for parent in parents_of(world, child)
        if parent.age >= 18
    ]


def appoint_guardian(world, child, guardian):
    if (child not in world.citizens or guardian not in world.citizens
            or child is guardian or child.age >= 18.0 or guardian.age < 18.0):
        raise ValueError("Wali harus warga dewasa untuk anak di bawah umur.")
    relatives = (
        guardian in parents_of(world, child)
        or child in children_of(world, guardian)
        or guardian in siblings_of(world, child)
    )
    edge = relationship(world, guardian, child)
    trusted = (
        edge is not None and edge["status"] == "active"
        and edge["trust"] >= 0.65
    )
    if not relatives and not trusted:
        raise ValueError("Wali harus kerabat atau warga tepercaya.")
    state = ensure_family_state(world)
    guardian_ids = state["guardians"].setdefault(str(child.id), [])
    if guardian.id not in guardian_ids:
        guardian_ids.append(guardian.id)
    _set_relation(world, "guardian", guardian.id, child.id)
    _event(world, "guardian_appointed", guardian.id, child.id, "active")
    return True


def _add_parent_child(world, parent, child):
    _set_relation(world, "parent", parent.id, child.id)
    existing = children_of(world, parent)
    for sibling in existing:
        if sibling.id == child.id:
            continue
        _set_relation(world, "sibling", child.id, sibling.id)
        _set_relation(world, "sibling", sibling.id, child.id)


def register_birth(world, parents, child):
    parents = list(dict.fromkeys(parents))
    if (not parents or child not in world.citizens
            or any(parent not in world.citizens or parent is child
                   for parent in parents)):
        raise ValueError("Relasi orang tua dan anak tidak valid.")
    for parent in parents:
        _add_parent_child(world, parent, child)
    guardian_ids = [
        parent.id for parent in parents
        if parent.age >= 18
    ]
    ensure_family_state(world)["guardians"][str(child.id)] = guardian_ids
    _event(world, "birth", parents[0].id, child.id, "registered")


def propose_partnership(world, proposer, recipient):
    if (proposer not in world.citizens or recipient not in world.citizens
            or proposer is recipient or proposer.age < 18
            or recipient.age < 18):
        raise ValueError("Pasangan harus dua warga dewasa yang berbeda.")
    if active_partner(world, proposer) or active_partner(world, recipient):
        raise ValueError("Salah satu warga sudah memiliki pasangan.")
    edge = relationship(world, proposer, recipient)
    if (edge is None or edge["status"] != "active"
            or edge["trust"] < 0.55):
        raise ValueError("Relasi sosial tepercaya diperlukan.")
    state = ensure_family_state(world)
    if any(
        proposal["status"] == "pending"
        and proposal["proposer_id"] == proposer.id
        and proposal["recipient_id"] == recipient.id
        for proposal in state["proposals"].values()
    ):
        raise ValueError("Lamaran pasangan masih menunggu jawaban.")
    while len(state["proposals"]) >= MAX_PARTNERSHIP_PROPOSALS:
        removable = next(
            (key for key, proposal in state["proposals"].items()
             if proposal["status"] != "pending"),
            None,
        )
        if removable is None:
            raise ValueError("Batas lamaran pasangan telah tercapai.")
        del state["proposals"][removable]
    proposal_id = state["next_proposal_id"]
    state["next_proposal_id"] += 1
    state["proposals"][str(proposal_id)] = {
        "id": proposal_id,
        "proposer_id": proposer.id,
        "recipient_id": recipient.id,
        "status": "pending",
        "created_day": world.day,
        "expires_day": world.day + 30,
    }
    _event(world, "partnership_proposed", proposer.id, recipient.id, "pending")
    return proposal_id


def respond_partnership(world, recipient, proposal_id, accept):
    if recipient not in world.citizens or not isinstance(accept, bool):
        raise ValueError("Jawaban lamaran pasangan tidak valid.")
    state = ensure_family_state(world)
    proposal = state["proposals"].get(str(proposal_id))
    if (proposal is None or proposal["status"] != "pending"
            or proposal["recipient_id"] != recipient.id):
        raise ValueError("Lamaran pasangan tidak aktif untuk warga ini.")
    proposer = _citizen(world, proposal["proposer_id"])
    if (proposer is None or world.day > proposal["expires_day"]
            or active_partner(world, proposer)
            or active_partner(world, recipient)):
        proposal["status"] = "expired"
        _event(
            world, "partnership_resolved", proposal["proposer_id"],
            recipient.id, "expired",
        )
        return False
    edge = relationship(world, proposer, recipient)
    if (edge is None or edge["status"] != "active"
            or edge["trust"] < 0.55):
        accept = False
    if not accept:
        proposal["status"] = "rejected"
        _event(
            world, "partnership_resolved", proposer.id, recipient.id,
            "rejected",
        )
        return False
    _set_relation(world, "partner", proposer.id, recipient.id)
    _set_relation(world, "partner", recipient.id, proposer.id)
    proposal["status"] = "accepted"
    proposal["resolved_day"] = world.day
    _event(world, "partnership_resolved", proposer.id, recipient.id, "accepted")
    target_home = next(
        (
            house for house in (recipient.home, proposer.home)
            if house is not None
            and (house.free > 0
                 or recipient.home is house and proposer.home is house)
        ),
        None,
    )
    if target_home is not None:
        for citizen in (proposer, recipient):
            if citizen.home is target_home:
                continue
            if citizen.home is not None and citizen in citizen.home.occupants:
                citizen.home.occupants.remove(citizen)
            if target_home.free > 0:
                world.move_in(citizen, target_home)
    return True


def family_heirs(world, deceased):
    state = ensure_family_state(world)
    ranked_ids = []
    partner = active_partner(world, deceased)
    if partner is not None:
        ranked_ids.append(partner.id)
    child_ids = sorted(
        (
            edge["target_id"]
            for edge in state["relationships"].values()
            if edge["kind"] == "parent"
            and edge["source_id"] == deceased.id
        ),
        key=lambda citizen_id: (
            _citizen(world, citizen_id) is None
            or _citizen(world, citizen_id).age < 18,
            citizen_id,
        ),
    )
    ranked_ids.extend(child_ids)
    ranked_ids.extend(
        edge["source_id"]
        for edge in state["relationships"].values()
        if edge["kind"] == "parent" and edge["target_id"] == deceased.id
    )
    ranked_ids.extend(
        edge["target_id"]
        for edge in state["relationships"].values()
        if edge["kind"] == "sibling"
        and edge["source_id"] == deceased.id
    )
    ranked_ids.extend(state["guardians"].get(str(deceased.id), []))
    heirs = []
    for citizen_id in ranked_ids:
        heir = _citizen(world, citizen_id)
        if (heir is not None and heir is not deceased and heir.age >= 18
                and heir not in heirs):
            heirs.append(heir)
    return heirs


def handle_removal(world, deceased, cause):
    state = ensure_family_state(world)
    for edge in state["relationships"].values():
        if deceased.id not in (edge["source_id"], edge["target_id"]):
            continue
        if edge["kind"] == "partner" and edge["status"] == "active":
            status = "widowed" if cause == "death" else "moved"
            _set_relation(
                world, "partner", edge["source_id"], edge["target_id"], status
            )
        elif edge["kind"] in ("parent", "sibling", "guardian") and edge["status"] == "active":
            edge["status"] = "historical"
            edge["history"].append({"day": world.day, "status": "historical"})
    for child_id, guardian_ids in list(state["guardians"].items()):
        if deceased.id not in guardian_ids:
            continue
        child = _citizen(world, int(child_id))
        living_parents = [
            parent.id for parent in parents_of(world, child)
            if parent is not deceased and parent.age >= 18
        ] if child is not None else []
        replacements = [
            guardian_id for guardian_id in guardian_ids
            if guardian_id != deceased.id
            and _citizen(world, guardian_id) is not None
            and _citizen(world, guardian_id).age >= 18
        ] + living_parents
        if child is not None and not replacements:
            replacements = [
                sibling.id for sibling in siblings_of(world, child)
                if sibling is not deceased and sibling.age >= 18
            ]
        state["guardians"][child_id] = list(dict.fromkeys(replacements))
        for guardian_id in replacements:
            _set_relation(world, "guardian", guardian_id, int(child_id))
    state["guardians"].pop(str(deceased.id), None)
    for proposal in state["proposals"].values():
        if (proposal["status"] == "pending"
                and deceased.id in (
                    proposal["proposer_id"], proposal["recipient_id"]
                )):
            proposal["status"] = "cancelled"
    _event(world, cause, deceased.id, None, "family ties preserved")


def handle_death(world, deceased):
    handle_removal(world, deceased, "death")


def handle_departure(world, citizen):
    handle_removal(world, citizen, "departure")


def teach_knowledge(world, teacher, child, observation_id, method="teaching"):
    if (teacher not in world.citizens or child not in world.citizens
            or teacher is child or child.age >= 18.0):
        raise ValueError("Transfer pengetahuan memerlukan pengajar dan anak.")
    is_parent_or_guardian = (
        child in children_of(world, teacher)
        or teacher in guardians_of(world, child)
    )
    apprenticeship = (
        method == "apprenticeship" and child.age >= 14.0
        and teacher.business is not None
        and child.home is teacher.home
    )
    if method == "apprenticeship" and not apprenticeship:
        raise ValueError("Apprenticeship memerlukan mentor usaha dan anak usia 14+.")
    if not is_parent_or_guardian and not apprenticeship:
        raise ValueError("Pengajar harus keluarga atau mentor yang layak.")
    if method not in ("teaching", "apprenticeship", "observation"):
        raise ValueError("Metode transfer pengetahuan tidak dikenal.")
    source = next(
        (item for item in teacher.knowledge.observations
         if item.id == observation_id),
        None,
    )
    if source is None:
        raise ValueError("Observasi pengajar tidak ditemukan.")
    edge = relationship(world, teacher, child)
    trust = edge["trust"] if edge and edge["status"] == "active" else 0.5
    probability = min(
        0.85,
        0.25 + teacher.skill * 0.2 + teacher.patience * 0.15
        + child.patience * 0.1 + trust * 0.15,
    )
    success = world.rng.random() < probability
    outcome = f"{method}:{teacher.id}:{source.id}:to:{child.id}"
    if success:
        values = {
            name: value + world.rng.normalvariate(
                0.0, max(0.01, abs(value) * 0.08)
            )
            for name, value in source.values.items()
        }
        context = dict(list(source.context.items())[:13])
        context.update({
            "family_transfer": True,
            "method": method,
            "teacher_id": teacher.id,
        })
        child.knowledge.observe(
            world.day,
            "social_information",
            outcome,
            values,
            context=context,
        )
    child.memory.record(
        world.day,
        "family",
        method,
        {"teacher_id": teacher.id},
        "menerima pengetahuan" if success else "pelajaran tidak terserap",
        success,
        impact=0.05,
        value=0.03 if success else -0.02,
    )
    _event(
        world, "knowledge_transfer", teacher.id, child.id,
        "learned" if success else "not_learned",
    )
    return success


def consider_teaching(world, teacher):
    if teacher not in world.citizens or teacher.age < 18.0:
        return False
    children = [
        child for child in children_of(world, teacher)
        if child.age < 18.0
    ]
    if not children or not teacher.knowledge.observations:
        return False
    world.rng.shuffle(children)
    child = children[0]
    source = teacher.knowledge.observations[-1]
    provenance = (
        f"teaching:{teacher.id}:{source.id}:to:{child.id}",
        f"apprenticeship:{teacher.id}:{source.id}:to:{child.id}",
        f"observation:{teacher.id}:{source.id}:to:{child.id}",
    )
    if any(item.source_id in provenance for item in child.knowledge.observations):
        return False
    if world.rng.random() > 0.02 * teacher.parenting_desire:
        return False
    method = (
        "apprenticeship"
        if child.age >= 14.0 and teacher.business is not None
        else "teaching"
    )
    teach_knowledge(world, teacher, child, source.id, method)
    return True


def consider_family_action(world, citizen):
    if citizen not in world.citizens or citizen.age < 18:
        return False
    state = ensure_family_state(world)
    proposal = next(
        (
            item for item in state["proposals"].values()
            if item["status"] == "pending"
            and item["recipient_id"] == citizen.id
        ),
        None,
    )
    if proposal is not None:
        proposer = _citizen(world, proposal["proposer_id"])
        edge = relationship(world, proposer, citizen) if proposer else None
        trust = edge["trust"] if edge and edge["status"] == "active" else 0.0
        age_fit = max(0.0, 1.0 - abs(citizen.age - proposer.age) / 40.0) if proposer else 0.0
        stability = min(
            1.0,
            max(0.0, (citizen.cash + citizen.savings) / 10_000_000.0),
        )
        accept = (
            proposer is not None
            and active_partner(world, citizen) is None
            and trust >= 0.65
            and age_fit >= 0.5
            and (citizen.happy / 100.0 + stability) >= 0.6
        )
        respond_partnership(world, citizen, proposal["id"], accept)
        return True
    if active_partner(world, citizen) is not None:
        return False
    candidates = []
    for other in world.citizens:
        if (other is citizen or other.age < 18
                or active_partner(world, other) is not None):
            continue
        edge = relationship(world, citizen, other)
        if (edge is None or edge["status"] != "active"
                or edge["trust"] < 0.65):
            continue
        age_fit = max(0.0, 1.0 - abs(citizen.age - other.age) / 40.0)
        compatibility = 1.0 - (
            abs(citizen.patience - other.patience)
            + abs(citizen.optimism - other.optimism)
        ) / 2.0
        candidates.append((
            edge["trust"] * 0.55 + age_fit * 0.25
            + compatibility * 0.20,
            other.id,
            other,
        ))
    if not candidates:
        return False
    score, _, recipient = max(candidates)
    willingness = (
        citizen.parenting_desire
        * (citizen.happy / 100.0)
        * (0.5 + 0.5 * citizen.patience)
    )
    if score < 0.68 or world.rng.random() >= 0.002 * willingness:
        return False
    try:
        world.propose_partnership(citizen, recipient)
    except ValueError:
        return False
    return True
