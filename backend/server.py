from decimal import Decimal, ROUND_HALF_UP
from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import os
import asyncio
import logging
import hmac
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import resend
import razorpay
import shiprocket_client
import shopify_client

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

SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL", "")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-04")

shopify_client.init_shopify_client(
    SHOPIFY_STORE_URL,
    SHOPIFY_CLIENT_ID,
    SHOPIFY_CLIENT_SECRET,
    SHOPIFY_API_VERSION,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MOSSERO API")
api_router = APIRouter(prefix="/api")

@api_router.get("/shopify-config-check")
async def shopify_config_check():
    import hashlib

    def fingerprint(value):
        value = value or ""
        return {
            "configured": bool(value),
            "length": len(value),
            "fingerprint": hashlib.sha256(
                value.encode()
            ).hexdigest()[:12],
        }

    return {
        "store_url": SHOPIFY_STORE_URL,
        "client_id": fingerprint(SHOPIFY_CLIENT_ID),
        "client_secret": fingerprint(SHOPIFY_CLIENT_SECRET),
    }


# ---------------- Static product catalog ----------------
PRODUCTS = [
    {
        "slug": "oura",
        "name": "OURA",
        "type": "Eau de Parfum",
        "size": "50ml",
        "target": "For Him",
        "tagline": "Power in every presence.",
        "price": 1149.00,
        "currency": "INR",
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
        "price": 1149.00,
        "currency": "INR",
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
    amount: int  # amount in paise
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


async def _get_shopify_priced_products(products: list) -> list:
    client = shopify_client.shopify_client

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Product pricing is temporarily unavailable.",
        )

    try:
        slugs = [product["slug"] for product in products]
        pricing = await client.get_variant_prices(slugs)

        currency = pricing["currency"]
        prices = pricing["prices"]

        if currency != "INR":
            raise ValueError(f"Unexpected Shopify currency: {currency}")

        updated_products = []

        for product in products:
            price = Decimal(str(prices[product["slug"]]))

            if not price.is_finite() or price <= 0:
                raise ValueError(
                    f"Invalid Shopify price for {product['slug']}"
                )

            updated_products.append({
                **product,
                "price": float(price),
                "currency": currency,
            })

        return updated_products

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shopify product catalogue lookup failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve current product prices.",
        )


@api_router.get("/products", response_model=List[Product])
async def list_products():
    return await _get_shopify_priced_products(PRODUCTS)


@api_router.get("/products/{slug}", response_model=Product)
async def get_product(slug: str):
    product = next(
        (p for p in PRODUCTS if p["slug"] == slug),
        None,
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    priced_products = await _get_shopify_priced_products([product])
    return priced_products[0]


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

async def _send_payment_link_email(order_doc: dict, link_url: str) -> tuple[bool, Optional[str]]:
    """Send a branded email to the customer with the Razorpay UPI payment link."""
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"
    if not link_url:
        return False, "No payment link URL"

    item_rows = "".join(
        f"""<tr>
            <td style="padding:14px 0;border-bottom:1px solid #E5DCC9;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;">
              <strong style="letter-spacing:0.18em;">{it['name']}</strong>
              <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#6b6357;margin-top:4px;">50ml · Eau de Parfum</div>
            </td>
            <td style="padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:center;color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;">× {it['quantity']}</td>
            <td style="padding:14px 0;border-bottom:1px solid #E5DCC9;text-align:right;color:#1A1A1A;font-family:Georgia,serif;font-size:16px;">{_format_currency(it['line_total'], order_doc['currency'])}</td>
        </tr>"""
        for it in order_doc.get("items", [])
    )

    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F0E8;padding:40px 16px;font-family:Arial,sans-serif;">
      <tr><td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#FBF7F2;border:1px solid #C4A258;">
          <tr><td style="padding:48px 40px 24px 40px;text-align:center;">
            <h1 style="margin:0;font-family:Georgia,serif;font-weight:bold;color:#000000;letter-spacing:0.35em;font-size:24px;">MOSSERO</h1>
            <p style="margin:24px 0 0 0;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#C4A258;">Your payment link</p>
            <hr style="border:none;border-top:1px solid #C4A258;width:48px;margin:24px auto 0 auto;"/>
          </td></tr>
          <tr><td style="padding:0 40px 16px 40px;">
            <p style="color:#1A1A1A;font-family:Arial,sans-serif;font-size:14px;line-height:1.9;">
              Dear {order_doc['customer_name']},<br/><br/>
              Thank you for your selection. Complete your purchase any time within the next 24 hours via UPI — Google Pay, PhonePe, Paytm or BHIM — using the secure link below.
            </p>
          </td></tr>
          <tr><td style="padding:0 40px 32px 40px;text-align:center;">
            <a href="{link_url}" style="display:inline-block;background:#C4A258;color:#000000;padding:18px 42px;font-family:Arial,sans-serif;font-weight:600;font-size:12px;letter-spacing:0.3em;text-transform:uppercase;text-decoration:none;border:1px solid #C4A258;">Complete Payment</a>
            <p style="margin:18px 0 0 0;font-family:Arial,sans-serif;font-size:11px;color:#6b6357;word-break:break-all;">{link_url}</p>
          </td></tr>
          <tr><td style="padding:0 40px;">
            <table width="100%" cellpadding="0" cellspacing="0">{item_rows}
              <tr>
                <td colspan="2" style="padding:18px 0 0 0;text-align:right;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;">Total</td>
                <td style="padding:18px 0 0 0;text-align:right;font-family:Georgia,serif;font-size:20px;color:#1A1A1A;">{_format_currency(order_doc['total'], order_doc['currency'])}</td>
              </tr>
            </table>
          </td></tr>
          <tr><td style="padding:32px 40px;">
            <p style="margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;">Order reference</p>
            <p style="margin:0 0 16px 0;font-family:Georgia,serif;font-size:18px;color:#1A1A1A;letter-spacing:0.1em;">{order_doc['order_id']}</p>
            <p style="margin:0 0 6px 0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#1A1A1A;">Shipping to</p>
            <p style="margin:0;font-size:14px;color:#1A1A1A;line-height:1.8;white-space:pre-line;">{order_doc['shipping_address']}</p>
          </td></tr>
          <tr><td style="padding:24px 40px;background:#F5F0E8;text-align:center;">
            <p style="margin:0;font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#6b6357;">Leave a trace of elegance wherever you go.</p>
            <p style="margin:16px 0 0 0;font-size:11px;color:#9b9285;">Maison Mossero · www.mossero.in</p>
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
                "subject": f"[MOSSERO] Your UPI payment link — {order_doc['order_id']}",
                "html": html,
            },
        )
        return True, None
    except Exception as e:
        logger.error(f"Payment link email failed: {e}")
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


