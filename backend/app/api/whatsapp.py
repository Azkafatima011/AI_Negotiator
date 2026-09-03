"""
WhatsApp integration — notifications & webhook.
Production: WhatsApp Business Platform Cloud API.
Development: Opens wa.me deep link for manual send.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import User, Negotiation, Contract
from app.security.auth import get_current_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations/whatsapp", tags=["WhatsApp"])


def build_agreement_message(neg: Negotiation, contract: Contract | None) -> str:
    """Build the WhatsApp message text sent after a deal is agreed."""
    total = (neg.final_price or 0) * (neg.final_quantity or neg.quantity)
    lines = [
        f"\U0001f91d *AI Negotiator — Deal Agreed: {neg.commodity}*",
        "",
        f"\U0001f4e6 Quantity   : {neg.quantity:,.0f} {neg.unit}",
        f"\U0001f4b0 Unit Price : {neg.currency} {neg.final_price:,.2f}/{neg.unit}",
        f"\U0001f4b5 Total Value: {neg.currency} {total:,.2f}",
        f"\U0001f69a Delivery   : {neg.final_delivery_days or neg.buyer_delivery_days} days",
        f"\U0001f4cb Payment    : {neg.buyer_payment_terms.replace('_', ' ')}",
        "",
    ]
    if contract:
        lines.append(f"\U0001f512 Contract ID: {contract.id[:8].upper()}")
        lines.append(f"\U0001f50d Doc Hash   : {contract.document_hash[:16]}...")
        lines.append("")
    lines.append("Agreed via AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform.")
    lines.append("Please confirm receipt to proceed with order fulfilment.")
    return "\n".join(lines)


def send_whatsapp_message(phone: str, message: str) -> dict:
    """
    Send a WhatsApp message via the Cloud API.
    Falls back to a wa.me deep-link URL when no API token is configured.
    """
    settings = get_settings()

    # Clean phone number (remove spaces/dashes, ensure + prefix)
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    if settings.whatsapp_access_token and settings.whatsapp_phone_number_id:
        # Production: call WhatsApp Cloud API
        import httpx
        url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }
        headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
        resp = httpx.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"WhatsApp sent to {phone}: {data}")
        return {"status": "sent", "phone": phone, "wa_message_id": data.get("messages", [{}])[0].get("id")}
    else:
        # Dev mode: generate wa.me deep link for manual send
        import urllib.parse
        encoded = urllib.parse.quote(message)
        wa_url = f"https://wa.me/{phone.lstrip('+')}"
        logger.info(f"WhatsApp dev-mode: open {wa_url} to send message manually")
        return {
            "status": "dev_link",
            "phone": phone,
            "wa_url": wa_url,
            "message": message,
            "note": "No WHATSAPP_ACCESS_TOKEN configured. Use wa_url to send manually.",
        }


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification endpoint."""
    settings = get_settings()
    verify_token = settings.whatsapp_webhook_verify_token or "your_webhook_verify_token"
    if hub_mode == "subscribe" and hub_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive incoming WhatsApp messages.
    Production: verify signature, parse message, route to negotiation engine.
    """
    body = await request.json()
    return {"status": "received", "entry_count": len(body.get("entry", []))}


@router.post("/notify-agreement")
async def notify_agreement(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send WhatsApp agreement notification to the seller for a completed negotiation.
    Returns a wa.me deep-link in dev mode when API token is not configured.
    """
    neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if neg.status != "AGREED":
        raise HTTPException(status_code=400, detail=f"Negotiation is not AGREED (status: {neg.status})")

    phone = neg.seller_whatsapp
    if not phone:
        raise HTTPException(status_code=422, detail="No WhatsApp number registered for this seller")

    contract = db.query(Contract).filter(Contract.negotiation_id == negotiation_id).first()
    message = build_agreement_message(neg, contract)

    try:
        result = send_whatsapp_message(phone, message)
    except Exception as exc:
        logger.error(f"WhatsApp send failed: {exc}")
        raise HTTPException(status_code=502, detail=f"WhatsApp send failed: {exc}")

    return result


@router.post("/send")
async def send_custom(
    negotiation_id: str,
    recipient: str,
    message: str,
    current_user: User = Depends(get_current_user),
):
    """Send a custom WhatsApp message (manual use)."""
    try:
        result = send_whatsapp_message(recipient, message)
        result["negotiation_id"] = negotiation_id
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
