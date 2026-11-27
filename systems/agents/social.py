"""Bounded social relationships, explicit learning, and cooperative institutions."""
import math


TRUST_TO_SHARE = 0.35
TRUST_TO_ORGANIZE = 0.65
MAX_SOCIAL_EVENTS = 4_000
MAX_COOPERATION_OFFERS = 256
MAX_ORGANIZATIONS = 128


def new_social_state():
    # Built-in containers let ledger transactions snapshot and roll back social changes.
    return {
        "relationships": {},
        "reputation": {},
        "events": [],
        "offers": {},
        "organizations": {},
        "next_offer_id": 1,
        "next_organization_id": 1,
    }


def ensure_social_state(world):
    if not hasattr(world, "social_state") or not isinstance(
            world.social_state, dict):
        world.social_state = new_social_state()
    state = world.social_state
    for key, value in new_social_state().items():
        if key not in state:
            state[key] = value
    return state


def _finite(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} harus berupa angka terbatas.")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} harus berupa angka terbatas.") from None
    if not math.isfinite(value):
        raise ValueError(f"{label} harus berupa angka terbatas.")
    return value


def _text(value, label, maximum=80):
    if (not isinstance(value, str) or not value.strip()
            or len(value) > maximum):
        raise ValueError(f"{label} sosial tidak valid.")
    return value.strip()


def _relationship_key(source_id, target_id):
    return f"{source_id}:{target_id}"


def relationship(world, source, target):
    state = ensure_social_state(world)
    edge = state["relationships"].get(
        _relationship_key(source.id, target.id)
    )
    return dict(edge) if edge is not None else None


def reputation(world, citizen):
    return ensure_social_state(world)["reputation"].get(
        str(citizen.id), 0.5
    )


def _edge(state, source_id, target_id):
    key = _relationship_key(source_id, target_id)
    edge = state["relationships"].get(key)
    if edge is None:
        edge = {
            "source_id": source_id,
            "target_id": target_id,
            "trust": 0.5,
            "status": "active",
            "interaction_count": 0,
            "successful_interactions": 0,
            "failed_interactions": 0,
            "trade_days": 0,
            "last_trade_day": -1,
            "last_interaction_day": -1,
            "last_kind": "",
            "last_outcome": "unknown",
        }
        state["relationships"][key] = edge
    elif edge["status"] == "ended":
        edge["status"] = "active"
        edge["trust"] = min(edge["trust"], 0.5)
    return edge


def _event(state, event):
    state["events"].append(event)
    if len(state["events"]) > MAX_SOCIAL_EVENTS:
        del state["events"][:-MAX_SOCIAL_EVENTS]


def _remember(citizen, world, partner, kind, outcome, success, value):
    citizen.memory.record(
        world.day,
        "social",
        "interaction",
        {"partner_id": partner.id, "kind": kind},
        outcome,
        success,
        impact=min(1.0, abs(value)),
        value=max(-1.0, min(1.0, value)),
    )


def record_interaction(world, actor, other, kind, success=None, outcome=""):
    if actor not in world.citizens or other not in world.citizens:
        raise ValueError("Kedua pihak interaksi harus warga kota.")
    if actor is other:
        raise ValueError("Warga tidak dapat membentuk relasi dengan dirinya.")
    if success is not None and not isinstance(success, bool):
        raise ValueError("Status interaksi sosial tidak valid.")
    kind = _text(kind, "Jenis interaksi", 40)
    outcome = _text(outcome or kind, "Hasil interaksi", 120)
    state = ensure_social_state(world)
    left = _edge(state, actor.id, other.id)
    right = _edge(state, other.id, actor.id)
    before_trust = (left["trust"] + right["trust"]) / 2.0
    for edge in (left, right):
        edge["interaction_count"] += 1
        edge["last_interaction_day"] = world.day
        edge["last_kind"] = kind
        edge["last_outcome"] = (
            "successful" if success is True
            else "failed" if success is False else "observed"
        )
        if success is True:
            edge["successful_interactions"] += 1
            target, rate = 0.85, 0.06
        elif success is False:
            edge["failed_interactions"] += 1
            target, rate = 0.1, 0.2
        else:
            target, rate = 0.5, 0.0
        edge["trust"] = max(
            0.0, min(1.0, edge["trust"] + rate * (target - edge["trust"]))
        )
    after_trust = (left["trust"] + right["trust"]) / 2.0
    if success is not None:
        shift = 0.004 if success else -0.025
        for citizen in (actor, other):
            key = str(citizen.id)
            state["reputation"][key] = max(
                0.0,
                min(1.0, state["reputation"].get(key, 0.5) + shift),
            )
    _event(state, {
        "day": world.day,
        "actor_id": actor.id,
        "other_id": other.id,
        "kind": kind,
        "success": success,
        "outcome": outcome,
    })
    trust_change = after_trust - before_trust
    _remember(actor, world, other, kind, outcome, success, trust_change)
    _remember(other, world, actor, kind, outcome, success, trust_change)
    return left, right


