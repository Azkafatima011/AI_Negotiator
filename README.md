# AI Negotiator

**Autonomous B2B Wholesale Negotiation Platform**

An AI-powered platform where autonomous buyer and seller agents negotiate price, quantity, delivery, and payment terms for B2B wholesale commodity deals. Built for the Bano Qabil Hackathon.

## Features

- **Autonomous AI Negotiation** - Buyer and seller agents negotiate using configurable strategies (Stubborn, Balanced, Conceding) with deterministic concession curves
- **Multi-Round Negotiation** - Configurable max rounds with convergence detection and price charting
- **Two-Party Approval Flow** - Every deal (single or batch) requires buyer approval, then a unique token link is shared with the seller for final acceptance
- **Seller Response Page** - Token-authenticated public page where sellers accept or decline deals without logging in
- **Link Sharing via WhatsApp** - Copy the approval link or open WhatsApp Web with the message pre-filled (wa.me deep link) — you send it yourself, no API keys needed
- **Mandi Rate Comparison** - Real-time market rate lookup for 8 Pakistani commodities (PKR/kg) with visual comparison
- **Contract Generation** - SHA-256 hash-chained contracts auto-generated upon mutual approval
- **Immutable Audit Trail** - Every negotiation step recorded with cryptographic hash chaining
- **Batch Negotiations** - Negotiate with up to 10 suppliers in parallel; results ranked by price, you approve the winner, and that seller confirms via the same approval link
- **Dashboard** - Real-time stats, status badges, negotiation timeline, and price charts

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, SQLite |
| Frontend | Vanilla JS SPA, Chart.js |
| AI | OpenAI-compatible API (Alibaba Qwen) with deterministic fallback |
| Auth | JWT (python-jose + passlib/bcrypt) |
| Security | Pydantic v2 schema validation (LLM never trusted for financial boundaries) |

## Project Structure

```
backend/
  app/
    main.py              # FastAPI entry point
    api/                 # API endpoints (negotiations, contracts, suppliers, batches, whatsapp)
    agents/              # AI buyer/seller agents, prompts, schemas
    database/            # SQLAlchemy models, DB setup
    negotiation/         # Engine, rules, scoring, state machine
    security/            # JWT auth
    integrations/        # LLM integration (Model Studio / Qwen)
    config.py            # Settings
  requirements.txt

frontend/
  index.html             # Main SPA dashboard
  seller-respond.html    # Standalone seller approval page
  js/
    api.js               # API client with JWT handling
    dashboard.js         # UI controller (all views, modals, flows)
  css/
    main.css             # Dashboard styles

launch.bat               # One-click launcher for Windows
```

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Launch

**Option 1 - Double-click:**
```
launch.bat
```

**Option 2 - Terminal:**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open **http://localhost:8000**

### First Use
1. Register an account (Name, Email, Password, Company)
2. Click **+ New Negotiation**
3. Select a commodity, set quantity, price range, and approval mode
4. Launch the AI negotiation and watch agents negotiate in real-time
5. Approve the deal (buyer side) and share the seller approval link

## Negotiation Flow

```
CREATED -> INITIALIZED -> BUYER_TURN <-> SELLER_TURN -> CHECK_CONVERGENCE
    -> HUMAN_APPROVAL (buyer) -> SELLER_APPROVAL (seller via unique link) -> AGREED
    -> Contract generated with SHA-256 hash chain
```

Rejection at any approval step -> WALKAWAY (negotiation terminated).

### Batch Negotiation Flow

Batch negotiations run the same two-party approval pipeline - no deal is final without both humans:

```
Launch batch (2-10 sellers)
    -> AI negotiates with every seller in parallel
    -> All converged deals pause at HUMAN_APPROVAL, ranked by lowest price
    -> Buyer approves the winning deal (Approve Deal button)
    -> Unique approval link is generated for that seller -> SELLER_APPROVAL
    -> Buyer shares the link (Copy button or WhatsApp Web pre-filled message)
    -> Seller accepts on their phone (no login needed) -> AGREED + contract
```

If the winning seller declines, the buyer can approve another seller's deal from the ranked list.

## API Docs

Once running, visit **http://localhost:8000/docs** for the interactive Swagger UI.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` (or leave defaults - the app runs with zero configuration):

```
DATABASE_URL=sqlite:///./negotiation.db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Optional: Alibaba Qwen (falls back to deterministic agents when empty)
ALIBABA_MODEL_STUDIO_API_KEY=

# Optional: WhatsApp Business Platform Cloud API for deal-agreement notifications
# (falls back to wa.me deep links when empty - no setup needed)
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_WEBHOOK_VERIFY_TOKEN=
```

**Seller approval links never require the WhatsApp API** - the WhatsApp button simply opens WhatsApp Web (wa.me) with the message pre-filled, and you press Send yourself.

## License

Built for the Bano Qabil Hackathon.
