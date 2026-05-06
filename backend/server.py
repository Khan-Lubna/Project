from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import resend


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
CONTACT_RECIPIENT_EMAIL = os.environ.get('CONTACT_RECIPIENT_EMAIL', 'mossero.in@gmail.com')

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MOSSERO API")
api_router = APIRouter(prefix="/api")


# ---------------- Static product catalog ----------------
PRODUCTS = [
    {
        "slug": "oura",
        "name": "OURA",
        "type": "Eau de Parfum",
        "size": "50ml",
        "target": "For Him",
        "tagline": "Power in every presence.",
        "price": 185.00,
        "currency": "USD",
        "theme": "dark",
        "description": (
            "OURA is a study in restraint and command. A masculine composition "
            "that opens with the bright cut of bergamot and the spark of fresh pepper, "
            "softens through a quiet heart of lavender, geranium and a whispered spice, "
            "and settles into the long, low warmth of ambroxan, cedarwood and musk. "
            "It is presence — felt before it is named."
        ),
        "notes": {
            "top": ["Bergamot", "Fresh Pepper"],
            "heart": ["Lavender", "Geranium", "Spicy Accord"],
            "base": ["Ambroxan", "Cedarwood", "Warm Musk"]
        },
        "image": "https://images.unsplash.com/photo-1736605406021-afd8241d5edd?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
    },
    {
        "slug": "veloura",
        "name": "VELOURA",
        "type": "Eau de Parfum",
        "size": "50ml",
        "target": "For Her",
        "tagline": "A trace of the eternal feminine.",
        "price": 185.00,
        "currency": "USD",
        "theme": "light",
        "description": (
            "VELOURA is luminous and unhurried. A feminine bouquet built on the soft, "
            "narcotic light of jasmine, the velvet weight of tuberose and the rare, "
            "honeyed bloom of Rangoon creeper. Romantic without nostalgia. "
            "Quiet, enduring, alive."
        ),
        "notes": {
            "top": ["Jasmine"],
            "heart": ["Tuberose"],
            "base": ["Rangoon Creeper"]
        },
        "image": "https://images.unsplash.com/photo-1759793499819-bf60128a54b4?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
    },
]


# ---------------- Models ----------------
class Product(BaseModel):
    slug: str
    name: str
    type: str
    size: str
    target: str
    tagline: str
    price: float
    currency: str
    theme: str
    description: str
    notes: dict
    image: str


class CartItem(BaseModel):
    slug: str
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    customer_name: str
    customer_email: EmailStr
    shipping_address: str
    items: List[CartItem]


class CheckoutResponse(BaseModel):
    order_id: str
    total: float
    currency: str
    status: str
    message: str


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: Optional[str] = "Inquiry from Mossero website"
    message: str


# ---------------- Routes ----------------
@api_router.get("/")
async def root():
    return {"message": "MOSSERO API"}


@api_router.get("/products", response_model=List[Product])
async def list_products():
    return PRODUCTS


@api_router.get("/products/{slug}", response_model=Product)
async def get_product(slug: str):
    for p in PRODUCTS:
        if p["slug"] == slug:
            return p
    raise HTTPException(status_code=404, detail="Product not found")


@api_router.post("/checkout", response_model=CheckoutResponse)
async def checkout(req: CheckoutRequest):
    by_slug = {p["slug"]: p for p in PRODUCTS}
    total = 0.0
    detailed_items = []
    for item in req.items:
        p = by_slug.get(item.slug)
        if not p:
            raise HTTPException(status_code=400, detail=f"Unknown product: {item.slug}")
        line_total = p["price"] * item.quantity
        total += line_total
        detailed_items.append({
            "slug": item.slug,
            "name": p["name"],
            "unit_price": p["price"],
            "quantity": item.quantity,
            "line_total": line_total,
        })

    order_id = f"MSR-{uuid.uuid4().hex[:8].upper()}"
    doc = {
        "order_id": order_id,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "shipping_address": req.shipping_address,
        "items": detailed_items,
        "total": round(total, 2),
        "currency": "USD",
        "status": "received",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.orders.insert_one(doc)

    return CheckoutResponse(
        order_id=order_id,
        total=round(total, 2),
        currency="USD",
        status="received",
        message="Thank you. Your order has been received. A confirmation will follow shortly.",
    )


@api_router.post("/contact")
async def contact(req: ContactRequest):
    submission_id = str(uuid.uuid4())
    doc = {
        "id": submission_id,
        "name": req.name,
        "email": req.email,
        "subject": req.subject,
        "message": req.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "email_sent": False,
        "email_error": None,
    }

    email_sent = False
    email_error = None

    if RESEND_API_KEY:
        html_content = f"""
        <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"font-family:Arial,sans-serif;background:#F5F0E8;padding:32px;\">
          <tr><td>
            <h2 style=\"font-family:Georgia,serif;color:#1A1A1A;letter-spacing:0.2em;\">MOSSERO &mdash; New Inquiry</h2>
            <hr style=\"border:none;border-top:1px solid #C4A258;margin:24px 0;\"/>
            <p style=\"color:#1A1A1A;\"><strong>Name:</strong> {req.name}</p>
            <p style=\"color:#1A1A1A;\"><strong>Email:</strong> {req.email}</p>
            <p style=\"color:#1A1A1A;\"><strong>Subject:</strong> {req.subject}</p>
            <p style=\"color:#1A1A1A;\"><strong>Message:</strong></p>
            <p style=\"color:#1A1A1A;line-height:1.7;\">{req.message}</p>
          </td></tr>
        </table>
        """
        params = {
            "from": SENDER_EMAIL,
            "to": [CONTACT_RECIPIENT_EMAIL],
            "reply_to": req.email,
            "subject": f"[MOSSERO] {req.subject}",
            "html": html_content,
        }
        try:
            await asyncio.to_thread(resend.Emails.send, params)
            email_sent = True
        except Exception as e:
            email_error = str(e)
            logger.error(f"Resend send failed: {email_error}")

    doc["email_sent"] = email_sent
    doc["email_error"] = email_error
    await db.contact_messages.insert_one(doc)

    return {
        "id": submission_id,
        "status": "received",
        "email_sent": email_sent,
        "message": "Thank you for reaching out. We will respond shortly.",
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
