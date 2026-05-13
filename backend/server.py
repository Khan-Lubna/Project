from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import hmac
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import resend
import razorpay


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

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

rzp_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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
        "price": 100.00,
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
        "price": 100.00,
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


class OrderCreateRequest(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_contact: Optional[str] = None
    shipping_address: str
    items: List[CartItem]


class OrderCreateResponse(BaseModel):
    order_id: str
    rzp_order_id: str
    rzp_key_id: str
    amount: int  # smallest unit (cents)
    currency: str
    total: float
    customer_name: str
    customer_email: EmailStr
    customer_contact: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


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


def _verify_signature(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@api_router.post("/checkout/order", response_model=OrderCreateResponse)
async def create_order(req: OrderCreateRequest):
    if rzp_client is None:
        raise HTTPException(status_code=500, detail="Razorpay is not configured")

    by_slug = {p["slug"]: p for p in PRODUCTS}
    total = 0.0
    currency = "USD"
    detailed_items = []
    for item in req.items:
        p = by_slug.get(item.slug)
        if not p:
            raise HTTPException(status_code=400, detail=f"Unknown product: {item.slug}")
        line_total = p["price"] * item.quantity
        total += line_total
        currency = p["currency"]
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
    amount_minor = int(round(total * 100))  # USD -> cents
    order_id = f"MSR-{uuid.uuid4().hex[:8].upper()}"

    try:
        rzp_order = await asyncio.to_thread(
            rzp_client.order.create,
            {
                "amount": amount_minor,
                "currency": currency,
                "receipt": order_id,
                "payment_capture": 1,
                "notes": {
                    "order_id": order_id,
                    "customer_email": req.customer_email,
                    "customer_name": req.customer_name,
                },
            },
        )
    except Exception as e:
        logger.error(f"Razorpay order create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Razorpay error: {e}")

    txn_doc = {
        "order_id": order_id,
        "rzp_order_id": rzp_order["id"],
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "customer_contact": req.customer_contact,
        "shipping_address": req.shipping_address,
        "items": detailed_items,
        "amount": total,
        "amount_minor": amount_minor,
        "currency": currency,
        "payment_status": "initiated",
        "status": "open",
        "rzp_payment_id": None,
        "rzp_signature": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(txn_doc)

    return OrderCreateResponse(
        order_id=order_id,
        rzp_order_id=rzp_order["id"],
        rzp_key_id=RAZORPAY_KEY_ID,
        amount=amount_minor,
        currency=currency,
        total=total,
        customer_name=req.customer_name,
        customer_email=req.customer_email,
        customer_contact=req.customer_contact,
    )


@api_router.post("/checkout/verify")
async def verify_payment(req: VerifyPaymentRequest):
    if rzp_client is None:
        raise HTTPException(status_code=500, detail="Razorpay is not configured")

    txn = await db.payment_transactions.find_one(
        {"order_id": req.order_id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Order not found")
    if txn["rzp_order_id"] != req.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Order mismatch")

    # If already paid, return cached (idempotent)
    if txn.get("payment_status") == "paid":
        return {
            "order_id": req.order_id,
            "payment_status": "paid",
            "amount_total": txn["amount_minor"],
            "currency": txn["currency"],
        }

    payload = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    if not _verify_signature(payload, req.razorpay_signature, RAZORPAY_KEY_SECRET):
        await db.payment_transactions.update_one(
            {"order_id": req.order_id},
            {"$set": {
                "payment_status": "failed",
                "status": "signature_invalid",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Signature valid → mark paid
    await db.payment_transactions.update_one(
        {"order_id": req.order_id},
        {"$set": {
            "payment_status": "paid",
            "status": "complete",
            "rzp_payment_id": req.razorpay_payment_id,
            "rzp_signature": req.razorpay_signature,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    existing_order = await db.orders.find_one({"order_id": req.order_id}, {"_id": 0})
    if not existing_order:
        order_doc = {
            "order_id": req.order_id,
            "rzp_order_id": req.razorpay_order_id,
            "rzp_payment_id": req.razorpay_payment_id,
            "customer_name": txn["customer_name"],
            "customer_email": txn["customer_email"],
            "customer_contact": txn.get("customer_contact"),
            "shipping_address": txn["shipping_address"],
            "items": txn["items"],
            "total": txn["amount"],
            "currency": txn["currency"],
            "status": "paid",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.orders.insert_one(order_doc)

    return {
        "order_id": req.order_id,
        "payment_status": "paid",
        "amount_total": txn["amount_minor"],
        "currency": txn["currency"],
    }


@api_router.get("/checkout/status/{order_id}")
async def get_order_status(order_id: str):
    txn = await db.payment_transactions.find_one(
        {"order_id": order_id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order_id,
        "payment_status": txn.get("payment_status", "initiated"),
        "status": txn.get("status", "open"),
        "amount_total": txn["amount_minor"],
        "currency": txn["currency"],
    }


@api_router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if RAZORPAY_WEBHOOK_SECRET:
        if not _verify_signature(body.decode("utf-8"), signature, RAZORPAY_WEBHOOK_SECRET):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        import json
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Razorpay webhook parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    event = payload.get("event")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    rzp_order_id = payment_entity.get("order_id")
    rzp_payment_id = payment_entity.get("id")
    status = payment_entity.get("status")

    if rzp_order_id:
        update_fields = {
            "webhook_event": event,
            "rzp_payment_id": rzp_payment_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status == "captured" or event == "payment.captured":
            update_fields["payment_status"] = "paid"
            update_fields["status"] = "complete"
        elif event in ("payment.failed",):
            update_fields["payment_status"] = "failed"
            update_fields["status"] = "failed"
        await db.payment_transactions.update_one(
            {"rzp_order_id": rzp_order_id},
            {"$set": update_fields},
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
