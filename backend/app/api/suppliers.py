"""
Supplier API endpoints — Alibaba.com Open Platform integration (stub for MVP).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import SupplierCandidate, User
from app.security.auth import get_current_user
from app.agents.schemas import SupplierResponse

router = APIRouter(prefix="/api/v1/suppliers", tags=["Suppliers"])


@router.get("", response_model=List[SupplierResponse])
def list_suppliers(
    commodity: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List supplier candidates."""
    query = db.query(SupplierCandidate)
    if commodity:
        query = query.filter(SupplierCandidate.commodity.ilike(f"%{commodity}%"))
    return query.offset(skip).limit(limit).all()


@router.post("/seed")
def seed_sample_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed sample supplier data for demo purposes."""
    sample_suppliers = [
        SupplierCandidate(
            supplier_name="Al-Rehman Rice Mills", commodity="Basmati Rice",
            country="Pakistan", price=220, currency="PKR",
            minimum_order_quantity=5000, unit="kg",
            supplier_rating=4.8, score=92.5,
            availability="In Stock", shipping_info="Karachi Port, 7-10 days",
            whatsapp_number="+923001234567", business_type="Rice Mill",
            city="Karachi",
        ),
        SupplierCandidate(
            supplier_name="Golden Harvest Grains", commodity="Basmati Rice",
            country="Pakistan", price=235, currency="PKR",
            minimum_order_quantity=3000, unit="kg",
            supplier_rating=4.5, score=87.0,
            availability="In Stock", shipping_info="Lahore, 5-7 days",
            whatsapp_number="+923009876543", business_type="Grain Trader",
            city="Lahore",
        ),
        SupplierCandidate(
            supplier_name="Chenab Agro Industries", commodity="Basmati Rice",
            country="Pakistan", price=210, currency="PKR",
            minimum_order_quantity=10000, unit="kg",
            supplier_rating=4.6, score=89.3,
            availability="2 weeks lead time", shipping_info="Faisalabad, 10-14 days",
            whatsapp_number="+923211234567", business_type="Agro Processing",
            city="Faisalabad",
        ),
        SupplierCandidate(
            supplier_name="Indus Valley Exports", commodity="Wheat",
            country="Pakistan", price=85, currency="PKR",
            minimum_order_quantity=8000, unit="kg",
            supplier_rating=4.3, score=82.1,
            availability="In Stock", shipping_info="Multan, 7-10 days",
            whatsapp_number="+923331234567", business_type="Wheat Trader",
            city="Multan",
        ),
        SupplierCandidate(
            supplier_name="Punjab Sugar Mills", commodity="Sugar",
            country="Pakistan", price=155, currency="PKR",
            minimum_order_quantity=5000, unit="kg",
            supplier_rating=4.7, score=90.0,
            availability="In Stock", shipping_info="Rawalpindi, 5-7 days",
            whatsapp_number="+923451234567", business_type="Sugar Mill",
            city="Rawalpindi",
        ),
        SupplierCandidate(
            supplier_name="Himalayan Spice Co.", commodity="Spices",
            country="Pakistan", price=450, currency="PKR",
            minimum_order_quantity=500, unit="kg",
            supplier_rating=4.9, score=95.2,
            availability="In Stock", shipping_info="Islamabad, 3-5 days",
            whatsapp_number="+923121234567", business_type="Spice Trader",
            city="Islamabad",
        ),
        SupplierCandidate(
            supplier_name="Sindh Cotton Traders", commodity="Cotton",
            country="Pakistan", price=210, currency="PKR",
            minimum_order_quantity=2000, unit="kg",
            supplier_rating=4.4, score=85.6,
            availability="1 week lead time", shipping_info="Hyderabad, 7-10 days",
            whatsapp_number="+923111234567", business_type="Cotton Ginning",
            city="Hyderabad",
        ),
        SupplierCandidate(
            supplier_name="Northern Fruits Dry", commodity="Dry Fruits",
            country="Pakistan", price=850, currency="PKR",
            minimum_order_quantity=200, unit="kg",
            supplier_rating=4.8, score=93.0,
            availability="Seasonal", shipping_info="Peshawar, 5-7 days",
            whatsapp_number="+923461234567", business_type="Dry Fruit Trader",
            city="Peshawar",
        ),
        SupplierCandidate(
            supplier_name="Al-Noor Cooking Oil", commodity="Cooking Oil",
            country="Pakistan", price=310, currency="PKR",
            minimum_order_quantity=1000, unit="kg",
            supplier_rating=4.2, score=80.5,
            availability="In Stock", shipping_info="Karachi, 3-5 days",
            whatsapp_number="+923009988776", business_type="Oil Mill",
            city="Karachi",
        ),
        SupplierCandidate(
            supplier_name="Punjab Maize Dealers", commodity="Maize",
            country="Pakistan", price=72, currency="PKR",
            minimum_order_quantity=5000, unit="kg",
            supplier_rating=4.1, score=78.0,
            availability="In Stock", shipping_info="Okara, 5-7 days",
            whatsapp_number="+923005544332", business_type="Maize Trader",
            city="Okara",
        ),
    ]
    for s in sample_suppliers:
        db.add(s)
    db.commit()
    return {"message": f"Seeded {len(sample_suppliers)} sample suppliers"}
