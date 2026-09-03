"""
Negotiation API endpoints.
Core CRUD + negotiation execution + status monitoring.
"""
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.database import get_db
from app.database.models import Negotiation, Offer, Message, Contract, NegotiationStatus, ApprovalMode
from app.security.auth import get_current_user
from app.database.models import User, Business
from app.agents.schemas import (
    NegotiationCreate, NegotiationResponse, NegotiationStatusResponse,
    NegotiationListItem, OfferResponse, MessageResponse, DashboardStats,
    MandiRateResponse
)
from app.negotiation.engine import (
    initialize_negotiation, process_negotiation_round,
    run_full_negotiation, generate_agent_offer,
    _generate_contract_if_agreed, create_audit_record
)

router = APIRouter(prefix="/api/v1/negotiations", tags=["Negotiations"])


@router.post("", response_model=NegotiationResponse)
def create_negotiation(
    data: NegotiationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new negotiation session."""
    # Create or get buyer business
    buyer_biz = db.query(Business).filter(Business.organization_id == current_user.organization_id).first()
    if not buyer_biz:
        buyer_biz = Business(
            name=f"{current_user.full_name}'s Business",
            business_type="wholesaler",
            country="Pakistan",
            currency=data.currency,
            contact_person=current_user.full_name,
            organization_id=current_user.organization_id,
        )
        db.add(buyer_biz)
        db.flush()

    # Create seller business (simulated — real seller contacted via WhatsApp)
    seller_biz = Business(
        name=data.seller_name or f"Supplier — {data.commodity}",
        business_type="supplier",
        country="Pakistan",
        currency=data.currency,
        contact_person=data.seller_name or "",
        whatsapp_number=data.seller_whatsapp or "",
        organization_id=current_user.organization_id,
    )
    db.add(seller_biz)
    db.flush()

    # Auto-estimate seller AI params if buyer didn't set them.
    # Seller starts 30% above buyer max; won't go below 10% under buyer's start.
    auto_seller_start = data.buyer_reservation_price * 1.30
    auto_seller_reserve = data.buyer_starting_price * 0.90

    # Create negotiation
    neg = Negotiation(
        commodity=data.commodity,
        quantity=data.quantity,
        unit=data.unit,
        currency=data.currency,
        buyer_business_id=buyer_biz.id,
        buyer_starting_price=data.buyer_starting_price,
        buyer_reservation_price=data.buyer_reservation_price,
        buyer_delivery_days=data.buyer_delivery_days,
        buyer_payment_terms=data.buyer_payment_terms,
        buyer_strategy=data.buyer_strategy,
        buyer_max_rounds=data.buyer_max_rounds,
        seller_business_id=seller_biz.id,
        seller_name=data.seller_name or f"Supplier — {data.commodity}",
        seller_whatsapp=data.seller_whatsapp or "",
        seller_starting_price=data.seller_starting_price or auto_seller_start,
        seller_reservation_price=data.seller_reservation_price or auto_seller_reserve,
        seller_delivery_days=data.seller_delivery_days,
        seller_payment_terms=data.seller_payment_terms,
        seller_strategy=data.seller_strategy,
        seller_max_rounds=data.seller_max_rounds,
        convergence_mode=data.convergence_mode,
        approval_mode=data.approval_mode,
        mandi_rate=data.mandi_rate,
        status=NegotiationStatus.CREATED.value,
    )
    db.add(neg)
    db.commit()
    db.refresh(neg)
    return neg


@router.get("", response_model=List[NegotiationListItem])
def list_negotiations(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all negotiations for the current organization."""
    query = db.query(Negotiation).join(Business, Negotiation.buyer_business_id == Business.id).filter(
        Business.organization_id == current_user.organization_id
    )
    if status_filter:
        query = query.filter(Negotiation.status == status_filter)

    negotiations = query.order_by(Negotiation.created_at.desc()).offset(skip).limit(limit).all()
    return negotiations


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics."""
    biz_ids = [b.id for b in db.query(Business).filter(Business.organization_id == current_user.organization_id).all()]

    all_negs = db.query(Negotiation).filter(Negotiation.buyer_business_id.in_(biz_ids)).all()
    active = sum(1 for n in all_negs if n.status not in ["AGREED", "WALKAWAY", "TERMINATED", "CANCELLED"])
    completed = sum(1 for n in all_negs if n.status == "AGREED")
    terminated = sum(1 for n in all_negs if n.status in ["WALKAWAY", "TERMINATED"])
    pending = sum(1 for n in all_negs if n.status in ["HUMAN_APPROVAL", "SELLER_APPROVAL"])
    total_value = sum((n.final_price or 0) * (n.final_quantity or n.quantity) for n in all_negs if n.status == "AGREED")
    avg_rounds = sum(n.current_round for n in all_negs) / max(len(all_negs), 1)
    agreement_rate = completed / max(len(all_negs), 1) * 100
    walkaway_rate = terminated / max(len(all_negs), 1) * 100
    suppliers = db.query(Business).filter(Business.business_type == "supplier", Business.organization_id == current_user.organization_id).count()

    return DashboardStats(
        active_negotiations=active,
        completed_deals=completed,
        terminated_negotiations=terminated,
        pending_approvals=pending,
        total_negotiated_value=round(total_value, 2),
        average_rounds=round(avg_rounds, 1),
        agreement_rate=round(agreement_rate, 1),
        walkaway_rate=round(walkaway_rate, 1),
        total_suppliers=suppliers,
    )


# ── Market Rates Endpoint (must be BEFORE /{negotiation_id} catch-all) ──

# Static mandi rates (estimated wholesale rates in PKR/kg — for demo/MVP)
MANDI_RATES = {
    "Basmati Rice": {"rate_per_kg": 280.0, "source": "Estimated — Punjab Mandi"},
    "Wheat":        {"rate_per_kg": 85.0,  "source": "Estimated — Punjab Mandi"},
    "Sugar":        {"rate_per_kg": 165.0, "source": "Estimated — Sindh Mandi"},
    "Cotton":       {"rate_per_kg": 210.0, "source": "Estimated — Punjab Mandi"},
    "Spices":       {"rate_per_kg": 450.0, "source": "Estimated — Karachi Mandi"},
    "Dry Fruits":   {"rate_per_kg": 850.0, "source": "Estimated — Peshawar Mandi"},
    "Maize":        {"rate_per_kg": 72.0,  "source": "Estimated — Punjab Mandi"},
    "Cooking Oil":  {"rate_per_kg": 320.0, "source": "Estimated — Karachi Mandi"},
}

@router.get("/market-rates", response_model=List[MandiRateResponse])
def get_market_rates(
    commodity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Get current mandi (market) wholesale rates. Filter by commodity name or get all."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")

    results = []
    for name, info in MANDI_RATES.items():
        if commodity and commodity.lower() not in name.lower():
            continue
        results.append(MandiRateResponse(
            commodity=name,
            rate_per_kg=info["rate_per_kg"],
            currency="PKR",
            source=info["source"],
            updated_at=today,
        ))
    return results


@router.get("/market-rates/{commodity}", response_model=MandiRateResponse)
def get_market_rate(
    commodity: str,
    current_user: User = Depends(get_current_user),
):
    """Get mandi rate for a specific commodity."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")

    for name, info in MANDI_RATES.items():
        if name.lower() == commodity.lower():
            return MandiRateResponse(
                commodity=name,
                rate_per_kg=info["rate_per_kg"],
                currency="PKR",
                source=info["source"],
                updated_at=today,
            )
    raise HTTPException(status_code=404, detail=f"No mandi rate found for '{commodity}'")


