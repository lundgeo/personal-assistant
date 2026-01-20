from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
import json
import os

app = Flask(__name__)
CORS(app)

# Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

def get_llm():
    """Initialize and return the appropriate LLM based on configuration."""
    if LLM_PROVIDER == "claude" or LLM_PROVIDER == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude")
        return ChatAnthropic(
            model=model,
            temperature=TEMPERATURE,
            streaming=True,
            anthropic_api_key=api_key
        )
    elif LLM_PROVIDER == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI")
        return ChatOpenAI(
            model=model,
            temperature=TEMPERATURE,
            streaming=True,
            openai_api_key=api_key
        )
    elif LLM_PROVIDER == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(
            model=model,
            temperature=TEMPERATURE,
            base_url=base_url,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}. Choose 'openai', 'claude', or 'ollama'")

# Initialize LangChain LLM with streaming
llm = get_llm()

parser = StrOutputParser()

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'healthy'}, 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return {'error': 'No message provided'}, 400

    def generate():
        try:
            messages = [
                SystemMessage(content="You are a helpful AI assistant."),
                HumanMessage(content=user_message)
            ]

            # Stream the response
            for chunk in llm.stream(messages):
                content = chunk.content
                if content:
                    # Send as JSON with newline delimiter
                    yield f"data: {json.dumps({'content': content})}\n\n"

            # Send completion signal
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
