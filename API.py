"""
Modal API Server for Claude Agent
Simplified version for building websites with live preview
"""

import time
import modal
import json
import asyncio
import subprocess
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

app = modal.App("website-builder-api")

agent_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "ca-certificates", "gnupg", "sudo")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs"
    )
    .run_commands("npm install -g pnpm")
    .pip_install_from_requirements("requirements.txt")
    .run_commands(
        "useradd -m -s /bin/bash -u 1000 claudeuser",
        "mkdir -p /home/claudeuser/.local/bin /home/claudeuser/.local/share /home/claudeuser/.cache",
        "chown -R claudeuser:claudeuser /home/claudeuser",
        "chmod -R 755 /home/claudeuser",
        "echo 'claudeuser ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/npm, /usr/sbin/update-ca-certificates' >> /etc/sudoers"
    )
    .env({"PATH": "/home/claudeuser/.local/bin:$PATH", "SHELL": "/bin/bash", "HOME": "/home/claudeuser"})
    # Install Claude Code CLI which is required by the Python SDK
    .run_commands(
        "su - claudeuser -c 'curl -fsSL https://claude.ai/install.sh | bash'"
    )
)

ws_urls = modal.Dict.from_name("ws_urls", create_if_missing=True)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


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


sessions: modal.Dict = modal.Dict.from_name("sessions", create_if_missing=True)


class DevServerManager:
    def __init__(self, session_id: str, work_dir: str, dev_tunnel_url: str, ws_tunnel_url: str, send_event):
        self.session_id = session_id
        self.work_dir = work_dir
        self.dev_tunnel_url = dev_tunnel_url
        self.ws_tunnel_url = ws_tunnel_url
        self.send_event = send_event
        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.monitor_running = threading.Event()
        self.monitor_running.set()
    
    def check_health(self, timeout=5, verbose=False):
        """Health check - verify server is responding"""
        try:
            # Check if server responds at root path
            request_obj = urlopen(f"http://localhost:3000/", timeout=timeout)
            response_code = request_obj.getcode()
            
            if verbose:
                print(f"[Sandbox:{self.session_id}] Health check: server responded with {response_code}")
            
            # Server is healthy if it responds at all
            return True
            
        except HTTPError as e:
            # HTTPError means server responded with an error code - server IS running!
            if verbose:
                print(f"[Sandbox:{self.session_id}] Health check: server responded with {e.code}")
            return True
            
        except URLError as e:
            # URLError (connection refused) means server isn't running yet
            if verbose:
                print(f"[Sandbox:{self.session_id}] Health check: connection refused (server not ready)")
            return False
            
        except Exception as e:
            if verbose:
                print(f"[Sandbox:{self.session_id}] Health check exception: {type(e).__name__}: {e}")
            return False
    
    def start(self):
        self.send_event("dev_server_starting", {})
        print(f"[Sandbox:{self.session_id}] Starting simple HTTP server in {self.work_dir}")
        
        # Check what files exist in the workspace
        import os
        import glob
        files = glob.glob(f"{self.work_dir}/*")
        print(f"[Sandbox:{self.session_id}] Files in workspace: {len(files)} files")
        for file in files[:10]:  # Show first 10 files
            file_name = os.path.basename(file)
            file_size = os.path.getsize(file) if os.path.isfile(file) else 0
            print(f"[Sandbox:{self.session_id}]   - {file_name} ({file_size} bytes)")
        
        # Check specifically for index.html
        index_path = os.path.join(self.work_dir, "index.html")
        if os.path.exists(index_path):
            file_size = os.path.getsize(index_path)
            print(f"[Sandbox:{self.session_id}] ✓ index.html found ({file_size} bytes)")
        else:
            print(f"[Sandbox:{self.session_id}] ✗ index.html NOT found in {self.work_dir}")
            print(f"[Sandbox:{self.session_id}] WARNING: Starting server anyway, but preview may not work")
        
        log_path = f"/tmp/dev_server_{self.session_id}.log"
        try:
            import pwd
            claude_user = pwd.getpwnam('claudeuser')
            
            def demote():
                os.setgid(claude_user.pw_gid)
                os.setuid(claude_user.pw_uid)
                os.environ['HOME'] = claude_user.pw_dir
                os.environ['USER'] = 'claudeuser'
                os.environ['LOGNAME'] = 'claudeuser'
            
            # Start a simple Python HTTP server
            with open(log_path, "w") as log_file:
                process = subprocess.Popen(
                    ["python3", "-m", "http.server", "3000"],
                    cwd=self.work_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    preexec_fn=demote
                )
            
            print(f"[Sandbox:{self.session_id}] HTTP server process started as claudeuser (PID: {process.pid}), log: {log_path}")
            
            for attempt in range(30):
                if process.poll() is not None:
                    exit_code = process.returncode
                    error = f"Process exited with code {exit_code}"
                    print(f"[Sandbox:{self.session_id}] {error}")
                    
                    try:
                        with open(log_path, "r") as f:
                            log_content = f.read()
                            if log_content:
                                print(f"[Sandbox:{self.session_id}] Last 20 lines of log:")
                                for line in log_content.split('\n')[-20:]:
                                    if line.strip():
                                        print(f"[Sandbox:{self.session_id}]   {line}")
                    except Exception:
                        pass
                    
                    self.send_event("dev_server_failed", {"error": error})
                    return None
                
                verbose = (attempt == 0 or attempt % 10 == 9)
                if self.check_health(timeout=2, verbose=verbose):
                    print(f"[Sandbox:{self.session_id}] Dev server health check passed (attempt {attempt + 1}/30)")
                    return process
                
                if attempt % 5 == 4:
                    print(f"[Sandbox:{self.session_id}] Still waiting for dev server... (attempt {attempt + 1}/30)")
                
                time.sleep(1)
            
            print(f"[Sandbox:{self.session_id}] Health check timeout after 30 seconds")
            
            try:
                with open(log_path, "r") as f:
                    log_content = f.read()
                    if log_content:
                        print(f"[Sandbox:{self.session_id}] Last 30 lines of dev server log:")
                        for line in log_content.split('\n')[-30:]:
                            if line.strip():
                                print(f"[Sandbox:{self.session_id}]   {line}")
                    else:
                        print(f"[Sandbox:{self.session_id}] Log file is empty")
            except Exception as e:
                print(f"[Sandbox:{self.session_id}] Could not read log file: {e}")
            
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            error = "Health check timeout after 30 seconds"
            self.send_event("dev_server_failed", {"error": error})
            return None
            
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(f"[Sandbox:{self.session_id}] Error starting dev server: {error}")
            import traceback
            traceback.print_exc()
            self.send_event("dev_server_failed", {"error": error})
            return None
    
    def _stop_process(self, process):
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                print(f"[Sandbox:{self.session_id}] Error stopping process: {e}")
    
    def _monitor_loop(self):
        while self.monitor_running.is_set():
            time.sleep(10)
            
            with self.lock:
                process = self.process
                is_unhealthy = (
                    process is None or 
                    process.poll() is not None or 
                    not self.check_health(timeout=5)
                )
                
                if is_unhealthy and self.monitor_running.is_set():
                    if process and process.poll() is None:
                        self.send_event("dev_server_error", {"error": "Server became unresponsive"})
                        print(f"[Sandbox:{self.session_id}] Dev server unhealthy, restarting...")
                        self._stop_process(process)
                    
                    self.send_event("dev_server_restarting", {})
                    new_process = self.start()
                    
                    if new_process:
                        self.process = new_process
                        self.send_event("dev_server_restarted", {
                            "tunnel_url": self.dev_tunnel_url,
                            "websocket_url": self.ws_tunnel_url
                        })
                        print(f"[Sandbox:{self.session_id}] Dev server restarted successfully")
                    else:
                        print(f"[Sandbox:{self.session_id}] Failed to restart dev server")
    
    def start_monitor(self):
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print(f"[Sandbox:{self.session_id}] Dev server monitor started")
        return thread


