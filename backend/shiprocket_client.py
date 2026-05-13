"""Shiprocket courier integration.

Uses a long-lived API user token (no email/password login).
Best-effort: failures here MUST NOT break order finalization or email confirmation.
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

SHIPROCKET_BASE_URL = "https://apiv2.shiprocket.in"


def _token() -> str:
    return os.environ.get("SHIPROCKET_API_TOKEN", "")


def _pickup() -> str:
    return os.environ.get("SHIPROCKET_PICKUP_LOCATION", "Primary")


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


def is_configured() -> bool:
    return bool(_token())


async def create_adhoc_order(order_doc: dict) -> Dict[str, Any]:
    """Create a Shiprocket Custom (Adhoc) order from a paid Mossero order.

    Returns dict with at least: success (bool), shiprocket_order_id, shipment_id, awb_number, courier_name, raw, error
    """
    if not is_configured():
        return {"success": False, "error": "SHIPROCKET_API_TOKEN not set"}

    address = order_doc.get("address_struct") or {}
    items = order_doc.get("items", [])
    sub_total = order_doc.get("total", 0.0)

    payload = {
        "order_id": order_doc["order_id"],
        "order_date": order_doc["created_at"][:19].replace("T", " "),
        "pickup_location": _pickup(),
        "billing_customer_name": order_doc["customer_name"].split(" ")[0] or order_doc["customer_name"],
        "billing_last_name": " ".join(order_doc["customer_name"].split(" ")[1:]) or ".",
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
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{SHIPROCKET_BASE_URL}/v1/external/orders/create/adhoc",
                json=payload,
                headers=_headers(),
            )
            r.raise_for_status()
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
    except httpx.HTTPStatusError as e:
        body = e.response.text[:500] if e.response is not None else ""
        logger.error(f"Shiprocket create adhoc HTTP error: {e}: {body}")
        return {"success": False, "error": f"HTTP {e.response.status_code}: {body}", "raw": None}
    except Exception as e:
        logger.error(f"Shiprocket create adhoc failed: {e}")
        return {"success": False, "error": str(e), "raw": None}


async def track_by_awb(awb: str) -> Dict[str, Any]:
    """Fetch tracking by AWB number. Returns dict with current_status, location, etd, courier, url, raw, error."""
    if not is_configured():
        return {"error": "SHIPROCKET_API_TOKEN not set"}
    if not awb:
        return {"error": "Missing AWB"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{SHIPROCKET_BASE_URL}/v1/external/courier/track/awb/{awb}",
                headers=_headers(),
            )
            r.raise_for_status()
            data = r.json()
        return _parse_tracking(data, awb)
    except Exception as e:
        logger.warning(f"Shiprocket track by AWB failed for {awb}: {e}")
        return {"error": str(e)}


async def track_by_shipment(shipment_id: str) -> Dict[str, Any]:
    if not is_configured():
        return {"error": "SHIPROCKET_API_TOKEN not set"}
    if not shipment_id:
        return {"error": "Missing shipment_id"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{SHIPROCKET_BASE_URL}/v1/external/courier/track/shipment/{shipment_id}",
                headers=_headers(),
            )
            r.raise_for_status()
            data = r.json()
        return _parse_tracking(data, "")
    except Exception as e:
        logger.warning(f"Shiprocket track by shipment failed for {shipment_id}: {e}")
        return {"error": str(e)}


def _parse_tracking(data: Any, awb: str) -> Dict[str, Any]:
    """Shiprocket tracking JSON shape can vary; collapse to a flat dict."""
    if isinstance(data, dict):
        # Common shapes: {tracking_data: {...}} or {<awb>: {tracking_data: {...}}}
        td = None
        if "tracking_data" in data:
            td = data["tracking_data"]
        elif awb and awb in data and isinstance(data[awb], dict):
            td = data[awb].get("tracking_data") or data[awb]
        else:
            # take first dict-valued key
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
