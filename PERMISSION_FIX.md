# Directory Permission Fix

## Issue

Dev server starts successfully but returns error when accessing files:

```
Error response
Error code: 404
Message: No permission to list directory.
Error code explanation: 404 - Nothing matches the given URI.
```

## Root Cause

The HTTP server process runs as `claudeuser`, but the workspace directory didn't have **execute permissions** for accessing it.

### Why Execute Permission Matters

In Unix/Linux, you need:
- **Read permission** (`r`) to list directory contents
- **Execute permission** (`x`) to **enter** (cd into) the directory
- Both `r+x` to browse and serve files from a directory

Without execute permission, the HTTP server can't even enter the directory to serve files!

## Permissions Explained

```bash
# Directory permissions format: drwxrwxrwx
# d = directory
# rwx = owner permissions (read, write, execute)
# rwx = group permissions
# rwx = others permissions

# Example:
drwxr-xr-x  # 755 - Owner: rwx, Group: r-x, Others: r-x
-rw-r--r--  # 644 - Owner: rw-, Group: r--, Others: r--
```

## Fixes Applied

### 1. **Workspace Directory Creation**
```python
# After creating workspace, set 755 permissions
os.chmod(workspace, 0o755)  # rwxr-xr-x
# Owner: read, write, execute
# Group: read, execute
# Others: read, execute
```

### 2. **After Claude Creates Files**
```python
# Before fix - only read permission:
os.system(f"chmod -R a+r {workspace}")  # ✗ No execute on directory!

# After fix - read + execute:
os.system(f"chmod -R a+rX {workspace}")  # ✓ Capital X = execute on dirs
# Lowercase x = execute on all files
# Capital X = execute only on directories (not files)
```

### 3. **Individual File Permissions**
```python
# index.html and other files
os.chmod(index_path, 0o644)  # rw-r--r--
# Owner: read, write
# Group: read
# Others: read
```

## Permission Modes

| Mode | Octal | Symbolic | Description |
|------|-------|----------|-------------|
| Directory | `0o755` | `rwxr-xr-x` | Owner full access, others can read & enter |
| HTML Files | `0o644` | `rw-r--r--` | Owner can edit, others can read |

## Debugging Output

After the fix, you'll see:

```
[Sandbox:xxx] Workspace created at /tmp/session-xxx-yyy
[Sandbox:xxx] Set permissions on workspace directory
[Sandbox:xxx] ✓ index.html exists (21753 bytes, permissions: 644)
[Sandbox:xxx] Set read permissions on index.html (644)
[Sandbox:xxx] Workspace dir permissions before fix: 755
[Sandbox:xxx] Workspace dir permissions after fix: 755
```

## Expected Behavior

### Before Fix
```
Request → http://server:3000/
Response → 404 No permission to list directory
Reason → Server can't enter directory (no execute permission)
```

### After Fix
```
Request → http://server:3000/
Response → 200 OK (serves index.html)
Reason → Server can enter directory and read files
```

## Testing Permissions Manually

If you want to verify permissions:

```bash
# Check directory permissions
ls -ld /tmp/session-xxx-yyy
# Should show: drwxr-xr-x (755)

# Check file permissions
ls -l /tmp/session-xxx-yyy/index.html
# Should show: -rw-r--r-- (644)

# Test as claudeuser
sudo -u claudeuser ls /tmp/session-xxx-yyy/
# Should successfully list files

# Test HTTP server manually
cd /tmp/session-xxx-yyy
sudo -u claudeuser python3 -m http.server 3000
# Visit http://localhost:3000/ - should work
```

## Why `chmod -R a+rX` Works

The `-R` flag means recursive (all subdirectories).
The `a+rX` means:
- `a` = all (owner, group, others)
- `+` = add permission
- `r` = read permission (always added)
- `X` = execute permission **only if** it's a directory or already has execute for someone

This is perfect because:
- ✅ Adds execute to directories (so they can be entered)
- ✅ Keeps files without execute (HTML doesn't need to be executable)
- ✅ Doesn't make files executable unnecessarily

## Summary

| Component | Permission | Reason |
|-----------|------------|--------|
| Workspace directory | `755` (`rwxr-xr-x`) | Allow entering directory |
| index.html file | `644` (`rw-r--r--`) | Allow reading file |
| Fix command | `chmod -R a+rX` | Add read + execute recursively |

The key insight: **directories need execute permission for the HTTP server to access them!**

## Deploy

```bash
modal deploy API.py
```

After deploying, the dev server preview should work correctly! 🎉
