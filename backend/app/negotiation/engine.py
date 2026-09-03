"""
Negotiation Engine — the core orchestrator.
Implements the deterministic negotiation loop with LLM-assisted agents.
"""
import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import (
    Negotiation, Offer, Message, AuditRecord, Contract,
    NegotiationStatus, Strategy, ApprovalMode
)
from app.agents.schemas import AgentResponseSchema
from app.negotiation.rules import validate_buyer_offer, validate_seller_offer
from app.negotiation.scoring import check_convergence
from app.negotiation.state import get_next_turn
from app.agents.buyer_agent import BuyerAgent
from app.agents.seller_agent import SellerAgent
from app.integrations.model_studio import get_llm_response


def create_audit_record(
    db: Session,
    negotiation_id: str,
    event_type: str,
    round_number: Optional[int] = None,
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    public_message: Optional[str] = None,
    offer_data: Optional[dict] = None,
    decision: Optional[str] = None,
    validation_result: Optional[str] = None,
    model_used: Optional[str] = None,
):
    """Create an immutable audit record with hash chain."""
    # Get previous hash
    prev = (
        db.query(AuditRecord)
        .filter(AuditRecord.negotiation_id == negotiation_id)
        .order_by(AuditRecord.created_at.desc())
        .first()
    )
    previous_hash = prev.record_hash if prev else "genesis"

    # Compute hash
    record_data = {
        "negotiation_id": negotiation_id,
        "event_type": event_type,
        "round": round_number,
        "timestamp": datetime.utcnow().isoformat(),
        "previous_hash": previous_hash,
    }
    record_hash = hashlib.sha256(json.dumps(record_data, sort_keys=True).encode()).hexdigest()

    audit = AuditRecord(
        negotiation_id=negotiation_id,
        round_number=round_number,
        event_type=event_type,
        sender=sender,
        receiver=receiver,
        public_message=public_message,
        offer_data=offer_data,
        decision=decision,
        validation_result=validation_result,
        model_used=model_used,
        record_hash=record_hash,
        previous_hash=previous_hash,
    )
    db.add(audit)
    db.flush()
    return audit


