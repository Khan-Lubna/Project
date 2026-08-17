# MOSSERO

A luxury fragrance e-commerce experience built with React and FastAPI.

## Prerequisites

- Node.js >= 18
- Yarn >= 1.22
- Python >= 3.10
- MongoDB running locally on `mongodb://localhost:27017`
- Razorpay, Resend, Shiprocket, and Shopify credentials (for production checkout, emails, shipping, and store sync)

## Project Structure

```
Project/
├── frontend/   # React + Tailwind CSS + CRACO
├── backend/    # FastAPI + MongoDB (Motor)
├── README.md
```

## Environment Variables

### Backend — `backend/.env`

```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
RESEND_API_KEY="<your-resend-key>"
SENDER_EMAIL="hello@mossero.in"
CONTACT_RECIPIENT_EMAIL="mossero.in@gmail.com"
RAZORPAY_KEY_ID="rzp_live_..."
RAZORPAY_KEY_SECRET="..."
RAZORPAY_WEBHOOK_SECRET="..."
SHIPROCKET_EMAIL="..."
SHIPROCKET_PASSWORD="..."
SHIPROCKET_PICKUP_LOCATION="Primary"
SHOPIFY_STORE_URL="..."
SHOPIFY_ACCESS_TOKEN="..."
SHOPIFY_API_VERSION="2024-01"
```

### Frontend — `frontend/.env`

```
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_RAZORPAY_KEY_ID=rzp_live_...
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
```

> **Note:** `.env` files are git-ignored. Copy the example values above and replace with your own credentials.

## Running Locally

### 1. Start MongoDB

Ensure MongoDB is running on the default port.

```powershell
# Windows (if installed as a service)
net start MongoDB
```

### 2. Install Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 3. Start Backend Server

```powershell
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

If `uvicorn` is not installed:

```powershell
pip install uvicorn
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Install Frontend Dependencies

```powershell
cd frontend
yarn install
```

### 5. Start Frontend Dev Server

```powershell
cd frontend
yarn start
```

The app will open at `http://localhost:3000`.

## Deploying Backend (Render)

Build Command:

```powershell
pip install -r requirements.txt
```

Start Command:

```powershell
python server.py
```

Ensure these environment variables are set in your Render dashboard:

- `MONGO_URL`
- `DB_NAME`
- `CORS_ORIGINS`
- `RESEND_API_KEY`
- `SENDER_EMAIL`
- `CONTACT_RECIPIENT_EMAIL`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `SHIPROCKET_EMAIL`
- `SHIPROCKET_PASSWORD`
- `SHIPROCKET_PICKUP_LOCATION`
- `SHOPIFY_STORE_URL`
- `SHOPIFY_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION`

## Available Scripts

| Command | Location | Description |
|---|---|---|
| `yarn start` | `frontend/` | Start React dev server (CRACO) |
| `yarn build` | `frontend/` | Build production bundle |
| `yarn test` | `frontend/` | Run Jest tests |
| `python server.py` | `backend/` | Start FastAPI server (also works on Render) |
| `pytest` | `backend/` | Run backend tests |

## Notes

- Product pricing and catalog are defined in `frontend/src/lib/products.js` and mirrored in `backend/server.py`.
- Shipping is free; COD is not available. Payment is via Razorpay UPI only.