def record_trade_interaction(world, buyer, seller, contract):
    buyer_owner = buyer if hasattr(buyer, "memory") else getattr(buyer, "owner", None)
    seller_owner = seller if hasattr(seller, "memory") else getattr(seller, "owner", None)
    if (buyer_owner is None or seller_owner is None or buyer_owner is seller_owner
            or buyer_owner not in world.citizens
            or seller_owner not in world.citizens):
        return
    state = ensure_social_state(world)
    left = _edge(state, buyer_owner.id, seller_owner.id)
    right = _edge(state, seller_owner.id, buyer_owner.id)
    first_trade_today = left["last_trade_day"] != world.day
    for edge in (left, right):
        if edge["last_trade_day"] == world.day:
            continue
        edge["trade_days"] += 1
        edge["last_trade_day"] = world.day
        edge["interaction_count"] += 1
        edge["successful_interactions"] += 1
        edge["last_interaction_day"] = world.day
        edge["last_kind"] = "settled_trade"
        edge["last_outcome"] = "successful"
        edge["trust"] = min(1.0, edge["trust"] + 0.06 * (0.85 - edge["trust"]))
    if first_trade_today:
        for citizen in (buyer_owner, seller_owner):
            key = str(citizen.id)
            state["reputation"][key] = min(
                1.0, state["reputation"].get(key, 0.5) + 0.001
            )
    _event(state, {
        "day": world.day,
        "actor_id": buyer_owner.id,
        "other_id": seller_owner.id,
        "kind": "settled_trade",
        "success": True,
        "outcome": contract["id"],
    })


def end_relationship(world, actor, other):
    if actor not in world.citizens or other not in world.citizens:
        raise ValueError("Kedua pihak relasi harus warga kota.")
    if actor is other:
        raise ValueError("Relasi diri sendiri tidak dapat diakhiri.")
    state = ensure_social_state(world)
    edges = (
        state["relationships"].get(_relationship_key(actor.id, other.id)),
        state["relationships"].get(_relationship_key(other.id, actor.id)),
    )
    if not any(edge and edge["status"] == "active" for edge in edges):
        return False
    for edge in edges:
        if edge is not None:
            edge["status"] = "ended"
            edge["last_interaction_day"] = world.day
            edge["last_kind"] = "relationship_ended"
            edge["last_outcome"] = "ended"
    _event(state, {
        "day": world.day,
        "actor_id": actor.id,
        "other_id": other.id,
        "kind": "relationship_ended",
        "success": None,
        "outcome": "ended",
    })
    _remember(actor, world, other, "relationship_ended", "Relasi diakhiri.", None, 0.0)
    _remember(other, world, actor, "relationship_ended", "Relasi diakhiri.", None, 0.0)
    return True


