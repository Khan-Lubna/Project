"""MOSSERO backend API tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://moss-refined.preview.emergentagent.com').rstrip('/')
# Fallback - read from frontend .env
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Products ----------
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
        assert d["name"] == "OURA"
        assert d["target"] == "For Him"
        assert d["price"] == 185.00
        assert "top" in d["notes"]

    def test_get_veloura(self, api):
        r = api.get(f"{BASE_URL}/api/products/veloura")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == "veloura"
        assert d["name"] == "VELOURA"
        assert d["target"] == "For Her"

    def test_get_invalid_product(self, api):
        r = api.get(f"{BASE_URL}/api/products/invalid-xyz")
        assert r.status_code == 404


# ---------- Contact ----------
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
        assert d["email_sent"] is False  # no RESEND_API_KEY
        assert "id" in d and len(d["id"]) > 0

    def test_contact_invalid_email(self, api):
        payload = {
            "name": "TEST_User",
            "email": "not-an-email",
            "message": "hi",
        }
        r = api.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 422


# ---------- Checkout ----------
class TestCheckout:
    def test_checkout_valid(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "1 Test Lane, Test City",
            "items": [
                {"slug": "oura", "quantity": 2},
                {"slug": "veloura", "quantity": 1},
            ],
        }
        r = api.post(f"{BASE_URL}/api/checkout", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "received"
        assert d["currency"] == "USD"
        assert d["total"] == 555.00  # 185*2 + 185
        assert d["order_id"].startswith("MSR-")

    def test_checkout_invalid_slug(self, api):
        payload = {
            "customer_name": "TEST_Buyer",
            "customer_email": "TEST_buyer@example.com",
            "shipping_address": "addr",
            "items": [{"slug": "nonexistent-product", "quantity": 1}],
        }
        r = api.post(f"{BASE_URL}/api/checkout", json=payload)
        assert r.status_code == 400
