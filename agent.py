"""
Claude Agent integration for running agent in Modal sandbox
"""

import os
import time
import asyncio
import threading
import queue
import tempfile
import glob
import subprocess
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import modal

from config import app, agent_image, sessions, ws_urls
from dev_server import DevServerManager

def send_event_factory(session_id: str, event_queue: queue.Queue):
    """Factory function to create a send_event function for a specific session"""
    def send_event(event_type: str, data: Optional[dict] = None):
        event = {
            "session_id": session_id,
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        event_queue.put(event)
        print(f"[Sandbox:{session_id}] Queued event '{event_type}' (queue size: {event_queue.qsize()})")
    return send_event


def setup_websocket_server(session_id: str, event_queue: queue.Queue):
    """Setup WebSocket server for real-time event streaming"""
    websocket_clients = []
    websocket_lock = threading.Lock()
    
    ws_app = FastAPI()
    
    @ws_app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "session_id": session_id,
            "connected_clients": len(websocket_clients),
            "queued_events": event_queue.qsize()
        }
    
    @ws_app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        client_id = id(websocket)
        await websocket.accept()
        print(f"[Sandbox:{session_id}] WebSocket client {client_id} connected (total clients: {len(websocket_clients) + 1})")
        
        with websocket_lock:
            websocket_clients.append(websocket)
        
        try:
            await websocket.send_json({
                "event": "connected",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "client_id": client_id
            })
            
            async def send_queued_events():
                while True:
                    try:
                        event = event_queue.get_nowait()
                        await websocket.send_json(event)
                        print(f"[Sandbox:{session_id}] Sent event '{event['event']}' to client")
                    except queue.Empty:
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        print(f"[Sandbox:{session_id}] Error sending event: {type(e).__name__}: {e}")
                        break
            
            send_task = asyncio.create_task(send_queued_events())
            
            try:
                while True:
                    await websocket.receive_text()
            finally:
                send_task.cancel()
                
        except WebSocketDisconnect:
            print(f"[Sandbox:{session_id}] WebSocket client {client_id} disconnected (remaining clients: {len(websocket_clients) - 1})")
        except Exception as e:
            print(f"[Sandbox:{session_id}] WebSocket client {client_id} error: {type(e).__name__}: {e}")
        finally:
            with websocket_lock:
                if websocket in websocket_clients:
                    websocket_clients.remove(websocket)
            print(f"[Sandbox:{session_id}] WebSocket client {client_id} cleaned up")
    
    def run_websocket_server():
        print(f"[Sandbox:{session_id}] Starting WebSocket server on port 8080")
        uvicorn.run(ws_app, host="0.0.0.0", port=8080, log_level="error")
    
    return run_websocket_server


def setup_workspace(session_id: str) -> str:
    """Create and configure workspace directory"""
    workspace = tempfile.mkdtemp(prefix=f"session-{session_id}-", dir="/tmp")
    print(f"[Sandbox:{session_id}] Workspace created at {workspace}")
    
    # Set permissions on workspace directory so claudeuser can access it
    try:
        os.chmod(workspace, 0o755)  # rwxr-xr-x - everyone can read and execute
        print(f"[Sandbox:{session_id}] Set permissions on workspace directory")
    except Exception as e:
        print(f"[Sandbox:{session_id}] Warning: Could not set workspace dir permissions: {e}")
    
    return workspace


