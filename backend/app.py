from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json
import os
from database import db, Tool, init_db
from tools import get_enabled_tools, build_tool_context

load_dotenv()

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

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

@app.route('/tools', methods=['GET'])
def get_tools():
    """Get all available tools with their configurations."""
    tools = Tool.query.all()
    return jsonify([tool.to_dict() for tool in tools]), 200

@app.route('/tools/<int:tool_id>', methods=['PUT'])
def update_tool(tool_id):
    """Update a tool's custom context and enabled status."""
    tool = Tool.query.get_or_404(tool_id)
    data = request.json

    if 'custom_context' in data:
        tool.custom_context = data['custom_context']
    if 'enabled' in data:
        tool.enabled = data['enabled']

    db.session.commit()
    return jsonify(tool.to_dict()), 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return {'error': 'No message provided'}, 400

    def generate():
        try:
            # Get enabled tools from database
            tools_query = Tool.query.filter_by(enabled=True).all()
            tool_configs = [tool.to_dict() for tool in tools_query]

            # Get tool functions
            tools = get_enabled_tools(tool_configs)

            # Build system message with tool context
            base_context = "You are a helpful AI assistant."
            tool_context = build_tool_context(tool_configs)

            if tool_context:
                system_content = f"{base_context}\n\n{tool_context}"
            else:
                system_content = base_context

            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_message)
            ]

            # Bind tools to the LLM if tools are available
            if tools:
                llm_with_tools = llm.bind_tools(tools)
            else:
                llm_with_tools = llm

            # Stream the response
            for chunk in llm_with_tools.stream(messages):
                content = chunk.content
                if content:
                    # Send as JSON with newline delimiter
                    yield f"data: {json.dumps({'content': content})}\n\n"

                # Handle tool calls if present
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    for tool_call in chunk.tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        yield f"data: {json.dumps({'content': f' [Using tool: {tool_name}]'})}\n\n"

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
    app.run(debug=True, host='0.0.0.0', port=3001)
