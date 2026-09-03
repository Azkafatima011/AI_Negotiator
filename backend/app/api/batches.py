"""
Batch Negotiation API endpoints.
Allows a buyer to negotiate simultaneously with multiple sellers for the same commodity.
All negotiations run sequentially (synchronous MVP); the best deal is auto-selected.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Negotiation, NegotiationBatch, Business, NegotiationStatus, User
from app.security.auth import get_current_user
from app.agents.schemas import BatchCreate, BatchResponse, BatchListItem, NegotiationResponse
from app.negotiation.engine import run_full_negotiation

router = APIRouter(prefix="/api/v1/batches", tags=["Batch Negotiations"])


def _build_neg_response(neg: Negotiation) -> NegotiationResponse:
    """Convert a Negotiation ORM object to its Pydantic response schema."""
    return NegotiationResponse.model_validate(neg)


def _build_batch_response(batch: NegotiationBatch) -> BatchResponse:
    """Build a BatchResponse with negotiations sorted: AGREED first (lowest price), then WALKAWAY."""
    agreed = sorted(
        [n for n in batch.negotiations if n.status == "AGREED" and n.final_price],
        key=lambda n: n.final_price,
    )
    others = [n for n in batch.negotiations if n.status != "AGREED"]
    ranked = agreed + others

    return BatchResponse(
        id=batch.id,
        commodity=batch.commodity,
        quantity=batch.quantity,
        unit=batch.unit,
        currency=batch.currency,
        status=batch.status,
        best_negotiation_id=batch.best_negotiation_id,
        negotiations=[_build_neg_response(n) for n in ranked],
        created_at=batch.created_at,
    )


@router.post("", response_model=BatchResponse)
def create_batch(
    data: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a batch negotiation.
    Spins up one Negotiation per seller, runs all negotiations to completion,
    then picks the best deal (lowest final_price among AGREED).
    """
    # ── 1. Get or create the buyer's Business record ──
    buyer_biz = db.query(Business).filter(
        Business.organization_id == current_user.organization_id,
        Business.business_type == "wholesaler",
    ).first()
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

    # ── 2. Create the NegotiationBatch record ──
    batch = NegotiationBatch(
        commodity=data.commodity,
        quantity=data.quantity,
        unit=data.unit,
        currency=data.currency,
        status="RUNNING",
        organization_id=current_user.organization_id,
    )
    db.add(batch)
    db.flush()

    # ── 3. Create one Negotiation per seller ──
    negotiations = []
    for seller_input in data.sellers:
        # Each seller gets their own Business record
        seller_biz = Business(
            name=seller_input.seller_name,
            business_type="supplier",
            country="Pakistan",
            currency=data.currency,
            contact_person=seller_input.seller_name,
            whatsapp_number=seller_input.seller_whatsapp or "",
            organization_id=current_user.organization_id,
        )
        db.add(seller_biz)
        db.flush()

        # Auto-estimate seller AI params from buyer constraints if not provided
        auto_seller_start = data.buyer_reservation_price * 1.30
        auto_seller_reserve = data.buyer_starting_price * 0.90

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
            seller_name=seller_input.seller_name,
            seller_whatsapp=seller_input.seller_whatsapp or "",
            seller_starting_price=seller_input.seller_starting_price or auto_seller_start,
            seller_reservation_price=seller_input.seller_reservation_price or auto_seller_reserve,
            seller_delivery_days=21,
            seller_payment_terms="15_DAYS",
            seller_strategy="BALANCED",
            seller_max_rounds=data.buyer_max_rounds,
            convergence_mode=data.convergence_mode,
            approval_mode=data.approval_mode,
            mandi_rate=data.mandi_rate,
            status=NegotiationStatus.CREATED.value,
            batch_id=batch.id,
        )
        db.add(neg)
        db.flush()
        negotiations.append(neg)

    db.commit()

    # ── 4. Run all negotiations sequentially ──
    for neg in negotiations:
        try:
            run_full_negotiation(db, neg.id)
            db.refresh(neg)
        except Exception as e:
            # Mark as WALKAWAY if engine throws, continue with remaining
            neg.status = NegotiationStatus.WALKAWAY.value
            db.commit()

    # ── 5. Determine best deal ──
    db.refresh(batch)
    agreed_negs = [n for n in batch.negotiations if n.status == "AGREED" and n.final_price]
    if agreed_negs:
        best = min(agreed_negs, key=lambda n: n.final_price)
        batch.best_negotiation_id = best.id
        batch.status = "COMPLETED"
    else:
        # No agreement reached with any seller
        batch.status = "PARTIAL" if any(n.status == "AGREED" for n in batch.negotiations) else "WALKAWAY"

    db.commit()
    db.refresh(batch)

    return _build_batch_response(batch)


@router.get("", response_model=List[BatchListItem])
def list_batches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all batch negotiations for the current organisation."""
    batches = (
        db.query(NegotiationBatch)
        .filter(NegotiationBatch.organization_id == current_user.organization_id)
        .order_by(NegotiationBatch.created_at.desc())
        .all()
    )

    result = []
    for batch in batches:
        agreed = [n for n in batch.negotiations if n.status == "AGREED" and n.final_price]
        best_price = min((n.final_price for n in agreed), default=None)
        result.append(BatchListItem(
            id=batch.id,
            commodity=batch.commodity,
            quantity=batch.quantity,
            unit=batch.unit,
            currency=batch.currency,
            status=batch.status,
            best_negotiation_id=batch.best_negotiation_id,
            seller_count=len(batch.negotiations),
            best_price=best_price,
            created_at=batch.created_at,
        ))

    return result


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a batch with all child negotiations, ranked best-to-worst."""
    batch = db.query(NegotiationBatch).filter(NegotiationBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _build_batch_response(batch)


@router.post("/{batch_id}/accept/{negotiation_id}")
def accept_deal(
    batch_id: str,
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually mark one negotiation from the batch as the accepted/winning deal.
    Updates batch.best_negotiation_id.
    """
    batch = db.query(NegotiationBatch).filter(NegotiationBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    neg = db.query(Negotiation).filter(
        Negotiation.id == negotiation_id,
        Negotiation.batch_id == batch_id,
    ).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found in this batch")

    batch.best_negotiation_id = negotiation_id
    db.commit()
    return {"status": "accepted", "batch_id": batch_id, "negotiation_id": negotiation_id}
