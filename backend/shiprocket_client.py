"""Shiprocket courier integration.

Auth: exchanges email + password for a JWT via /v1/external/auth/login.
The JWT is cached in-process for ~9 days (Shiprocket tokens last 10 days).
Best-effort: failures here MUST NOT break order finalization or email confirmation.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

SHIPROCKET_BASE_URL = "https://apiv2.shiprocket.in"

_token_cache: Dict[str, Any] = {"token": None, "expires_at": None}
_token_lock = asyncio.Lock()


def _email() -> str:
    return os.environ.get("SHIPROCKET_EMAIL", "")


def _password() -> str:
    return os.environ.get("SHIPROCKET_PASSWORD", "")


def _pickup() -> str:
    return os.environ.get("SHIPROCKET_PICKUP_LOCATION", "Primary")


def is_configured() -> bool:
    return bool(_email() and _password())


async def _login() -> Optional[str]:
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{SHIPROCKET_BASE_URL}/v1/external/auth/login",
                json={"email": _email(), "password": _password()},
            )
            r.raise_for_status()
            data = r.json()
        token = data.get("token")
        if not token:
            logger.error(f"Shiprocket login returned no token: {data}")
            return None
        _token_cache["token"] = token
        _token_cache["expires_at"] = datetime.now(timezone.utc) + timedelta(days=9)
        logger.info("Shiprocket: obtained fresh JWT (cached 9 days).")
        return token
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300] if e.response is not None else ""
        logger.error(f"Shiprocket login failed: HTTP {e.response.status_code}: {body}")
        return None
    except Exception as e:
        logger.error(f"Shiprocket login error: {e}")
        return None


async def _get_token(force_refresh: bool = False) -> Optional[str]:
    async with _token_lock:
        if not force_refresh:
            tok = _token_cache.get("token")
            exp = _token_cache.get("expires_at")
            if tok and exp and exp > datetime.now(timezone.utc):
                return tok
        return await _login()


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    """Authenticated request. Retries once on 401 by refreshing token."""
    token = await _get_token()
    if not token:
        raise RuntimeError("Shiprocket auth unavailable")
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Content-Type", "application/json")
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.request(method, f"{SHIPROCKET_BASE_URL}{path}", headers=headers, **kwargs)
        if r.status_code == 401:
            token = await _get_token(force_refresh=True)
            if not token:
                return r
            headers["Authorization"] = f"Bearer {token}"
            r = await client.request(method, f"{SHIPROCKET_BASE_URL}{path}", headers=headers, **kwargs)
        return r


async def create_adhoc_order(order_doc: dict) -> Dict[str, Any]:
    """Create a Shiprocket Custom (Adhoc) order from a paid Mossero order.

    Returns dict: success, shiprocket_order_id, shipment_id, awb_number, courier_name, raw, error
    """
    if not is_configured():
        return {"success": False, "error": "SHIPROCKET_EMAIL/PASSWORD not set"}

    address = order_doc.get("address_struct") or {}
    items = order_doc.get("items", [])
    sub_total = order_doc.get("total", 0.0)

    name_parts = order_doc["customer_name"].split(" ", 1)
    first_name = name_parts[0] or order_doc["customer_name"]
    last_name = name_parts[1] if len(name_parts) > 1 else "."

    payload = {
        "order_id": order_doc["order_id"],
        "order_date": order_doc["created_at"][:19].replace("T", " "),
        "pickup_location": _pickup(),
        "billing_customer_name": first_name,
        "billing_last_name": last_name,
        "billing_address": address.get("line1") or order_doc.get("shipping_address", ""),
        "billing_address_2": address.get("line2", ""),
        "billing_city": address.get("city", ""),
        "billing_pincode": address.get("postal_code", ""),
        "billing_state": address.get("state", ""),
        "billing_country": address.get("country", "India"),
        "billing_email": order_doc["customer_email"],
        "billing_phone": (order_doc.get("customer_contact") or "0000000000").lstrip("+"),
        "shipping_is_billing": True,
        "order_items": [
            {
                "name": it["name"],
                "sku": it.get("slug", "MSR-SKU").upper(),
                "units": it["quantity"],
                "selling_price": it["unit_price"],
            }
            for it in items
        ],
        "payment_method": "Prepaid",
        "sub_total": sub_total,
        "length": 12,
        "breadth": 8,
        "height": 6,
        "weight": 0.5,
    }

    try:
        r = await _request("POST", "/v1/external/orders/create/adhoc", json=payload)
        if r.status_code >= 400:
            body = r.text[:500]
            logger.error(f"Shiprocket adhoc create {r.status_code}: {body}")
            return {"success": False, "error": f"HTTP {r.status_code}: {body}", "raw": None}
        data = r.json()
        return {
            "success": True,
            "shiprocket_order_id": str(data.get("order_id") or ""),
            "shipment_id": str(data.get("shipment_id") or ""),
            "awb_number": data.get("awb_code") or "",
            "courier_name": data.get("courier_name") or "",
            "raw": data,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Shiprocket create adhoc failed: {e}")
        return {"success": False, "error": str(e), "raw": None}


async def track_by_awb(awb: str) -> Dict[str, Any]:
    if not is_configured():
        return {"error": "Shiprocket not configured"}
    if not awb:
        return {"error": "Missing AWB"}
    try:
        r = await _request("GET", f"/v1/external/courier/track/awb/{awb}")
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        return _parse_tracking(r.json(), awb)
    except Exception as e:
        logger.warning(f"Shiprocket track by AWB failed for {awb}: {e}")
        return {"error": str(e)}


async def track_by_shipment(shipment_id: str) -> Dict[str, Any]:
    if not is_configured():
        return {"error": "Shiprocket not configured"}
    if not shipment_id:
        return {"error": "Missing shipment_id"}
    try:
        r = await _request("GET", f"/v1/external/courier/track/shipment/{shipment_id}")
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        return _parse_tracking(r.json(), "")
    except Exception as e:
        logger.warning(f"Shiprocket track by shipment failed for {shipment_id}: {e}")
        return {"error": str(e)}


def _parse_tracking(data: Any, awb: str) -> Dict[str, Any]:
    if isinstance(data, dict):
        td = None
        if "tracking_data" in data:
            td = data["tracking_data"]
        elif awb and awb in data and isinstance(data[awb], dict):
            td = data[awb].get("tracking_data") or data[awb]
        else:
            for v in data.values():
                if isinstance(v, dict) and "tracking_data" in v:
                    td = v["tracking_data"]
                    break
        if td:
            shipment_track = td.get("shipment_track") or []
            shipment_status = td.get("shipment_status") or td.get("track_status") or "In Transit"
            current = shipment_track[0] if shipment_track else {}
            return {
                "current_status": current.get("current_status") or shipment_status,
                "current_location": current.get("current_city") or current.get("destination"),
                "estimated_delivery": current.get("edd"),
                "courier_name": current.get("courier_name", ""),
                "awb_number": current.get("awb_code", awb),
                "tracking_url": td.get("track_url") or (f"https://shiprocket.co/tracking/{awb}" if awb else None),
                "raw": data,
                "error": None,
            }
    return {"error": "Unrecognised tracking response", "raw": data}
