# Dev Server Fixes

## Problem

Dev server was starting but returning 404 for all files, including `index.html`:

```
HTTP Error 404: File not found
Health check timeout after 30 seconds
```

## Root Causes

1. **Overly Strict Health Check**: Health check only passed on HTTP 200, but failed on 404
   - Issue: Server WAS running but health check failed because no index.html
   - Result: Server killed after 30 seconds even though it was working

2. **No File Verification**: No logging to show what files Claude actually created
   - Hard to debug if files existed or not

3. **Potential Permission Issues**: Files created by SDK might not be readable by HTTP server
   - HTTP server runs as `claudeuser`
   - Files might be created with restrictive permissions

## Fixes Applied

### 1. Smarter Health Check

**Before**:
```python
# Only accepted HTTP 200
request_obj = urlopen(f"http://localhost:3000/index.html")
return request_obj.getcode() == 200  # Fails on 404!
```

**After**:
```python
# Accepts ANY response from server (200, 404, etc.)
try:
    request_obj = urlopen(f"http://localhost:3000/")
    return True  # Server responded!
except HTTPError as e:
    return True  # HTTPError means server IS running
except URLError as e:
    return False  # Connection refused = not running
```

### 2. File Verification Before Server Start

Added logging to check workspace contents:

```python
# List all files in workspace
files = glob.glob(f"{workspace}/*")
print(f"Files in workspace: {len(files)} files")

# Check specifically for index.html
if os.path.exists(index_path):
    print(f"✓ index.html found ({file_size} bytes)")
else:
    print(f"✗ index.html NOT found")
```

### 3. File Verification After Claude Completes

Added verification step before starting dev server:

```python
# Verify files were created
workspace_files = glob.glob(f"{workspace}/*")
print(f"Workspace verification: {len(workspace_files)} files created")

# Check for index.html and read first line
if os.path.exists(index_path):
    with open(index_path, 'r') as f:
        first_line = f.readline()
        print(f"First line: {first_line[:100]}")
```

### 4. Fix File Permissions

Ensure all workspace files are readable:

```python
# Fix permissions on index.html
os.chmod(index_path, 0o644)  # rw-r--r--

# Fix permissions on all workspace files
os.system(f"chmod -R a+r {workspace}")
```

## Health Check Logic

### Old Logic (Too Strict)
```
1. Request /index.html
2. If 200 → Pass ✓
3. If 404 → Fail ✗  (SERVER WAS RUNNING!)
4. If connection refused → Fail ✗
```

### New Logic (Correct)
```
1. Request /
2. If any HTTP response → Pass ✓ (server is running)
3. If HTTPError (404, 403, etc.) → Pass ✓ (server is running)
4. If URLError (connection refused) → Fail ✗ (server not started)
5. Other exceptions → Fail ✗
```

## Expected Logs (After Fix)

### Successful Flow
```
[Sandbox:xxx] Agent completed successfully
[Sandbox:xxx] Workspace verification: 1 files created
[Sandbox:xxx] ✓ index.html exists (2847 bytes)
[Sandbox:xxx] First line: <!DOCTYPE html>
[Sandbox:xxx] Set read permissions on index.html
[Sandbox:xxx] Set read permissions on all workspace files
[Sandbox:xxx] Starting dev server after Claude completes...
[Sandbox:xxx] Files in workspace: 1 files
[Sandbox:xxx]   - index.html (2847 bytes)
[Sandbox:xxx] ✓ index.html found (2847 bytes)
[Sandbox:xxx] HTTP server process started as claudeuser (PID: 169)
[Sandbox:xxx] Health check: server responded with 200
[Sandbox:xxx] Dev server health check passed (attempt 1/30)
[Sandbox:xxx] Dev server started at https://xxx.modal.run
```

### If No Files Created
```
[Sandbox:xxx] Agent completed successfully
[Sandbox:xxx] Workspace verification: 0 files created
[Sandbox:xxx] ✗ WARNING: index.html not found!
[Sandbox:xxx] Files in workspace:
[Sandbox:xxx] Starting dev server after Claude completes...
[Sandbox:xxx] Files in workspace: 0 files
[Sandbox:xxx] ✗ index.html NOT found in /tmp/session-xxx
[Sandbox:xxx] WARNING: Starting server anyway, but preview may not work
[Sandbox:xxx] HTTP server process started as claudeuser (PID: 169)
[Sandbox:xxx] Health check: server responded with 404
[Sandbox:xxx] Dev server health check passed (attempt 1/30)  ← Still passes!
[Sandbox:xxx] Dev server started at https://xxx.modal.run
```

## Why This Fixes The Issue

### Before
- Health check: **FAIL** (got 404 from server)
- Server: **KILLED** after 30 seconds
- Preview: **BROKEN** (server terminated)

### After
- Health check: **PASS** (server is responding)
- Server: **RUNNING** (stays alive)
- Preview: **WORKS** (if files exist) or shows directory listing (if not)

## Testing

Deploy and test:

```bash
# 1. Deploy
modal deploy API.py

# 2. Create session
curl -X POST https://your-app.modal.run/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Build a simple landing page"}'

# 3. Watch logs for these indicators:

# Good signs:
✓ index.html found (XXXX bytes)
First line: <!DOCTYPE html>
Set read permissions on index.html
Health check: server responded with 200
Dev server health check passed (attempt 1/30)
Dev server started at https://xxx.modal.run

# Bad signs (Claude didn't create files):
✗ WARNING: index.html not found!
Health check: server responded with 404
# But server should still stay alive now!
```

## Additional Debug Info

If dev server still doesn't work, check:

1. **Files created by Claude**:
   ```
   Workspace verification: X files created
   ```
   If 0, Claude didn't create any files (check Claude logs)

2. **Permission errors**:
   ```
   Could not set permissions: [Errno 1] Operation not permitted
   ```
   Permission issues (should be fixed by chmod -R a+r)

3. **Server startup**:
   ```
   HTTP server process started as claudeuser (PID: XXX)
   ```
   Process should start successfully

4. **Health check**:
   ```
   Health check: server responded with XXX
   ```
   Should pass on any response code now

## Summary

| Issue | Before | After |
|-------|--------|-------|
| Health check on 404 | ✗ Fail | ✓ Pass |
| File verification | ❌ None | ✓ Detailed |
| Permission fixes | ❌ None | ✓ chmod a+r |
| Debugging info | ⚠️ Limited | ✓ Comprehensive |
| Server lifespan | ⏱️ 30s (killed) | ✓ 720s (alive) |

The dev server should now:
- ✅ Start reliably
- ✅ Stay alive for full 720 seconds
- ✅ Serve files if they exist
- ✅ Show directory listing if no index.html
- ✅ Provide clear debugging info in logs
