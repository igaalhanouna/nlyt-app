from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

load_dotenv()

from routers import auth, workspaces, appointments, participants, contracts, calendar_routes, disputes, admin, webhooks, debug, invitations, user_settings, charity_associations, attendance_routes
from scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(title="NLYT API", version="1.0.0", lifespan=lifespan)

CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ['*'] else ['*'],
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
app.include_router(disputes.router, prefix="/api/disputes", tags=["Disputes"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(debug.router, prefix="/api/debug", tags=["Debug"])
app.include_router(invitations.router, prefix="/api/invitations", tags=["Invitations"])
app.include_router(user_settings.router, prefix="/api/user-settings", tags=["User Settings"])
app.include_router(charity_associations.router, prefix="/api/charity-associations", tags=["Charity Associations"])
app.include_router(attendance_routes.router, prefix="/api/attendance", tags=["Attendance"])

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