def verify_workspace_files(session_id: str, workspace: str):
    """Verify files were created and fix permissions"""
    workspace_files = glob.glob(f"{workspace}/*")
    print(f"[Sandbox:{session_id}] Workspace verification: {len(workspace_files)} files created")
    
    # Check for index.html specifically
    index_path = os.path.join(workspace, "index.html")
    if os.path.exists(index_path):
        file_size = os.path.getsize(index_path)
        
        # Check current permissions
        file_stat = os.stat(index_path)
        file_mode = oct(file_stat.st_mode)[-3:]
        print(f"[Sandbox:{session_id}] ✓ index.html exists ({file_size} bytes, permissions: {file_mode})")
        
        # Fix permissions to ensure HTTP server can read it
        try:
            os.chmod(index_path, 0o644)  # rw-r--r--
            print(f"[Sandbox:{session_id}] Set read permissions on index.html (644)")
        except Exception as e:
            print(f"[Sandbox:{session_id}] Could not set file permissions: {e}")
        
        # Read first few lines to verify content
        try:
            with open(index_path, 'r') as f:
                first_line = f.readline().strip()
                print(f"[Sandbox:{session_id}] First line: {first_line[:100]}")
        except Exception as e:
            print(f"[Sandbox:{session_id}] Could not read index.html: {e}")
    else:
        print(f"[Sandbox:{session_id}] ✗ WARNING: index.html not found!")
        print(f"[Sandbox:{session_id}] Files in workspace:")
        for file in workspace_files[:10]:
            print(f"[Sandbox:{session_id}]   - {os.path.basename(file)}")
    
    # Fix permissions on workspace directory and files
    try:
        # Check workspace directory permissions first
        dir_stat = os.stat(workspace)
        dir_mode = oct(dir_stat.st_mode)[-3:]
        print(f"[Sandbox:{session_id}] Workspace dir permissions before fix: {dir_mode}")
        
        # Need both read and execute on directories, read on files
        os.system(f"chmod -R a+rX {workspace}")  # Capital X = execute only on directories
        
        # Verify after
        dir_stat = os.stat(workspace)
        dir_mode = oct(dir_stat.st_mode)[-3:]
        print(f"[Sandbox:{session_id}] Workspace dir permissions after fix: {dir_mode}")
    except Exception as e:
        print(f"[Sandbox:{session_id}] Could not set workspace permissions: {e}")


async def run_claude_agent(session_id: str, prompt: str, workspace: str, send_event):
    """Run the Claude Agent SDK and process messages"""
    from claude_agent_sdk import (
        ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock,
        ThinkingBlock, ToolUseBlock, ToolResultBlock, ResultMessage
    )
    
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        error_msg = "ANTHROPIC_API_KEY secret is missing"
        print(f"[Sandbox:{session_id}] ERROR: {error_msg}")
        raise ValueError(error_msg)
    
    print(f"[Sandbox:{session_id}] ANTHROPIC_API_KEY found")
    
    # Create a simple prompt for building websites
    full_prompt = f"""Build a {prompt}.

Create a single index.html file with:
- Embedded CSS in a <style> tag
- Embedded JavaScript if needed in a <script> tag
- Modern, beautiful design
- Responsive layout
- Clean, professional look

The file must be saved as index.html in the current directory."""
    
    print(f"[Sandbox:{session_id}] Initializing Claude Agent SDK client...")
    
    # Configure Claude Agent SDK options
    sdk_options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",  # Auto-accepts file edits
        cwd=workspace,
        env={"ANTHROPIC_API_KEY": anthropic_api_key}
    )
    
    event_count = 0
    claude_session_id = None
    exit_code = 0
    
    print(f"[Sandbox:{session_id}] Connecting to Claude Agent SDK...")
    async with ClaudeSDKClient(options=sdk_options) as client:
        print(f"[Sandbox:{session_id}] Sending prompt to Claude...")
        await client.query(full_prompt)
        
        print(f"[Sandbox:{session_id}] Streaming Claude SDK messages...")
        async for message in client.receive_messages():
            event_count += 1
            
            # Handle different message types
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        send_event("claude_text", {
                            "text": block.text,
                            "event_number": event_count
                        })
                        print(f"[Sandbox:{session_id}] Text: {block.text[:100]}...")
                    
                    elif isinstance(block, ThinkingBlock):
                        send_event("claude_thinking", {
                            "thinking": block.thinking,
                            "event_number": event_count
                        })
                    
                    elif isinstance(block, ToolUseBlock):
                        send_event("claude_tool_use", {
                            "tool": block.name,
                            "input": block.input,
                            "tool_use_id": block.id,
                            "event_number": event_count
                        })
                        print(f"[Sandbox:{session_id}] Tool use: {block.name}")
                    
                    elif isinstance(block, ToolResultBlock):
                        result_text = ""
                        if isinstance(block.content, str):
                            result_text = block.content
                        elif isinstance(block.content, list):
                            result_text = str(block.content)
                        
                        send_event("claude_tool_result", {
                            "tool_use_id": block.tool_use_id,
                            "result": result_text,
                            "is_error": block.is_error or False,
                            "event_number": event_count
                        })
                        print(f"[Sandbox:{session_id}] Tool result for {block.tool_use_id}")
            
            elif isinstance(message, ResultMessage):
                claude_session_id = message.session_id
                exit_code = 1 if message.is_error else 0
                
                send_event("claude_session_end", {
                    "session_id": claude_session_id,
                    "duration_ms": message.duration_ms,
                    "num_turns": message.num_turns,
                    "total_cost_usd": message.total_cost_usd,
                    "is_error": message.is_error,
                    "event_number": event_count
                })
                
                print(f"[Sandbox:{session_id}] Session ended: {claude_session_id} (turns: {message.num_turns}, cost: ${message.total_cost_usd})")
                break
            
            if event_count % 50 == 0:
                print(f"[Sandbox:{session_id}] Processed {event_count} SDK messages...")
    
    print(f"[Sandbox:{session_id}] Claude SDK completed ({event_count} messages processed)")
    
    return {
        "event_count": event_count,
        "claude_session_id": claude_session_id,
        "exit_code": exit_code
    }


