# AI Negotiator

**Autonomous B2B Wholesale Negotiation Platform**

An AI-powered platform where autonomous buyer and seller agents negotiate price, quantity, delivery, and payment terms for B2B wholesale commodity deals. Built for the Bano Qabil Hackathon.

## Features

- **Autonomous AI Negotiation** - Buyer and seller agents negotiate using configurable strategies (Stubborn, Balanced, Conceding) with deterministic concession curves
- **Multi-Round Negotiation** - Configurable max rounds with convergence detection and price charting
- **Two-Party Approval Flow** - Buyer approves the deal, then a unique link is sent to the seller (mock WhatsApp/SMS) for final acceptance
- **Seller Response Page** - Token-authenticated public page where sellers accept or decline deals without logging in
- **Mandi Rate Comparison** - Real-time market rate lookup for 8 Pakistani commodities (PKR/kg) with visual comparison
- **Contract Generation** - SHA-256 hash-chained contracts auto-generated upon mutual approval
- **Immutable Audit Trail** - Every negotiation step recorded with cryptographic hash chaining
- **Batch Negotiations** - Launch parallel negotiations against multiple suppliers
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
    -> HUMAN_APPROVAL (buyer) -> SELLER_APPROVAL (seller via link) -> AGREED
    -> Contract generated with SHA-256 hash chain
```

Rejection at any approval step -> WALKAWAY (negotiation terminated).

## API Docs

Once running, visit **http://localhost:8000/docs** for the interactive Swagger UI.

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

```
DATABASE_URL=sqlite:///./negotiation.db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
MODEL_STUDIO_API_KEY=          # Optional: Alibaba Qwen API key
```

Without `MODEL_STUDIO_API_KEY`, the system uses deterministic negotiation agents with configurable concession strategies.

## License

Built for the Bano Qabil Hackathon.