def initialize_negotiation(db: Session, negotiation_id: str) -> Negotiation:
    """Initialize a negotiation and set it ready for the first buyer turn."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise ValueError(f"Negotiation {negotiation_id} not found")

    neg.status = NegotiationStatus.INITIALIZED.value
    neg.current_round = 1
    db.commit()

    create_audit_record(db, negotiation_id, "NEGOTIATION_INITIALIZED", round_number=1)
    db.commit()
    return neg


def generate_agent_offer(
    db: Session,
    negotiation_id: str,
    role: str,
    use_ai: bool = True,
) -> Offer:
    """
    Generate an offer from the specified agent.
    The LLM generates a recommendation → Pydantic validates → Business rules enforce.
    """
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise ValueError(f"Negotiation {negotiation_id} not found")

    # Get negotiation history for context
    history = (
        db.query(Offer)
        .filter(Offer.negotiation_id == negotiation_id)
        .order_by(Offer.round_number, Offer.created_at)
        .all()
    )

    current_round = neg.current_round

    if role == "BUYER":
        agent = BuyerAgent(
            starting_price=neg.buyer_starting_price,
            reservation_price=neg.buyer_reservation_price,
            strategy=neg.buyer_strategy,
            max_rounds=neg.buyer_max_rounds,
            delivery_days=neg.buyer_delivery_days,
            payment_terms=neg.buyer_payment_terms,
        )
        reservation = neg.buyer_reservation_price
    else:
        agent = SellerAgent(
            starting_price=neg.seller_starting_price or neg.buyer_reservation_price * 1.3,
            reservation_price=neg.seller_reservation_price or neg.buyer_starting_price * 0.9,
            strategy=neg.seller_strategy,
            max_rounds=neg.seller_max_rounds,
            delivery_days=neg.seller_delivery_days,
            payment_terms=neg.seller_payment_terms,
        )
        reservation = neg.seller_reservation_price or neg.buyer_starting_price * 0.9

    # Generate offer using agent
    if use_ai:
        agent_response = get_llm_response(agent, history, current_round, neg)
    else:
        agent_response = agent.calculate_deterministic_offer(current_round, history)

    # Validate
    if role == "BUYER":
        validation = validate_buyer_offer(agent_response, reservation, neg.buyer_max_rounds, current_round)
    else:
        validation = validate_seller_offer(agent_response, reservation, neg.seller_max_rounds, current_round)

    validation_status = "VALID" if validation.valid else f"INVALID: {validation.reason}"

    # If invalid, use deterministic fallback
    if not validation.valid:
        agent_response = agent.calculate_deterministic_offer(current_round, history)
        validation_status = "FALLBACK_USED"

    # Create offer record
    offer = Offer(
        negotiation_id=negotiation_id,
        round_number=current_round,
        sender=role,
        offer_price=agent_response.offer_price,
        quantity=agent_response.quantity or neg.quantity,
        delivery_days=agent_response.delivery_days,
        payment_terms=agent_response.payment_terms,
        action=agent_response.action,
        public_rationale=agent_response.public_rationale,
        validation_result=validation_status,
        strategy_used=agent.strategy,
        concession_percentage=agent.calculate_concession(current_round, agent_response.offer_price),
    )
    db.add(offer)

    # Create message
    msg = Message(
        negotiation_id=negotiation_id,
        sender=role,
        receiver="SELLER" if role == "BUYER" else "BUYER",
        message_type=agent_response.action,
        body=agent_response.public_rationale,
        channel="INTERNAL",
    )
    db.add(msg)

    # Audit
    create_audit_record(
        db, negotiation_id, f"{role}_OFFER",
        round_number=current_round,
        sender=role,
        receiver="SELLER" if role == "BUYER" else "BUYER",
        public_message=agent_response.public_rationale,
        offer_data=agent_response.model_dump(),
        decision=agent_response.action,
        validation_result=validation_status,
    )

    db.commit()
    db.refresh(offer)
    return offer


def process_negotiation_round(db: Session, negotiation_id: str) -> dict:
    """
    Process one complete negotiation round (buyer offer + seller offer).
    Returns the updated negotiation status and results.
    """
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise ValueError(f"Negotiation {negotiation_id} not found")

    results = {"round": neg.current_round, "offers": [], "events": []}

    # Buyer turn
    neg.status = NegotiationStatus.BUYER_TURN.value
    db.commit()
    buyer_offer = generate_agent_offer(db, negotiation_id, "BUYER")
    results["offers"].append({
        "sender": "BUYER",
        "price": buyer_offer.offer_price,
        "action": buyer_offer.action,
    })
    results["events"].append("Buyer offer generated")

    if buyer_offer.action == "WALKAWAY":
        neg.status = NegotiationStatus.WALKAWAY.value
        db.commit()
        results["events"].append("Buyer walked away")
        _generate_contract_if_agreed(db, neg)
        return results

    # Seller turn
    neg.status = NegotiationStatus.SELLER_TURN.value
    db.commit()
    seller_offer = generate_agent_offer(db, negotiation_id, "SELLER")
    results["offers"].append({
        "sender": "SELLER",
        "price": seller_offer.offer_price,
        "action": seller_offer.action,
    })
    results["events"].append("Seller offer generated")

    if seller_offer.action == "WALKAWAY":
        neg.status = NegotiationStatus.WALKAWAY.value
        db.commit()
        results["events"].append("Seller walked away")
        _generate_contract_if_agreed(db, neg)
        return results

    # Check convergence
    convergence = check_convergence(
        buyer_offer.offer_price,
        seller_offer.offer_price,
        neg.convergence_mode,
    )

    if convergence["converged"]:
        neg.final_price = convergence["final_price"]
        neg.final_quantity = neg.quantity
        neg.final_delivery_days = min(
            buyer_offer.delivery_days or neg.buyer_delivery_days,
            seller_offer.delivery_days or neg.seller_delivery_days,
        )

        # Check approval mode — pause for human review or auto-agree
        if neg.approval_mode == ApprovalMode.HUMAN_APPROVAL.value:
            neg.status = NegotiationStatus.HUMAN_APPROVAL.value
            db.commit()
            results["events"].append(
                f"Convergence at {convergence['final_price']} — awaiting human approval"
            )
            create_audit_record(
                db, negotiation_id, "PENDING_HUMAN_APPROVAL",
                round_number=neg.current_round,
                decision="HUMAN_APPROVAL",
                offer_data=convergence,
            )
            db.commit()
            return results

        neg.status = NegotiationStatus.AGREED.value
        db.commit()
        results["events"].append(f"Agreement reached at {convergence['final_price']}")

        create_audit_record(
            db, negotiation_id, "AGREEMENT_REACHED",
            round_number=neg.current_round,
            decision="AGREED",
            offer_data=convergence,
        )
        db.commit()

        _generate_contract_if_agreed(db, neg)
        return results

    # Check walkaway conditions
    max_rounds = min(neg.buyer_max_rounds, neg.seller_max_rounds)
    if neg.current_round >= max_rounds:
        neg.status = NegotiationStatus.WALKAWAY.value
        db.commit()
        results["events"].append(f"Max rounds ({max_rounds}) reached — walkaway")
        return results

    # Continue to next round
    neg.current_round += 1
    neg.status = NegotiationStatus.INITIALIZED.value
    db.commit()
    results["events"].append(f"No convergence. Gap: {convergence['gap']}. Moving to round {neg.current_round}")

    return results


def run_full_negotiation(db: Session, negotiation_id: str) -> list[dict]:
    """Run the complete negotiation until agreement or walkaway."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise ValueError(f"Negotiation {negotiation_id} not found")

    if neg.status == NegotiationStatus.CREATED.value:
        initialize_negotiation(db, negotiation_id)

    all_rounds = []
    max_iterations = min(neg.buyer_max_rounds, neg.seller_max_rounds) + 2

    for _ in range(max_iterations):
        neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
        if neg.status in [
            NegotiationStatus.AGREED.value,
            NegotiationStatus.WALKAWAY.value,
            NegotiationStatus.TERMINATED.value,
            NegotiationStatus.CANCELLED.value,
            NegotiationStatus.HUMAN_APPROVAL.value,
            NegotiationStatus.SELLER_APPROVAL.value,
        ]:
            break

        round_result = process_negotiation_round(db, negotiation_id)
        all_rounds.append(round_result)

    return all_rounds


