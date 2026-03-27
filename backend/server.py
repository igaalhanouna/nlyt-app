from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os

# Allow .env to provide real Stripe key when system env has only the sentinel
if os.environ.get('STRIPE_API_KEY') == 'sk_test_emergent':
    del os.environ['STRIPE_API_KEY']

load_dotenv()

from routers import auth, workspaces, appointments, participants, contracts, calendar_routes, admin, webhooks, debug, invitations, user_settings, charity_associations, attendance_routes, checkin_routes, modification_routes, video_evidence_routes, proof_routes, wallet_routes, connect_routes, impact_routes, external_events_routes, result_cards, financial_routes, declarative_routes, dispute_routes
from scheduler import start_scheduler, stop_scheduler
from rate_limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    # Ensure all database indexes
    from database import ensure_indexes
    ensure_indexes()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(title="NLYT API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──
# Production: restrict to FRONTEND_URL domain only
# Dev/Preview: falls back to '*' if CORS_ORIGINS not set
FRONTEND_URL = os.environ.get('FRONTEND_URL', '').rstrip('/')
CORS_RAW = os.environ.get('CORS_ORIGINS', '')

if CORS_RAW and CORS_RAW != '*':
    CORS_ORIGINS = [o.strip() for o in CORS_RAW.split(',') if o.strip()]
elif FRONTEND_URL:
    CORS_ORIGINS = [FRONTEND_URL]
else:
    CORS_ORIGINS = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["Workspaces"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(participants.router, prefix="/api/participants", tags=["Participants"])
app.include_router(contracts.router, prefix="/api/contracts", tags=["Contracts"])
app.include_router(calendar_routes.router, prefix="/api/calendar", tags=["Calendar"])
app.include_router(declarative_routes.router, prefix="/api/attendance-sheets", tags=["Declarative"])
app.include_router(dispute_routes.router, prefix="/api/disputes", tags=["Disputes"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(debug.router, prefix="/api/debug", tags=["Debug"])
app.include_router(invitations.router, prefix="/api/invitations", tags=["Invitations"])
app.include_router(user_settings.router, prefix="/api/user-settings", tags=["User Settings"])
app.include_router(charity_associations.router, prefix="/api/charity-associations", tags=["Charity Associations"])
app.include_router(attendance_routes.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(checkin_routes.router, prefix="/api/checkin", tags=["Check-in"])
app.include_router(modification_routes.router, prefix="/api/modifications", tags=["Modifications"])
app.include_router(video_evidence_routes.router, prefix="/api/video-evidence", tags=["Video Evidence"])
app.include_router(proof_routes.router, prefix="/api/proof", tags=["Proof Sessions"])
app.include_router(wallet_routes.router, prefix="/api/wallet", tags=["Wallet"])
app.include_router(connect_routes.router, prefix="/api/connect", tags=["Connect"])
app.include_router(impact_routes.router, prefix="/api/impact", tags=["Impact"])
app.include_router(external_events_routes.router, prefix="/api/external-events", tags=["External Events"])
app.include_router(result_cards.router, prefix="/api/result-cards", tags=["Result Cards"])
app.include_router(financial_routes.router, prefix="/api/financial", tags=["Financial"])

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "NLYT API"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne du serveur: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
