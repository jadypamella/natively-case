# Website Builder

An AI-powered website builder that creates beautiful websites instantly using Claude AI.

## Features

- 🤖 AI-powered website generation
- 🎨 Live preview in iframe
- ⚡ Real-time development server
- 🔄 WebSocket updates for build progress

## Setup Backend

This project uses Modal for serverless deployment:

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Run `uv sync`
3. Run `uv run modal setup` to connect your Modal account
4. Add your Anthropic API key as a Modal secret: `modal secret create anthropic-secret ANTHROPIC_API_KEY=sk-...`
5. Deploy: `uv run modal deploy API.py`
6. Find your backend URL in the Modal dashboard

## Setup Frontend

1. Install pnpm: `npm install -g pnpm`
2. Navigate to the frontend: `cd appandrunning`
3. Create `.env.local` with: `NEXT_PUBLIC_API_URL=https://your-modal-url.modal.run`
4. Install dependencies: `pnpm i`
5. Run dev server: `pnpm run dev`
6. Open http://localhost:3000

## How It Works

1. User describes a website they want to build
2. Claude AI generates the HTML/CSS/JavaScript
3. A development server spins up in a Modal sandbox
4. The website is displayed live in an iframe
5. User can iterate with additional prompts