def observe_action(world, observer, actor, action, values, context=None):
    if observer not in world.citizens or actor not in world.citizens:
        raise ValueError("Pengamat dan pelaku harus warga kota.")
    if observer is actor:
        raise ValueError("Warga tidak dapat mengamati dirinya sebagai pihak lain.")
    action = _text(action, "Aksi yang diamati", 64)
    source_id = f"observed:{actor.id}:{action}:{world.day}"
    observation = observer.knowledge.observe(
        world.day,
        "social_information",
        source_id,
        values,
        context=context,
    )
    record_interaction(
        world, observer, actor, "observed_action", None,
        f"Mengamati tindakan {action}.",
    )
    return observation


def share_knowledge(world, sender, receiver, observation_id):
    if sender not in world.citizens or receiver not in world.citizens:
        raise ValueError("Pengirim dan penerima harus warga kota.")
    if sender is receiver:
        raise ValueError("Pengetahuan harus dibagikan kepada warga lain.")
    edge = relationship(world, sender, receiver)
    if (edge is None or edge["status"] != "active"
            or edge["trust"] < TRUST_TO_SHARE):
        raise ValueError("Relasi aktif dengan kepercayaan cukup diperlukan.")
    source = next(
        (item for item in sender.knowledge.observations
         if item.id == observation_id),
        None,
    )
    if source is None:
        raise ValueError("Observasi sumber tidak ditemukan.")
    observation = receiver.knowledge.observe(
        world.day,
        "social_information",
        f"shared:{sender.id}:{source.id}:to:{receiver.id}",
        source.values,
        context=source.context,
    )
    record_interaction(
        world, sender, receiver, "knowledge_shared", True,
        "Berbagi satu observasi berdasarkan relasi aktif.",
    )
    return observation


def _business(world, business_id):
    return next(
        (item for item in world.businesses if item.ledger_id == business_id),
        None,
    )


def _offer_key(offer_id):
    return str(offer_id)


def _validate_trade_terms(world, buyer, seller, quantity, unit_price):
    quantity = _finite(quantity, "Jumlah kontrak")
    unit_price = _finite(unit_price, "Harga kontrak")
    if (buyer not in world.businesses or seller not in world.businesses
            or buyer is seller or buyer.kind != "shop"
            or seller.kind not in ("farm", "factory")
            or quantity <= 0 or unit_price <= 0
            or quantity > seller.stock
            or unit_price < seller.price * 0.8
            or unit_price > seller.price * 1.2):
        raise ValueError("Ketentuan kontrak perdagangan tidak layak.")
    if buyer.cash < quantity * unit_price:
        raise ValueError("Kas pembeli tidak cukup untuk kontrak.")
    return quantity, unit_price


def _trim_offers(state):
    offers = state["offers"]
    while len(offers) >= MAX_COOPERATION_OFFERS:
        removable = next(
            (key for key, item in offers.items()
             if item["status"] != "pending"),
            None,
        )
        if removable is None:
            raise ValueError("Batas penawaran kerja sama telah tercapai.")
        del offers[removable]


