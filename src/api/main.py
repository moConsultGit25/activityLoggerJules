# src/api/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path # To construct paths for templates and static files

# Import API routers
from .v1.routers import ingestion, logs, auth

# Import Frontend routers
from src.frontend.routers import pages as frontend_pages

# Import event handler registration functions
# These ensure that domain events trigger cross-context reactions.
from src.analysis_context.interfaces.event_handlers import register_analysis_event_handlers
from src.activity_log_context.interfaces.event_handlers import register_activity_log_event_handlers

app = FastAPI(
    title="Automated Activity Logger API",
    description="API for ingesting email data, triggering analysis, and logging activities.",
    version="0.1.0"
)

# --- Static Files and Templates Setup ---
# Construct paths relative to this file's location or project root.
# Assuming src/api/main.py, so src/frontend is ../frontend relative to src/api
BASE_DIR = Path(__file__).resolve().parent.parent # This should be src/
STATIC_FILES_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"

app.mount("/static", StaticFiles(directory=STATIC_FILES_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Make templates easily accessible, e.g. via request.state or a dependency
# For now, routers needing it can import it or it can be passed.


# --- Event Handlers Registration ---
@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    Registers domain event handlers to ensure the event-driven architecture is active.
    """
    print("FastAPI application starting up...")
    register_analysis_event_handlers()
    register_activity_log_event_handlers()
    print("Application startup complete: Event handlers registered.")

# Include API routers
app.include_router(ingestion.router, prefix="/api/v1/ingestion", tags=["Ingestion API"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Activity Logs API"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication API"])

# Include Frontend router
# (Mounting it at "/app" to distinguish from API, or can be at root if desired)
app.include_router(frontend_pages.router, prefix="/app", tags=["Frontend Pages"])


# --- Simple Middleware for User State (Example) ---
# This is a very basic example. Real applications might use sessions, more robust token checks.
from jose import jwt, JWTError
from src.auth_context.application.security import JWT_SECRET_KEY, ALGORITHM, decode_access_token
# This middleware needs to be defined before it's added if using @app.middleware("http")

@app.middleware("http")
async def add_user_state_to_request(request: Request, call_next):
    token = request.cookies.get("access_token") # Assuming token is stored in a cookie named "access_token"
    user_authenticated = False
    username = None

    if token:
        payload = decode_access_token(token.split(" ")[1] if " " in token else token) # Handle "Bearer <token>" or just "<token>"
        if payload:
            username = payload.get("sub") # 'sub' usually holds the username
            if username:
                user_authenticated = True # Mark as authenticated if username is found in a valid token

    request.state.user_authenticated = user_authenticated
    request.state.username = username
    request.state.flash_messages = [] # Initialize flash messages list

    response = await call_next(request)
    return response


# --- Root Endpoint ---
# This can be moved to the frontend router later if a dedicated page is made.
@app.get("/", tags=["Root"])
async def root(request: Request): # Add request: Request for template rendering
    """
    Root endpoint, potentially serving a home page or API welcome.
    For now, it can serve a simple HTML response or redirect to a frontend page.
    """
    # Example: Render a home page if one exists, or just return JSON
    # return templates.TemplateResponse("home.html", {"request": request, "title": "Home"})
    # For now, keeping the JSON response for the API root.
    # The frontend specific root ("/") is now handled by frontend_pages.router mounted at "/app".
    # So, this root endpoint for the API itself should ideally not conflict.
    # If frontend_pages.router handles "/", this API root might need a different path or be removed
    # if all root access should go to the frontend's home.
    # For clarity, let's assume API root is still useful for API discoverability.
    return {"message": "Welcome to the Automated Activity Logger (API Root). Visit /docs for API docs or /app for frontend."}


# To run this application (after installing uvicorn and fastapi):
# uvicorn src.api.main:app --reload
# The --reload flag is for development; remove it in production.
# Access the API at http://localhost:8000
# Access OpenAPI docs at http://localhost:8000/docs
# Access ReDoc docs at http://localhost:8000/redoc
