"""
Contract & Audit API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Contract, AuditRecord, Negotiation, NegotiationStatus, Offer
from app.security.auth import get_current_user
from app.database.models import User
from app.agents.schemas import ContractResponse, AuditRecordResponse

router = APIRouter(tags=["Contracts & Audit"])


@router.get("/api/v1/negotiations/{negotiation_id}/contract", response_model=ContractResponse)
def get_contract(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the generated contract for a negotiation."""
    contract = db.query(Contract).filter(Contract.negotiation_id == negotiation_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="No contract found for this negotiation")
    return contract


@router.get("/api/v1/contracts", response_model=List[ContractResponse])
def list_contracts(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all contracts."""
    contracts = db.query(Contract).offset(skip).limit(limit).all()
    return contracts


@router.get("/api/v1/negotiations/{negotiation_id}/audit", response_model=List[AuditRecordResponse])
def get_audit_trail(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the complete audit trail for a negotiation."""
    records = (
        db.query(AuditRecord)
        .filter(AuditRecord.negotiation_id == negotiation_id)
        .order_by(AuditRecord.created_at)
        .all()
    )
    return records


def _render_contract_html(contract: Contract, negotiation: Negotiation, offers: list) -> str:
    """Render a full B2B contract document as HTML."""
    agreement_date = (contract.agreement_timestamp or contract.created_at).strftime("%B %d, %Y")
    created_date = contract.created_at.strftime("%B %d, %Y at %H:%M UTC")

    # Build offer history rows
    offer_rows = ""
    for o in offers:
        sender_badge = "buyer" if o.sender == "BUYER" else "seller"
        offer_rows += f"""
        <tr>
            <td>{o.round_number}</td>
            <td><span class="badge {sender_badge}">{o.sender}</span></td>
            <td>{contract.currency} {o.offer_price:,.2f}/{contract.unit}</td>
            <td>{o.quantity or contract.quantity:,.0f} {contract.unit}</td>
            <td>{o.delivery_days or '—'} days</td>
            <td>{o.payment_terms or '—'}</td>
            <td>{o.action}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Contract — {contract.commodity} — {contract.id[:8].upper()}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1a1a2e; background: #f8f9fa; line-height: 1.6; }}
    .contract-wrapper {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
    .contract-doc {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 60px 50px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    .contract-header {{ text-align: center; border-bottom: 3px double #1a1a2e; padding-bottom: 24px; margin-bottom: 32px; }}
    .contract-header h1 {{ font-size: 28px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 4px; }}
    .contract-header .subtitle {{ font-size: 14px; color: #666; letter-spacing: 1px; }}
    .contract-header .contract-id {{ font-size: 12px; color: #999; margin-top: 8px; font-family: monospace; }}
    .section {{ margin-bottom: 28px; }}
    .section-title {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #1a1a2e; border-bottom: 1px solid #e0e0e0; padding-bottom: 6px; margin-bottom: 14px; }}
    .party-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
    .party-box {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; background: #fafbfc; }}
    .party-box .role {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 4px; }}
    .party-box .name {{ font-size: 18px; font-weight: 600; }}
    .terms-table {{ width: 100%; border-collapse: collapse; }}
    .terms-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
    .terms-table td:first-child {{ font-weight: 600; width: 200px; color: #555; }}
    .terms-table td:last-child {{ color: #1a1a2e; }}
    .highlight {{ background: linear-gradient(135deg, #e8f5e9, #f1f8e9); border: 1px solid #c8e6c9; border-radius: 6px; padding: 20px; text-align: center; margin: 20px 0; }}
    .highlight .amount {{ font-size: 32px; font-weight: 700; color: #2e7d32; }}
    .highlight .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 4px; }}
    .offer-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .offer-table th {{ background: #f5f5f5; padding: 8px 10px; text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #e0e0e0; }}
    .offer-table td {{ padding: 6px 10px; border-bottom: 1px solid #f0f0f0; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }}
    .badge.buyer {{ background: #e3f2fd; color: #1565c0; }}
    .badge.seller {{ background: #fff3e0; color: #e65100; }}
    .hash-box {{ font-family: 'Courier New', monospace; font-size: 11px; color: #666; background: #f5f5f5; padding: 10px 14px; border-radius: 4px; word-break: break-all; margin-top: 8px; }}
    .signatures {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px; padding-top: 20px; }}
    .sig-block {{ text-align: center; }}
    .sig-line {{ border-top: 1px solid #333; padding-top: 8px; font-size: 13px; }}
    .sig-date {{ font-size: 11px; color: #999; margin-top: 4px; }}
    .footer {{ text-align: center; margin-top: 32px; padding-top: 16px; border-top: 1px solid #e0e0e0; font-size: 11px; color: #999; }}
    .print-bar {{ display: flex; justify-content: center; gap: 12px; margin-bottom: 16px; }}
    .print-bar button {{ padding: 10px 24px; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; }}
    .btn-print {{ background: #1a1a2e; color: #fff; }}
    .btn-print:hover {{ background: #2d2d44; }}
    .btn-download {{ background: #2e7d32; color: #fff; }}
    .btn-download:hover {{ background: #1b5e20; }}
    .btn-close {{ background: #e0e0e0; color: #333; }}
    .btn-close:hover {{ background: #ccc; }}
    @media print {{
        body {{ background: #fff; }}
        .print-bar {{ display: none !important; }}
        .contract-wrapper {{ padding: 0; }}
        .contract-doc {{ border: none; box-shadow: none; padding: 20px; }}
    }}
</style>
</head>
<body>
<div class="contract-wrapper">
    <div class="print-bar">
        <button class="btn-print" onclick="window.print()">&#128424; Print Contract</button>
        <button class="btn-download" onclick="downloadAsPDF()">&#8595; Download PDF</button>
        <button class="btn-close" onclick="window.close()">Close</button>
    </div>
    <div class="contract-doc" id="contractDocument">
        <div class="contract-header">
            <h1>B2B Purchase Agreement</h1>
            <div class="subtitle">AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform</div>
            <div class="contract-id">Contract ID: {contract.id[:8].upper()}-{contract.id[8:16]}</div>
        </div>

        <div class="section">
            <div class="section-title">Agreement Date</div>
            <p>This agreement is entered into on <strong>{agreement_date}</strong>.</p>
        </div>

        <div class="section">
            <div class="section-title">Parties</div>
            <div class="party-grid">
                <div class="party-box">
                    <div class="role">Buyer</div>
                    <div class="name">{contract.buyer_name}</div>
                </div>
                <div class="party-box">
                    <div class="role">Seller</div>
                    <div class="name">{contract.seller_name}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Commodity &amp; Quantity</div>
            <table class="terms-table">
                <tr><td>Commodity</td><td>{contract.commodity}</td></tr>
                <tr><td>Quantity</td><td>{contract.quantity:,.0f} {contract.unit}</td></tr>
                <tr><td>Currency</td><td>{contract.currency}</td></tr>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Agreed Terms</div>
            <table class="terms-table">
                <tr><td>Unit Price</td><td><strong>{contract.currency} {contract.unit_price:,.2f}</strong> per {contract.unit}</td></tr>
                <tr><td>Delivery Period</td><td>{contract.delivery_days} days from agreement date</td></tr>
                <tr><td>Payment Terms</td><td>{contract.payment_terms.replace('_', ' ').title()}</td></tr>
                <tr><td>Shipping Terms</td><td>{contract.shipping_terms or 'Standard (to be confirmed)'}</td></tr>
                <tr><td>Quality Requirements</td><td>{contract.quality_requirements or 'Standard commercial grade'}</td></tr>
            </table>
        </div>

        <div class="highlight">
            <div class="label">Total Contract Value</div>
            <div class="amount">{contract.currency} {contract.total_value:,.2f}</div>
        </div>

        <div class="section">
            <div class="section-title">Negotiation History</div>
            <p style="font-size:13px;color:#666;margin-bottom:12px">
                This agreement was reached after {len(offers)} rounds of autonomous AI negotiation.
                Agreement was achieved at <strong>{contract.currency} {contract.unit_price:,.2f}/{contract.unit}</strong>.
            </p>
            <table class="offer-table">
                <thead>
                    <tr><th>Rnd</th><th>Party</th><th>Price</th><th>Qty</th><th>Delivery</th><th>Payment</th><th>Action</th></tr>
                </thead>
                <tbody>{offer_rows}</tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Document Integrity</div>
            <p style="font-size:13px;color:#666">This contract is cryptographically secured with a SHA-256 hash for tamper verification.</p>
            <div class="hash-box">SHA-256: {contract.document_hash}</div>
        </div>

        <div class="signatures">
            <div class="sig-block">
                <div class="sig-line"><strong>{contract.buyer_name}</strong></div>
                <div class="sig-date">Buyer — {agreement_date}</div>
            </div>
            <div class="sig-block">
                <div class="sig-line"><strong>{contract.seller_name}</strong></div>
                <div class="sig-date">Seller — {agreement_date}</div>
            </div>
        </div>

        <div class="footer">
            Generated by AI Negotiator &bull; {created_date}<br>
            This is a legally binding agreement generated through AI-assisted autonomous negotiation.
        </div>
    </div>
</div>
<script>
function downloadAsPDF() {{
    // Use browser print dialog to save as PDF
    window.print();
}}
</script>
</body>
</html>"""


@router.get("/api/v1/negotiations/{negotiation_id}/contract/preview", response_class=HTMLResponse)
def preview_contract(
    negotiation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the full contract as an HTML document for preview/download."""
    contract = db.query(Contract).filter(Contract.negotiation_id == negotiation_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="No contract found for this negotiation")

    negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    offers = (
        db.query(Offer)
        .filter(Offer.negotiation_id == negotiation_id)
        .order_by(Offer.round_number, Offer.created_at)
        .all()
    )

    return HTMLResponse(content=_render_contract_html(contract, negotiation, offers))
