"""
FastAPI routes for the Claude Agent API
"""

import uuid
from datetime import datetime
from fastapi import HTTPException

from models import ChatRequest, ChatResponse, SessionStatus
from config import sessions, ws_urls
from agent import run_agent_in_sandbox


async def root():
    """Health check endpoint"""
    return {
        "service": "Claude Agent API",
        "status": "running",
        "version": "1.0.0"
    }


async def chat(request: ChatRequest) -> ChatResponse:
    """
    Handle chat requests - create new sessions or add messages to existing ones
    """
    session_id = request.session_id or str(uuid.uuid4())
    print(f"[API] POST /api/chat - session_id: {session_id}")
    print(f"[API] Message: {request.message[:100]}..." if len(request.message) > 100 else f"[API] Message: {request.message}")
    
    is_new_session = not sessions.contains(session_id)
    print(f"[API] New session: {is_new_session}")
    
    # Check if session exists and is running - return it so frontend can use WebSocket
    if not is_new_session:
        existing_session = sessions[session_id]
        print(f"[API] Existing session {session_id} found (status: {existing_session.get('status')})")
        
        # Add message to session history for tracking
        existing_session["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        existing_session["last_activity"] = datetime.utcnow().isoformat()
        sessions[session_id] = existing_session
        
        print(f"[API] Message added to session history. Frontend should send via WebSocket.")
        
        return ChatResponse(
            session_id=session_id,
            message="Send this message via WebSocket to the running sandbox",
            status=existing_session["status"],
            sandbox_id=existing_session.get("sandbox_id"),
            websocket_url=ws_urls.get(session_id) or existing_session.get("websocket_url"),
            dev_url=existing_session.get("dev_url")
        )
    
    if is_new_session:
        print(f"[API] Creating new session {session_id}")
        sessions[session_id] = {
            "session_id": session_id,
            "status": "initializing",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "messages": [],
            "sandbox_id": None,
            "websocket_url": None,
            "dev_url": None
        }
        
        try:
            print(f"[API] Spawning sandbox for session {session_id}")
            call = run_agent_in_sandbox.spawn(
                session_id=session_id,
                prompt=request.message
            )
            
            print(f"[API] Sandbox spawned with ID: {call.object_id}")

            new_session_info = {
                "session_id": session_id,
                "status": "running",
                "sandbox_id": call.object_id,
                "websocket_url": ws_urls.get(session_id),
                "dev_url": None,
                "created_at": sessions[session_id]["created_at"],
                "last_activity": datetime.utcnow().isoformat(),
                "messages": sessions[session_id]["messages"]
            }
            sessions[session_id] = new_session_info
            
            print(f"[API] Session {session_id} started successfully")
            return ChatResponse(
                session_id=session_id,
                message="Building your website...",
                status="running",
                sandbox_id=call.object_id,
                websocket_url=ws_urls.get(session_id),
                dev_url=None
            )
            
        except Exception as e:
            print(f"[API] ERROR starting session {session_id}: {type(e).__name__}: {e}")
            sessions[session_id]["status"] = "error"
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        print(f"[API] Using existing session {session_id}")
        session = sessions[session_id]
        session["last_activity"] = datetime.utcnow().isoformat()
        session["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        print(f"[API] Added message to session {session_id} (status: {session['status']})")
        
        return ChatResponse(
            session_id=session_id,
            message="Message added to existing session",
            status=session["status"],
            sandbox_id=session["sandbox_id"],
            websocket_url=session["websocket_url"],
            dev_url=session.get("dev_url")
        )


async def get_session(session_id: str) -> SessionStatus:
    """
    Get status and details of a specific session
    """
    print(f"[API] GET /api/sessions/{session_id}")
    if session_id not in sessions:
        print(f"[API] Session {session_id} not found")
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    websocket_url = ws_urls.get(session_id) or session.get("websocket_url")
    if websocket_url and session.get("websocket_url") != websocket_url:
        session["websocket_url"] = websocket_url
        sessions[session_id] = session
    
    print(f"[API] Returning session {session_id} (status: {session['status']}, ws_url: {websocket_url is not None})")
    return SessionStatus(
        session_id=session_id,
        status=session["status"],
        sandbox_id=session.get("sandbox_id"),
        created_at=session["created_at"],
        last_activity=session["last_activity"],
        websocket_url=websocket_url,
        dev_url=session.get("dev_url")
    )


async def list_sessions():
    """
    List all active sessions
    """
    print("[API] GET /api/sessions")
    session_list = []
    for session_id, session in sessions.items():
        websocket_url = ws_urls.get(session_id) or session.get("websocket_url")
        if websocket_url:
            session["websocket_url"] = websocket_url
        session_list.append(session)
    
    session_count = len(session_list)
    print(f"[API] Returning {session_count} sessions")
    return {
        "sessions": session_list,
        "total": session_count
    }


async def delete_session(session_id: str):
    """
    Delete a session
    """
    print(f"[API] DELETE /api/sessions/{session_id}")
    if session_id not in sessions:
        print(f"[API] Session {session_id} not found")
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    print(f"[API] Session {session_id} deleted")

    return {"message": "Session deleted", "session_id": session_id}