def _generate_contract_if_agreed(db: Session, neg: Negotiation):
    """Generate contract when negotiation reaches agreement."""
    if neg.status != NegotiationStatus.AGREED.value:
        return

    existing = db.query(Contract).filter(Contract.negotiation_id == neg.id).first()
    if existing:
        return

    total_value = (neg.final_price or 0) * (neg.final_quantity or neg.quantity)
    doc_hash = hashlib.sha256(
        json.dumps({
            "negotiation_id": neg.id,
            "final_price": neg.final_price,
            "quantity": neg.final_quantity,
            "timestamp": datetime.utcnow().isoformat(),
        }, sort_keys=True).encode()
    ).hexdigest()

    buyer_name = ""
    seller_name = ""
    if neg.buyer_business:
        buyer_name = neg.buyer_business.name
    if neg.seller_business:
        seller_name = neg.seller_business.name

    contract = Contract(
        negotiation_id=neg.id,
        buyer_name=buyer_name or "Buyer",
        seller_name=seller_name or "Seller",
        commodity=neg.commodity,
        quantity=neg.final_quantity or neg.quantity,
        unit=neg.unit,
        unit_price=neg.final_price,
        total_value=total_value,
        currency=neg.currency,
        delivery_days=neg.final_delivery_days or neg.buyer_delivery_days,
        payment_terms=neg.buyer_payment_terms,
        agreement_timestamp=datetime.utcnow(),
        document_hash=doc_hash,
        status="GENERATED",
    )
    db.add(contract)

    create_audit_record(
        db, neg.id, "CONTRACT_GENERATED",
        round_number=neg.current_round,
        decision="CONTRACT",
        offer_data={"contract_hash": doc_hash, "total_value": total_value},
    )
    db.commit()