async def _claim_shopify_sync(order_id: str) -> Optional[str]:
    """
    Atomically claim Shopify synchronization for an order.
    Returns a unique claim token if successful, otherwise None.
    """
    now = datetime.now(timezone.utc)
    claim_token = str(uuid.uuid4())
    lease_until = now + timedelta(minutes=5)

    result = await db.orders.update_one(
        {
            "order_id": order_id,
            "shopify_order_id": {"$in": [None, ""]},
            "$or": [
                {"shopify_sync_status": {"$in": [None, "failed"]}},
                {
                    "shopify_sync_status": "processing",
                    "shopify_sync_lease_until": {"$lte": now},
                },
            ],
        },
        {
            "$set": {
                "shopify_sync_status": "processing",
                "shopify_sync_token": claim_token,
                "shopify_sync_started_at": now,
                "shopify_sync_lease_until": lease_until,
                "shopify_error": None,
            }
        },
    )

    if result.modified_count == 1:
        logger.info("Claimed Shopify sync for order %s", order_id)
        return claim_token

    logger.info(
        "Shopify sync claim unavailable for order %s; another attempt may be active",
        order_id,
    )
    return None


async def _finalize_paid_order(txn: dict, rzp_payment_id: Optional[str]) -> dict:
    """Idempotently create the orders record and send confirmation emails."""
    order_id = txn["order_id"]
    existing = await db.orders.find_one({"order_id": order_id}, {"_id": 0})

    if existing:
        if existing.get("shopify_order_id"):
            return existing
        order_doc = existing
    else:
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
            "shopify_order_id": None,
            "shopify_order_number": None,
            "shopify_error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await db.orders.insert_one(order_doc)

        except DuplicateKeyError:
            logger.warning(
                "Order %s was already created by another callback",
                order_id,
            )

            existing = await db.orders.find_one(
                {"order_id": order_id},
                {"_id": 0},
            )

            if not existing:
                raise

            order_doc = existing
            existing = order_doc

        else:
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

        # Best-effort Shiprocket adhoc order creation (does not block paid-order finalization)
    if not existing:
        try:
            sr_result = await shiprocket_client.create_adhoc_order(order_doc)
            sr_update = {
                "shiprocket_order_id": sr_result.get("shiprocket_order_id") or None,
                "shiprocket_shipment_id": sr_result.get("shipment_id") or None,
                "awb_number": sr_result.get("awb_number") or None,
                "courier_name": sr_result.get("courier_name") or None,
                "shiprocket_error": (
                    None if sr_result.get("success") else sr_result.get("error")
                ),
            }
        except Exception as exc:
            logger.exception("Shiprocket order creation failed for order %s", order_id)
            sr_update = {
                "shiprocket_order_id": None,
                "shiprocket_shipment_id": None,
                "awb_number": None,
                "courier_name": None,
                "shiprocket_error": str(exc),
            }

        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": sr_update},
        )
        order_doc.update(sr_update)

    # Best-effort Shopify Admin order creation with atomic claim
    if not order_doc.get("shopify_order_id"):
        claim_token = await _claim_shopify_sync(order_id)

        if claim_token:
            try:
                shopify_result = await shopify_client.create_shopify_order(order_doc)

                outcome = shopify_result.get("outcome", "unknown")
                shopify_order_id = shopify_result.get("shopify_order_id")

                if outcome == "success" and shopify_order_id:
                    shopify_update = {
                        "shopify_order_id": shopify_order_id,
                        "shopify_order_number": shopify_result.get("order_number"),
                        "shopify_error": None,
                        "shopify_sync_status": "synced",
                        "shopify_sync_completed_at": datetime.now(timezone.utc),
                    }

                elif outcome == "failed":
                    shopify_update = {
                        "shopify_error": shopify_result.get("error"),
                        "shopify_sync_status": "failed",
                    }

                else:
                    shopify_update = {
                        "shopify_error": shopify_result.get("error")
                        or "Shopify creation outcome is unknown; manual reconciliation required",
                        "shopify_sync_status": "unknown",
                    }

                update_result = await db.orders.update_one(
                    {
                        "order_id": order_id,
                        "shopify_sync_token": claim_token,
                    },
                    {
                        "$set": shopify_update,
                        "$unset": {
                            "shopify_sync_token": "",
                            "shopify_sync_lease_until": "",
                        },
                    },
                )

                if update_result.modified_count == 1:
                    order_doc.update(shopify_update)
                else:
                    logger.warning(
                        "Shopify sync result not saved because claim ownership changed for order %s",
                        order_id,
                    )


            except Exception as exc:
                logger.exception(
                    "Unexpected Shopify sync error for order %s", order_id
                )

                try:
                    await db.orders.update_one(
                        {
                            "order_id": order_id,
                            "shopify_sync_token": claim_token,
                        },
                        {
                            "$set": {
                                "shopify_sync_status": "unknown",
                                "shopify_error": str(exc),
                            },
                            "$unset": {
                                "shopify_sync_token": "",
                                "shopify_sync_lease_until": "",
                            },
                        },
                    )
                except Exception:
                    logger.exception(
                        "Could not persist Shopify sync error for order %s",
                        order_id,
                    )

        else:
            logger.info(
                "Skipping Shopify creation for order %s; sync is already claimed or needs reconciliation",
                order_id,
            )

        # Return the latest persisted state rather than a potentially stale copy.
        latest_order = await db.orders.find_one(
            {"order_id": order_id},
            {"_id": 0},
        )
        if latest_order:
            order_doc = latest_order

    return order_doc


