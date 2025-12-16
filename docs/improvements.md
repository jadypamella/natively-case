# Future Improvements

Things we should add to make the website builder production-ready.

---

## 1. Chat History

Right now, if you close the browser, your chats are gone. We need to save them.

**What's needed:**
- Save chats to localStorage or a database
- Show a list of past chats in the sidebar
- Click to restore and continue an old chat

**Where to start:**  
The backend already stores sessions in Modal Dict, we just need to expose them via the `GET /api/sessions` endpoint and update the `AppSidebar.tsx` component to display them.

---

## 2. Save to Database

We're using Modal Dict which is temporary storage. Sessions disappear when Modal restarts.

**Options:**
- Supabase (free tier, PostgreSQL, built-in auth)
- PlanetScale (MySQL, serverless)
- MongoDB Atlas

**What to store:**
- Sessions (id, status, timestamps, urls)
- Messages (user prompts and AI responses)
- Generated files (HTML, CSS, JS)

---

## 3. Better Error Handling

When something breaks, users just see a loading spinner forever. Not great.

**What we need:**
- Show friendly error messages when sandbox fails
- Add a "Retry" button when WebSocket disconnects
- Timeout warning if generation takes over 60 seconds
- Handle rate limits from Anthropic API

---

## 4. Save Money on AI Tokens

Claude API gets expensive fast. A few ways to cut costs:

- **Prompt caching**: Anthropic supports this for repeated system prompts (30-50% savings)
- **Context pruning**: Don't send the entire conversation, just the last 5 messages
- **Use Haiku for follow-ups**: It's 10x cheaper than Sonnet for simple edits
- **Set max_tokens limits**: Stop Claude from generating 10,000 tokens when 2,000 is enough

---

## 5. Export & GitHub Integration

Users want to download their websites and deploy them easily.

**Features:**
- Download as ZIP file
- Push directly to a GitHub repo
- Deploy to GitHub Pages or Vercel with one click
- Include a README with setup instructions

**Implementation:**
- Add `GET /api/sessions/{id}/download` endpoint for ZIP export
- OAuth flow with GitHub for repo access
- Create repo, commit files, optionally enable GitHub Pages
- Store GitHub tokens securely (Modal secrets or database)

---

## 6. Code Editor

Let users manually edit the generated code without leaving the app.

**Features:**
- Monaco Editor (same as VS Code) with syntax highlighting
- Tabs for HTML, CSS, JS files
- Save edits and refresh preview instantly
- Basic validation (HTML errors, missing closing tags)

**Implementation:**
- Add Monaco Editor component (lazy load to save bundle size)
- `PUT /api/sessions/{id}/files/{path}` to save file changes
- WebSocket event to push updated files to sandbox
- Show file tree with edit icons

---

## 7. Default Prompt Settings

Customize the default system prompt so all generated websites follow our style guidelines.

**Default rules to add:**
- Always use Plus Jakarta Sans font (from Google Fonts)
- Use Tailwind CSS icons, never emojis
- Color palette: navy blue (#0a0a1a) and light blue/cyan (#00d4ff), never purple
- Footer copyright year: 2025
- Responsive design required
- Clean, professional aesthetic

**Implementation:**
Add a `SYSTEM_PROMPT` constant in `agent.py` that gets prepended to every user prompt:

```python
SYSTEM_PROMPT = """
Design Guidelines:
- Font: Plus Jakarta Sans (Google Fonts)
- Icons: Tailwind CSS / Lucide icons only, no emojis
- Colors: Navy blue (#0a0a1a) background, cyan (#00d4ff) accents
- Year: 2025 for all copyright notices
- Always responsive design
"""
```

---

## Nice to Have (Later)

- Dark mode
- Responsive preview (mobile/tablet/desktop)
- Code editor to manually tweak files
- Template library for quick starts
- Real-time collaboration