# ── Public Seller Response Endpoints (no auth — token-based) ─────────────

@router.get("/seller-respond/{token}")
def get_seller_deal_info(
    token: str,
    db: Session = Depends(get_db),
):
    """Public endpoint: seller views deal details via unique token link."""
    neg = db.query(Negotiation).filter(Negotiation.seller_approval_token == token).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if neg.status != NegotiationStatus.SELLER_APPROVAL.value:
        return {
            "valid": False,
            "status": neg.status,
            "message": f"This deal is no longer awaiting seller approval (current status: {neg.status}).",
        }

    buyer_name = "Buyer"
    if neg.buyer_business:
        buyer_name = neg.buyer_business.name

    return {
        "valid": True,
        "negotiation_id": neg.id,
        "commodity": neg.commodity,
        "quantity": neg.quantity,
        "unit": neg.unit,
        "currency": neg.currency,
        "final_price": neg.final_price,
        "mandi_rate": neg.mandi_rate,
        "buyer_name": buyer_name,
        "seller_name": neg.seller_name or "Seller",
        "seller_whatsapp": neg.seller_whatsapp,
        "delivery_days": neg.final_delivery_days or neg.seller_delivery_days,
    }


@router.post("/seller-respond/{token}/approve")
def seller_approve_via_token(
    token: str,
    db: Session = Depends(get_db),
):
    """Public endpoint: seller approves deal via unique token (no auth needed)."""
    neg = db.query(Negotiation).filter(Negotiation.seller_approval_token == token).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if neg.status != NegotiationStatus.SELLER_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Deal is no longer awaiting seller approval (status: {neg.status})")

    neg.status = NegotiationStatus.AGREED.value
    db.commit()

    create_audit_record(
        db, neg.id, "SELLER_APPROVED",
        round_number=neg.current_round,
        decision="SELLER_APPROVED_VIA_LINK",
        offer_data={"final_price": neg.final_price},
    )
    db.commit()

    _generate_contract_if_agreed(db, neg)
    return {"status": "AGREED", "message": "Deal accepted — contract has been generated for both parties."}