@api_router.post("/checkout/order", response_model=OrderCreateResponse)
async def create_order(req: OrderCreateRequest):
    if rzp_client is None:
        raise HTTPException(status_code=500, detail="Razorpay is not configured")

    if not req.items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        # Validate product slugs before contacting Shopify.
    product_catalog = {p["slug"]: p for p in PRODUCTS}

    for item in req.items:
        if item.slug not in product_catalog:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown product: {item.slug}",
            )

    # Shopify must be available to provide authoritative prices.
    client = shopify_client.shopify_client

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Product pricing is temporarily unavailable. Please try again later.",
        )

    try:
        slugs = list(dict.fromkeys(item.slug for item in req.items))
        shopify_pricing = await client.get_variant_prices(slugs)

        currency = shopify_pricing["currency"]
        prices = shopify_pricing["prices"]

        if currency != "INR":
            raise ValueError(f"Unexpected Shopify store currency: {currency}")

        total_decimal = Decimal("0")
        detailed_items = []

        product_catalog = {p["slug"]: p for p in PRODUCTS}

        for item in req.items:
            product = product_catalog[item.slug]

            unit_price = Decimal(str(prices[item.slug]))

            if not unit_price.is_finite() or unit_price <= 0:
                raise ValueError(f"Invalid Shopify price for {item.slug}")

            line_total = unit_price * item.quantity
            total_decimal += line_total

            detailed_items.append({
                "slug": item.slug,
                "name": product["name"],
                "unit_price": float(unit_price),
                "quantity": item.quantity,
                "line_total": float(line_total),
            })

        total_decimal = total_decimal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        amount_minor = int(
            (total_decimal * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )

        total = float(total_decimal)

        if amount_minor <= 0:
            raise ValueError("Calculated checkout amount must be positive")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shopify checkout price lookup failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to verify current product prices. Please try again later.",
        )
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
    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    client = shopify_client.shopify_client

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Product pricing is temporarily unavailable.",
        )

    try:
        slugs = list(dict.fromkeys(item.slug for item in req.items))
        shopify_pricing = await client.get_variant_prices(slugs)

        currency = shopify_pricing["currency"]
        prices = shopify_pricing["prices"]

        if currency != "INR":
            raise ValueError(f"Unexpected Shopify currency: {currency}")

        product_catalog = {p["slug"]: p for p in PRODUCTS}
        total_decimal = Decimal("0")
        detailed_items = []

        for item in req.items:
            product = product_catalog.get(item.slug)

            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown product: {item.slug}",
                )

            unit_price = Decimal(str(prices[item.slug]))

            if not unit_price.is_finite() or unit_price <= 0:
                raise ValueError(f"Invalid Shopify price for {item.slug}")

            line_total = unit_price * item.quantity
            total_decimal += line_total

            detailed_items.append({
                "slug": item.slug,
                "name": product["name"],
                "unit_price": float(unit_price),
                "quantity": item.quantity,
                "line_total": float(line_total),
            })

        total_decimal = total_decimal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        total = float(total_decimal)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shopify concierge pricing failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to verify current product prices.",
        )
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