def propose_trade_cooperation(
        world, buyer_citizen, seller_citizen, quantity, unit_price,
        organization_id=None, parent_offer_id=None):
    if (buyer_citizen not in world.citizens
            or seller_citizen not in world.citizens
            or buyer_citizen is seller_citizen):
        raise ValueError("Pihak kontrak harus dua warga kota yang berbeda.")
    buyer, seller = buyer_citizen.business, seller_citizen.business
    quantity, unit_price = _validate_trade_terms(
        world, buyer, seller, quantity, unit_price
    )
    edge = relationship(world, buyer_citizen, seller_citizen)
    if (edge is None or edge["status"] != "active"
            or edge["trust"] < 0.55 or edge["trade_days"] < 2):
        raise ValueError("Relasi dagang yang tepercaya diperlukan.")
    if organization_id is not None:
        organization = ensure_social_state(world)["organizations"].get(
            _offer_key(organization_id)
        )
        if (organization is None or organization["status"] != "active"
                or str(buyer_citizen.id) not in organization["members"]
                or str(seller_citizen.id) not in organization["members"]):
            raise ValueError("Kedua pihak harus anggota organisasi aktif.")
        fee_rate = _finite(
            organization["rules"]["brokerage_fee_rate"],
            "Tarif koperasi",
        )
        if not 0.0 <= fee_rate <= 0.05:
            raise ValueError("Tarif koperasi berada di luar batas.")
        if buyer.cash < quantity * unit_price * (1.0 + fee_rate):
            raise ValueError("Kas pembeli tidak cukup termasuk biaya koperasi.")
    state = ensure_social_state(world)
    duplicate = any(
        offer["status"] == "pending"
        and offer["buyer_id"] == buyer_citizen.id
        and offer["seller_id"] == seller_citizen.id
        and offer["organization_id"] == organization_id
        for offer in state["offers"].values()
    )
    if duplicate:
        raise ValueError("Penawaran kontrak sejenis masih menunggu jawaban.")
    _trim_offers(state)
    offer_id = state["next_offer_id"]
    state["next_offer_id"] += 1
    state["offers"][_offer_key(offer_id)] = {
        "id": offer_id,
        "sender_id": buyer_citizen.id,
        "recipient_id": seller_citizen.id,
        "buyer_id": buyer_citizen.id,
        "seller_id": seller_citizen.id,
        "buyer_business_id": buyer.ledger_id,
        "seller_business_id": seller.ledger_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "organization_id": organization_id,
        "parent_offer_id": parent_offer_id,
        "status": "pending",
        "created_day": world.day,
        "expires_day": world.day + 7,
    }
    _remember(
        buyer_citizen, world, seller_citizen, "cooperation_offer",
        f"Mengajukan kontrak {quantity:g} unit dengan harga {unit_price:g}.",
        None, 0.0,
    )
    _remember(
        seller_citizen, world, buyer_citizen, "cooperation_offer",
        f"Menerima penawaran kontrak {quantity:g} unit.",
        None, 0.0,
    )
    return offer_id


def respond_trade_offer(
        world, citizen, offer_id, decision, quantity=None, unit_price=None):
    if citizen not in world.citizens:
        raise ValueError("Warga penjawab tidak ditemukan.")
    if decision not in ("accept", "reject", "counter"):
        raise ValueError("Keputusan penawaran tidak dikenal.")
    state = ensure_social_state(world)
    offer = state["offers"].get(_offer_key(offer_id))
    if offer is None or offer["status"] != "pending":
        raise ValueError("Penawaran kerja sama tidak aktif.")
    if offer["recipient_id"] != citizen.id:
        raise ValueError("Hanya penerima penawaran yang dapat menjawab.")
    sender = next(
        (item for item in world.citizens if item.id == offer["sender_id"]),
        None,
    )
    if sender is None:
        offer["status"] = "cancelled"
        return False
    if world.day > offer["expires_day"]:
        offer["status"] = "expired"
        record_interaction(
            world, citizen, sender, "cooperation_expired", False,
            "Penawaran kedaluwarsa.",
        )
        return False
    if decision == "reject":
        offer["status"] = "rejected"
        record_interaction(
            world, citizen, sender, "cooperation_rejected", False,
            "Menolak kontrak perdagangan.",
        )
        return True
    buyer = _business(world, offer["buyer_business_id"])
    seller = _business(world, offer["seller_business_id"])
    if decision == "counter":
        quantity, unit_price = _validate_trade_terms(
            world, buyer, seller,
            offer["quantity"] if quantity is None else quantity,
            offer["unit_price"] if unit_price is None else unit_price,
        )
        offer["status"] = "countered"
        new_offer_id = propose_trade_cooperation(
            world,
            next(item for item in world.citizens
                 if item.id == offer["buyer_id"]),
            next(item for item in world.citizens
                 if item.id == offer["seller_id"]),
            quantity,
            unit_price,
            offer["organization_id"],
            offer["id"],
        )
        counter = state["offers"][_offer_key(new_offer_id)]
        counter["sender_id"] = citizen.id
        counter["recipient_id"] = sender.id
        return new_offer_id
    contract = world._settle_cooperation_trade(offer_id)
    if contract is None:
        offer["status"] = "failed_resources"
        record_interaction(
            world, citizen, sender, "cooperation_failed", False,
            "Kontrak gagal karena stok atau dana berubah.",
        )
        return False
    offer["status"] = "settled"
    _remember(
        citizen, world, sender, "cooperation_settled",
        "Kontrak perdagangan bersama diselesaikan.", True, 0.05,
    )
    _remember(
        sender, world, citizen, "cooperation_settled",
        "Kontrak perdagangan bersama diselesaikan.", True, 0.05,
    )
    return contract


