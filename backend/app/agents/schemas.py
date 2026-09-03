"""
Pydantic v2 schemas for API request/response validation.
Ensures strict JSON validation — LLM output never directly modifies business state.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
from datetime import datetime
from decimal import Decimal


# ── Auth Schemas ───────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., max_length=200)
    organization_name: str = Field(default="Default Org", max_length=200)

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Business Schemas ──────────────────────────────────────────────────
class BusinessCreate(BaseModel):
    name: str = Field(..., max_length=200)
    business_type: str = Field(default="wholesaler")
    country: str = Field(default="Pakistan")
    currency: str = Field(default="PKR")
    contact_person: str = Field(default="")
    whatsapp_number: str = Field(default="")

class BusinessResponse(BaseModel):
    id: str
    name: str
    business_type: str
    country: str
    currency: str
    contact_person: str
    whatsapp_number: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Negotiation Schemas ──────────────────────────────────────────────
class NegotiationCreate(BaseModel):
    role: Literal["BUYER", "SELLER"] = "BUYER"
    commodity: str = Field(..., max_length=200)
    quantity: float = Field(..., gt=0)
    unit: str = Field(default="kg")
    currency: str = Field(default="PKR")

    # Buyer sets their own params
    buyer_starting_price: float = Field(..., gt=0)
    buyer_reservation_price: float = Field(..., gt=0)
    buyer_delivery_days: int = Field(default=14, gt=0)
    buyer_payment_terms: str = Field(default="30_DAYS")
    buyer_strategy: Literal["STUBBORN", "BALANCED", "CONCEDING"] = "BALANCED"
    buyer_max_rounds: int = Field(default=10, gt=0, le=50)

    # Seller contact info
    seller_name: Optional[str] = Field(default=None, max_length=200)
    seller_whatsapp: Optional[str] = Field(default=None, max_length=50,
        description="Seller's WhatsApp number in international format e.g. +923001234567")

    # Seller negotiation params — if None, AI auto-estimates from buyer's constraints.
    # Buyer can set these if they know the seller's expected pricing.
    seller_starting_price: Optional[float] = Field(default=None, gt=0)
    seller_reservation_price: Optional[float] = Field(default=None, gt=0)
    seller_delivery_days: int = Field(default=21, gt=0)
    seller_payment_terms: str = Field(default="15_DAYS")
    seller_strategy: Literal["STUBBORN", "BALANCED", "CONCEDING"] = "BALANCED"
    seller_max_rounds: int = Field(default=10, gt=0, le=50)

    # Market rate for comparison display
    mandi_rate: Optional[float] = Field(default=None, ge=0)

    convergence_mode: str = Field(default="MIDPOINT")
    approval_mode: str = Field(default="AUTO")

    @field_validator("buyer_reservation_price")
    @classmethod
    def validate_buyer_reservation(cls, v, info):
        starting = info.data.get("buyer_starting_price")
        if starting and v <= starting:
            raise ValueError("Reservation price must be > starting price for buyer (buyer wants to buy cheap)")
        return v

class NegotiationResponse(BaseModel):
    id: str
    status: str
    commodity: str
    quantity: float
    unit: str
    currency: str
    current_round: int
    buyer_starting_price: float
    buyer_reservation_price: float
    buyer_delivery_days: int
    buyer_strategy: str
    seller_name: Optional[str]
    seller_whatsapp: Optional[str]
    seller_starting_price: Optional[float]
    seller_reservation_price: Optional[float]
    seller_delivery_days: int
    seller_strategy: str
    final_price: Optional[float]
    final_quantity: Optional[float]
    mandi_rate: Optional[float] = None
    batch_id: Optional[str] = None
    seller_approval_token: Optional[str] = None
    convergence_mode: str
    approval_mode: str
    created_at: datetime
    model_config = {"from_attributes": True}

class NegotiationStatusResponse(BaseModel):
    id: str
    status: str
    round: int
    buyer_latest_offer: Optional[float]
    seller_latest_offer: Optional[float]
    remaining_rounds: int
    final_price: Optional[float]
    model_config = {"from_attributes": True}

class NegotiationListItem(BaseModel):
    id: str
    status: str
    commodity: str
    quantity: float
    unit: str
    currency: str
    current_round: int
    final_price: Optional[float]
    batch_id: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Agent Output Schema ──────────────────────────────────────────────
class AgentResponseSchema(BaseModel):
    """Strict schema for agent LLM output. Never trusted directly."""
    round: int
    status: Literal["NEGOTIATING", "AGREED", "TERMINATED", "ESCALATE"]
    offer_price: float
    quantity: Optional[float] = None
    delivery_days: Optional[int] = None
    payment_terms: Optional[str] = None
    action: Literal["OFFER", "COUNTER_OFFER", "ACCEPT", "WALKAWAY", "ESCALATE"]
    public_rationale: str = Field(max_length=500)


# ── Offer Schemas ────────────────────────────────────────────────────
class OfferCreate(BaseModel):
    sender: Literal["BUYER", "SELLER"]
    offer_price: float = Field(..., gt=0)
    quantity: Optional[float] = None
    delivery_days: Optional[int] = None
    payment_terms: Optional[str] = None
    public_rationale: str = Field(default="", max_length=500)

class OfferResponse(BaseModel):
    id: str
    negotiation_id: str
    round_number: int
    sender: str
    offer_price: float
    quantity: Optional[float]
    delivery_days: Optional[int]
    payment_terms: Optional[str]
    action: str
    public_rationale: str
    validation_result: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Message Schemas ──────────────────────────────────────────────────
class MessageResponse(BaseModel):
    id: str
    negotiation_id: str
    sender: str
    receiver: Optional[str]
    message_type: str
    body: str
    channel: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Contract Schemas ─────────────────────────────────────────────────
class ContractResponse(BaseModel):
    id: str
    negotiation_id: str
    buyer_name: Optional[str]
    seller_name: Optional[str]
    commodity: str
    quantity: float
    unit: str
    unit_price: float
    total_value: float
    currency: str
    delivery_days: int
    payment_terms: str
    agreement_timestamp: Optional[datetime]
    document_hash: Optional[str]
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Audit Schemas ────────────────────────────────────────────────────
class AuditRecordResponse(BaseModel):
    id: str
    negotiation_id: str
    round_number: Optional[int]
    event_type: str
    sender: Optional[str]
    receiver: Optional[str]
    public_message: Optional[str]
    decision: Optional[str]
    validation_result: Optional[str]
    model_used: Optional[str]
    record_hash: Optional[str]
    previous_hash: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Supplier Schemas ─────────────────────────────────────────────────
class SupplierResponse(BaseModel):
    id: str
    supplier_name: str
    commodity: str
    country: str
    price: Optional[float]
    currency: str
    minimum_order_quantity: Optional[float]
    unit: str
    supplier_rating: Optional[float]
    score: Optional[float]
    selected: bool
    whatsapp_number: Optional[str] = None
    business_type: Optional[str] = None
    city: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Batch Negotiation Schemas ─────────────────────────────────────────
class SellerInput(BaseModel):
    """A single seller's contact info for a batch negotiation request."""
    seller_name: str = Field(..., max_length=200)
    seller_whatsapp: Optional[str] = Field(default=None, max_length=50,
        description="Seller's WhatsApp number in international format e.g. +923001234567")
    # Optional: if buyer knows the seller's expected pricing
    seller_starting_price: Optional[float] = Field(default=None, gt=0)
    seller_reservation_price: Optional[float] = Field(default=None, gt=0)


