# WebSocket Connection Stability Improvements

## Issues Fixed

### 1. **Race Condition with Tunnel URL**
**Problem**: WebSocket tunnel URL was created inside the Modal function but not immediately available to clients.

**Solution**:
- Immediately update session data with WebSocket URL after tunnel creation
- Send `websocket_ready` event through the event queue
- Added 1-second delay to ensure WebSocket server is accepting connections

### 2. **Duplicate Session Creation**
**Problem**: Multiple requests to `/api/chat` could spawn duplicate sessions.

**Solution**:
- Check if session is already in `initializing` or `running` state
- Return existing session info instead of spawning duplicate

### 3. **URL Change Detection**
**Problem**: No visibility when tunnel URLs were changing.

**Solution**:
- Added logging to detect and warn when WebSocket URL changes
- Added stability message confirming tunnel persists for function duration

### 4. **Connection Tracking**
**Problem**: Hard to debug connection issues without client tracking.

**Solution**:
- Added unique client IDs to each WebSocket connection
- Track total connected clients count
- Improved disconnect logging with client count

### 5. **Health Check Endpoint**
**Added**: `/health` endpoint on WebSocket server showing:
- Server status
- Session ID
- Number of connected clients
- Queued events count

## WebSocket URL Lifecycle

```
1. POST /api/chat (session_id: abc123)
   └─> Spawn Modal function
   └─> Return { websocket_url: null }

2. Modal function starts
   └─> Create WebSocket server on port 8080
   └─> Create Modal tunnel: wss://xyz.modal.run/ws
   └─> Store in ws_urls[abc123]
   └─> Update sessions[abc123].websocket_url
   └─> Send "websocket_ready" event

3. Client polls GET /api/sessions/abc123
   └─> Returns websocket_url from ws_urls or session data

4. Client connects to wss://xyz.modal.run/ws
   └─> Receives "connected" event
   └─> Receives queued events including "websocket_ready"

5. URL remains stable until function exits
```

## Frontend Integration

### Recommended Connection Flow

```typescript
async function connectToSession(sessionId: string) {
  // 1. Start the session
  const chatResponse = await fetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ 
      session_id: sessionId,
      message: "Build a restaurant menu"
    })
  });
  
  const session = await chatResponse.json();
  console.log('Session started:', session.session_id);
  
  // 2. Poll for WebSocket URL
  let websocketUrl = null;
  let attempts = 0;
  
  while (!websocketUrl && attempts < 30) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const statusResponse = await fetch(`/api/sessions/${sessionId}`);
    const status = await statusResponse.json();
    
    if (status.websocket_url) {
      websocketUrl = status.websocket_url;
      console.log('WebSocket URL ready:', websocketUrl);
      break;
    }
    
    attempts++;
  }
  
  if (!websocketUrl) {
    throw new Error('WebSocket URL not available after 30 seconds');
  }
  
  // 3. Connect to WebSocket
  const ws = new WebSocket(websocketUrl);
  
  ws.onopen = () => {
    console.log('WebSocket connected');
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.event === 'websocket_ready') {
      console.log('WebSocket URL confirmed:', data.data.websocket_url);
    }
    
    // Handle other events...
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket closed');
  };
  
  return ws;
}
```

### Event: `websocket_ready`

New event sent when the WebSocket tunnel is ready:

```json
{
  "session_id": "abc123",
  "event": "websocket_ready",
  "timestamp": "2025-12-15T10:30:00.000Z",
  "data": {
    "websocket_url": "wss://xyz.modal.run/ws",
    "session_id": "abc123"
  }
}
```

### Health Check Usage

Check if WebSocket server is ready before connecting:

```typescript
async function checkWebSocketHealth(websocketUrl: string): Promise<boolean> {
  try {
    const healthUrl = websocketUrl.replace('/ws', '/health').replace('wss://', 'https://');
    const response = await fetch(healthUrl);
    const health = await response.json();
    
    console.log('WebSocket health:', health);
    return health.status === 'healthy';
  } catch (error) {
    console.error('Health check failed:', error);
    return false;
  }
}
```

## Debugging

### Server-Side Logs to Watch

```bash
# Good - normal flow
[API] POST /api/chat - session_id: abc123
[API] New session: True
[API] Creating new session abc123
[API] Spawning sandbox for session abc123
[API] Sandbox spawned with ID: xyz789
[Sandbox:abc123] Modal websocket tunnel created: wss://xyz.modal.run/ws
[Sandbox:abc123] This tunnel will remain stable for the duration of this function
[Sandbox:abc123] Updated session with WebSocket URL
[Sandbox:abc123] WebSocket client 12345 connected (total clients: 1)

# Bad - URL changing (shouldn't happen)
[Sandbox:abc123] WARNING: WebSocket URL changed!
[Sandbox:abc123]   Old: wss://old.modal.run/ws
[Sandbox:abc123]   New: wss://new.modal.run/ws

# Bad - duplicate spawn attempt
[API] POST /api/chat - session_id: abc123
[API] New session: False
[API] Session abc123 already running, returning existing session
```

### Common Issues

1. **"Receiving new tunnel URLs all the time"**
   - Check logs for "WARNING: WebSocket URL changed"
   - Verify client isn't creating duplicate sessions
   - Ensure session_id is consistent across requests

2. **WebSocket connects but no events**
   - Check health endpoint: `/health` should show queued events
   - Verify events are being sent with `send_event()`
   - Check client is waiting for events in async loop

3. **Connection drops immediately**
   - Check if Modal function is exiting early
   - Verify ANTHROPIC_API_KEY is set
   - Check function timeout (currently 3600s)

## Testing

Test the improvements:

```bash
# 1. Deploy the updated code
modal deploy API.py

# 2. Create a session
curl -X POST https://your-modal-app.modal.run/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Build a simple website"}'

# 3. Get the session status (poll until websocket_url is available)
curl https://your-modal-app.modal.run/api/sessions/SESSION_ID

# 4. Check WebSocket health
curl https://WEBSOCKET_URL/health  # Replace wss:// with https:// and remove /ws

# 5. Connect with wscat (install: npm install -g wscat)
wscat -c WEBSOCKET_URL
```

## Summary

The WebSocket connection should now be:
- ✅ **Stable** - URL doesn't change during session
- ✅ **Available faster** - Immediate session update after tunnel creation
- ✅ **Debuggable** - Better logging and health checks
- ✅ **Resilient** - Prevents duplicate spawns
- ✅ **Trackable** - Client IDs and connection counts
