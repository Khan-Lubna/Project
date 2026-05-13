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
- 6 pages: Home, Fragrances, Product (OURA dark + VELOURA cream), Our Story (pull-quote), Contact, Cart with mock checkout & confirmation.
- Sticky centered-logo nav with live cart badge; gold/black sharp-corner buttons; fade-in scroll animations.
- Backend: product catalog, mock checkout (orders → Mongo), contact endpoint (submissions → Mongo).
- **Resend email LIVE** — `hello@mossero.in` verified sender → `mossero.in@gmail.com` recipient, end-to-end delivery confirmed.
- 100% backend (8/8) and 100% frontend (12/12) tests passing.

## P1 / P2 Backlog
- **P1**: Real Stripe (or alt PSP) integration for production checkout — currently mock.
- **P1**: Replace placeholder Unsplash imagery with original MOSSERO product photography (one VELOURA shot carries a faint third-party label).
- **P2**: Newsletter / waitlist capture on Fragrances page.
- **P2**: Admin/CMS for editing copy & product imagery.
- **P2**: Multilingual (EN/FR) toggle.

## Next Tasks
1. Wire payment provider (Stripe).
2. Swap in original product photography.
3. Add waitlist / early-access capture.
