# Chatbot Backend

Flask-based chatbot backend using LangChain with streaming support for both OpenAI and Claude (Anthropic).

## Setup

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create a `.env` file with your API configuration:
```bash
cp .env.example .env
# Edit .env and configure your preferred LLM provider
```

3. Install dependencies:
```bash
uv sync
```

## Configuration

The backend supports both OpenAI and Claude (Anthropic) as LLM providers. Configure via environment variables in your `.env` file:

### Using OpenAI (default)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-3.5-turbo  # or gpt-4, gpt-4-turbo, etc.
TEMPERATURE=0.7
```

### Using Claude (Anthropic)
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # or other Claude models
TEMPERATURE=0.7
```

### Available Models

**OpenAI:**
- `gpt-3.5-turbo` (default, fast and cost-effective)
- `gpt-4`
- `gpt-4-turbo`
- `gpt-4o`

**Claude (Anthropic):**
- `claude-3-5-sonnet-20241022` (default, most capable)
- `claude-3-5-haiku-20241022` (fast and efficient)
- `claude-3-opus-20240229`

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