class BatchCreate(BaseModel):
    """Request body to create a multi-seller batch negotiation."""
    commodity: str = Field(..., max_length=200)
    quantity: float = Field(..., gt=0)
    unit: str = Field(default="kg")
    currency: str = Field(default="PKR")
    # Buyer params
    buyer_starting_price: float = Field(..., gt=0)
    buyer_reservation_price: float = Field(..., gt=0)
    buyer_delivery_days: int = Field(default=14, gt=0)
    buyer_payment_terms: str = Field(default="30_DAYS")
    buyer_strategy: Literal["STUBBORN", "BALANCED", "CONCEDING"] = "BALANCED"
    buyer_max_rounds: int = Field(default=10, gt=0, le=50)
    # Sellers list (min 2, max 10)
    sellers: List[SellerInput] = Field(..., min_length=2, max_length=10)
    # Market rate for comparison
    mandi_rate: Optional[float] = Field(default=None, ge=0)
    convergence_mode: str = Field(default="MIDPOINT")
    approval_mode: str = Field(default="AUTO")

    @field_validator("buyer_reservation_price")
    @classmethod
    def validate_buyer_reservation(cls, v, info):
        starting = info.data.get("buyer_starting_price")
        if starting and v <= starting:
            raise ValueError("Reservation price must be > starting price")
        return v


class BatchResponse(BaseModel):
    """Response for a batch negotiation with ranked results."""
    id: str
    commodity: str
    quantity: float
    unit: str
    currency: str
    status: str
    best_negotiation_id: Optional[str]
    negotiations: List[NegotiationResponse]
    created_at: datetime
    model_config = {"from_attributes": True}


class BatchListItem(BaseModel):
    """Summary row for batch list table."""
    id: str
    commodity: str
    quantity: float
    unit: str
    currency: str
    status: str
    best_negotiation_id: Optional[str]
    seller_count: int
    best_price: Optional[float]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Market Rates ────────────────────────────────────────────────────
class MandiRateResponse(BaseModel):
    """Current mandi (market) rates for commodities."""
    commodity: str
    rate_per_kg: float
    currency: str = "PKR"
    source: str = "Estimated"
    updated_at: str


# ── Dashboard Stats ──────────────────────────────────────────────────
class DashboardStats(BaseModel):
    active_negotiations: int
    completed_deals: int
    terminated_negotiations: int
    pending_approvals: int
    total_negotiated_value: float
    average_rounds: float
    agreement_rate: float
    walkaway_rate: float
    total_suppliers: int
