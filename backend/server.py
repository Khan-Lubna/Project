from fastapi import FastAPI, APIRouter, HTTPException, Request
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
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)


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

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

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


class CheckoutSessionCreate(BaseModel):
    customer_name: str
    customer_email: EmailStr
    shipping_address: str
    items: List[CartItem]
    origin_url: str


class CheckoutSessionCreateResponse(BaseModel):
    url: str
    session_id: str
    order_id: str
    total: float
    currency: str


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


def _build_stripe(origin_url: str) -> StripeCheckout:
    webhook_url = f"{origin_url.rstrip('/')}/api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@api_router.post("/checkout/session", response_model=CheckoutSessionCreateResponse)
async def create_checkout_session(req: CheckoutSessionCreate):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

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

    if total <= 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = round(total, 2)
    order_id = f"MSR-{uuid.uuid4().hex[:8].upper()}"

    origin = req.origin_url.rstrip('/')
    success_url = f"{origin}/cart/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/cart"

    stripe_checkout = _build_stripe(origin)
    metadata = {
        "order_id": order_id,
        "customer_email": req.customer_email,
        "customer_name": req.customer_name,
        "source": "mossero_web",
    }
    checkout_request = CheckoutSessionRequest(
        amount=float(total),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe_checkout.create_checkout_session(checkout_request)

    txn_doc = {
        "order_id": order_id,
        "session_id": session.session_id,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "shipping_address": req.shipping_address,
        "items": detailed_items,
        "amount": total,
        "currency": "usd",
        "metadata": metadata,
        "payment_status": "initiated",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(txn_doc)

    return CheckoutSessionCreateResponse(
        url=session.url,
        session_id=session.session_id,
        order_id=order_id,
        total=total,
        currency="usd",
    )


@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    txn = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Session not found")

    # If already finalized as paid in our DB, return cached
    if txn.get("payment_status") == "paid":
        return {
            "session_id": session_id,
            "order_id": txn["order_id"],
            "payment_status": "paid",
            "status": txn.get("status", "complete"),
            "amount_total": int(round(txn["amount"] * 100)),
            "currency": txn["currency"],
        }

    origin = str(request.base_url).rstrip('/')
    stripe_checkout = _build_stripe(origin)
    try:
        status_resp = await stripe_checkout.get_checkout_status(session_id)
    except Exception as e:
        logger.warning(f"Stripe status lookup failed for {session_id}: {e}")
        # Return cached state — webhook will update once Stripe confirms
        return {
            "session_id": session_id,
            "order_id": txn["order_id"],
            "payment_status": txn.get("payment_status", "initiated"),
            "status": txn.get("status", "open"),
            "amount_total": int(round(txn["amount"] * 100)),
            "currency": txn["currency"],
        }

    new_status = status_resp.status
    new_payment_status = status_resp.payment_status

    update = {
        "$set": {
            "payment_status": new_payment_status,
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    await db.payment_transactions.update_one({"session_id": session_id}, update)

    # On first transition to paid, write a final order record (idempotent)
    if new_payment_status == "paid":
        existing = await db.orders.find_one({"order_id": txn["order_id"]}, {"_id": 0})
        if not existing:
            order_doc = {
                "order_id": txn["order_id"],
                "session_id": session_id,
                "customer_name": txn["customer_name"],
                "customer_email": txn["customer_email"],
                "shipping_address": txn["shipping_address"],
                "items": txn["items"],
                "total": txn["amount"],
                "currency": txn["currency"],
                "status": "paid",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.orders.insert_one(order_doc)

    return {
        "session_id": session_id,
        "order_id": txn["order_id"],
        "payment_status": new_payment_status,
        "status": new_status,
        "amount_total": status_resp.amount_total,
        "currency": status_resp.currency,
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    origin = str(request.base_url).rstrip('/')
    stripe_checkout = _build_stripe(origin)
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")

    session_id = getattr(event, "session_id", None)
    payment_status = getattr(event, "payment_status", None)
    if session_id and payment_status:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": payment_status,
                "webhook_event": getattr(event, "event_type", None),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    return {"received": True}


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