@api_router.post("/checkout/payment-link")
async def create_payment_link(req: OrderCreateRequest):
    """Create a Razorpay Payment Link and email it to the customer for later UPI payment."""
    if rzp_client is None:
        raise HTTPException(status_code=500, detail="Razorpay is not configured")

    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    client = shopify_client.shopify_client

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Product pricing is temporarily unavailable.",
        )

    try:
        slugs = list(dict.fromkeys(item.slug for item in req.items))
        shopify_pricing = await client.get_variant_prices(slugs)

        currency = shopify_pricing["currency"]
        prices = shopify_pricing["prices"]

        if currency != "INR":
            raise ValueError(f"Unexpected Shopify currency: {currency}")

        total_decimal = Decimal("0")
        detailed_items = []
        product_catalog = {p["slug"]: p for p in PRODUCTS}

        for item in req.items:
            product = product_catalog.get(item.slug)

            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown product: {item.slug}",
                )

            unit_price = Decimal(str(prices[item.slug]))

            if not unit_price.is_finite() or unit_price <= 0:
                raise ValueError(f"Invalid Shopify price for {item.slug}")

            line_total = unit_price * item.quantity
            total_decimal += line_total

            detailed_items.append({
                "slug": item.slug,
                "name": product["name"],
                "unit_price": float(unit_price),
                "quantity": item.quantity,
                "line_total": float(line_total),
            })

        total_decimal = total_decimal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        total = float(total_decimal)
        amount_minor = int(
            (total_decimal * 100).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )

        if amount_minor <= 0:
            raise ValueError("Calculated payment amount must be positive")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shopify payment-link price lookup failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to verify current product prices.",
        )
    order_id = f"MSR-{uuid.uuid4().hex[:8].upper()}"
    description = ", ".join(
        f"{i['name']} x {i['quantity']}" for i in detailed_items
    )

    try:
        link = await asyncio.to_thread(
            rzp_client.payment_link.create,
            {
                "amount": amount_minor,
                "currency": currency,
                "accept_partial": False,
                "description": f"MOSSERO order {order_id} - {description}",
                "customer": {
                    "name": req.customer_name,
                    "email": req.customer_email,
                    "contact": (req.customer_contact or "").lstrip("+") or None,
                },
                "notify": {"sms": bool(req.customer_contact), "email": True},
                "reminder_enable": True,
                "notes": {
                    "order_id": order_id,
                    "shipping": req.shipping_address[:200],
                },
                "options": {
                    "checkout": {
                        "method": {
                            "upi": 1,
                            "card": 0,
                            "netbanking": 0,
                            "wallet": 0,
                            "emi": 0,
                            "paylater": 0,
                        }
                    }
                },
            },
        )
    except Exception as e:
        logger.error(f"Razorpay payment_link create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Razorpay error: {e}")

    rzp_plink_id = link.get("id")
    short_url = link.get("short_url")

    txn_doc = {
        "order_id": order_id,
        "rzp_order_id": None,
        "rzp_payment_link_id": rzp_plink_id,
        "payment_link_url": short_url,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "customer_contact": req.customer_contact,
        "shipping_address": req.shipping_address,
        "address_struct": req.address_struct.model_dump() if req.address_struct else None,
        "items": detailed_items,
        "amount": total,
        "amount_minor": amount_minor,
        "currency": currency,
        "channel": "payment_link",
        "payment_status": "link_sent",
        "status": "link_sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(txn_doc)

    # Send our branded email with the link (Razorpay also sends its own; ours is the on-brand one)
    email_sent, email_error = await _send_payment_link_email(
        {
            "order_id": order_id,
            "customer_name": req.customer_name,
            "customer_email": req.customer_email,
            "items": detailed_items,
            "total": total,
            "currency": currency,
            "shipping_address": req.shipping_address,
        },
        short_url,
    )

    await db.payment_transactions.update_one(
        {"order_id": order_id},
        {"$set": {
            "branded_email_sent": email_sent,
            "branded_email_error": email_error,
        }},
    )

    return {
        "order_id": order_id,
        "rzp_payment_link_id": rzp_plink_id,
        "payment_link_url": short_url,
        "amount": amount_minor,
        "currency": currency,
        "total": total,
        "email_sent": email_sent,
        "message": "We have emailed you a secure UPI payment link. Complete it any time within 24 hours.",
    }



@api_router.post("/checkout/verify")
async def verify_payment(req: VerifyPaymentRequest):
    if rzp_client is None:
        raise HTTPException(
            status_code=500,
            detail="Razorpay is not configured",
        )

    txn = await db.payment_transactions.find_one(
        {"order_id": req.order_id},
        {"_id": 0},
    )

    if not txn:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if txn.get("rzp_order_id") != req.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Order mismatch",
        )

    # Step 1: Verify the Checkout signature.
    payload = (
        f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    )

    if not _verify_signature(
        payload,
        req.razorpay_signature,
        RAZORPAY_KEY_SECRET,
    ):
        logger.warning(
            "Invalid Razorpay payment signature for order %s",
            req.order_id,
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid signature",
        )

    # Step 2: Fetch the payment directly from Razorpay.
    try:
        payment_details = await asyncio.to_thread(
            rzp_client.payment.fetch,
            req.razorpay_payment_id,
        )
    except Exception:
        logger.exception(
            "Unable to fetch Razorpay payment for order %s",
            req.order_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to verify payment with Razorpay",
        )

    # Step 3: Verify payment identity and captured status.
    if (
        payment_details.get("id") != req.razorpay_payment_id
        or payment_details.get("order_id") != req.razorpay_order_id
        or payment_details.get("status") != "captured"
    ):
        raise HTTPException(
            status_code=400,
            detail="Payment is not captured or does not match the order",
        )

    # Step 4: Verify the actual amount and currency.
    try:
        actual_amount = Decimal(str(payment_details["amount"]))
        expected_amount = Decimal(str(txn["amount_minor"]))

        if (
            not actual_amount.is_finite()
            or actual_amount != expected_amount
            or payment_details.get("currency") != txn["currency"]
        ):
            raise ValueError("Payment amount or currency mismatch")

    except (KeyError, ValueError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=400,
            detail="Payment amount or currency mismatch",
        )

    # Step 5: Handle already-paid transactions safely.
    if txn.get("payment_status") == "paid":
        stored_payment_id = txn.get("rzp_payment_id")

        if stored_payment_id and stored_payment_id != req.razorpay_payment_id:
            raise HTTPException(
                status_code=409,
                detail="Transaction is already linked to another payment",
            )

        await _finalize_paid_order(
            txn,
            stored_payment_id or req.razorpay_payment_id,
        )

        return {
            "order_id": req.order_id,
            "payment_status": "paid",
            "amount_total": txn["amount_minor"],
            "currency": txn["currency"],
        }

    # Step 6: Mark the transaction paid only after all checks pass.
    await db.payment_transactions.update_one(
        {
            "order_id": req.order_id,
            "payment_status": {"$ne": "paid"},
        },
        {
            "$set": {
                "payment_status": "paid",
                "status": "complete",
                "rzp_payment_id": req.razorpay_payment_id,
                "rzp_signature": req.razorpay_signature,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Step 7: Reload and verify the stored transaction.
    latest_txn = await db.payment_transactions.find_one(
        {"order_id": req.order_id},
        {"_id": 0},
    )

    if (
        not latest_txn
        or latest_txn.get("payment_status") != "paid"
        or latest_txn.get("rzp_payment_id") != req.razorpay_payment_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Payment could not be confirmed",
        )

    await _finalize_paid_order(
        latest_txn,
        req.razorpay_payment_id,
    )

    return {
        "order_id": req.order_id,
        "payment_status": "paid",
        "amount_total": latest_txn["amount_minor"],
        "currency": latest_txn["currency"],
    }


    # Valid signature: mark the transaction as paid.
    await db.payment_transactions.update_one(
        {
            "order_id": req.order_id,
            "payment_status": {"$ne": "paid"},
        },
        {
            "$set": {
                "payment_status": "paid",
                "status": "complete",
                "rzp_payment_id": req.razorpay_payment_id,
                "rzp_signature": req.razorpay_signature,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Reload the latest transaction before finalization.
    latest_txn = await db.payment_transactions.find_one(
        {"order_id": req.order_id},
        {"_id": 0},
    )

    if not latest_txn or latest_txn.get("payment_status") != "paid":
        raise HTTPException(
            status_code=409,
            detail="Payment could not be confirmed",
        )

    await _finalize_paid_order(
        latest_txn,
        latest_txn.get("rzp_payment_id"),
    )

    return {
        "order_id": req.order_id,
        "payment_status": "paid",
        "amount_total": latest_txn["amount_minor"],
        "currency": latest_txn["currency"],
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

    # Webhook signature is mandatory.
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.error("Razorpay webhook secret is not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook configuration error",
        )

    if not _verify_signature(
        body.decode("utf-8"),
        signature,
        RAZORPAY_WEBHOOK_SECRET,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature",
        )

    # Parse the verified payload.
    try:
        import json
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid payload",
        )

    event = payload.get("event")

    payment_entity = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    plink_entity = (
        payload.get("payload", {})
        .get("payment_link", {})
        .get("entity", {})
    )

    rzp_order_id = payment_entity.get("order_id")
    rzp_payment_id = payment_entity.get("id")
    rzp_plink_id = plink_entity.get("id")

    # ---------------------------------------------------------
    # Payment Link events
    # ---------------------------------------------------------
    if event == "payment_link.paid":
        if not rzp_plink_id:
            raise HTTPException(
                status_code=400,
                detail="Missing payment-link ID",
            )

        txn = await db.payment_transactions.find_one(
            {"rzp_payment_link_id": rzp_plink_id},
            {"_id": 0},
        )

        if not txn:
            logger.error(
                "Payment-link transaction not found: %s",
                rzp_plink_id,
            )
            raise HTTPException(
                status_code=404,
                detail="Payment-link transaction not found",
            )

        # Verify the actual amount collected.
        try:
            amount_paid = Decimal(str(plink_entity["amount_paid"]))
            expected_amount = Decimal(str(txn["amount_minor"]))

            if (
                not amount_paid.is_finite()
                or amount_paid != expected_amount
                or plink_entity.get("currency") != txn["currency"]
            ):
                raise ValueError("Payment amount or currency mismatch")

        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            logger.error(
                "Payment-link validation failed for %s: %s",
                rzp_plink_id,
                exc,
            )
            raise HTTPException(
                status_code=400,
                detail="Payment amount or currency mismatch",
            )

        plink_payments = plink_entity.get("payments") or []

        plink_payment_id = next(
            (
                payment.get("payment_id")
                for payment in plink_payments
                if isinstance(payment, dict)
                and payment.get("payment_id")
            ),
            None,
        )

        payment_id = rzp_payment_id or plink_payment_id

        await db.payment_transactions.update_one(
            {"rzp_payment_link_id": rzp_plink_id},
            {"$set": {
                "payment_status": "paid",
                "status": "complete",
                "rzp_payment_id": payment_id,
                "webhook_event": event,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        txn_after = await db.payment_transactions.find_one(
            {"rzp_payment_link_id": rzp_plink_id},
            {"_id": 0},
        )

        if not txn_after:
            raise HTTPException(
                status_code=500,
                detail="Unable to reload payment-link transaction",
            )

        await _finalize_paid_order(
            txn_after,
            txn_after.get("rzp_payment_id"),
        )

        return {"received": True}

    # ---------------------------------------------------------
    # Regular Razorpay order events
    # ---------------------------------------------------------
    if rzp_order_id:
        txn = await db.payment_transactions.find_one(
            {"rzp_order_id": rzp_order_id},
            {"_id": 0},
        )

        if not txn:
            logger.warning(
                "Transaction not found for Razorpay order %s",
                rzp_order_id,
            )
            return {"received": True}

        update_fields = {
            "webhook_event": event,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if rzp_payment_id:
            update_fields["rzp_payment_id"] = rzp_payment_id

        if event == "payment.captured" or payment_entity.get("status") == "captured":

            # Verify amount and currency before marking the transaction paid.
            try:
                actual_amount = Decimal(str(payment_entity["amount"]))
                expected_amount = Decimal(str(txn["amount_minor"]))

                if (
                    not actual_amount.is_finite()
                    or actual_amount != expected_amount
                    or payment_entity.get("currency") != txn["currency"]
                ):
                    raise ValueError("Payment amount or currency mismatch")

            except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
                logger.error(
                    "Payment validation failed for order %s: %s",
                    rzp_order_id,
                    exc,
                )
                raise HTTPException(
                    status_code=400,
                    detail="Payment amount or currency mismatch",
                )

            update_fields["payment_status"] = "paid"
            update_fields["status"] = "complete"

        elif event == "payment.failed":
            update_fields["payment_status"] = "failed"
            update_fields["status"] = "failed"

        else:
            return {"received": True}

        update_filter = {"rzp_order_id": rzp_order_id}

        # A delayed failure event must never downgrade a paid transaction.
        if event == "payment.failed":
            update_filter["payment_status"] = {"$ne": "paid"}

        await db.payment_transactions.update_one(
            update_filter,
            {"$set": update_fields},
        )

        # Reload and finalize only confirmed paid transactions.
        if update_fields.get("payment_status") == "paid":
            txn_after = await db.payment_transactions.find_one(
                {"rzp_order_id": rzp_order_id},
                {"_id": 0},
            )

            if txn_after and txn_after.get("payment_status") == "paid":
                await _finalize_paid_order(
                    txn_after,
                    txn_after.get("rzp_payment_id"),
                )

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


@app.on_event("startup")
async def startup_event():
    if shopify_client.shopify_client:
        validation = await shopify_client.shopify_client.validate_token()
        if not validation.get("valid"):
            logger.warning(
                f"Shopify authentication failed: {validation.get('error')}"
            )
            shopify_client.shopify_client.disable()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
