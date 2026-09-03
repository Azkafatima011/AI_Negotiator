"""
Buyer Agent — autonomous procurement negotiation agent.
Uses deterministic math + optional LLM for communication and contextual adjustments.
"""
from typing import Optional
from app.agents.schemas import AgentResponseSchema
from app.agents.prompts import BUYER_SYSTEM_PROMPT


class BuyerAgent:
    def __init__(
        self,
        starting_price: float,
        reservation_price: float,
        strategy: str = "BALANCED",
        max_rounds: int = 10,
        delivery_days: int = 14,
        payment_terms: str = "30_DAYS",
    ):
        self.starting_price = starting_price
        self.reservation_price = reservation_price
        self.strategy = strategy
        self.max_rounds = max_rounds
        self.delivery_days = delivery_days
        self.payment_terms = payment_terms

    def get_system_prompt(
        self,
        commodity: str,
        quantity: float,
        unit: str,
        currency: str,
        current_round: int,
        history: str,
    ) -> str:
        return BUYER_SYSTEM_PROMPT.format(
            starting_price=self.starting_price,
            reservation_price=self.reservation_price,
            strategy=self.strategy,
            max_rounds=self.max_rounds,
            commodity=commodity,
            quantity=quantity,
            unit=unit,
            currency=currency,
            delivery_days=self.delivery_days,
            payment_terms=self.payment_terms,
            current_round=current_round,
            history=history or "No previous offers.",
        )

    def calculate_deterministic_offer(
        self,
        current_round: int,
        history: list,
    ) -> AgentResponseSchema:
        """
        Deterministic offer calculation — the math the controller always enforces.
        Uses concession curves based on strategy.
        """
        # Concession rates by strategy (linear model for predictable convergence)
        rates = {"STUBBORN": 0.08, "BALANCED": 0.13, "CONCEDING": 0.20}
        rate = rates.get(self.strategy, 0.13)

        # Linear concession: move steadily from starting toward reservation
        price_range = self.reservation_price - self.starting_price
        concession_factor = min(rate * current_round, 1.0)
        offer_price = self.starting_price + (price_range * concession_factor)

        # Clamp to reservation
        offer_price = min(offer_price, self.reservation_price)
        offer_price = round(offer_price, 2)

        # Determine action
        action = "OFFER" if current_round == 1 else "COUNTER_OFFER"

        # Check if we should walk away
        if current_round >= self.max_rounds:
            action = "WALKAWAY"

        return AgentResponseSchema(
            round=current_round,
            status="NEGOTIATING" if action != "WALKAWAY" else "TERMINATED",
            offer_price=offer_price,
            quantity=None,
            delivery_days=self.delivery_days,
            payment_terms=self.payment_terms,
            action=action,
            public_rationale=(
                f"We offer {currency_format(offer_price)} per unit based on our volume requirements "
                f"and market analysis. Round {current_round}."
            ),
        )

    def calculate_concession(self, current_round: int, offer_price: float) -> float:
        """Calculate concession percentage from starting price."""
        if self.starting_price == 0:
            return 0.0
        return round(((offer_price - self.starting_price) / self.starting_price) * 100, 2)


def currency_format(value: float) -> str:
    """Format a numeric value as currency string."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"
