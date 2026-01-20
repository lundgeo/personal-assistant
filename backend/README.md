# Chatbot Backend

Flask-based chatbot backend using LangChain with streaming support for OpenAI, Claude (Anthropic), and local models via Ollama.

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

The backend supports OpenAI, Claude (Anthropic), and Ollama (local models) as LLM providers. Configure via environment variables in your `.env` file:

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

### Using Ollama (Local Models)

First, install Ollama from [https://ollama.ai](https://ollama.ai), then pull a model:
```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (e.g., llama3.2)
ollama pull llama3.2

# Verify Ollama is running
ollama list
```

Then configure your `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2  # or any other model you've pulled
OLLAMA_BASE_URL=http://localhost:11434  # default Ollama URL
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

**Ollama (Local Models):**
- `llama3.2` (default, latest Llama 3.2)
- `llama3.1` (Llama 3.1)
- `llama3` (Llama 3)
- `mistral` (Mistral 7B)
- `codellama` (Code-focused Llama)
- `phi3` (Microsoft Phi-3)
- `gemma2` (Google Gemma 2)
- And many more available at [https://ollama.ai/library](https://ollama.ai/library)

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
