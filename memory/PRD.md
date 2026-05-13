# MOSSERO — Product Requirements Document

## Original Problem Statement
Build a Shopify-style e-commerce website for **MOSSERO**, a luxury perfume brand, with a Louis Vuitton-level visual identity. Two products: OURA (For Him) and VELOURA (For Her). Brand uses cream/black/gold palette with serif headlines and elegant typography.

User choices: React/FastAPI replica, functional cart with **Razorpay LIVE** checkout, Unsplash imagery (interim), Resend email for contact form, recipient `mossero.in@gmail.com`, sender `hello@mossero.in`, domain `www.mossero.in`. Prices: **$100 USD** for OURA and VELOURA.

## Architecture
- **Backend** (FastAPI + MongoDB + Motor):
  - `GET /api/products`, `GET /api/products/{slug}` — catalog
  - `POST /api/checkout/order` — creates Razorpay order, stores `payment_transactions`
  - `POST /api/checkout/verify` — HMAC-SHA256 signature verification, idempotent paid-state transition, writes `orders`
  - `GET /api/checkout/status/{order_id}` — lookup by internal order id (MSR-…)
  - `POST /api/webhook/razorpay` — async confirmation handler
  - `POST /api/contact` — Resend email send + persist
- **Frontend** (React 19 + react-router v7 + Tailwind + Cormorant Garamond / Montserrat):
  - 6 pages: Home / Fragrances / Product / Our Story / Contact / Cart + `/cart/success`
  - LocalStorage cart, Sonner toasts, lazy-loaded Razorpay Checkout JS
- **Theme**: cream `#F5F0E8`, gold `#C4A258`, charcoal `#2B2725`, sharp corners only.

## Implemented (2026-02-06)
- 6 pages + cart success/error states + **Order Tracking** (`/track`) with live Shiprocket data
- Sticky centered-logo nav with live cart badge; sharp-corner gold/black CTAs; fade-in animations
- **Resend LIVE**: `hello@mossero.in` → `mossero.in@gmail.com` (delivery confirmed)
- **Razorpay LIVE** (`rzp_live_SoukX8sERjIS3Z`): real orders, real signature verification, idempotent finalization, webhook handler with `RAZORPAY_WEBHOOK_SECRET` verification
- **Order confirmation emails** sent on paid event (customer + maison) — idempotent
- **Order tracking** via `POST /api/orders/lookup` (order_id + email, no enumeration leak, case-insensitive)
- **Shiprocket integration**: JWT login + 9-day cache + 401 auto-refresh, best-effort adhoc order creation on paid event, 30-min tracking cache. Status mapping → `awaiting_payment | preparing | fulfillment_pending | dispatched | in_transit | out_for_delivery | delivered`. Graceful UX when account-level permissions deny order creation.
- **Structured address** on checkout: `line1`, `line2`, `city`, `state`, `postal_code`, `country`
- Tests: backend 33/33 (iter 5). Two HIGH-priority frontend bugs found and fixed (Cart undefined `form.shipping_address`; OrderTracking `.toFixed` on missing field).

## P1 / P2 Backlog
- **P1 (action required by user)**: Resolve Shiprocket 403 — in Shiprocket dashboard verify (a) pickup location named `Primary` exists (or update `SHIPROCKET_PICKUP_LOCATION` in `.env`), (b) API user has "Create Orders" permission, (c) KYC is complete.
- **P1**: Replace placeholder Unsplash imagery with original MOSSERO product photography.
- **P1**: Rotate Razorpay key + Shiprocket password (both shared via chat).
- **P2**: Newsletter / waitlist capture on Fragrances page.
- **P2**: Admin/CMS for editing copy & product imagery.
- **P2**: Multilingual (EN/FR) toggle.

## Personas
- **Discerning consumer**: browses bottles, reads notes, completes Razorpay-secured checkout.
- **Press / concierge**: uses contact form (Resend) to inquire.

## Next Tasks
1. Configure Razorpay webhook + webhook secret for async confirmation reliability.
2. Wire order confirmation email via Resend on successful payment.
3. Replace placeholder photography with original brand assets.
