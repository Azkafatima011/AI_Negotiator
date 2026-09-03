"""
Business Rules & Reservation Boundary Enforcement.
The LLM is never trusted to enforce its own financial boundary.
"""
from app.agents.schemas import AgentResponseSchema


class ValidationResult:
    def __init__(self, valid: bool, reason: str = ""):
        self.valid = valid
        self.reason = reason


def validate_buyer_offer(
    offer: AgentResponseSchema,
    reservation_price: float,
    max_rounds: int,
    current_round: int,
) -> ValidationResult:
    """Validate buyer agent offer against business constraints."""
    if offer.offer_price > reservation_price:
        return ValidationResult(
            False,
            f"Buyer offer {offer.offer_price} exceeds reservation price {reservation_price}"
        )
    if offer.offer_price <= 0:
        return ValidationResult(False, "Offer price must be positive")
    if current_round > max_rounds:
        return ValidationResult(False, f"Round {current_round} exceeds max rounds {max_rounds}")
    if offer.round != current_round:
        return ValidationResult(False, f"Round mismatch: expected {current_round}, got {offer.round}")
    return ValidationResult(True)


def validate_seller_offer(
    offer: AgentResponseSchema,
    reservation_price: float,
    max_rounds: int,
    current_round: int,
) -> ValidationResult:
    """Validate seller agent offer against business constraints."""
    if offer.offer_price < reservation_price:
        return ValidationResult(
            False,
            f"Seller offer {offer.offer_price} below reservation price {reservation_price}"
        )
    if offer.offer_price <= 0:
        return ValidationResult(False, "Offer price must be positive")
    if current_round > max_rounds:
        return ValidationResult(False, f"Round {current_round} exceeds max rounds {max_rounds}")
    if offer.round != current_round:
        return ValidationResult(False, f"Round mismatch: expected {current_round}, got {offer.round}")
    return ValidationResult(True)


def check_boundary_violation(offer_price: float, reservation_price: float, role: str) -> bool:
    """Check if offer violates reservation boundary."""
    if role == "BUYER":
        return offer_price > reservation_price
    else:
        return offer_price < reservation_price