def propose_organization(world, founder, invitees, name, contribution):
    if founder not in world.citizens:
        raise ValueError("Pendiri organisasi tidak ditemukan.")
    invitees = list(dict.fromkeys(invitees))
    if (founder in invitees or not 1 <= len(invitees) <= 7
            or any(member not in world.citizens for member in invitees)):
        raise ValueError("Anggota organisasi yang diundang tidak valid.")
    name = _text(name, "Nama organisasi", 48)
    contribution = _finite(contribution, "Kontribusi anggota")
    if contribution <= 0:
        raise ValueError("Kontribusi awal harus positif.")
    members = [founder] + invitees
    state = ensure_social_state(world)
    active_member_ids = {
        member_id
        for organization in state["organizations"].values()
        if organization["status"] in ("active", "pending")
        for member_id in organization["members"]
    }
    for member in members:
        business = member.business
        if (business is None or business not in world.businesses
                or business.cash < contribution
                or str(member.id) in active_member_ids):
            raise ValueError("Semua calon anggota perlu usaha dan dana bebas.")
    for member in invitees:
        edge = relationship(world, founder, member)
        if (edge is None or edge["status"] != "active"
                or edge["trust"] < TRUST_TO_ORGANIZE
                or edge["trade_days"] < 3):
            raise ValueError("Organisasi memerlukan kemitraan dagang tepercaya.")
    if len(state["organizations"]) >= MAX_ORGANIZATIONS:
        raise ValueError("Batas organisasi kota telah tercapai.")
    organization_id = state["next_organization_id"]
    state["next_organization_id"] += 1
    state["organizations"][_offer_key(organization_id)] = {
        "id": organization_id,
        "name": name,
        "kind": "trade_cooperative",
        "status": "pending",
        "created_day": world.day,
        "founder_id": founder.id,
        "members": {
            str(member.id): {
                "business_id": member.business.ledger_id,
                "accepted": member is founder,
                "contribution": contribution,
                "share": 0.0,
            }
            for member in members
        },
        "fund": 0.0,
        "contributed_capital": 0.0,
        "undistributed_profit": 0.0,
        "maintenance_failures": 0,
        "last_settlement_day": world.day,
        "reputation": 0.5,
        "rules": {
            "voting": "one_member_one_vote",
            "brokerage_fee_rate": 0.01,
            "monthly_maintenance_per_member": 5_000.0,
            "profit_share_rate": 0.5,
            "reserve_months": 3,
        },
        "rule_proposals": {},
        "next_rule_proposal_id": 1,
    }
    for member in invitees:
        _remember(
            founder, world, member, "organization_invitation",
            f"Mengundang ke organisasi {name}.", None, 0.0,
        )
        _remember(
            member, world, founder, "organization_invitation",
            f"Diundang ke organisasi {name}.", None, 0.0,
        )
    return organization_id


