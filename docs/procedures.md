# Page Selector Implementation - Step by Step Guide

This guide shows what was implemented for the Page Selector feature.

---

## What was implemented

A hierarchical dropdown that shows all HTML pages in the generated website (like `index.html`, `about.html`) with their sections, allowing users to navigate between pages and jump to specific sections.

---

## Environment Setup

### Python & Backend

```bash
# Install uv (if not installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies (this creates the .venv folder automatically)
uv sync

# Activate venv (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Setup Modal (opens browser for authentication)
uv run modal setup

# Create API secret with your Anthropic API key
modal secret create anthropic-secret ANTHROPIC_API_KEY=your_key_here

# Deploy backend to Modal
uv run modal deploy API.py
```

### Frontend

```bash
cd appandrunning

# Install dependencies
npm install

# Install Radix dropdown menu (required for PageSelector)
npm install @radix-ui/react-dropdown-menu

# Create .env.local file with the Modal backend URL
# NEXT_PUBLIC_API_URL=https://my-username--website-builder-api-web.modal.run

# Start development server
npm run dev
```

---

## Step 1: Backend - Add `scan_workspace_pages` Function

**File:** `agent.py`  
**Location:** After the `verify_workspace_files` function

### What to do:
1. Open `agent.py`
2. Find the function `verify_workspace_files`
3. After that function ends, add this new function:

```python
def scan_workspace_pages(session_id: str, workspace: str) -> dict:
    """
    Scan workspace for HTML files and extract page structure with sections.
    Returns a dict with pages, their titles, and internal sections/anchors.
    """
    import re
    
    pages = []
    html_files = glob.glob(f"{workspace}/*.html") + glob.glob(f"{workspace}/**/*.html", recursive=True)
    
    print(f"[Sandbox:{session_id}] Scanning for HTML files in {workspace}...")
    print(f"[Sandbox:{session_id}] Found {len(html_files)} HTML files")
    
    for html_file in html_files:
        try:
            rel_path = os.path.relpath(html_file, workspace)
            
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else rel_path
            
            sections = []
            id_pattern = r'<(h[1-6]|section|article|nav|aside|div)[^>]*\sid=["\']([^"\']+)["\'][^>]*>(.*?)</\1>'
            
            for match in re.finditer(id_pattern, content, re.IGNORECASE | re.DOTALL):
                element_type = match.group(1)
                section_id = match.group(2)
                inner_content = match.group(3)
                
                text_content = re.sub(r'<[^>]+>', '', inner_content).strip()
                text_content = re.sub(r'\s+', ' ', text_content)
                
                if len(text_content) > 50:
                    text_content = text_content[:50] + '...'
                
                section_name = text_content if text_content else section_id
                
                sections.append({
                    "id": section_id,
                    "name": section_name,
                    "element": element_type
                })
                
                if len(sections) >= 20:
                    break
            
            url_path = '/' + rel_path.replace('\\', '/')
            if url_path == '/index.html':
                url_path = '/'
            
            pages.append({
                "path": rel_path,
                "title": title,
                "url": url_path,
                "sections": sections
            })
            
            print(f"[Sandbox:{session_id}] Page: {rel_path} - {title} ({len(sections)} sections)")
            
        except Exception as e:
            print(f"[Sandbox:{session_id}] Error scanning {html_file}: {type(e).__name__}: {e}")
    
    pages.sort(key=lambda p: (p['path'] != 'index.html', p['path']))
    
    return {
        "pages": pages,
        "total_pages": len(pages),
        "total_sections": sum(len(p["sections"]) for p in pages)
    }
```

---

## Step 2: Backend - Send `pages_discovered` Event via WebSocket

**File:** `agent.py`  
**Location:** Inside `run_claude_agent_multiturn` function

### What to do:
1. After `verify_workspace_files(session_id, workspace)`, add:

```python
        # Get and send initial website structure
        structure = scan_workspace_pages(session_id, workspace)
        send_event("pages_discovered", structure)
```

