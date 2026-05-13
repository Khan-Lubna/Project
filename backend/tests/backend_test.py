"""MOSSERO backend API tests — Razorpay checkout integration (LIVE keys)."""
import os
import hmac
import hashlib
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')

# Mongo + secret read from backend/.env
MONGO_URL = 'mongodb://localhost:27017'
DB_NAME = 'test_database'
RAZORPAY_KEY_SECRET = ''
RAZORPAY_KEY_ID = ''
try:
    with open('/app/backend/.env') as f:
        for line in f:
            line = line.strip()
            if line.startswith('MONGO_URL='):
                MONGO_URL = line.split('=', 1)[1].strip().strip('"').strip("'")
            elif line.startswith('DB_NAME='):
                DB_NAME = line.split('=', 1)[1].strip().strip('"').strip("'")
            elif line.startswith('RAZORPAY_KEY_SECRET='):
                RAZORPAY_KEY_SECRET = line.split('=', 1)[1].strip().strip('"').strip("'")
            elif line.startswith('RAZORPAY_KEY_ID='):
                RAZORPAY_KEY_ID = line.split('=', 1)[1].strip().strip('"').strip("'")
except Exception:
    pass


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


# ---------- Products (regression) ----------
class TestProducts:
    def test_list_products(self, api):
        r = api.get(f"{BASE_URL}/api/products")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 2
        slugs = {p["slug"] for p in data}
        assert slugs == {"oura", "veloura"}
        for p in data:
            assert p["price"] == 100.00
            assert p["currency"] == "USD"

    def test_get_oura(self, api):
        r = api.get(f"{BASE_URL}/api/products/oura")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == "oura"
        assert d["price"] == 100.00

    def test_get_veloura(self, api):
        r = api.get(f"{BASE_URL}/api/products/veloura")
        assert r.status_code == 200
        assert r.json()["price"] == 100.00

    def test_get_invalid_product(self, api):
        r = api.get(f"{BASE_URL}/api/products/invalid-xyz")
        assert r.status_code == 404


# ---------- Contact (regression) ----------
class TestContact:
    def test_contact_valid(self, api):
        payload = {
            "name": "TEST_User",
            "email": "TEST_user@example.com",
            "subject": "TEST_Inquiry",
            "message": "TEST message body",
        }
        r = api.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "received"
        assert "id" in d and len(d["id"]) > 0

    def test_contact_invalid_email(self, api):
        payload = {"name": "TEST_User", "email": "not-an-email", "message": "hi"}
        r = api.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 422


# ---------- Checkout Order creation (Razorpay) ----------
class TestCheckoutOrder:
    def test_create_order_valid(self, api, mongo):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "customer_contact": "+919999999999",
            "shipping_address": "1 Test Lane, Test City",
            "items": [
                {"slug": "oura", "quantity": 2},
                {"slug": "veloura", "quantity": 1},
            ],
        }
        r = api.post(f"{BASE_URL}/api/checkout/order", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"].startswith("MSR-")
        assert d["rzp_order_id"].startswith("order_")
        assert d["rzp_key_id"].startswith("rzp_live_")
        assert d["currency"] == "USD"
        assert d["total"] == 300.00
        assert d["amount"] == 30000  # cents
        assert d["customer_name"] == "TEST_Buyer"

        # Verify Mongo persistence
        txn = mongo.payment_transactions.find_one({"order_id": d["order_id"]})
        assert txn is not None
        assert txn["payment_status"] == "initiated"
        assert txn["rzp_order_id"] == d["rzp_order_id"]
        assert txn["amount"] == 300.00
        assert txn["amount_minor"] == 30000
        assert txn["currency"] == "USD"
        assert len(txn["items"]) == 2

        pytest.shared_order_id = d["order_id"]
        pytest.shared_rzp_order_id = d["rzp_order_id"]

    def test_create_order_unknown_slug(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "nonexistent-product", "quantity": 1}],
        }
        r = api.post(f"{BASE_URL}/api/checkout/order", json=payload)
        assert r.status_code == 400
        assert "Unknown product" in r.json().get("detail", "")

    def test_create_order_empty_items(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "addr",
            "items": [],
        }
        r = api.post(f"{BASE_URL}/api/checkout/order", json=payload)
        # Either 400 (total<=0) or 422 (pydantic) is acceptable
        assert r.status_code in (400, 422), r.text
        if r.status_code == 400:
            assert "empty" in r.json().get("detail", "").lower()


