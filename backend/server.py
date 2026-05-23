import os
import uuid
import hmac
import hashlib
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
import razorpay

# ── Bootstrap ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mossero Checkout API")

# ── CORS ─────────────────────────────────────────────────────────────────────
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Env / Secrets ─────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL", "")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")

# ── Razorpay client singleton ─────────────────────────────────────────────────
_rzp_client: Optional[razorpay.Client] = None


def get_rzp() -> razorpay.Client:
    global _rzp_client
    if _rzp_client is None:
        _rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return _rzp_client


# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo: Optional[AsyncIOMotorClient] = None


async def get_db():
    global _mongo
    if _mongo is None:
        _mongo = AsyncIOMotorClient(MONGO_URL)
    return _mongo[DB_NAME]

# ── Shopify ───────────────────────────────────────────────────────────────────
_shopify_client: Any = None


def _init_shopify():
    global _shopify_client
    if SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN:
        from shopify_client import ShopifyClient
        _shopify_client = ShopifyClient(
            SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN, SHOPIFY_API_VERSION
        )
        logger.info("Shopify client initialised")


_init_shopify()

# ── Product catalogue ─────────────────────────────────────────────────────────
PRODUCTS: Dict[str, Dict[str, Any]] = {
    "oura": {"slug": "oura",   "name": "OURA",   "price": 100.0},
    "veloura": {"slug": "veloura", "name": "VELOURA", "price": 100.0},
}

# ── Schemas ───────────────────────────────────────────────────────────────────


class ProductSlugRequest(BaseModel):
    slug: str


class OrderItem(BaseModel):
    slug: str
    quantity: int = Field(gt=0)


