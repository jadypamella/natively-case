# Migration from Claude Code CLI to Claude Agent SDK

## Summary

Successfully migrated from using the Claude Code CLI via subprocess to using the Claude Agent SDK (Python).

## Changes Made

### 1. **requirements.txt**
- Added `claude-agent-sdk` package

### 2. **API.py - Imports**
- Removed: `import pty`, `import select` (no longer needed for subprocess handling)
- Added: Claude SDK imports
  ```python
  from claude_agent_sdk import (
      ClaudeSDKClient,
      ClaudeAgentOptions,
      AssistantMessage,
      TextBlock,
      ThinkingBlock,
      ToolUseBlock,
      ToolResultBlock,
      ResultMessage
  )
  ```

### 3. **API.py - Agent Execution**

#### Before (CLI + subprocess):
```python
# Built command line arguments
claude_cmd = ["claude", "-p", full_prompt, "--output-format", "stream-json", ...]

# Created PTY for process communication
master, slave = pty.openpty()

# Spawned subprocess
claude_process = subprocess.Popen(claude_cmd, stdout=slave, stderr=slave, ...)

# Parsed JSON line-by-line from stdout
while True:
    data = os.read(master, 4096)
    # Parse JSON manually...
```

#### After (SDK):
```python
# Configure SDK options
sdk_options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    permission_mode="bypassPermissions",
    cwd=workspace,
    env={"ANTHROPIC_API_KEY": anthropic_api_key}
)

# Use async context manager
async with ClaudeSDKClient(options=sdk_options) as client:
    await client.query(full_prompt)
    
    # Stream typed messages
    async for message in client.receive_messages():
        if isinstance(message, AssistantMessage):
            # Handle text, tool use, etc.
        elif isinstance(message, ResultMessage):
            # Handle completion
```

### 4. **Event Mapping**

SDK message types are mapped to WebSocket events:

| SDK Message Type | WebSocket Event | Data |
|-----------------|-----------------|------|
| `TextBlock` | `claude_text` | Text content |
| `ThinkingBlock` | `claude_thinking` | Thinking content |
| `ToolUseBlock` | `claude_tool_use` | Tool name, input, ID |
| `ToolResultBlock` | `claude_tool_result` | Result content, error status |
| `ResultMessage` | `claude_session_end` | Session ID, cost, duration |

## Benefits of SDK Over CLI

1. **Type Safety**: Structured message types instead of parsing raw JSON
2. **Better Error Handling**: Native Python exceptions instead of parsing stderr
3. **Simpler Code**: No PTY management, subprocess handling, or manual JSON parsing
4. **More Reliable**: No buffering issues or line-splitting edge cases
5. **Better Documentation**: Full Python API reference and type hints
6. **Async Native**: Built for async/await patterns

## Backwards Compatibility

The WebSocket event structure remains the same, so frontend clients don't need changes:
- `claude_text` events still contain text
- `claude_tool_use` events still contain tool name and input
- `claude_tool_result` events still contain results
- `claude_session_end` events still signal completion

## Testing

After deployment, verify:
1. Sessions start correctly
2. WebSocket events stream properly
3. Tool usage is logged
4. Session completes successfully
5. Dev server starts after completion
6. Cost and usage statistics are tracked

## Notes

- The Claude Code CLI is still installed in the Modal image because the Python SDK requires it internally
- The SDK provides a cleaner abstraction over the CLI
- All environment variables and workspace configuration work the same way