# ---------- Checkout Status ----------
class TestCheckoutStatus:
    def test_status_known_order(self, api):
        order_id = getattr(pytest, "shared_order_id", None)
        if not order_id:
            pytest.skip("No shared order_id from prior test")
        r = api.get(f"{BASE_URL}/api/checkout/status/{order_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["order_id"] == order_id
        assert d["payment_status"] == "initiated"
        assert d["currency"] == "USD"
        assert d["amount_total"] == 30000

    def test_status_unknown(self, api):
        r = api.get(f"{BASE_URL}/api/checkout/status/MSR-DOESNOTEXIST")
        assert r.status_code == 404


# ---------- Verify payment ----------
class TestVerifyPayment:
    def test_verify_invalid_signature_marks_failed(self, api, mongo):
        # Create fresh order
        cr = api.post(f"{BASE_URL}/api/checkout/order", json={
            "customer_name": "TEST_VerifyBad",
            "customer_email": "TEST_verifybad@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "oura", "quantity": 1}],
        })
        assert cr.status_code == 200
        order_id = cr.json()["order_id"]
        rzp_order_id = cr.json()["rzp_order_id"]

        r = api.post(f"{BASE_URL}/api/checkout/verify", json={
            "order_id": order_id,
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": "pay_fake_payment_id",
            "razorpay_signature": "deadbeef" * 8,
        })
        assert r.status_code == 400
        assert "Invalid signature" in r.json().get("detail", "")

        txn = mongo.payment_transactions.find_one({"order_id": order_id})
        assert txn["payment_status"] == "failed"
        assert txn["status"] == "signature_invalid"

    def test_verify_valid_signature_marks_paid_and_creates_order_idempotent(self, api, mongo):
        if not RAZORPAY_KEY_SECRET:
            pytest.skip("RAZORPAY_KEY_SECRET not loaded")
        # Create fresh order
        cr = api.post(f"{BASE_URL}/api/checkout/order", json={
            "customer_name": "TEST_VerifyGood",
            "customer_email": "TEST_verifygood@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "veloura", "quantity": 1}],
        })
        assert cr.status_code == 200
        order_id = cr.json()["order_id"]
        rzp_order_id = cr.json()["rzp_order_id"]

        fake_payment_id = "pay_fake_test_payment_001"
        payload_str = f"{rzp_order_id}|{fake_payment_id}"
        valid_sig = _sign(payload_str, RAZORPAY_KEY_SECRET)

        r1 = api.post(f"{BASE_URL}/api/checkout/verify", json={
            "order_id": order_id,
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": fake_payment_id,
            "razorpay_signature": valid_sig,
        })
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["payment_status"] == "paid"
        assert d1["order_id"] == order_id
        assert d1["amount_total"] == 10000
        assert d1["currency"] == "USD"

        # Mongo: txn paid + 1 order doc created
        txn = mongo.payment_transactions.find_one({"order_id": order_id})
        assert txn["payment_status"] == "paid"
        assert txn["rzp_payment_id"] == fake_payment_id
        orders_count = mongo.orders.count_documents({"order_id": order_id})
        assert orders_count == 1

        # Idempotency: call again, should still return paid + still 1 order
        r2 = api.post(f"{BASE_URL}/api/checkout/verify", json={
            "order_id": order_id,
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": fake_payment_id,
            "razorpay_signature": valid_sig,
        })
        assert r2.status_code == 200
        assert r2.json()["payment_status"] == "paid"
        orders_count2 = mongo.orders.count_documents({"order_id": order_id})
        assert orders_count2 == 1, "Idempotency violated — duplicate order created"

        # Status endpoint now returns paid
        s = api.get(f"{BASE_URL}/api/checkout/status/{order_id}")
        assert s.status_code == 200
        assert s.json()["payment_status"] == "paid"

    def test_verify_unknown_order(self, api):
        r = api.post(f"{BASE_URL}/api/checkout/verify", json={
            "order_id": "MSR-NOPE0000",
            "razorpay_order_id": "order_nope",
            "razorpay_payment_id": "pay_nope",
            "razorpay_signature": "x" * 64,
        })
        assert r.status_code == 404


# ---------- Webhook ----------
class TestWebhook:
    def test_webhook_payment_captured_updates_txn(self, api, mongo):
        # Create fresh order
        cr = api.post(f"{BASE_URL}/api/checkout/order", json={
            "customer_name": "TEST_WebhookBuyer",
            "customer_email": "TEST_webhook@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "oura", "quantity": 1}],
        })
        assert cr.status_code == 200
        order_id = cr.json()["order_id"]
        rzp_order_id = cr.json()["rzp_order_id"]

        body = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_test_001",
                        "order_id": rzp_order_id,
                        "status": "captured",
                    }
                }
            },
        }
        import json as _json
        raw = _json.dumps(body, separators=(',', ':'))
        # Read webhook secret
        wh_secret = ""
        try:
            with open('/app/backend/.env') as f:
                for line in f:
                    if line.strip().startswith('RAZORPAY_WEBHOOK_SECRET='):
                        wh_secret = line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        headers = {"Content-Type": "application/json"}
        if wh_secret:
            sig = hmac.new(wh_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
            headers["X-Razorpay-Signature"] = sig
        r = api.post(f"{BASE_URL}/api/webhook/razorpay", data=raw, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json().get("received") is True

        txn = mongo.payment_transactions.find_one({"rzp_order_id": rzp_order_id})
        assert txn["payment_status"] == "paid"
        assert txn["status"] == "complete"
        assert txn["rzp_payment_id"] == "pay_webhook_test_001"
        assert txn["webhook_event"] == "payment.captured"



# ---------- Order Lookup (/api/orders/lookup) ----------
SEED_ORDER_ID = "MSR-B71D46B3"
SEED_EMAIL = "mossero.in@gmail.com"


class TestOrderLookup:
    def test_lookup_valid_paid_order(self, api):
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": SEED_ORDER_ID,
            "email": SEED_EMAIL,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"] == SEED_ORDER_ID
        assert "customer_name" in d
        assert isinstance(d["items"], list) and len(d["items"]) >= 1
        assert "total" in d
        assert d["currency"]
        assert d["payment_status"] == "paid"
        assert d["shipping_status"] == "preparing"
        assert "shipping_address" in d
        assert "created_at" in d

    def test_lookup_wrong_email_returns_404_no_leak(self, api):
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": SEED_ORDER_ID,
            "email": "wrong_email@example.com",
        })
        assert r.status_code == 404
        assert r.json().get("detail") == "No order found with that reference."

    def test_lookup_unknown_order_returns_404_same_message(self, api):
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": "MSR-DOESNOTX",
            "email": SEED_EMAIL,
        })
        assert r.status_code == 404
        assert r.json().get("detail") == "No order found with that reference."

    def test_lookup_malformed_email_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": SEED_ORDER_ID,
            "email": "not-an-email",
        })
        assert r.status_code == 422

    def test_lookup_case_insensitive_email(self, api):
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": SEED_ORDER_ID,
            "email": "MOSSERO.IN@GMAIL.COM",
        })
        assert r.status_code == 200, r.text
        assert r.json()["order_id"] == SEED_ORDER_ID

    def test_lookup_case_insensitive_order_id(self, api):
        lower_id = SEED_ORDER_ID.lower()  # 'msr-b71d46b3'
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": lower_id,
            "email": SEED_EMAIL,
        })
        assert r.status_code == 200, r.text
        assert r.json()["order_id"] == SEED_ORDER_ID  # normalized upper

    def test_lookup_unpaid_order_returns_awaiting_payment(self, api):
        # Create a brand-new initiated order via /checkout/order to test fallback to payment_transactions
        cr = api.post(f"{BASE_URL}/api/checkout/order", json={
            "customer_name": "TEST_LookupUnpaid",
            "customer_email": "TEST_lookup_unpaid@example.com",
            "shipping_address": "1 Unpaid Ln",
            "items": [{"slug": "oura", "quantity": 1}],
        })
        assert cr.status_code == 200, cr.text
        new_order_id = cr.json()["order_id"]

        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": new_order_id,
            "email": "TEST_lookup_unpaid@example.com",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"] == new_order_id
        assert d["payment_status"] in ("initiated",)
        assert d["shipping_status"] == "awaiting_payment"
        assert d["total"] == 100.00
        assert d["currency"] == "USD"


