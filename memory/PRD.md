# MOSSERO — Product Requirements Document

## Original Problem Statement
Build a Shopify-style e-commerce website for **MOSSERO**, a luxury perfume brand, with a Louis Vuitton-level visual identity and design DNA. Two products: OURA (For Him) and VELOURA (For Her). Brand uses cream/black/gold palette with serif headlines and elegant typography.

User chose: React/FastAPI replica, functional cart with mock checkout, Unsplash imagery, Resend email for contact form, recipient `mossero.in@gmail.com`, domain `www.mossero.in`.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor). Endpoints: `/api/products`, `/api/products/{slug}`, `/api/checkout`, `/api/contact`.
- **Frontend**: React 19 + react-router-dom v7 + TailwindCSS + Cormorant Garamond/Montserrat fonts. Sonner for toasts. LocalStorage cart via React Context.
- **Theme**: cream `#F5F0E8`, gold `#C4A258`, charcoal `#2B2725`, sharp corners only.

## Personas
- **Discerning consumer**: browses bottles, reads notes, completes a refined checkout.
- **Press / concierge**: uses contact form to inquire about the maison.

## Implemented (2026-02-06)
- 6 pages: Home, Fragrances, Product (OURA dark + VELOURA cream), Our Story (pull-quote), Contact, Cart with **real Stripe Checkout** + `/cart/success` confirmation page.
- Sticky centered-logo nav with live cart badge; gold/black sharp-corner buttons; fade-in scroll animations.
- Backend: product catalog, **Stripe Checkout via emergentintegrations** (POST `/api/checkout/session`, GET `/api/checkout/status/{id}`, POST `/api/webhook/stripe`), MongoDB `payment_transactions` + `orders` collections with idempotent finalization.
- **Resend email LIVE** — `hello@mossero.in` verified sender → `mossero.in@gmail.com` recipient.
- **Stripe LIVE (test mode)** — sk_test_emergent. Real Stripe-hosted checkout URLs. Status endpoint gracefully falls back to cached DB state when emergentintegrations lookup raises (known platform quirk); webhook is source of truth.
- Tests: backend 10/10, frontend e2e + error states all pass.

## P1 / P2 Backlog
- **P1**: Production Stripe key + production domain in Stripe dashboard for live payments.
- **P1**: Replace placeholder Unsplash imagery with original MOSSERO product photography.
- **P2**: Newsletter / waitlist capture on Fragrances page.
- **P2**: Order confirmation email via Resend on successful payment.
- **P2**: Admin/CMS for editing copy & product imagery.
- **P2**: Multilingual (EN/FR) toggle.

## Next Tasks
1. Swap in original product photography.
2. Wire post-payment order confirmation email (Resend) on webhook payment_status=paid.
3. Move to live Stripe key when ready to launch.
