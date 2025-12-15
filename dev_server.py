"""
Development server manager for running and monitoring HTTP server
"""

import os
import subprocess
import threading
import time
import glob
from typing import Optional, Callable
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


class DevServerManager:
    """Manages the development server lifecycle including starting, monitoring, and restarting"""
    
    def __init__(self, session_id: str, work_dir: str, dev_tunnel_url: str, ws_tunnel_url: str, send_event: Callable):
        self.session_id = session_id
        self.work_dir = work_dir
        self.dev_tunnel_url = dev_tunnel_url
        self.ws_tunnel_url = ws_tunnel_url
        self.send_event = send_event
        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.monitor_running = threading.Event()
        self.monitor_running.set()
    
    def check_health(self, timeout: int = 5, verbose: bool = False) -> bool:
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
    
    def start(self) -> Optional[subprocess.Popen]:
        """Start the development server"""
        self.send_event("dev_server_starting", {})
        print(f"[Sandbox:{self.session_id}] Starting simple HTTP server in {self.work_dir}")
        
        # Check what files exist in the workspace
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
                """Demote privileges to run as claudeuser"""
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
            
            # Wait for server to be ready
            for attempt in range(30):
                if process.poll() is not None:
                    exit_code = process.returncode
                    error = f"Process exited with code {exit_code}"
                    print(f"[Sandbox:{self.session_id}] {error}")
                    
                    self._print_log_file(log_path, 20)
                    self.send_event("dev_server_failed", {"error": error})
                    return None
                
                verbose = (attempt == 0 or attempt % 10 == 9)
                if self.check_health(timeout=2, verbose=verbose):
                    print(f"[Sandbox:{self.session_id}] Dev server health check passed (attempt {attempt + 1}/30)")
                    return process
                
                if attempt % 5 == 4:
                    print(f"[Sandbox:{self.session_id}] Still waiting for dev server... (attempt {attempt + 1}/30)")
                
                time.sleep(1)
            
            # Health check timeout
            print(f"[Sandbox:{self.session_id}] Health check timeout after 30 seconds")
            self._print_log_file(log_path, 30)
            
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
    
    def _print_log_file(self, log_path: str, num_lines: int = 20):
        """Print the last N lines of the log file"""
        try:
            with open(log_path, "r") as f:
                log_content = f.read()
                if log_content:
                    print(f"[Sandbox:{self.session_id}] Last {num_lines} lines of log:")
                    for line in log_content.split('\n')[-num_lines:]:
                        if line.strip():
                            print(f"[Sandbox:{self.session_id}]   {line}")
                else:
                    print(f"[Sandbox:{self.session_id}] Log file is empty")
        except Exception as e:
            print(f"[Sandbox:{self.session_id}] Could not read log file: {e}")
    
    def _stop_process(self, process: Optional[subprocess.Popen]):
        """Stop a running process gracefully"""
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                print(f"[Sandbox:{self.session_id}] Error stopping process: {e}")
    
    def _monitor_loop(self):
        """Monitor the server and restart if needed"""
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
        """Start monitoring the server in a background thread"""
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print(f"[Sandbox:{self.session_id}] Dev server monitor started")
        return thread

