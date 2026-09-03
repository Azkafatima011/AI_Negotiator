"""
LLM Integration — Alibaba Cloud Model Studio / Qwen (OpenAI-compatible API).
Falls back to deterministic calculation if LLM is unavailable.
"""
import json
import logging
from typing import Optional

from app.config import get_settings
from app.agents.schemas import AgentResponseSchema

logger = logging.getLogger(__name__)


def _build_history_text(history: list, role: str) -> str:
    """Build a readable history string for the LLM prompt."""
    if not history:
        return "No previous offers."
    lines = []
    for offer in history:
        sender = offer.sender if hasattr(offer, "sender") else offer.get("sender", "Unknown")
        price = offer.offer_price if hasattr(offer, "offer_price") else offer.get("offer_price", 0)
        round_num = offer.round_number if hasattr(offer, "round_number") else offer.get("round_number", 0)
        rationale = offer.public_rationale if hasattr(offer, "public_rationale") else offer.get("public_rationale", "")
        lines.append(f"Round {round_num} — {sender}: Price={price}, Rationale: {rationale}")
    return "\n".join(lines)


def get_llm_response(
    agent,
    history: list,
    current_round: int,
    negotiation,
) -> AgentResponseSchema:
    """
    Get LLM-generated offer. Falls back to deterministic if LLM is unavailable.
    Pipeline: Qwen → Raw Response → JSON Extraction → Pydantic Validation → Business Rules
    """
    settings = get_settings()

    # If no API key configured, use deterministic
    if not settings.alibaba_model_studio_api_key:
        logger.info("No LLM API key configured — using deterministic agent")
        return agent.calculate_deterministic_offer(current_round, history)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.alibaba_model_studio_api_key,
            base_url=settings.alibaba_model_studio_base_url,
        )

        history_text = _build_history_text(history, agent.__class__.__name__)
        system_prompt = agent.get_system_prompt(
            commodity=negotiation.commodity,
            quantity=negotiation.quantity,
            unit=negotiation.unit,
            currency=negotiation.currency,
            current_round=current_round,
            history=history_text,
        )

        response = client.chat.completions.create(
            model=settings.qwen_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate your offer for round {current_round}. Return only JSON."},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        # Extract JSON from response
        parsed = json.loads(raw_content)
        agent_response = AgentResponseSchema(**parsed)

        return agent_response

    except Exception as e:
        logger.warning(f"LLM call failed: {e} — falling back to deterministic agent")
        return agent.calculate_deterministic_offer(current_round, history)
