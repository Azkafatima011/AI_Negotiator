"""
SQLAlchemy ORM models for AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform.
Maps to Alibaba Cloud RDS PostgreSQL in production, SQLite for MVP.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from app.database.database import Base
import enum


def generate_uuid():
    return str(uuid.uuid4())


# ── Enums ──────────────────────────────────────────────────────────────
class NegotiationStatus(str, enum.Enum):
    CREATED = "CREATED"
    INITIALIZED = "INITIALIZED"
    BUYER_TURN = "BUYER_TURN"
    SELLER_TURN = "SELLER_TURN"
    VALIDATING = "VALIDATING"
    CHECK_CONVERGENCE = "CHECK_CONVERGENCE"
    AGREED = "AGREED"
    TERMINATED = "TERMINATED"
    WALKAWAY = "WALKAWAY"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    SELLER_APPROVAL = "SELLER_APPROVAL"
    CANCELLED = "CANCELLED"


class AgentRole(str, enum.Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"


class Strategy(str, enum.Enum):
    STUBBORN = "STUBBORN"
    BALANCED = "BALANCED"
    CONCEDING = "CONCEDING"


class OfferAction(str, enum.Enum):
    OFFER = "OFFER"
    COUNTER_OFFER = "COUNTER_OFFER"
    ACCEPT = "ACCEPT"
    WALKAWAY = "WALKAWAY"
    ESCALATE = "ESCALATE"


class PaymentTerms(str, enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    SEVEN_DAYS = "7_DAYS"
    FIFTEEN_DAYS = "15_DAYS"
    THIRTY_DAYS = "30_DAYS"
    SIXTY_DAYS = "60_DAYS"
    NINETY_DAYS = "90_DAYS"


class ConvergenceMode(str, enum.Enum):
    MIDPOINT = "MIDPOINT"
    BUYER_ACCEPTS_SELLER = "BUYER_ACCEPTS_SELLER"
    SELLER_ACCEPTS_BUYER = "SELLER_ACCEPTS_BUYER"
    PREDEFINED_TARGET = "PREDEFINED_TARGET"
    MULTI_VARIABLE_SCORE = "MULTI_VARIABLE_SCORE"


class ApprovalMode(str, enum.Enum):
    AUTO = "AUTO"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


# ── Models ─────────────────────────────────────────────────────────────
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    business_type = Column(String(100), nullable=False)
    country = Column(String(100))
    currency = Column(String(10), default="PKR")
    contact_person = Column(String(200))
    whatsapp_business_number = Column(String(50))
    alibaba_com_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    businesses = relationship("Business", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(300), nullable=False)
    full_name = Column(String(200))
    role = Column(String(50), default="user")  # admin, manager, user
    is_active = Column(Boolean, default=True)
    organization_id = Column(String, ForeignKey("organizations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    business_type = Column(String(100))
    country = Column(String(100))
    currency = Column(String(10), default="PKR")
    contact_person = Column(String(200))
    whatsapp_number = Column(String(50))
    alibaba_auth_id = Column(String(100))
    organization_id = Column(String, ForeignKey("organizations.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="businesses")
    negotiations_as_buyer = relationship("Negotiation", foreign_keys="Negotiation.buyer_business_id", back_populates="buyer_business")
    negotiations_as_seller = relationship("Negotiation", foreign_keys="Negotiation.seller_business_id", back_populates="seller_business")


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(String, primary_key=True, default=generate_uuid)
    status = Column(String(50), default=NegotiationStatus.CREATED.value)

    # Commodity details
    commodity = Column(String(200), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), default="kg")
    currency = Column(String(10), default="PKR")

    # Buyer constraints
    buyer_business_id = Column(String, ForeignKey("businesses.id"))
    buyer_starting_price = Column(Float, nullable=False)
    buyer_reservation_price = Column(Float, nullable=False)
    buyer_delivery_days = Column(Integer, default=14)
    buyer_payment_terms = Column(String(50), default="30_DAYS")
    buyer_strategy = Column(String(50), default=Strategy.BALANCED.value)
    buyer_max_rounds = Column(Integer, default=10)

    # Seller constraints
    seller_business_id = Column(String, ForeignKey("businesses.id"))
    seller_name = Column(String(200), nullable=True)        # seller's real name/company
    seller_whatsapp = Column(String(50), nullable=True)     # seller's WhatsApp number
    seller_starting_price = Column(Float, nullable=True)
    seller_reservation_price = Column(Float, nullable=True)
    seller_delivery_days = Column(Integer, default=21)
    seller_payment_terms = Column(String(50), default="15_DAYS")
    seller_strategy = Column(String(50), default=Strategy.BALANCED.value)
    seller_max_rounds = Column(Integer, default=10)

    # Negotiation state
    current_round = Column(Integer, default=0)
    convergence_mode = Column(String(50), default=ConvergenceMode.MIDPOINT.value)
    approval_mode = Column(String(50), default=ApprovalMode.AUTO.value)

    # Results
    final_price = Column(Float, nullable=True)
    final_quantity = Column(Float, nullable=True)
    final_delivery_days = Column(Integer, nullable=True)

    # Market comparison
    mandi_rate = Column(Float, nullable=True)  # market rate at time of negotiation for comparison

    # Seller approval token (unique link sent via mock WhatsApp/SMS)
    seller_approval_token = Column(String(64), nullable=True, unique=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)

    # Batch negotiation FK (optional — set when this negotiation is part of a multi-seller batch)
    batch_id = Column(String, ForeignKey("negotiation_batches.id"), nullable=True)

    # Relationships
    buyer_business = relationship("Business", foreign_keys=[buyer_business_id], back_populates="negotiations_as_buyer")
    seller_business = relationship("Business", foreign_keys=[seller_business_id], back_populates="negotiations_as_seller")
    offers = relationship("Offer", back_populates="negotiation", order_by="Offer.round_number")
    messages = relationship("Message", back_populates="negotiation")
    audit_records = relationship("AuditRecord", back_populates="negotiation")
    contract = relationship("Contract", back_populates="negotiation", uselist=False)
    batch = relationship("NegotiationBatch", back_populates="negotiations", foreign_keys=[batch_id])


class Offer(Base):
    __tablename__ = "offers"

    id = Column(String, primary_key=True, default=generate_uuid)
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    sender = Column(String(20), nullable=False)  # BUYER or SELLER

    offer_price = Column(Float, nullable=False)
    quantity = Column(Float)
    delivery_days = Column(Integer)
    payment_terms = Column(String(50))

    action = Column(String(50), nullable=False)
    public_rationale = Column(Text)
    validation_result = Column(String(50), default="VALID")

    # Agent telemetry (private, not exposed to counterparty)
    strategy_used = Column(String(50))
    concession_percentage = Column(Float)
    model_used = Column(String(100))
    model_request_id = Column(String(200))

    created_at = Column(DateTime, default=datetime.utcnow)

    negotiation = relationship("Negotiation", back_populates="offers")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=False)
    sender = Column(String(20), nullable=False)
    receiver = Column(String(20))
    message_type = Column(String(50), default="TEXT")
    body = Column(Text, nullable=False)
    external_message_id = Column(String(200))
    channel = Column(String(50), default="INTERNAL")  # INTERNAL, WHATSAPP
    created_at = Column(DateTime, default=datetime.utcnow)

    negotiation = relationship("Negotiation", back_populates="messages")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(String, primary_key=True, default=generate_uuid)
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=False, unique=True)
    buyer_name = Column(String(200))
    seller_name = Column(String(200))
    commodity = Column(String(200))
    quantity = Column(Float)
    unit = Column(String(50))
    unit_price = Column(Float)
    total_value = Column(Float)
    currency = Column(String(10))
    delivery_days = Column(Integer)
    payment_terms = Column(String(50))
    shipping_terms = Column(String(100))
    quality_requirements = Column(Text)
    agreement_timestamp = Column(DateTime)
    document_hash = Column(String(200))
    signature = Column(Text)
    document_path = Column(String(500))
    status = Column(String(50), default="GENERATED")
    created_at = Column(DateTime, default=datetime.utcnow)

    negotiation = relationship("Negotiation", back_populates="contract")


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=False)
    round_number = Column(Integer)
    event_type = Column(String(100), nullable=False)
    sender = Column(String(50))
    receiver = Column(String(50))
    public_message = Column(Text)
    offer_data = Column(JSON)
    decision = Column(String(50))
    validation_result = Column(String(50))
    model_used = Column(String(100))
    model_request_id = Column(String(200))
    message_id = Column(String(200))
    record_hash = Column(String(200))
    previous_hash = Column(String(200))
    signature = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    negotiation = relationship("Negotiation", back_populates="audit_records")


class NegotiationBatch(Base):
    """Groups N individual Negotiation records for the same commodity/buyer against N different sellers."""
    __tablename__ = "negotiation_batches"

    id = Column(String, primary_key=True, default=generate_uuid)
    commodity = Column(String(200), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), default="kg")
    currency = Column(String(10), default="PKR")
    status = Column(String(50), default="RUNNING")  # RUNNING / COMPLETED / PARTIAL
    best_negotiation_id = Column(String, nullable=True)  # winner negotiation id
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    negotiations = relationship("Negotiation", back_populates="batch",
                                foreign_keys="Negotiation.batch_id",
                                order_by="Negotiation.created_at")


class SupplierCandidate(Base):
    __tablename__ = "supplier_candidates"

    id = Column(String, primary_key=True, default=generate_uuid)
    supplier_name = Column(String(200), nullable=False)
    commodity = Column(String(200))
    country = Column(String(100))
    price = Column(Float)
    currency = Column(String(10), default="PKR")
    minimum_order_quantity = Column(Float)
    unit = Column(String(50), default="kg")
    availability = Column(String(200))
    shipping_info = Column(Text)
    supplier_rating = Column(Float)
    alibaba_com_id = Column(String(200))
    score = Column(Float)
    selected = Column(Boolean, default=False)
    # Contact & business info
    whatsapp_number = Column(String(50), nullable=True)
    business_type = Column(String(100), nullable=True)  # e.g. "Rice Mill", "Sugar Mill", "Spice Trader"
    city = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
