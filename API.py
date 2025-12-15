"""
Modal API Server for Claude Agent
Simplified version for building websites with live preview
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import modal

from config import app
from models import ChatResponse, SessionStatus
from routes import root, chat, get_session, list_sessions, delete_session

# Create FastAPI web application
web_app = FastAPI(title="Claude Agent API")

# Configure CORS middleware
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register routes
web_app.get("/")(root)
web_app.post("/api/chat", response_model=ChatResponse)(chat)
web_app.get("/api/sessions/{session_id}", response_model=SessionStatus)(get_session)
web_app.get("/api/sessions")(list_sessions)
web_app.delete("/api/sessions/{session_id}")(delete_session)


# Modal ASGI app entry point
@app.function(
    image=modal.Image.debian_slim(python_version="3.12").pip_install(
        "fastapi[standard]",
        "pydantic",
        "websockets"
    ).add_local_python_source("config", "models", "routes", "dev_server", "agent")
)
@modal.asgi_app()
def web():
    """Entry point for Modal deployment"""
    return web_app
