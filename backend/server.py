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
import shiprocket_client


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


class StructuredAddress(BaseModel):
    line1: str
    line2: Optional[str] = ""
    city: str
    state: str
    postal_code: str
    country: str = "India"


class OrderCreateRequest(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_contact: Optional[str] = None
    shipping_address: str
    address_struct: Optional[StructuredAddress] = None
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


class OrderLookupRequest(BaseModel):
    order_id: str
    email: EmailStr


class ConciergeOrderRequest(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_contact: Optional[str] = None
    shipping_address: str
    address_struct: Optional[StructuredAddress] = None
    items: List[CartItem]
    notes: Optional[str] = ""


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


def _format_currency(amount: float, currency: str) -> str:
    symbol = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(currency.upper(), "")
    return f"{symbol}{amount:,.2f} {currency.upper()}"


def _order_email_html(order_doc: dict, for_maison: bool = False) -> str:
    rows = "".join(
        f"""<tr>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;\">
              <strong style=\"letter-spacing:0.18em;\">{it['name']}</strong>
              <div style=\"font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;margin-top:4px;\">50ml · Eau de Parfum</div>
            </td>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:center;color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;\">× {it['quantity']}</td>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:right;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;\">{_format_currency(it['line_total'], order_doc['currency'])}</td>
        </tr>"""
        for it in order_doc.get("items", [])
    )
    title = "A new order has been placed" if for_maison else "Thank you for your order"
    body_intro = (
        f"<p style=\"color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;line-height:1.9;\">A new order has been received from <strong>{order_doc['customer_name']}</strong> ({order_doc['customer_email']}).</p>"
        if for_maison
        else f"<p style=\"color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;line-height:1.9;\">Dear {order_doc['customer_name']},<br/><br/>Thank you for your order with the Maison Mossero. Your payment has been confirmed and your fragrance will be prepared with care. A despatch notification will follow.</p>"
    )
    return f"""
    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#F5F0E8;padding:40px 16px;font-family:Arial,sans-serif;\">
      <tr><td align=\"center\">
        <table width=\"560\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#FBF7F2;border:1px solid #C4A258;\">
          <tr><td style=\"padding:48px 40px 32px 40px;text-align:center;\">
            <h1 style=\"margin:0;font-family:Georgia,serif;font-weight:bold;color:#000000;letter-spacing:0.35em;font-size:24px;\">MOSSERO</h1>
            <p style=\"margin:24px 0 0 0;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#C4A258;\">{title}</p>
            <hr style=\"border:none;border-top:1px solid #C4A258;width:48px;margin:24px auto 0 auto;\"/>
          </td></tr>
          <tr><td style=\"padding:0 40px 24px 40px;\">{body_intro}</td></tr>
          <tr><td style=\"padding:0 40px;\">
            <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">{rows}
              <tr>
                <td colspan=\"2\" style=\"padding:18px 0 0 0;text-align:right;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Total</td>
                <td style=\"padding:18px 0 0 0;text-align:right;font-family:Georgia,serif;font-size:20px;color:#1A1A1A;\">{_format_currency(order_doc['total'], order_doc['currency'])}</td>
              </tr>
            </table>
          </td></tr>
          <tr><td style=\"padding:32px 40px;\">
            <p style=\"margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Order reference</p>
            <p style=\"margin:0 0 16px 0;font-family:Georgia,serif;font-size:18px;color:#1A1A1A;letter-spacing:0.1em;\">{order_doc['order_id']}</p>
            <p style=\"margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Shipping to</p>
            <p style=\"margin:0;font-size:14px;color:#1A1A1A;line-height:1.8;white-space:pre-line;\">{order_doc['shipping_address']}</p>
          </td></tr>
          <tr><td style=\"padding:32px 40px;background:#F5F0E8;text-align:center;\">
            <p style=\"margin:0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#6b6357;\">Leave a trace of elegance wherever you go.</p>
            <p style=\"margin:16px 0 0 0;font-size:11px;color:#9b9285;\">Maison Mossero &nbsp;·&nbsp; www.mossero.in</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """


async def _send_order_emails(order_doc: dict) -> tuple[bool, Optional[str]]:
    """Send confirmation to customer + notification to maison. Returns (sent, error)."""
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"

    customer_html = _order_email_html(order_doc, for_maison=False)
    maison_html = _order_email_html(order_doc, for_maison=True)

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": SENDER_EMAIL,
                "to": [order_doc["customer_email"]],
                "subject": f"[MOSSERO] Order confirmation — {order_doc['order_id']}",
                "html": customer_html,
            },
        )
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": SENDER_EMAIL,
                "to": [CONTACT_RECIPIENT_EMAIL],
                "reply_to": order_doc["customer_email"],
                "subject": f"[MOSSERO] New order {order_doc['order_id']} — {order_doc['customer_name']}",
                "html": maison_html,
            },
        )
        return True, None
    except Exception as e:
        logger.error(f"Order confirmation email failed: {e}")
        return False, str(e)


