"""MOSSERO backend API tests — Stripe checkout integration."""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')

# Mongo connection for verification
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')
try:
    with open('/app/backend/.env') as f:
        for line in f:
            if line.startswith('MONGO_URL='):
                MONGO_URL = line.split('=', 1)[1].strip().strip('"').strip("'")
            if line.startswith('DB_NAME='):
                DB_NAME = line.split('=', 1)[1].strip().strip('"').strip("'")
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

    def test_get_oura(self, api):
        r = api.get(f"{BASE_URL}/api/products/oura")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == "oura"
        assert d["price"] == 185.00

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


# ---------- Checkout Session (new) ----------
class TestCheckoutSession:
    def test_create_session_valid(self, api, mongo):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "1 Test Lane, Test City",
            "items": [
                {"slug": "oura", "quantity": 2},
                {"slug": "veloura", "quantity": 1},
            ],
            "origin_url": BASE_URL,
        }
        r = api.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d and "stripe.com" in d["url"]
        assert "session_id" in d and len(d["session_id"]) > 0
        assert d["order_id"].startswith("MSR-")
        assert d["total"] == 555.00
        assert d["currency"] == "usd"

        # DB persistence
        txn = mongo.payment_transactions.find_one({"session_id": d["session_id"]})
        assert txn is not None
        assert txn["payment_status"] == "initiated"
        assert txn["amount"] == 555.00
        assert txn["currency"] == "usd"
        assert len(txn["items"]) == 2

        # stash for next tests
        pytest.shared_session_id = d["session_id"]
        pytest.shared_order_id = d["order_id"]

    def test_create_session_unknown_slug(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "nonexistent-product", "quantity": 1}],
            "origin_url": BASE_URL,
        }
        r = api.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert r.status_code == 400
        assert "Unknown product" in r.json().get("detail", "")

    def test_create_session_empty_items(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "addr",
            "items": [],
            "origin_url": BASE_URL,
        }
        r = api.post(f"{BASE_URL}/api/checkout/session", json=payload)
        # Either 400 from total<=0 OR 422 from pydantic. Both acceptable as "rejected".
        assert r.status_code in (400, 422), r.text


# ---------- Checkout Status (new) ----------
class TestCheckoutStatus:
    def test_status_for_known_session_graceful(self, api):
        # Create a fresh session first
        payload = {
            "customer_name": "TEST_Status",
            "customer_email": "TEST_status@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "oura", "quantity": 1}],
            "origin_url": BASE_URL,
        }
        cr = api.post(f"{BASE_URL}/api/checkout/session", json=payload)
        assert cr.status_code == 200
        sid = cr.json()["session_id"]

        r = api.get(f"{BASE_URL}/api/checkout/status/{sid}")
        # MUST gracefully fall back even when emergentintegrations cannot find it
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["session_id"] == sid
        assert d["payment_status"] in ("initiated", "paid", "unpaid", "no_payment_required")
        assert "order_id" in d and d["order_id"].startswith("MSR-")
        assert d["currency"] == "usd"

    def test_status_for_unknown_session(self, api):
        r = api.get(f"{BASE_URL}/api/checkout/status/cs_unknown_test_session_xyz")
        assert r.status_code == 404
