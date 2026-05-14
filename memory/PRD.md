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
- 6 pages + cart success/error states + **Order Tracking** (`/track`) with Shiprocket integration scaffolding
- Sticky centered-logo nav with live cart badge; sharp-corner gold/black CTAs; fade-in animations
- **Resend LIVE**: `hello@mossero.in` → `mossero.in@gmail.com` (delivery confirmed)
- **Soft Concierge Checkout (active)**: `POST /api/checkout/concierge` accepts reservations, persists to `orders` collection with `status=concierge_pending`, and dispatches branded reservation emails to both customer (confirmation) and maison (alert with order details + optional customer note). No payment is taken.
- **Razorpay LIVE wiring** is intact but **NOT exposed in UI** while user changes bank accounts. Backend endpoints `/api/checkout/order` and `/api/checkout/verify` still functional — frontend can be flipped back by reverting `Cart.jsx` to the Razorpay flow.
- **Shiprocket** wired with email/password JWT auth + caching, but PAUSED pending account-level permission resolution (KYC + pickup location setup on Shiprocket dashboard side).
- **Order confirmation emails** (paid path) preserved for when Razorpay is re-enabled.
- **Order tracking** via `POST /api/orders/lookup` (order_id + email, no enumeration leak) — handles paid, concierge_pending, in_transit, delivered, etc.
- Tests: backend 33/33 (iter 5). Two HIGH-priority frontend bugs found and fixed during iter 5.

## P1 / P2 Backlog (when user resumes)
- **P1 (user)**: Finish bank change, then in `Cart.jsx` swap concierge POST back to Razorpay flow (single function change) + re-test.
- **P1 (user)**: Complete Shiprocket KYC + create pickup location (`SHIPROCKET_PICKUP_LOCATION` in `.env` is currently `HOME`).
- **P1**: Rotate Razorpay key + Shiprocket password (both shared via chat).
- **P1**: Replace placeholder Unsplash imagery with original MOSSERO product photography.
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
