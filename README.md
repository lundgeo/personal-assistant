# Personal Assistant Chatbot

A full-stack chatbot application with a Flask backend using LangChain (supporting OpenAI, Claude, and local models via Ollama) and a Next.js frontend.

## Project Structure

```
.
├── backend/          # Flask API with LangChain
│   ├── app.py        # Main Flask application
│   ├── pyproject.toml # uv package configuration
│   └── README.md
└── frontend/         # Next.js web application
    ├── app/          # Next.js app directory
    └── README.md
```

## Quick Start

### Backend

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a `.env` file with your API configuration:
```bash
cp .env.example .env
# Edit .env and configure your preferred LLM provider (OpenAI, Claude, or Ollama)
```

3. Install dependencies with uv:
```bash
uv sync
```

4. Run the Flask server:
```bash
uv run python app.py
```

The backend will run on http://localhost:5000

### Frontend

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

The frontend will run on http://localhost:3000

## Features

- **Backend**:
  - Flask REST API with CORS support
  - LangChain integration with OpenAI, Claude (Anthropic), and Ollama (local models)
  - Configurable LLM provider via environment variables
  - Server-Sent Events (SSE) for streaming responses
  - uv for fast, reliable Python package management

- **Frontend**:
  - Modern Next.js 15 with React 19
  - TypeScript for type safety
  - Tailwind CSS for styling
  - Real-time streaming message display
  - Responsive chat interface

## Tech Stack

- **Backend**: Flask, LangChain, OpenAI, Anthropic (Claude), Ollama, Python 3.11+
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Package Management**: uv (backend), npm (frontend)

## LLM Provider Configuration

The backend supports OpenAI, Claude (Anthropic), and Ollama (local models). Set your preferred provider in the `.env` file:

**For OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-3.5-turbo
```

**For Claude:**
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**For Ollama (Local Models):**
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

Note: Ollama requires installation from [https://ollama.ai](https://ollama.ai) and pulling a model first (e.g., `ollama pull llama3.2`).

See `backend/README.md` for detailed configuration options and available models.