class CheckoutOrderRequest(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_contact: str
    shipping_address: str
    address_struct: Optional[Dict[str, Any]] = None
    notes: Optional[str] = ""
    items: List[OrderItem] = Field(min_length=1)


class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class QrPinRequest(BaseModel):
    slug: str
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")

# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_order_id() -> str:
    return "MSR-" + uuid.uuid4().hex[:6].upper()


def _product_total(items: List[OrderItem]) -> float:
    total = 0.0
    for item in items:
        prod = PRODUCTS.get(item.slug)
        if prod:
            total += prod["price"] * item.quantity
    return total


def _build_rzp_order_id() -> str:
    return "order_" + uuid.uuid4().hex[:15]

# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/api/products")
def get_products():
    return list(PRODUCTS.values())


@app.get("/api/products/{slug}")
def get_product(slug: str):
    product = PRODUCTS.get(slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/api/payment-link")
async def create_payment_link(request: ProductSlugRequest):
    product = PRODUCTS.get(request.slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    client = get_rzp()
    payment_link = client.payment_link.create({
        "amount": int(product["price"] * 100),
        "currency": "USD",
        "description": f"{product['name']} - {product['slug']}",
        "reference_id": f"product_{product['slug']}",
        "reminder_enable": True,
        "notes": {
            "product": product["slug"],
            "product_name": product["name"],
        },
    })
    return {
        "payment_link": payment_link["short_url"],
        "amount": payment_link["amount"],
        "product": product,
    }


@app.get("/api/qr-code/{slug}")
async def get_qr_code(slug: str):
    """
    Returns a Razorpay payment-link URL whose amount is already fixed to the
    product's price. The frontend encodes this URL into a QR image; when the
    customer scans it the Razorpay page opens with the correct amount pre-filled,
    so they do not have to type anything.
    """
    product = PRODUCTS.get(slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    client = get_rzp()
    payment_link = client.payment_link.create({
        "amount": int(product["price"] * 100),
        "currency": "USD",
        "description": f"{product['name']} - {product['slug']}",
        "reference_id": f"qr_{product['slug']}",
        "reminder_enable": True,
    })
    return {
        "payment_url": payment_link["short_url"],
        "amount": payment_link["amount"],
        "product": product,
    }


# ── QR Express (PIN-based) ───────────────────────────────────────────────────
@app.post("/api/qr-checkout")
async def qr_checkout(request: QrPinRequest):
    """
    Verify a 4-digit PIN (placeholder auth — replace with real PIN store in prod)
    and immediately create a Razorpay order for the corresponding product.
    Client receives the order_id + amount to open the Razorpay Checkout modal.
    """
    product = PRODUCTS.get(request.slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    _VALID_PINS = {"0000", "1234"}
    if request.pin not in _VALID_PINS:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    order_id = _generate_order_id()
    amount = int(product["price"] * 100)

    client = get_rzp()
    rzp_order_resp = client.order.create({
        "amount": amount,
        "currency": "USD",
        "receipt": order_id,
        "payment_capture": 1,
        "notes": {
            "product": product["slug"],
            "product_name": product["name"],
            "msr_order_id": order_id,
        },
    })

    db = await get_db()
    await db.payment_transactions.insert_one({
        "order_id": order_id,
        "rzp_order_id": rzp_order_resp["id"],
        "customer_name": "QR Express",
        "customer_email": "",
        "customer_contact": "",
        "shipping_address": "",
        "address_struct": None,
        "items": [{
            "slug": product["slug"],
            "name": product["name"],
            "quantity": 1,
            "unit_price": product["price"],
        }],
        "total": product["price"],
        "amount": product["price"],
        "amount_minor": amount,
        "currency": "USD",
        "payment_status": "initiated",
        "status": "initiated",
        "rzp_payment_id": None,
        "rzp_signature": None,
        "webhook_event": None,
        "notes": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "order_id": order_id,
        "rzp_order_id": rzp_order_resp["id"],
        "amount": amount,
        "currency": "USD",
        "product": product,
    }


# ── Razorpay Checkout ─────────────────────────────────────────────────────────
@app.post("/api/checkout/order")
async def checkout_order(request: CheckoutOrderRequest):
    db = await get_db()

    validated_items = []
    items_total = 0.0
    for item in request.items:
        product = PRODUCTS.get(item.slug)
        if not product:
            raise HTTPException(
                status_code=400, detail=f"Unknown product: {item.slug}"
            )
        line_total = product["price"] * item.quantity
        items_total += line_total
        validated_items.append({
            "slug": product["slug"],
            "name": product["name"],
            "quantity": item.quantity,
            "unit_price": product["price"],
        })

    if items_total <= 0:
        raise HTTPException(
            status_code=400, detail="Order total must be greater than zero"
        )

    order_id = _generate_order_id()
    amount = int(items_total * 100)

    client = get_rzp()
    try:
        rzp_resp = client.order.create({
            "amount": amount,
            "currency": "USD",
            "receipt": order_id,
            "payment_capture": 1,
            "notes": {
                "customer_email": request.customer_email,
                "msr_order_id": order_id,
            },
        })
        rzp_order = rzp_resp["id"]
    except Exception as exc:
        logger.error(f"Razorpay order creation failed: {exc}")
        raise HTTPException(
            status_code=502, detail="Payment gateway error"
        ) from exc

    await db.payment_transactions.insert_one({
        "order_id": order_id,
        "rzp_order_id": rzp_order,
        "customer_name": request.customer_name,
        "customer_email": request.customer_email,
        "customer_contact": request.customer_contact,
        "shipping_address": request.shipping_address,
        "address_struct": request.address_struct,
        "items": validated_items,
        "total": items_total,
        "amount": items_total,
        "amount_minor": amount,
        "currency": "USD",
        "payment_status": "initiated",
        "status": "initiated",
        "rzp_payment_id": None,
        "rzp_signature": None,
        "webhook_event": None,
        "notes": request.notes or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "order_id": order_id,
        "rzp_order_id": rzp_order,
        "rzp_key_id": RAZORPAY_KEY_ID,
        "currency": "USD",
        "total": items_total,
        "amount": amount,
        "customer_name": request.customer_name,
    }


@app.post("/api/checkout/verify")
async def checkout_verify(request: VerifyPaymentRequest):
    db = await get_db()
    txn = await db.payment_transactions.find_one(
        {"order_id": request.order_id}
    )
    if txn is None:
        raise HTTPException(status_code=404, detail="Order not found")

    payload = (
        f"{request.razorpay_order_id}|{request.razorpay_payment_id}"
    )
    expected_sig = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_sig, request.razorpay_signature)
    now = datetime.now(timezone.utc).isoformat()

    if not is_valid:
        await db.payment_transactions.update_one(
            {"order_id": request.order_id},
            {"$set": {
                "payment_status": "failed",
                "status": "signature_invalid",
                "rzp_payment_id": request.razorpay_payment_id,
                "updated_at": now,
            }},
        )
        raise HTTPException(status_code=400, detail="Invalid signature")

    if txn.get("payment_status") == "paid":
        existing_order = await db.orders.find_one(
            {"order_id": request.order_id}
        )
        if existing_order:
            return {
                "payment_status": "paid",
                "order_id": request.order_id,
                "amount_total": txn.get("amount_minor", 0),
                "currency": "USD",
            }

    await db.payment_transactions.update_one(
        {"order_id": request.order_id},
        {"$set": {
            "payment_status": "paid",
            "status": "complete",
            "rzp_payment_id": request.razorpay_payment_id,
            "rzp_signature": request.razorpay_signature,
            "updated_at": now,
        }},
    )

    existing = await db.orders.find_one({"order_id": request.order_id})
    if existing is None:
        await db.orders.insert_one({
            "order_id": request.order_id,
            "rzp_order_id": txn["rzp_order_id"],
            "customer_name": txn.get("customer_name", ""),
            "customer_email": txn.get("customer_email", ""),
            "customer_contact": txn.get("customer_contact", ""),
            "shipping_address": txn.get("shipping_address", ""),
            "address_struct": txn.get("address_struct"),
            "items": txn.get("items", []),
            "total": txn.get("total", 0.0),
            "amount": txn.get("amount", 0.0),
            "amount_minor": txn.get("amount_minor", 0),
            "currency": "USD",
            "payment_status": "paid",
            "shipping_status": "preparing",
            "created_at": now,
            "notes": txn.get("notes", ""),
        })

        if _shopify_client:
            asyncio.create_task(
                _shopify_client.create_order({
                    "order_id": request.order_id,
                    "rzp_order_id": txn["rzp_order_id"],
                    "customer_name": txn.get("customer_name", ""),
                    "customer_email": txn.get("customer_email", ""),
                    "total": txn.get("total", 0.0),
                    "currency": "USD",
                    "items": txn.get("items", []),
                })
            )

    return {
        "payment_status": "paid",
        "order_id": request.order_id,
        "amount_total": txn.get("amount_minor", 0),
        "currency": "USD",
    }


@app.get("/api/checkout/status/{order_id}")
async def checkout_status(order_id: str):
    db = await get_db()
    txn = await db.payment_transactions.find_one(
        {"order_id": order_id}
    )
    if txn is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order_id,
        "payment_status": txn.get("payment_status", "initiated"),
        "amount_total": txn.get("amount_minor", 0),
        "currency": txn.get("currency", "USD"),
    }


@app.post("/api/webhook/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    raw = body.decode("utf-8")

    if RAZORPAY_WEBHOOK_SECRET:
        expected_sig = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()
        provided_sig = request.headers.get("X-Razorpay-Signature", "")
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(
                status_code=401, detail="Invalid webhook signature"
            )

    try:
        import json
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid JSON"
        ) from None

    event = payload.get("event", "")
    payment = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )
    rzp_order_id = payment.get("order_id", "")
    rzp_payment_id = payment.get("id", "")

    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    if event == "payment.captured":
        result = await db.payment_transactions.find_one_and_update(
            {"rzp_order_id": rzp_order_id},
            {"$set": {
                "payment_status": "paid",
                "status": "complete",
                "rzp_payment_id": rzp_payment_id,
                "webhook_event": event,
                "updated_at": now,
            }},
            return_document=True,
        )
        if result:
            existing = await db.orders.find_one(
                {"order_id": result["order_id"]}
            )
            if existing is None:
                await db.orders.insert_one({
                    "order_id": result["order_id"],
                    "rzp_order_id": rzp_order_id,
                    "customer_name": result.get("customer_name", ""),
                    "customer_email": result.get("customer_email", ""),
                    "customer_contact": result.get("customer_contact", ""),
                    "shipping_address": result.get("shipping_address", ""),
                    "address_struct": result.get("address_struct"),
                    "items": result.get("items", []),
                    "total": result.get("total", 0.0),
                    "amount": result.get("amount", 0.0),
                    "amount_minor": result.get("amount_minor", 0),
                    "currency": "USD",
                    "payment_status": "paid",
                    "shipping_status": "preparing",
                    "created_at": now,
                    "notes": result.get("notes", ""),
                })
                if _shopify_client:
                    asyncio.create_task(
                        _shopify_client.create_order({
                            "order_id": result["order_id"],
                            "rzp_order_id": rzp_order_id,
                            "customer_name": result.get("customer_name", ""),
                            "customer_email": result.get("customer_email", ""),
                            "total": result.get("total", 0.0),
                            "currency": "USD",
                            "items": result.get("items", []),
                        })
                    )
        return {"received": True, "event": event}

    if event == "payment.failed":
        await db.payment_transactions.update_one(
            {"rzp_order_id": rzp_order_id},
            {"$set": {
                "payment_status": "failed",
                "status": "payment_failed",
                "webhook_event": event,
                "updated_at": now,
            }},
        )
        return {"received": True, "event": event}

    return {"received": True, "event": event}


# ── Concierge reservation ────────────────────────────────────────────────────
@app.post("/api/checkout/concierge")
async def checkout_concierge(request: CheckoutOrderRequest):
    order_id = _generate_order_id()
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    validated_items = []
    for item in request.items:
        product = PRODUCTS.get(item.slug)
        if not product:
            raise HTTPException(
                status_code=400, detail=f"Unknown product: {item.slug}"
            )
        validated_items.append({
            "slug": product["slug"],
            "name": product["name"],
            "quantity": item.quantity,
            "unit_price": product["price"],
        })

    await db.orders.insert_one({
        "order_id": order_id,
        "customer_name": request.customer_name,
        "customer_email": request.customer_email,
        "customer_contact": request.customer_contact,
        "shipping_address": request.shipping_address,
        "address_struct": request.address_struct,
        "items": validated_items,
        "total": _product_total(request.items),
        "currency": "USD",
        "payment_status": "pending",
        "shipping_status": "awaiting_payment",
        "created_at": now,
        "notes": request.notes or "",
        "mode": "concierge",
    })
    return {"order_id": order_id, "mode": "concierge"}


# ── Orders lookup ─────────────────────────────────────────────────────────────
@app.post("/api/orders/lookup")
async def orders_lookup(request: Request):
    body = await request.json()
    oid = str(body.get("order_id", "")).upper()
    email = str(body.get("email", "")).lower().strip()

    db = await get_db()

    order = await db.orders.find_one({"order_id": oid})
    if order:
        if order.get("customer_email", "").lower().strip() != email:
            raise HTTPException(
                status_code=404,
                detail="No order found with that reference.",
            )
        return {
            "order_id": order["order_id"],
            "customer_name": order.get("customer_name", ""),
            "items": order.get("items", []),
            "total": order.get("total", 0.0),
            "currency": order.get("currency", "USD"),
            "payment_status": order.get("payment_status", "paid"),
            "shipping_status": order.get("shipping_status", "preparing"),
            "shipping_address": order.get("shipping_address", ""),
            "created_at": order.get("created_at", ""),
            "awb_number": order.get("awb_number"),
            "courier_name": order.get("courier_name"),
            "tracking": order.get("tracking"),
            "tracking_url": order.get("tracking_url"),
        }

    txn = await db.payment_transactions.find_one({"order_id": oid})
    if txn:
        if txn.get("customer_email", "").lower().strip() != email:
            raise HTTPException(
                status_code=404,
                detail="No order found with that reference.",
            )
        return {
            "order_id": txn["order_id"],
            "customer_name": txn.get("customer_name", ""),
            "items": txn.get("items", []),
            "total": txn.get("total", 0.0),
            "currency": txn.get("currency", "USD"),
            "payment_status": txn.get("payment_status", "initiated"),
            "shipping_status": "awaiting_payment",
            "shipping_address": txn.get("shipping_address", ""),
            "created_at": txn.get("created_at", ""),
            "awb_number": None,
            "courier_name": None,
            "tracking": None,
            "tracking_url": None,
        }

    raise HTTPException(
        status_code=404, detail="No order found with that reference."
    )


# ── Contact ───────────────────────────────────────────────────────────────────
@app.post("/api/contact")
async def contact(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()

    from email_validator import validate_email, EmailNotValidError
    try:
        validate_email(email)
    except EmailNotValidError:
        raise HTTPException(
            status_code=422, detail="Invalid email address"
        )

    if not all([name, message]):
        raise HTTPException(
            status_code=422, detail="Name and message are required"
        )

    logger.info(
        f"Contact — {name} <{email}> | {subject}: {message[:120]}..."
    )
    return {"status": "received", "id": str(uuid.uuid4())}


# ── Legacy GET payment-link passthrough ──────────────────────────────────────
@app.get("/api/payment-link")
async def create_payment_link_query(request: Request):
    slug = request.query_params.get("slug", "")
    from pydantic import ValidationError as VE
    try:
        req = ProductSlugRequest(slug=slug)
    except VE:
        raise HTTPException(
            status_code=422, detail="Missing or invalid 'slug'"
        ) from None
    return await create_payment_link(req)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
