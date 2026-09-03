"""
Negotiation State Machine
Deterministic state transitions for the negotiation lifecycle.
The controller owns the mathematics — LLM is never the final authority over money.
"""
from app.database.models import NegotiationStatus, OfferAction


# Valid state transitions
VALID_TRANSITIONS = {
    NegotiationStatus.CREATED: [NegotiationStatus.INITIALIZED],
    NegotiationStatus.INITIALIZED: [NegotiationStatus.BUYER_TURN, NegotiationStatus.CANCELLED],
    NegotiationStatus.BUYER_TURN: [NegotiationStatus.VALIDATING, NegotiationStatus.CANCELLED],
    NegotiationStatus.SELLER_TURN: [NegotiationStatus.VALIDATING, NegotiationStatus.CANCELLED],
    NegotiationStatus.VALIDATING: [
        NegotiationStatus.CHECK_CONVERGENCE,
        NegotiationStatus.TERMINATED,  # on validation failure
    ],
    NegotiationStatus.CHECK_CONVERGENCE: [
        NegotiationStatus.AGREED,
        NegotiationStatus.WALKAWAY,
        NegotiationStatus.HUMAN_APPROVAL,
        NegotiationStatus.BUYER_TURN,
        NegotiationStatus.SELLER_TURN,
        NegotiationStatus.TERMINATED,
    ],
    NegotiationStatus.HUMAN_APPROVAL: [
        NegotiationStatus.AGREED,
        NegotiationStatus.TERMINATED,
    ],
    NegotiationStatus.AGREED: [],
    NegotiationStatus.TERMINATED: [],
    NegotiationStatus.WALKAWAY: [],
    NegotiationStatus.CANCELLED: [],
}


def can_transition(from_status: str, to_status: str) -> bool:
    """Check if a state transition is valid."""
    from_enum = NegotiationStatus(from_status)
    to_enum = NegotiationStatus(to_status)
    return to_enum in VALID_TRANSITIONS.get(from_enum, [])


def get_next_turn(current_status: str, action: str, round_num: int, max_rounds: int) -> str:
    """Determine the next state based on current state and action."""
    if action == OfferAction.WALKAWAY.value:
        return NegotiationStatus.WALKAWAY.value
    if action == OfferAction.ESCALATE.value:
        return NegotiationStatus.HUMAN_APPROVAL.value

    if current_status == NegotiationStatus.INITIALIZED.value:
        return NegotiationStatus.BUYER_TURN.value

    if current_status == NegotiationStatus.BUYER_TURN.value:
        return NegotiationStatus.SELLER_TURN.value

    if current_status == NegotiationStatus.SELLER_TURN.value:
        if round_num >= max_rounds:
            return NegotiationStatus.WALKAWAY.value
        return NegotiationStatus.BUYER_TURN.value

    return current_status