2. After the dev server starts successfully, add:

```python
        # Send updated structure after dev server is ready
        structure = scan_workspace_pages(session_id, workspace)
        send_event("pages_discovered", structure)
```

3. After each `process_prompt` call in the while loop, add:

```python
                    # Send updated structure after each turn
                    structure = scan_workspace_pages(session_id, workspace)
                    send_event("pages_discovered", structure)
```

---

## Step 3: Frontend - Add PageStructure Types

**File:** `appandrunning/app/lib/api-client.ts`  
**Location:** After `AgentEvent` interface

### What to do:
Add these interfaces:

```typescript
export interface PageSection {
  id: string;
  name: string;
  element: string;
}

export interface PageInfo {
  path: string;
  title: string;
  url: string;
  sections: PageSection[];
}

export interface PageStructure {
  pages: PageInfo[];
  total_pages: number;
  total_sections: number;
}
```

---

## Step 4: Frontend - Add dropdown-menu UI Component

**File:** `appandrunning/app/components/ui/dropdown-menu.tsx` (NEW FILE)

### What to do:
Create this file with the Radix UI dropdown menu component. See the full implementation in the codebase.

---

## Step 5: Frontend - Create PageSelector Component

**File:** `appandrunning/app/components/PageSelector.tsx` (REPLACE)

### What to do:
Replace the file with a component that:
- Uses Radix `DropdownMenu` components
- Takes `pages: PageStructure | null`, `devUrl: string`, `onNavigate: (url: string) => void` props
- Shows hierarchical menu with pages and their sections
- Uses `section.name` for display text

---

## Step 6: Frontend - Update WebsitePreview

**File:** `appandrunning/app/components/WebsitePreview.tsx`

### What to do:
1. Import `PageStructure` from api-client
2. Update props to use `pages?: PageStructure | null`
3. Always show PageSelector (not only when pages > 1)
4. Display `currentUrl` in the URL bar

---

## Step 7: Frontend - Update Chat Page

**File:** `appandrunning/app/chat/[id]/page.tsx`

### What to do:
1. Import `PageStructure` from api-client
2. Change state: `const [websitePages, setWebsitePages] = useState<PageStructure | null>(null);`
3. Update event handler to use `pages_discovered` event:

```typescript
    // Handle pages discovered
    if (latestEvent.event === "pages_discovered") {
      console.log('[Chat] Pages discovered:', latestEvent.data);
      setWebsitePages(latestEvent.data as PageStructure);
    }
```

---

## Step 8: Deploy & Test

### Deploy Backend:
```bash
uv run modal deploy API.py
```

### Run Frontend:
```bash
cd appandrunning
npm run dev
```

### Test:
1. Create a website with the prompt: "Create a website with Home, About, and Contact pages"
2. Wait for the website to generate
3. Check if the PageSelector dropdown appears
4. Click on different pages to navigate
5. Click on sections to jump to specific anchors

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| PageSelector not showing | Check browser console for `pages_discovered` event |
| Dropdown empty | Make sure the prompt asks for multiple pages |
| Navigation not working | Check that URLs are being built correctly |
| Backend errors | Check Modal logs: `modal logs website-builder-api` |
| Missing dropdown component | Run `npm install @radix-ui/react-dropdown-menu` |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `agent.py` | + `scan_workspace_pages` function, + `pages_discovered` events |
| `appandrunning/app/lib/api-client.ts` | + PageSection, PageInfo, PageStructure interfaces |
| `appandrunning/app/components/ui/dropdown-menu.tsx` | NEW - Radix dropdown component |
| `appandrunning/app/components/PageSelector.tsx` | REPLACED - Uses Radix DropdownMenu |
| `appandrunning/app/components/WebsitePreview.tsx` | + PageStructure prop, always show PageSelector |
| `appandrunning/app/chat/[id]/page.tsx` | + PageStructure state, + pages_discovered handler |