def respond_organization_invitation(world, citizen, organization_id, accept):
    if citizen not in world.citizens:
        raise ValueError("Warga yang diundang tidak ditemukan.")
    if not isinstance(accept, bool):
        raise ValueError("Jawaban undangan organisasi harus boolean.")
    state = ensure_social_state(world)
    organization = state["organizations"].get(_offer_key(organization_id))
    member = (
        organization["members"].get(str(citizen.id))
        if organization is not None else None
    )
    if (organization is None or organization["status"] != "pending"
            or member is None or member["accepted"]):
        raise ValueError("Undangan organisasi tidak aktif untuk warga ini.")
    if not accept:
        organization["status"] = "rejected"
        founder = next(
            (item for item in world.citizens
             if item.id == organization["founder_id"]),
            None,
        )
        if founder is None:
            organization["status"] = "cancelled"
            return False
        _remember(
            citizen, world, founder,
            "organization_declined",
            f"Menolak undangan {organization['name']}.", False, -0.1,
        )
        return False
    member["accepted"] = True
    if not all(item["accepted"] for item in organization["members"].values()):
        founder = next(
            (item for item in world.citizens
             if item.id == organization["founder_id"]),
            None,
        )
        if founder is None:
            organization["status"] = "cancelled"
            return False
        _remember(
            citizen, world, founder,
            "organization_accepted",
            f"Menerima undangan {organization['name']}.", True, 0.05,
        )
        return True
    if not world.activate_social_organization(organization_id):
        organization["status"] = "funding_failed"
        return False
    return True


def propose_organization_rule(world, citizen, organization_id, rule, value):
    if citizen not in world.citizens:
        raise ValueError("Anggota organisasi tidak ditemukan.")
    organization = ensure_social_state(world)["organizations"].get(
        _offer_key(organization_id)
    )
    member_id = str(citizen.id)
    if (organization is None or organization["status"] != "active"
            or member_id not in organization["members"]):
        raise ValueError("Hanya anggota organisasi aktif yang dapat mengusulkan aturan.")
    bounds = {
        "brokerage_fee_rate": (0.0, 0.05),
        "monthly_maintenance_per_member": (0.0, 100_000.0),
        "profit_share_rate": (0.0, 1.0),
        "reserve_months": (1.0, 12.0),
    }
    if rule not in bounds:
        raise ValueError("Aturan organisasi tidak dikenal.")
    value = _finite(value, "Nilai aturan")
    minimum, maximum = bounds[rule]
    if not minimum <= value <= maximum:
        raise ValueError("Nilai aturan organisasi berada di luar batas.")
    if rule == "reserve_months" and not value.is_integer():
        raise ValueError("Lama cadangan organisasi harus bilangan bulat.")
    proposal_id = organization["next_rule_proposal_id"]
    organization["next_rule_proposal_id"] += 1
    organization["rule_proposals"][str(proposal_id)] = {
        "id": proposal_id,
        "proposer_id": citizen.id,
        "rule": rule,
        "value": int(value) if rule == "reserve_months" else value,
        "votes": {member_id: True},
        "status": "pending",
        "created_day": world.day,
    }
    return proposal_id


def vote_organization_rule(
        world, citizen, organization_id, proposal_id, approve):
    if citizen not in world.citizens:
        raise ValueError("Anggota organisasi tidak ditemukan.")
    if not isinstance(approve, bool):
        raise ValueError("Suara aturan organisasi harus boolean.")
    organization = ensure_social_state(world)["organizations"].get(
        _offer_key(organization_id)
    )
    member_id = str(citizen.id)
    proposal = (
        organization["rule_proposals"].get(_offer_key(proposal_id))
        if organization is not None else None
    )
    if (organization is None or organization["status"] != "active"
            or member_id not in organization["members"]
            or proposal is None or proposal["status"] != "pending"
            or member_id in proposal["votes"]):
        raise ValueError("Pemungutan suara organisasi tidak aktif.")
    proposal["votes"][member_id] = approve
    if len(proposal["votes"]) == len(organization["members"]):
        approved = sum(proposal["votes"].values())
        if approved > len(organization["members"]) / 2:
            organization["rules"][proposal["rule"]] = proposal["value"]
            proposal["status"] = "approved"
        else:
            proposal["status"] = "rejected"
        proposal["resolved_day"] = world.day
    return proposal["status"]