# ---------- Shiprocket integration tests ----------
import asyncio
import sys
sys.path.insert(0, '/app/backend')


class TestShiprocketAuth:
    """LIVE Shiprocket auth — confirms JWT exchange works."""

    def test_login_returns_jwt(self):
        # Load env from backend/.env
        try:
            with open('/app/backend/.env') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('SHIPROCKET_EMAIL='):
                        os.environ['SHIPROCKET_EMAIL'] = line.split('=', 1)[1].strip().strip('"').strip("'")
                    elif line.startswith('SHIPROCKET_PASSWORD='):
                        os.environ['SHIPROCKET_PASSWORD'] = line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        if not os.environ.get('SHIPROCKET_EMAIL') or not os.environ.get('SHIPROCKET_PASSWORD'):
            pytest.skip("Shiprocket creds not set")

        # Reset module cache
        import importlib
        import shiprocket_client
        importlib.reload(shiprocket_client)
        token = asyncio.run(shiprocket_client._login())
        assert token is not None, "Shiprocket _login returned None"
        assert isinstance(token, str)
        assert len(token) > 100, f"Token suspiciously short: {len(token)} chars"

    def test_is_configured_true(self):
        import shiprocket_client
        assert shiprocket_client.is_configured() is True


# ---------- Structured address acceptance ----------
class TestStructuredAddress:
    def test_create_order_with_address_struct(self, api, mongo):
        payload = {
            "customer_name": "TEST_StructAddr",
            "customer_email": "TEST_struct@example.com",
            "customer_contact": "+919000011111",
            "shipping_address": "1 Lux Road\nMumbai, MH 400001\nIndia",
            "address_struct": {
                "line1": "1 Lux Road",
                "line2": "Apt 4",
                "city": "Mumbai",
                "state": "MH",
                "postal_code": "400001",
                "country": "India",
            },
            "items": [{"slug": "oura", "quantity": 1}],
        }
        r = api.post(f"{BASE_URL}/api/checkout/order", json=payload)
        assert r.status_code == 200, r.text
        oid = r.json()["order_id"]
        txn = mongo.payment_transactions.find_one({"order_id": oid})
        # Confirm address_struct persisted
        assert txn.get("address_struct") is not None
        assert txn["address_struct"]["city"] == "Mumbai"
        assert txn["address_struct"]["postal_code"] == "400001"

    def test_create_order_without_address_struct_still_works(self, api):
        # Backwards compat: omitting address_struct should still succeed
        r = api.post(f"{BASE_URL}/api/checkout/order", json={
            "customer_name": "TEST_NoStruct",
            "customer_email": "TEST_nostruct@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "oura", "quantity": 1}],
        })
        assert r.status_code == 200, r.text


