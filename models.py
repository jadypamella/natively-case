

from typing import Optional
from pydantic import BaseModel

class ChatResponse(BaseModel):
    session_id: str
    message: str
    status: str
    sandbox_id: Optional[str] = None
    websocket_url: Optional[str] = None
    dev_url: Optional[str] = None

class SessionStatus(BaseModel):
    session_id: str
    status: str
    sandbox_id: Optional[str] = None
    created_at: str
    last_activity: str
    websocket_url: Optional[str] = None
    dev_url: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str