from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import StructuredTool, BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field, create_model
from typing import Any, Optional
import asyncio
import json
import os
import time

from mcp_storage import get_storage
from mcp_client import get_mcp_client, MCPTool

load_dotenv()

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)

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


def json_schema_to_pydantic_field(prop_name: str, prop_schema: dict, required: bool):
    """Convert a JSON schema property to a Pydantic field definition."""
    json_type = prop_schema.get("type", "string")
    description = prop_schema.get("description", "")
    default = prop_schema.get("default", ... if required else None)

    # Map JSON schema types to Python types
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    python_type = type_map.get(json_type, str)

    # Make optional if not required
    if not required:
        python_type = Optional[python_type]

    return (python_type, Field(default=default, description=description))


def create_args_schema(mcp_tool: MCPTool):
    """Create a Pydantic model from MCP tool's input schema."""
    input_schema = mcp_tool.input_schema
    if not input_schema or "properties" not in input_schema:
        # No schema, return None to use default behavior
        return None

    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_definitions = {}
    for prop_name, prop_schema in properties.items():
        field_definitions[prop_name] = json_schema_to_pydantic_field(
            prop_name, prop_schema, prop_name in required
        )

    if not field_definitions:
        return None

    # Create a dynamic Pydantic model
    model = create_model(f"{mcp_tool.name}_args", **field_definitions)
    return model


def create_langchain_tool(mcp_tool: MCPTool) -> StructuredTool:
    """Create a LangChain StructuredTool from an MCP tool definition."""
    client = get_mcp_client()

    async def tool_func(**kwargs) -> str:
        return await client.call_tool(mcp_tool.server_url, mcp_tool.name, kwargs)

    def sync_tool_func(**kwargs) -> str:
        return asyncio.run(tool_func(**kwargs))

    args_schema = create_args_schema(mcp_tool)
    logger.debug(f"Created args_schema for {mcp_tool.name}: {args_schema}")

    return StructuredTool(
        name=mcp_tool.name,
        description=mcp_tool.description,
        args_schema=args_schema,
        func=sync_tool_func,
        coroutine=tool_func,
    )


async def get_langchain_tools() -> list[StructuredTool]:
    """Fetch all MCP tools and convert them to LangChain tools."""
    client = get_mcp_client()
    mcp_tools = await client.get_all_tools()
    return [create_langchain_tool(tool) for tool in mcp_tools]


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'healthy'}, 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    history = data.get('history', [])
    use_tools = data.get('use_tools', True)

    if not user_message:
        return {'error': 'No message provided'}, 400

    def generate():
        try:
            request_start = time.time()
            timings = {"request_start": request_start}

            # Discover available MCP tools
            tools = []
            tool_map = {}
            if use_tools:
                try:
                    timings["mcp_start"] = time.time()
                    tools = asyncio.run(get_langchain_tools())
                    tool_map = {tool.name: tool for tool in tools}
                    timings["mcp_end"] = time.time()
                    logger.info(f"[TIMING] MCP discovery: {timings['mcp_end'] - timings['mcp_start']:.2f}s ({len(tools)} tools)")
                except Exception as e:
                    # Log but continue without tools if MCP servers are unavailable
                    logger.warning(f"Could not load MCP tools: {e}", exc_info=True)

            system_prompt = "You are a helpful AI assistant."
            if tools:
                system_prompt += (
                    " You have access to tools that can help answer questions about "
                    "calendar events and scheduling. Use these tools when the user asks "
                    "about their calendar, upcoming events, or scheduling."
                )

            # Build messages from history
            messages = [SystemMessage(content=system_prompt)]
            for msg in history:
                if msg.get('role') == 'user':
                    messages.append(HumanMessage(content=msg.get('content', '')))
                elif msg.get('role') == 'assistant':
                    messages.append(AIMessage(content=msg.get('content', '')))
            # Add the current user message
            messages.append(HumanMessage(content=user_message))

            # Bind tools to LLM if available
            llm_with_tools = llm.bind_tools(tools) if tools else llm

            timings["setup_end"] = time.time()
            logger.info(f"[TIMING] Setup complete: {timings['setup_end'] - request_start:.2f}s")

            # Agent loop: handle tool calls
            max_iterations = 5
            for iteration in range(max_iterations):
                iter_start = time.time()
                first_chunk_time = None

                # Collect the full response to check for tool calls
                full_response = None
                buffered_content = []
                chunk_count = 0

                for chunk in llm_with_tools.stream(messages):
                    chunk_count += 1
                    if first_chunk_time is None:
                        first_chunk_time = time.time()

                    # Accumulate the full response for tool call detection
                    if full_response is None:
                        full_response = chunk
                    else:
                        full_response = full_response + chunk

                    # Buffer content - we'll only send it if there are no tool calls
                    if chunk.content:
                        content = chunk.content
                        if isinstance(content, list):
                            # Anthropic returns a list of content blocks
                            content = "".join(
                                block.get("text", "") if isinstance(block, dict) else str(block)
                                for block in content
                            )
                        if content:
                            buffered_content.append(content)

                iter_end = time.time()
                ttfc = (first_chunk_time - iter_start) if first_chunk_time else 0
                logger.info(f"[TIMING] Iteration {iteration + 1}: TTFC={ttfc:.2f}s, total={iter_end - iter_start:.2f}s, chunks={chunk_count}")

                # Check if the response contains tool calls
                if full_response and hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                    logger.info(f"[TIMING] Tool calls detected: {len(full_response.tool_calls)}, discarding {len(buffered_content)} content chunks")
                    messages.append(full_response)

                    # Execute each tool call
                    for tool_call in full_response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        tool_start = time.time()

                        if tool_name in tool_map:
                            tool = tool_map[tool_name]
                            try:
                                result = asyncio.run(
                                    tool.coroutine(**tool_args)
                                )
                                logger.info(f"[TIMING] Tool '{tool_name}': {time.time() - tool_start:.2f}s")
                            except Exception as e:
                                logger.error(f"[TIMING] Tool '{tool_name}' failed after {time.time() - tool_start:.2f}s: {e}")
                                result = f"Error calling tool: {str(e)}"
                        else:
                            logger.warning(f"Unknown tool requested: {tool_name}")
                            result = f"Unknown tool: {tool_name}"

                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tool_call['id']
                        ))

                    # Continue the loop to get the next response
                    continue

                # No tool calls - send the buffered content to the client
                for content in buffered_content:
                    yield f"data: {json.dumps({'content': content})}\n\n"

                total_time = time.time() - request_start
                logger.info(f"[TIMING] Request complete: {total_time:.2f}s total")
                break

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

