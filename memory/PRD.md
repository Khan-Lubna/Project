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
- 6 pages: Home (cinematic hero, OURA/VELOURA split, pronunciation banner, story teaser, IG grid), Fragrances index, Product (OURA dark + VELOURA light themes with notes pyramid), Our Story (pull-quote), Contact (Resend integration), Cart (mock checkout flow with order confirmation).
- Sticky centered-logo nav with cart badge; gold/black sharp-corner buttons; fade-in scroll animations.
- Backend product catalog, mock checkout persisting orders to MongoDB, contact form persisting submissions and (when key set) sending Resend emails.
- 100% backend (8/8) and 100% frontend (12/12) tests passing.

## P0 / P1 / P2 Backlog
- **P0**: Provide RESEND_API_KEY in `/app/backend/.env` to activate live email sending.
- **P1**: Real Stripe integration for production checkout.
- **P1**: Domain-verified Resend sender (`hello@mossero.in`) once `www.mossero.in` is verified in Resend dashboard.
- **P2**: Newsletter subscription (capture email).
- **P2**: Admin/CMS for editing copy & product imagery.
- **P2**: Multilingual (EN/FR) toggle.

## Next Tasks
1. Add Resend API key + verify domain.
2. Wire real payment provider (Stripe).
3. Replace temporary Unsplash imagery with custom product photography (the VELOURA Unsplash shot currently shows a faint third-party label that should be swapped).