@app.function(
    image=agent_image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=3600
)
async def run_agent_in_sandbox(
    session_id: str,
    prompt: str
):
    import os
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
    import queue
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock, ResultMessage
    
    websocket_clients = []
    websocket_lock = threading.Lock()
    event_queue = queue.Queue()
    
    def send_event(event_type: str, data: Optional[dict] = None):
        event = {
            "session_id": session_id,
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        event_queue.put(event)
        print(f"[Sandbox:{session_id}] Queued event '{event_type}' (queue size: {event_queue.qsize()})")
    
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
    
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()
    
    time.sleep(2)
    print(f"[Sandbox:{session_id}] WebSocket server started")
    
    print(f"[Sandbox:{session_id}] Starting agent in sandbox")
    print(f"[Sandbox:{session_id}] Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"[Sandbox:{session_id}] Prompt: {prompt}")
    
    import os
    import tempfile
    workspace = tempfile.mkdtemp(prefix=f"session-{session_id}-", dir="/tmp")
    print(f"[Sandbox:{session_id}] Workspace created at {workspace}")
    
    # Set permissions on workspace directory so claudeuser can access it
    try:
        os.chmod(workspace, 0o755)  # rwxr-xr-x - everyone can read and execute
        print(f"[Sandbox:{session_id}] Set permissions on workspace directory")
    except Exception as e:
        print(f"[Sandbox:{session_id}] Warning: Could not set workspace dir permissions: {e}")
    
    results = {
        "status": "started",
        "session_id": session_id,
        "workspace": workspace,
        "events": [],
        "websocket_url": None
    }

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
        print(f"[Sandbox:{session_id}] This tunnel will remain stable for the duration of this function")
        
        # Immediately update session data with WebSocket URL
        if sessions.contains(session_id):
            session_data = sessions[session_id]
            session_data["websocket_url"] = ws_tunnel_url
            session_data["last_activity"] = datetime.utcnow().isoformat()
            sessions[session_id] = session_data
            print(f"[Sandbox:{session_id}] Updated session with WebSocket URL")
        
        # Send WebSocket URL as an event so clients can connect immediately
        send_event("websocket_ready", {
            "websocket_url": ws_tunnel_url,
            "session_id": session_id
        })
        
        # Small delay to ensure WebSocket server is ready to accept connections
        time.sleep(1)
        
        try:
            event_data = {
                "type": "agent_coding_started",
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": prompt
            }
            results["events"].append(event_data)
            send_event("coding_start", {"prompt": prompt, "work_dir": workspace})
            
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not anthropic_api_key:
                error_msg = "ANTHROPIC_API_KEY secret is missing"
                print(f"[Sandbox:{session_id}] ERROR: {error_msg}")
                results["status"] = "error"
                results["error"] = error_msg
                
                if sessions.contains(session_id):
                    session_data = sessions[session_id]
                    session_data["status"] = "error"
                    session_data["last_activity"] = datetime.utcnow().isoformat()
                    if ws_urls.contains(session_id):
                        session_data["websocket_url"] = ws_urls[session_id]
                    sessions[session_id] = session_data
                
                event_data = {
                    "type": "agent_error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": error_msg
                }
                results["events"].append(event_data)
                send_event("agent_error", {"error": error_msg, "error_type": "missing_secret"})
                return results
            
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
            # Using acceptEdits instead of bypassPermissions to avoid root privilege issues
            sdk_options = ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                permission_mode="acceptEdits",  # Auto-accepts file edits, works with root
                cwd=workspace,
                env={"ANTHROPIC_API_KEY": anthropic_api_key}
            )
            
            event_count = 0
            claude_session_id = None
            exit_code = 0
            
            print(f"[Sandbox:{session_id}] Starting dev server manager...")
            dev_server = DevServerManager(
                session_id=session_id,
                work_dir=workspace,
                dev_tunnel_url=dev_tunnel_url,
                ws_tunnel_url=ws_tunnel_url,
                send_event=send_event
            )
            
            try:
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
                
            except Exception as sdk_error:
                print(f"[Sandbox:{session_id}] Claude SDK error: {type(sdk_error).__name__}: {sdk_error}")
                import traceback
                traceback.print_exc()
                exit_code = 1
            
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
                send_event("session_complete", {
                    "claude_session_id": claude_session_id
                })
            else:
                print(f"[Sandbox:{session_id}] No session_end event found")
            
            results["status"] = "completed"
            print(f"[Sandbox:{session_id}] Agent completed successfully")
            
            # Verify files were created
            import os
            import glob
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
            
            print(f"[Sandbox:{session_id}] Starting dev server after Claude completes...")
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
        finally:
            # Keep dev server alive for preview
            pass
        
        print(f"[Sandbox:{session_id}] Returning results with status: {results['status']}")
        return results


web_app = FastAPI(title="Claude Agent API")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@web_app.get("/")
async def root():
    return {
        "service": "Claude Agent API",
        "status": "running",
        "version": "1.0.0"
    }


@web_app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    print(f"[API] POST /api/chat - session_id: {session_id}")
    print(f"[API] Message: {request.message[:100]}..." if len(request.message) > 100 else f"[API] Message: {request.message}")
    
    is_new_session = not sessions.contains(session_id)
    print(f"[API] New session: {is_new_session}")
    
    # Check if session is already running to prevent duplicate spawns
    if not is_new_session:
        existing_session = sessions[session_id]
        if existing_session.get("status") in ["initializing", "running"]:
            print(f"[API] Session {session_id} already running, returning existing session")
            return ChatResponse(
                session_id=session_id,
                message="Session already running",
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


@web_app.get("/api/sessions/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str):
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


@web_app.get("/api/sessions")
async def list_sessions():
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


@web_app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    print(f"[API] DELETE /api/sessions/{session_id}")
    if session_id not in sessions:
        print(f"[API] Session {session_id} not found")
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    print(f"[API] Session {session_id} deleted")

    return {"message": "Session deleted", "session_id": session_id}


@app.function(
    image=modal.Image.debian_slim(python_version="3.12").pip_install(
        "fastapi[standard]",
        "pydantic",
        "websockets"
    )
)
@modal.asgi_app()
def web():
    return web_app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8000)