# MCP Tool Discovery Endpoint

@app.route('/mcp-tools', methods=['GET'])
def list_mcp_tools():
    """List all available tools from registered MCP servers."""
    try:
        client = get_mcp_client()
        tools = asyncio.run(client.get_all_tools())
        return jsonify([{
            'server_id': tool.server_id,
            'name': tool.name,
            'description': tool.description,
            'input_schema': tool.input_schema
        } for tool in tools])
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/mcp-test', methods=['GET'])
def test_mcp_connection():
    """Test connectivity to all registered MCP servers."""
    storage = get_storage()
    servers = storage.list_servers()

    results = []
    for server in servers:
        try:
            client = get_mcp_client()
            tools = asyncio.run(client.discover_tools(server))
            results.append({
                'server': server.name,
                'url': server.url,
                'status': 'connected',
                'tools_count': len(tools),
                'tools': [t.name for t in tools]
            })
        except Exception as e:
            results.append({
                'server': server.name,
                'url': server.url,
                'status': 'error',
                'error': str(e)
            })

    return jsonify({
        'servers_count': len(servers),
        'results': results
    })


# MCP Server Management Endpoints

@app.route('/mcp-servers', methods=['GET'])
def list_mcp_servers():
    """List all configured MCP servers."""
    storage = get_storage()
    servers = storage.list_servers()
    return jsonify([server.to_dict(include_secret=False) for server in servers])


@app.route('/mcp-servers', methods=['POST'])
def add_mcp_server():
    """Add a new MCP server configuration."""
    data = request.json
    if not data or not data.get('url'):
        return jsonify({'error': 'URL is required'}), 400

    storage = get_storage()
    server = storage.add_server(
        url=data['url'],
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        name=data.get('name')
    )
    return jsonify(server.to_dict(include_secret=False)), 201


@app.route('/mcp-servers/<server_id>', methods=['GET'])
def get_mcp_server(server_id):
    """Get a specific MCP server by ID."""
    storage = get_storage()
    server = storage.get_server(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    return jsonify(server.to_dict(include_secret=False))


@app.route('/mcp-servers/<server_id>', methods=['PUT'])
def update_mcp_server(server_id):
    """Update an existing MCP server configuration."""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    storage = get_storage()
    server = storage.update_server(
        server_id=server_id,
        url=data.get('url'),
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        name=data.get('name')
    )
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    return jsonify(server.to_dict(include_secret=False))


@app.route('/mcp-servers/<server_id>', methods=['DELETE'])
def delete_mcp_server(server_id):
    """Delete an MCP server configuration."""
    storage = get_storage()
    if storage.delete_server(server_id):
        return '', 204
    return jsonify({'error': 'Server not found'}), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3001)
