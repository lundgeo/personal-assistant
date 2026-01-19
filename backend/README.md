# Chatbot Backend

Flask-based chatbot backend using LangChain with streaming support.

## Setup

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create a `.env` file with your OpenAI API key:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. Install dependencies:
```bash
uv sync
```

## Running

Start the development server:
```bash
uv run python app.py
```

The server will run on `http://localhost:5000`

## Endpoints

- `GET /health` - Health check endpoint
- `POST /chat` - Chat endpoint with streaming support
  - Request body: `{"message": "your message here"}`
  - Response: Server-Sent Events (SSE) stream
