from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json
import os
from database import db, Tool, init_db
from tools import get_enabled_tools, build_tool_context
from mcp_manager import mcp_manager

load_dotenv()

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
init_db(app)

# Sync MCP tools after database initialization
try:
    sync_result = mcp_manager.sync_tools_to_database(app)
    if sync_result['errors']:
        print(f"Warning: Some MCP tools failed to sync: {sync_result['errors']}")
    if sync_result['tools_added'] > 0:
        print(f"Added {sync_result['tools_added']} MCP tools")
except Exception as e:
    print(f"Warning: Failed to sync MCP tools: {str(e)}")

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

@app.route('/mcp-servers', methods=['GET'])
def get_mcp_servers():
    """Get all configured MCP servers."""
    return jsonify(mcp_manager.servers), 200

@app.route('/mcp-servers', methods=['POST'])
def add_mcp_server():
    """Add a new MCP server."""
    data = request.json
    name = data.get('name')
    transport = data.get('transport', 'stdio')

    if not name:
        return {'error': 'Name is required'}, 400

    try:
        if transport == 'stdio':
            command = data.get('command')
            args = data.get('args', [])
            env = data.get('env', {})

            if not command:
                return {'error': 'Command is required for stdio transport'}, 400

            mcp_manager.add_server(name, transport, command=command, args=args, env=env)

        elif transport == 'http':
            url = data.get('url')
            headers = data.get('headers', {})

            if not url:
                return {'error': 'URL is required for http transport'}, 400

            mcp_manager.add_server(name, transport, url=url, headers=headers)

        else:
            return {'error': f'Unsupported transport type: {transport}'}, 400

        # Sync tools from new server
        sync_result = mcp_manager.sync_tools_to_database(app, server_name=name)

        response = {
            'message': 'MCP server added successfully',
            'tools_added': sync_result['tools_added']
        }

        if sync_result['errors']:
            response['warnings'] = sync_result['errors']

        return response, 201
    except Exception as e:
        return {'error': f'Failed to add server: {str(e)}'}, 500

@app.route('/mcp-servers/<server_name>', methods=['DELETE'])
def delete_mcp_server(server_name):
    """Delete an MCP server."""
    if mcp_manager.remove_server(server_name):
        # Remove associated tools from database
        Tool.query.filter_by(source='mcp', mcp_server_name=server_name).delete()
        db.session.commit()
        return {'message': 'MCP server deleted successfully'}, 200
    return {'error': 'MCP server not found'}, 404

@app.route('/mcp-servers/sync', methods=['POST'])
def sync_mcp_servers():
    """Manually trigger MCP tool sync."""
    try:
        sync_result = mcp_manager.sync_tools_to_database(app)
        response = {
            'message': 'MCP tools synced successfully',
            'tools_added': sync_result['tools_added'],
            'tools_removed': sync_result['tools_removed']
        }
        if sync_result['errors']:
            response['warnings'] = sync_result['errors']
        return response, 200
    except Exception as e:
        return {'error': f'Failed to sync tools: {str(e)}'}, 500

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

            # Build a map of tool name -> tool function for execution
            tool_map = {t.name: t for t in tools}

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

            # Tool execution loop - keep going until no more tool calls
            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Collect the full response (we need complete tool_calls before executing)
                full_response = None
                collected_content = []

                for chunk in llm_with_tools.stream(messages):
                    # Stream text content to the client
                    content = chunk.content
                    if content:
                        if isinstance(content, list):
                            content = ''.join(
                                block.get('text', '') if isinstance(block, dict) else str(block)
                                for block in content
                            )
                        elif not isinstance(content, str):
                            content = str(content)
                        if content:
                            collected_content.append(content)
                            yield f"data: {json.dumps({'content': content})}\n\n"

                    # Accumulate the full response to get complete tool calls
                    if full_response is None:
                        full_response = chunk
                    else:
                        full_response = full_response + chunk

                # Check if there are tool calls to execute
                if not full_response or not hasattr(full_response, 'tool_calls') or not full_response.tool_calls:
                    break  # No tool calls, we're done

                # Execute each tool call
                tool_results = []
                for tool_call in full_response.tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                    tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                    tool_id = tool_call.get('id') if isinstance(tool_call, dict) else getattr(tool_call, 'id', '')

                    if not tool_name:
                        continue

                    yield f"data: {json.dumps({'content': f' [Using tool: {tool_name}]'})}\n\n"

                    # Execute the tool
                    if tool_name in tool_map:
                        try:
                            tool_func = tool_map[tool_name]
                            result = tool_func.invoke(tool_args)
                            tool_results.append({
                                'tool_call_id': tool_id,
                                'name': tool_name,
                                'content': str(result)
                            })
                        except Exception as e:
                            tool_results.append({
                                'tool_call_id': tool_id,
                                'name': tool_name,
                                'content': f"Error executing tool: {str(e)}"
                            })
                    else:
                        tool_results.append({
                            'tool_call_id': tool_id,
                            'name': tool_name,
                            'content': f"Tool '{tool_name}' not found"
                        })

                # Add the assistant's response and tool results to messages
                messages.append(AIMessage(
                    content=''.join(collected_content),
                    tool_calls=full_response.tool_calls
                ))

                for result in tool_results:
                    messages.append(ToolMessage(
                        content=result['content'],
                        tool_call_id=result['tool_call_id']
                    ))

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