# ---------- Lookup shipping_status mapping ----------
import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz


class TestLookupShippingStatus:
    def _insert_paid_order(self, mongo, **overrides):
        order_id = f"MSR-TST{_uuid.uuid4().hex[:5].upper()}"
        email = "track_test@example.com"
        doc = {
            "order_id": order_id,
            "customer_name": "TEST_Track",
            "customer_email": email,
            "customer_contact": "+910000000000",
            "shipping_address": "Test address",
            "items": [{"slug": "oura", "name": "Oura", "quantity": 1, "unit_price": 100.0}],
            "total": 100.0,
            "currency": "USD",
            "status": "paid",
            "created_at": _dt.now(_tz.utc).isoformat(),
        }
        doc.update(overrides)
        mongo.orders.insert_one(doc)
        return order_id, email

    def test_lookup_fulfillment_pending_when_shiprocket_error(self, api, mongo):
        # Uses existing seed MSR-E0312109 with shiprocket_error=403
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": "MSR-E0312109",
            "email": "mossero.in@gmail.com",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["payment_status"] == "paid"
        assert d["shipping_status"] == "fulfillment_pending"
        assert d.get("awb_number") in (None, "")

    def test_lookup_preparing_when_paid_no_shiprocket(self, api):
        # Seed MSR-B71D46B3 is paid without shiprocket attempt
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={
            "order_id": "MSR-B71D46B3",
            "email": "mossero.in@gmail.com",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["payment_status"] == "paid"
        assert d["shipping_status"] == "preparing"

    def test_lookup_in_transit(self, api, mongo):
        oid, email = self._insert_paid_order(
            mongo,
            awb_number="AWBINTRANSIT01",
            courier_name="Bluedart",
            tracking={
                "current_status": "In Transit",
                "current_location": "Mumbai Hub",
                "estimated_delivery": "2026-02-12",
                "courier_name": "Bluedart",
                "tracking_url": "https://example.com/track/AWB1",
            },
            tracking_cached_at=_dt.now(_tz.utc).isoformat(),
        )
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={"order_id": oid, "email": email})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["shipping_status"] == "in_transit"
        assert d["awb_number"] == "AWBINTRANSIT01"
        assert d["courier_name"] == "Bluedart"
        assert d["tracking_url"] == "https://example.com/track/AWB1"
        assert d["tracking"]["current_status"] == "In Transit"

    def test_lookup_delivered(self, api, mongo):
        oid, email = self._insert_paid_order(
            mongo,
            awb_number="AWBDELIVERED01",
            courier_name="Delhivery",
            tracking={
                "current_status": "Delivered",
                "current_location": "Customer",
                "estimated_delivery": "2026-01-10",
                "courier_name": "Delhivery",
                "tracking_url": "https://example.com/track/D1",
            },
            tracking_cached_at=_dt.now(_tz.utc).isoformat(),
        )
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={"order_id": oid, "email": email})
        assert r.status_code == 200
        assert r.json()["shipping_status"] == "delivered"

    def test_lookup_out_for_delivery(self, api, mongo):
        oid, email = self._insert_paid_order(
            mongo,
            awb_number="AWBOFD01",
            courier_name="Bluedart",
            tracking={
                "current_status": "Out For Delivery",
                "courier_name": "Bluedart",
                "tracking_url": "https://example.com/track/O1",
            },
            tracking_cached_at=_dt.now(_tz.utc).isoformat(),
        )
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={"order_id": oid, "email": email})
        assert r.status_code == 200
        assert r.json()["shipping_status"] == "out_for_delivery"

    def test_lookup_dispatched(self, api, mongo):
        oid, email = self._insert_paid_order(
            mongo,
            awb_number="AWBDISP01",
            courier_name="Xpressbees",
            tracking={
                "current_status": "Picked Up",
                "courier_name": "Xpressbees",
                "tracking_url": "https://example.com/track/P1",
            },
            tracking_cached_at=_dt.now(_tz.utc).isoformat(),
        )
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={"order_id": oid, "email": email})
        assert r.status_code == 200
        assert r.json()["shipping_status"] == "dispatched"

    def test_lookup_cache_freshness_keeps_cached(self, api, mongo):
        """When tracking_cached_at is fresh (<30min), live call should NOT overwrite cached values."""
        oid, email = self._insert_paid_order(
            mongo,
            awb_number="AWBCACHED01",
            courier_name="Bluedart",
            tracking={
                "current_status": "In Transit",
                "current_location": "Cached Hub",
                "courier_name": "Bluedart",
                "tracking_url": "https://example.com/track/cached",
            },
            tracking_cached_at=_dt.now(_tz.utc).isoformat(),
        )
        r = api.post(f"{BASE_URL}/api/orders/lookup", json={"order_id": oid, "email": email})
        assert r.status_code == 200
        # Cached values should still be returned since fresh
        assert r.json()["tracking"]["current_location"] == "Cached Hub"
