"""
Multi-Variable Scoring Engine.
Calculates deal scores across price, quantity, delivery, quality, payment, and shipping.
"""
from typing import Optional


def calculate_price_score(
    offer_price: float,
    ideal_price: float,
    reservation_price: float,
    role: str,
) -> float:
    """
    Score the price component.
    Buyer: lower is better. Seller: higher is better.
    Returns 0.0 to 1.0.
    """
    if role == "BUYER":
        if offer_price <= ideal_price:
            return 1.0
        if offer_price >= reservation_price:
            return 0.0
        range_val = reservation_price - ideal_price
        if range_val == 0:
            return 0.5
        return 1.0 - ((offer_price - ideal_price) / range_val)
    else:  # SELLER
        if offer_price >= ideal_price:
            return 1.0
        if offer_price <= reservation_price:
            return 0.0
        range_val = ideal_price - reservation_price
        if range_val == 0:
            return 0.5
        return (offer_price - reservation_price) / range_val


def calculate_delivery_score(
    offered_days: int,
    ideal_days: int,
    max_days: int,
) -> float:
    """Score delivery timeline. Lower is better."""
    if offered_days <= ideal_days:
        return 1.0
    if offered_days >= max_days:
        return 0.0
    range_val = max_days - ideal_days
    if range_val == 0:
        return 0.5
    return 1.0 - ((offered_days - ideal_days) / range_val)


def calculate_deal_score(
    offer_price: float,
    buyer_ideal: float,
    seller_ideal: float,
    buyer_reservation: float,
    seller_reservation: float,
    delivery_days: Optional[int] = None,
    buyer_ideal_delivery: int = 14,
    seller_ideal_delivery: int = 21,
    max_delivery: int = 30,
) -> dict:
    """
    Calculate multi-variable deal score.
    Returns individual component scores and weighted total.
    """
    buyer_price_score = calculate_price_score(offer_price, buyer_ideal, buyer_reservation, "BUYER")
    seller_price_score = calculate_price_score(offer_price, seller_ideal, seller_reservation, "SELLER")

    result = {
        "buyer_price_score": round(buyer_price_score, 3),
        "seller_price_score": round(seller_price_score, 3),
        "price_overlap": buyer_reservation >= seller_reservation,
    }

    if delivery_days is not None:
        buyer_delivery_score = calculate_delivery_score(delivery_days, buyer_ideal_delivery, max_delivery)
        seller_delivery_score = calculate_delivery_score(delivery_days, seller_ideal_delivery, max_delivery)
        result["buyer_delivery_score"] = round(buyer_delivery_score, 3)
        result["seller_delivery_score"] = round(seller_delivery_score, 3)

    return result


def check_convergence(
    buyer_offer: float,
    seller_offer: float,
    mode: str = "MIDPOINT",
) -> dict:
    """
    Check if negotiation has converged.
    Returns agreement status and final terms.
    """
    if buyer_offer >= seller_offer:
        if mode == "MIDPOINT":
            final_price = (buyer_offer + seller_offer) / 2
        elif mode == "BUYER_ACCEPTS_SELLER":
            final_price = seller_offer
        elif mode == "SELLER_ACCEPTS_BUYER":
            final_price = buyer_offer
        else:
            final_price = (buyer_offer + seller_offer) / 2

        return {
            "converged": True,
            "final_price": round(final_price, 2),
            "mode": mode,
        }

    return {
        "converged": False,
        "gap": round(seller_offer - buyer_offer, 2),
        "mode": mode,
    }