async def _send_concierge_emails(order_doc: dict) -> tuple[bool, Optional[str]]:
    """Send reservation confirmation to customer + alert to maison (no payment yet)."""
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"

    item_rows = "".join(
        f"""<tr>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;\">
              <strong style=\"letter-spacing:0.18em;\">{it['name']}</strong>
              <div style=\"font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;margin-top:4px;\">50ml · Eau de Parfum</div>
            </td>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:center;color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;\">× {it['quantity']}</td>
            <td style=\"padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:right;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;\">{_format_currency(it['line_total'], order_doc['currency'])}</td>
        </tr>"""
        for it in order_doc.get("items", [])
    )

    customer_html = f"""
    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#F5F0E8;padding:40px 16px;font-family:Arial,sans-serif;\">
      <tr><td align=\"center\">
        <table width=\"560\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#FBF7F2;border:1px solid #C4A258;\">
          <tr><td style=\"padding:48px 40px 32px 40px;text-align:center;\">
            <h1 style=\"margin:0;font-family:Georgia,serif;font-weight:bold;color:#000000;letter-spacing:0.35em;font-size:24px;\">MOSSERO</h1>
            <p style=\"margin:24px 0 0 0;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#C4A258;\">Reservation Received</p>
            <hr style=\"border:none;border-top:1px solid #C4A258;width:48px;margin:24px auto 0 auto;\"/>
          </td></tr>
          <tr><td style=\"padding:0 40px 24px 40px;\">
            <p style=\"color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;line-height:1.9;\">
              Dear {order_doc['customer_name']},<br/><br/>
              Thank you for your reservation. The Maison Mossero will write to you within one working day with payment details and despatch arrangements. We do not run an automated checkout — every order is finalised personally.
            </p>
          </td></tr>
          <tr><td style=\"padding:0 40px;\">
            <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">{item_rows}
              <tr>
                <td colspan=\"2\" style=\"padding:18px 0 0 0;text-align:right;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Subtotal</td>
                <td style=\"padding:18px 0 0 0;text-align:right;font-family:Georgia,serif;font-size:20px;color:#1A1A1A;\">{_format_currency(order_doc['total'], order_doc['currency'])}</td>
              </tr>
            </table>
          </td></tr>
          <tr><td style=\"padding:32px 40px;\">
            <p style=\"margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Reservation Reference</p>
            <p style=\"margin:0 0 16px 0;font-family:Georgia,serif;font-size:18px;color:#1A1A1A;letter-spacing:0.1em;\">{order_doc['order_id']}</p>
            <p style=\"margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Shipping to</p>
            <p style=\"margin:0;font-size:14px;color:#1A1A1A;line-height:1.8;white-space:pre-line;\">{order_doc['shipping_address']}</p>
          </td></tr>
          <tr><td style=\"padding:32px 40px;background:#F5F0E8;text-align:center;\">
            <p style=\"margin:0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#6b6357;\">Leave a trace of elegance wherever you go.</p>
            <p style=\"margin:16px 0 0 0;font-size:11px;color:#9b9285;\">Maison Mossero · www.mossero.in · mossero.in@gmail.com</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """

    notes_block = (
        f"<p style=\"margin:16px 0 0 0;font-size:13px;color:#1A1A1A;background:#F5F0E8;padding:14px;border-left:2px solid #C4A258;white-space:pre-line;\"><strong>Customer note:</strong><br/>{order_doc.get('notes','')}</p>"
        if order_doc.get("notes")
        else ""
    )
    maison_html = f"""
    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#F5F0E8;padding:40px 16px;font-family:Arial,sans-serif;\">
      <tr><td align=\"center\">
        <table width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#FBF7F2;border:1px solid #C4A258;\">
          <tr><td style=\"padding:40px 40px 24px 40px;\">
            <h1 style=\"margin:0;font-family:Georgia,serif;font-weight:bold;color:#000000;letter-spacing:0.35em;font-size:22px;\">MOSSERO · CONCIERGE QUEUE</h1>
            <p style=\"margin:18px 0 0 0;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#C4A258;\">New reservation to invoice</p>
          </td></tr>
          <tr><td style=\"padding:0 40px 24px 40px;\">
            <p style=\"margin:0 0 8px 0;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;\">Customer</p>
            <p style=\"margin:0 0 4px 0;font-size:16px;color:#1A1A1A;\"><strong>{order_doc['customer_name']}</strong></p>
            <p style=\"margin:0 0 4px 0;font-size:14px;color:#1A1A1A;\">{order_doc['customer_email']}</p>
            <p style=\"margin:0 0 16px 0;font-size:14px;color:#1A1A1A;\">{order_doc.get('customer_contact') or '—'}</p>
            <p style=\"margin:0 0 8px 0;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;\">Ship to</p>
            <p style=\"margin:0;font-size:14px;color:#1A1A1A;line-height:1.8;white-space:pre-line;\">{order_doc['shipping_address']}</p>
            {notes_block}
          </td></tr>
          <tr><td style=\"padding:0 40px 24px 40px;\">
            <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">{item_rows}
              <tr>
                <td colspan=\"2\" style=\"padding:18px 0 0 0;text-align:right;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;\">Total to invoice</td>
                <td style=\"padding:18px 0 0 0;text-align:right;font-family:Georgia,serif;font-size:22px;color:#1A1A1A;\">{_format_currency(order_doc['total'], order_doc['currency'])}</td>
              </tr>
            </table>
          </td></tr>
          <tr><td style=\"padding:24px 40px 40px 40px;\">
            <p style=\"margin:0;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;\">Reference {order_doc['order_id']}</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": SENDER_EMAIL,
                "to": [order_doc["customer_email"]],
                "subject": f"[MOSSERO] Reservation received — {order_doc['order_id']}",
                "html": customer_html,
            },
        )
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": SENDER_EMAIL,
                "to": [CONTACT_RECIPIENT_EMAIL],
                "reply_to": order_doc["customer_email"],
                "subject": f"[MOSSERO Concierge] {order_doc['order_id']} — {order_doc['customer_name']}",
                "html": maison_html,
            },
        )
        return True, None
    except Exception as e:
        logger.error(f"Concierge email failed: {e}")
        return False, str(e)


async def _finalize_paid_order(txn: dict, rzp_payment_id: Optional[str]) -> dict:
    """Idempotently create the orders record and send confirmation emails."""
    order_id = txn["order_id"]
    existing = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if existing:
        return existing

    order_doc = {
        "order_id": order_id,
        "rzp_order_id": txn["rzp_order_id"],
        "rzp_payment_id": rzp_payment_id or txn.get("rzp_payment_id"),
        "customer_name": txn["customer_name"],
        "customer_email": txn["customer_email"],
        "customer_contact": txn.get("customer_contact"),
        "shipping_address": txn["shipping_address"],
        "address_struct": txn.get("address_struct"),
        "items": txn["items"],
        "total": txn["amount"],
        "currency": txn["currency"],
        "status": "paid",
        "confirmation_email_sent": False,
        "confirmation_email_error": None,
        "shiprocket_order_id": None,
        "shiprocket_shipment_id": None,
        "awb_number": None,
        "courier_name": None,
        "shiprocket_error": None,
        "tracking_cached_at": None,
        "tracking": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.orders.insert_one(order_doc)

    sent, error = await _send_order_emails(order_doc)
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {
            "confirmation_email_sent": sent,
            "confirmation_email_error": error,
        }},
    )
    order_doc["confirmation_email_sent"] = sent
    order_doc["confirmation_email_error"] = error

    # Best-effort Shiprocket adhoc order creation (does not block on failure)
    sr_result = await shiprocket_client.create_adhoc_order(order_doc)
    sr_update = {
        "shiprocket_order_id": sr_result.get("shiprocket_order_id") or None,
        "shiprocket_shipment_id": sr_result.get("shipment_id") or None,
        "awb_number": sr_result.get("awb_number") or None,
        "courier_name": sr_result.get("courier_name") or None,
        "shiprocket_error": None if sr_result.get("success") else sr_result.get("error"),
    }
    await db.orders.update_one({"order_id": order_id}, {"$set": sr_update})
    order_doc.update(sr_update)
    return order_doc


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
        "address_struct": req.address_struct.model_dump() if req.address_struct else None,
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


@api_router.post("/checkout/concierge")
async def concierge_checkout(req: ConciergeOrderRequest):
    """Soft checkout — no payment processor. Records the reservation and
    emails both the maison and the customer. The maison invoices manually."""
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
    order_id = f"MSR-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    order_doc = {
        "order_id": order_id,
        "rzp_order_id": None,
        "rzp_payment_id": None,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "customer_contact": req.customer_contact,
        "shipping_address": req.shipping_address,
        "address_struct": req.address_struct.model_dump() if req.address_struct else None,
        "items": detailed_items,
        "total": total,
        "currency": currency,
        "status": "concierge_pending",
        "channel": "concierge",
        "notes": req.notes or "",
        "confirmation_email_sent": False,
        "confirmation_email_error": None,
        "shiprocket_order_id": None,
        "shiprocket_shipment_id": None,
        "awb_number": None,
        "courier_name": None,
        "shiprocket_error": None,
        "tracking_cached_at": None,
        "tracking": None,
        "created_at": now_iso,
    }
    await db.orders.insert_one(order_doc)

    sent, error = await _send_concierge_emails(order_doc)
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {
            "confirmation_email_sent": sent,
            "confirmation_email_error": error,
        }},
    )

    return {
        "order_id": order_id,
        "status": "concierge_pending",
        "total": total,
        "currency": currency,
        "email_sent": sent,
        "message": "Reservation received. The maison will contact you shortly with payment details.",
    }


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
        # Reload latest txn fields with rzp_payment_id we just set
        latest_txn = await db.payment_transactions.find_one(
            {"order_id": req.order_id}, {"_id": 0}
        ) or txn
        await _finalize_paid_order(latest_txn, req.razorpay_payment_id)

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
        # Finalize + send emails if this webhook is the first paid signal
        if update_fields.get("payment_status") == "paid":
            txn_after = await db.payment_transactions.find_one(
                {"rzp_order_id": rzp_order_id}, {"_id": 0}
            )
            if txn_after:
                await _finalize_paid_order(txn_after, rzp_payment_id)

    return {"received": True}


@api_router.post("/orders/lookup")
async def lookup_order(req: OrderLookupRequest):
    order_id = req.order_id.strip().upper()
    email = req.email.strip().lower()

    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    txn = await db.payment_transactions.find_one({"order_id": order_id}, {"_id": 0})

    source = order or txn
    if not source:
        raise HTTPException(status_code=404, detail="No order found with that reference.")

    if source["customer_email"].lower() != email:
        # Same response as missing — don't leak existence
        raise HTTPException(status_code=404, detail="No order found with that reference.")

    payment_status = (order["status"] if order else txn.get("payment_status", "initiated"))
    if payment_status == "complete":
        payment_status = "paid"

    # ---- Live Shiprocket tracking (cached for 30 minutes) ----
    tracking_info = None
    courier_name = None
    awb_number = None
    tracking_url = None

    is_concierge = bool(order and order.get("channel") == "concierge")
    if is_concierge:
        shipping_status = "concierge_pending"
    elif payment_status == "paid":
        shipping_status = "preparing"
    else:
        shipping_status = "awaiting_payment"

    if order and order.get("awb_number"):
        awb_number = order["awb_number"]
        courier_name = order.get("courier_name")
        cached = order.get("tracking")
        cached_at = order.get("tracking_cached_at")
        fresh = False
        if cached and cached_at:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds()
                fresh = age < 1800
            except Exception:
                fresh = False
        if fresh:
            tracking_info = cached
        else:
            live = await shiprocket_client.track_by_awb(awb_number)
            if not live.get("error"):
                tracking_info = {
                    "current_status": live.get("current_status"),
                    "current_location": live.get("current_location"),
                    "estimated_delivery": live.get("estimated_delivery"),
                    "courier_name": live.get("courier_name") or courier_name,
                    "tracking_url": live.get("tracking_url"),
                }
                await db.orders.update_one(
                    {"order_id": order_id},
                    {"$set": {
                        "tracking": tracking_info,
                        "tracking_cached_at": datetime.now(timezone.utc).isoformat(),
                        "courier_name": tracking_info["courier_name"] or courier_name,
                    }},
                )
            elif cached:
                tracking_info = cached
        if tracking_info:
            courier_name = tracking_info.get("courier_name") or courier_name
            tracking_url = tracking_info.get("tracking_url")
            shipping_status = "in_transit"
            cs = (tracking_info.get("current_status") or "").lower()
            if "delivered" in cs:
                shipping_status = "delivered"
            elif "out for delivery" in cs:
                shipping_status = "out_for_delivery"
            elif "picked up" in cs or "manifested" in cs:
                shipping_status = "dispatched"
    elif order and order.get("shiprocket_error"):
        shipping_status = "fulfillment_pending"

    return {
        "order_id": order_id,
        "customer_name": source["customer_name"],
        "items": source["items"],
        "total": source.get("total", txn["amount"] if txn else 0),
        "currency": source["currency"],
        "payment_status": payment_status,
        "shipping_status": shipping_status,
        "shipping_address": source["shipping_address"],
        "courier_name": courier_name,
        "awb_number": awb_number,
        "tracking_url": tracking_url,
        "tracking": tracking_info,
        "created_at": source["created_at"],
    }


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