def consider_social_action(world, citizen):
    state = ensure_social_state(world)
    invitation = next(
        (
            organization
            for organization in state["organizations"].values()
            if organization["status"] == "pending"
            and str(citizen.id) in organization["members"]
            and not organization["members"][str(citizen.id)]["accepted"]
        ),
        None,
    )
    if invitation is not None:
        founder = next(
            (item for item in world.citizens
             if item.id == invitation["founder_id"]),
            None,
        )
        invite = invitation["members"][str(citizen.id)]
        edge = relationship(world, citizen, founder) if founder else None
        business = _business(world, invite["business_id"])
        accept = (
            edge is not None and edge["status"] == "active"
            and edge["trust"] >= TRUST_TO_ORGANIZE
            and business is not None
            and business.cash >= invite["contribution"]
        )
        respond_organization_invitation(
            world, citizen, invitation["id"], accept
        )
        return True
    pending_offer = next(
        (
            offer
            for offer in state["offers"].values()
            if offer["status"] == "pending"
            and offer["recipient_id"] == citizen.id
        ),
        None,
    )
    if pending_offer is not None:
        buyer = _business(world, pending_offer["buyer_business_id"])
        seller = _business(world, pending_offer["seller_business_id"])
        offer_sender = next(
            (item for item in world.citizens
             if item.id == pending_offer["sender_id"]),
            None,
        )
        relation_data = (
            relationship(world, citizen, offer_sender)
            if offer_sender is not None else None
        )
        organization = (
            state["organizations"].get(
                _offer_key(pending_offer["organization_id"])
            )
            if pending_offer["organization_id"] is not None else None
        )
        fee_rate = (
            organization["rules"]["brokerage_fee_rate"]
            if organization is not None
            and organization["status"] == "active"
            else 0.0
        )
        accept = (
            buyer is not None and seller is not None
            and buyer.cash >= (
                pending_offer["quantity"] * pending_offer["unit_price"]
                * (1.0 + fee_rate)
            )
            and seller.stock >= pending_offer["quantity"]
            and relation_data is not None
            and relation_data["status"] == "active"
            and relation_data["trust"] >= 0.55
            and pending_offer["unit_price"] >= seller.price * 0.95
        )
        respond_trade_offer(
            world, citizen, pending_offer["id"],
            "accept" if accept else "reject",
        )
        return True
    business = citizen.business
    if business is not None and business.kind == "shop":
        average_demand = (
            sum(business.daily_demand) / len(business.daily_demand)
            if business.daily_demand else max(business.prod, 1.0)
        )
        target_stock = max(5.0, average_demand * 2.5 + 2.0)
        if business.stock < max(1.0, target_stock * 0.2):
            partners = eligible_trade_partners(world, citizen)
            for partner in partners:
                supplier = partner.business
                if (supplier is None or supplier.kind not in ("farm", "factory")
                        or supplier.stock <= 0):
                    continue
                organization_id = next(
                    (
                        organization["id"]
                        for organization in state["organizations"].values()
                        if organization["status"] == "active"
                        and str(citizen.id) in organization["members"]
                        and str(partner.id) in organization["members"]
                    ),
                    None,
                )
                quantity = min(
                    12.0, target_stock - business.stock, supplier.stock
                )
                if quantity <= 0:
                    continue
                try:
                    propose_trade_cooperation(
                        world, citizen, partner, quantity,
                        supplier.price * 0.97, organization_id,
                    )
                except ValueError:
                    continue
                return True
    return False


def eligible_trade_partners(world, citizen):
    if citizen.business is None:
        return []
    candidates = []
    for other in world.citizens:
        if other is citizen or other.business is None:
            continue
        edge = relationship(world, citizen, other)
        if (edge is None or edge["status"] != "active"
                or edge["trust"] < TRUST_TO_ORGANIZE
                or edge["trade_days"] < 3):
            continue
        candidates.append((edge["trust"], edge["trade_days"], other))
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2].id))
    return [item[2] for item in candidates]


def consider_organization(world, founder):
    partners = eligible_trade_partners(world, founder)
    if not partners or founder.business is None:
        return False
    for partner in partners:
        try:
            org_id = propose_organization(
                world,
                founder,
                [partner],
                f"{founder.first}-{partner.first} Trade Co-op",
                min(250_000.0, max(25_000.0, founder.business.cash * 0.005)),
            )
        except ValueError:
            continue
        return org_id
    return False