@app.function(
    image=agent_image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=3600
)
async def run_agent_in_sandbox(session_id: str, prompt: str):
    """Main function to run Claude Agent in Modal sandbox with WebSocket streaming"""
    
    print(f"[Sandbox:{session_id}] Starting agent in sandbox")
    print(f"[Sandbox:{session_id}] Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"[Sandbox:{session_id}] Prompt: {prompt}")
    
    # Setup event queue and send_event function
    event_queue = queue.Queue()
    send_event = send_event_factory(session_id, event_queue)
    
    # Setup workspace
    workspace = setup_workspace(session_id)
    
    results = {
        "status": "started",
        "session_id": session_id,
        "workspace": workspace,
        "events": [],
        "websocket_url": None
    }
    
    # Start WebSocket server
    run_websocket_server = setup_websocket_server(session_id, event_queue)
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()
    time.sleep(2)
    print(f"[Sandbox:{session_id}] WebSocket server started")
    
    with modal.forward(3000) as dev_tunnel, modal.forward(8080) as ws_tunnel:
        dev_tunnel_url = dev_tunnel.url
        ws_tunnel_url = ws_tunnel.url.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws'
        
        # Check if URL is changing (shouldn't happen for same session)
        existing_ws_url = ws_urls.get(session_id)
        if existing_ws_url and existing_ws_url != ws_tunnel_url:
            print(f"[Sandbox:{session_id}] WARNING: WebSocket URL changed!")
            print(f"[Sandbox:{session_id}]   Old: {existing_ws_url}")
            print(f"[Sandbox:{session_id}]   New: {ws_tunnel_url}")
        
        ws_urls[session_id] = ws_tunnel_url
        
        print(f"[Sandbox:{session_id}] Modal dev tunnel created: {dev_tunnel_url}")
        print(f"[Sandbox:{session_id}] Modal websocket tunnel created: {ws_tunnel_url}")
        
        # Update session data with WebSocket URL
        if sessions.contains(session_id):
            session_data = sessions[session_id]
            session_data["websocket_url"] = ws_tunnel_url
            session_data["last_activity"] = datetime.utcnow().isoformat()
            sessions[session_id] = session_data
            print(f"[Sandbox:{session_id}] Updated session with WebSocket URL")
        
        # Send WebSocket URL as an event
        send_event("websocket_ready", {
            "websocket_url": ws_tunnel_url,
            "session_id": session_id
        })
        time.sleep(1)
        
        try:
            event_data = {
                "type": "agent_coding_started",
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": prompt
            }
            results["events"].append(event_data)
            send_event("coding_start", {"prompt": prompt, "work_dir": workspace})
            
            # Run Claude Agent
            try:
                agent_results = await run_claude_agent(session_id, prompt, workspace, send_event)
                event_count = agent_results["event_count"]
                claude_session_id = agent_results["claude_session_id"]
                exit_code = agent_results["exit_code"]
                
            except Exception as sdk_error:
                print(f"[Sandbox:{session_id}] Claude SDK error: {type(sdk_error).__name__}: {sdk_error}")
                import traceback
                traceback.print_exc()
                exit_code = 1
                event_count = 0
                claude_session_id = None
            
            event_data = {
                "type": "agent_coding_stopped",
                "timestamp": datetime.utcnow().isoformat(),
                "exit_code": exit_code
            }
            results["events"].append(event_data)
            send_event("coding_end", {"exit_code": exit_code})
            
            results["event_count"] = event_count
            results["exit_code"] = exit_code
            
            if claude_session_id:
                results["claude_session_id"] = claude_session_id
                print(f"[Sandbox:{session_id}] Claude session ID: {claude_session_id}")
                send_event("session_complete", {"claude_session_id": claude_session_id})
            else:
                print(f"[Sandbox:{session_id}] No session_end event found")
            
            results["status"] = "completed"
            print(f"[Sandbox:{session_id}] Agent completed successfully")
            
            # Verify files and fix permissions
            verify_workspace_files(session_id, workspace)
            
            # Start development server
            print(f"[Sandbox:{session_id}] Starting dev server after Claude completes...")
            dev_server = DevServerManager(
                session_id=session_id,
                work_dir=workspace,
                dev_tunnel_url=dev_tunnel_url,
                ws_tunnel_url=ws_tunnel_url,
                send_event=send_event
            )
            dev_server.process = dev_server.start()
            
            if dev_server.process:
                send_event("dev_server_started", {
                    "tunnel_url": dev_tunnel_url, 
                    "websocket_url": ws_tunnel_url
                })
                print(f"[Sandbox:{session_id}] Dev server started at {dev_tunnel_url}")
                dev_server.start_monitor()
            else:
                send_event("dev_server_failed", {
                    "error": "Failed to start server",
                    "tunnel_url": dev_tunnel_url
                })
            
            # Update session status
            if sessions.contains(session_id):
                session_data = sessions[session_id]
                session_data["status"] = "completed"
                session_data["last_activity"] = datetime.utcnow().isoformat()
                session_data["dev_url"] = dev_tunnel_url
                if ws_urls.contains(session_id):
                    session_data["websocket_url"] = ws_urls[session_id]
                sessions[session_id] = session_data
                print(f"[Sandbox:{session_id}] Updated session status to completed")
            
            send_event("agent_complete", {"status": "completed"})
            
            # Keep tunnels alive
            print(f"[Sandbox:{session_id}] Keeping tunnels alive for 720 seconds")
            start_time = time.time()
            while True:
                time.sleep(1)
                if time.time() - start_time > 720:
                    print(f"[Sandbox:{session_id}] 720 seconds elapsed, closing tunnels")
                    break
            print(f"[Sandbox:{session_id}] Tunnels closed")
            
        except subprocess.TimeoutExpired:
            print(f"[Sandbox:{session_id}] ERROR: Execution timeout")
            results["status"] = "timeout"
            
            if sessions.contains(session_id):
                session_data = sessions[session_id]
                session_data["status"] = "timeout"
                session_data["last_activity"] = datetime.utcnow().isoformat()
                if ws_urls.contains(session_id):
                    session_data["websocket_url"] = ws_urls[session_id]
                    session_data["dev_url"] = dev_tunnel_url
                sessions[session_id] = session_data
            
            event_data = {
                "type": "agent_error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Execution timeout"
            }
            results["events"].append(event_data)
            send_event("agent_error", {"error": "Execution timeout", "error_type": "timeout"})
            
        except Exception as e:
            print(f"[Sandbox:{session_id}] ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results["status"] = "error"
            results["error"] = str(e)
            
            if sessions.contains(session_id):
                session_data = sessions[session_id]
                session_data["status"] = "error"
                session_data["last_activity"] = datetime.utcnow().isoformat()
                if ws_urls.contains(session_id):
                    session_data["websocket_url"] = ws_urls[session_id]
                    session_data["dev_url"] = dev_tunnel_url
                sessions[session_id] = session_data
            
            event_data = {
                "type": "agent_error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
            results["events"].append(event_data)
            send_event("agent_error", {"error": str(e), "error_type": type(e).__name__})
        
        print(f"[Sandbox:{session_id}] Returning results with status: {results['status']}")
        return results