@router.post("/seller-respond/{token}/reject")
def seller_reject_via_token(
    token: str,
    db: Session = Depends(get_db),
):
    """Public endpoint: seller rejects deal via unique token (no auth needed)."""
    neg = db.query(Negotiation).filter(Negotiation.seller_approval_token == token).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if neg.status != NegotiationStatus.SELLER_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Deal is no longer awaiting seller approval (status: {neg.status})")

    create_audit_record(
        db, neg.id, "SELLER_REJECTED",
        round_number=neg.current_round,
        decision="SELLER_REJECTED_VIA_LINK",
        offer_data={"rejected_price": neg.final_price},
    )

    neg.status = NegotiationStatus.WALKAWAY.value
    neg.final_price = None
    neg.final_quantity = None
    neg.final_delivery_days = None
    db.commit()
    return {"status": "WALKAWAY", "message": "Deal declined — negotiation has been terminated."}


@router.get("/{negotiation_id}", response_model=NegotiationResponse)
def get_negotiation(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get negotiation details. Private reservation prices are never leaked to counterparty."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return neg


@router.get("/{negotiation_id}/status", response_model=NegotiationStatusResponse)
def get_negotiation_status(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get real-time negotiation status (no private data)."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    latest_buyer = (
        db.query(Offer).filter(Offer.negotiation_id == negotiation_id, Offer.sender == "BUYER")
        .order_by(Offer.round_number.desc()).first()
    )
    latest_seller = (
        db.query(Offer).filter(Offer.negotiation_id == negotiation_id, Offer.sender == "SELLER")
        .order_by(Offer.round_number.desc()).first()
    )

    max_rounds = min(neg.buyer_max_rounds, neg.seller_max_rounds)
    return NegotiationStatusResponse(
        id=neg.id,
        status=neg.status,
        round=neg.current_round,
        buyer_latest_offer=latest_buyer.offer_price if latest_buyer else None,
        seller_latest_offer=latest_seller.offer_price if latest_seller else None,
        remaining_rounds=max(0, max_rounds - neg.current_round),
        final_price=neg.final_price,
    )


@router.post("/{negotiation_id}/start")
def start_negotiation(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initialize and start the negotiation."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != NegotiationStatus.CREATED.value:
        raise HTTPException(status_code=400, detail=f"Cannot start: status is {neg.status}")

    neg = initialize_negotiation(db, negotiation_id)
    return {"status": "initialized", "round": neg.current_round}


@router.post("/{negotiation_id}/run-round")
def run_round(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run one negotiation round (buyer + seller offers)."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    result = process_negotiation_round(db, negotiation_id)
    db.refresh(neg)
    result["current_status"] = neg.status
    result["current_round"] = neg.current_round
    return result


@router.post("/{negotiation_id}/run-full")
def run_full(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the complete negotiation until agreement or walkaway."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    all_rounds = run_full_negotiation(db, negotiation_id)
    db.refresh(neg)
    return {
        "status": neg.status,
        "final_price": neg.final_price,
        "total_rounds": neg.current_round,
        "rounds": all_rounds,
    }


@router.get("/{negotiation_id}/offers", response_model=List[OfferResponse])
def list_offers(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all offers in a negotiation."""
    offers = db.query(Offer).filter(Offer.negotiation_id == negotiation_id).order_by(Offer.round_number).all()
    return offers


@router.get("/{negotiation_id}/messages", response_model=List[MessageResponse])
def list_messages(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all messages in a negotiation."""
    msgs = db.query(Message).filter(Message.negotiation_id == negotiation_id).order_by(Message.created_at).all()
    return msgs


# ── Human Approval Endpoints ─────────────────────────────────────────────

@router.post("/{negotiation_id}/approve")
def approve_deal(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Buyer approves the converged deal → transitions HUMAN_APPROVAL → SELLER_APPROVAL."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != NegotiationStatus.HUMAN_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Cannot approve: status is {neg.status} (must be HUMAN_APPROVAL)")

    neg.status = NegotiationStatus.SELLER_APPROVAL.value

    # Generate unique seller approval token for the response link
    token = secrets.token_urlsafe(32)
    neg.seller_approval_token = token
    db.commit()

    create_audit_record(
        db, negotiation_id, "BUYER_APPROVED",
        round_number=neg.current_round,
        decision="BUYER_APPROVED",
        offer_data={"final_price": neg.final_price},
    )
    db.commit()

    # Build mock notification message with unique seller link
    seller_link = f"http://localhost:8000/seller-respond/{token}"
    mock_message = (
        f"[WhatsApp] Notification sent to {neg.seller_name or 'seller'} "
        f"({neg.seller_whatsapp or 'N/A'}):\n\n"
        f"\"Deal proposed: {neg.commodity} - {neg.quantity} {neg.unit} "
        f"at {neg.currency} {neg.final_price}/unit.\n"
        f"Reply YES to accept or click: {seller_link}\""
    )

    return {
        "status": "SELLER_APPROVAL",
        "final_price": neg.final_price,
        "seller_approval_token": token,
        "seller_link": seller_link,
        "message": f"Buyer approved at {neg.currency} {neg.final_price}/unit. {mock_message}",
    }


@router.post("/{negotiation_id}/seller-approve")
def seller_approve_deal(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seller approves the buyer-approved deal → transitions SELLER_APPROVAL → AGREED and generates contract."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != NegotiationStatus.SELLER_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Cannot seller-approve: status is {neg.status} (must be SELLER_APPROVAL)")

    neg.status = NegotiationStatus.AGREED.value
    db.commit()

    create_audit_record(
        db, negotiation_id, "SELLER_APPROVED",
        round_number=neg.current_round,
        decision="SELLER_APPROVED",
        offer_data={"final_price": neg.final_price},
    )
    db.commit()

    _generate_contract_if_agreed(db, neg)
    return {"status": "AGREED", "final_price": neg.final_price, "message": "Both parties approved — contract generated."}


@router.post("/{negotiation_id}/seller-reject")
def seller_reject_deal(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seller rejects the buyer-approved deal → transitions SELLER_APPROVAL → WALKAWAY."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != NegotiationStatus.SELLER_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Cannot seller-reject: status is {neg.status} (must be SELLER_APPROVAL)")

    create_audit_record(
        db, negotiation_id, "SELLER_REJECTED",
        round_number=neg.current_round,
        decision="SELLER_REJECTED",
        offer_data={"rejected_price": neg.final_price},
    )

    neg.status = NegotiationStatus.WALKAWAY.value
    neg.final_price = None
    neg.final_quantity = None
    neg.final_delivery_days = None
    db.commit()
    return {"status": "WALKAWAY", "message": "Seller rejected the deal — negotiation terminated."}


@router.post("/{negotiation_id}/reject")
def reject_deal(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Human rejects the converged deal → continues negotiation or walks away if max rounds reached."""
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != NegotiationStatus.HUMAN_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Cannot reject: status is {neg.status} (must be HUMAN_APPROVAL)")

    create_audit_record(
        db, negotiation_id, "HUMAN_REJECTED",
        round_number=neg.current_round,
        decision="REJECTED",
        offer_data={"rejected_price": neg.final_price},
    )

    # Rejection always stops the negotiation
    neg.status = NegotiationStatus.WALKAWAY.value
    neg.final_price = None
    neg.final_quantity = None
    neg.final_delivery_days = None
    db.commit()
    return {"status": "WALKAWAY", "message": "Deal rejected — negotiation terminated."}
