from langchain_core.tools import tool, StructuredTool
from typing import Optional
import math
import re
import asyncio
import json
from mcp_manager import mcp_manager

@tool
def web_search(query: str) -> str:
    """Search the web for current information.

    Args:
        query: The search query string

    Returns:
        Search results or simulated results
    """
    # For demonstration purposes, this is a mock implementation
    # In production, you would integrate with a real search API
    return f"Search results for '{query}': This is a demonstration. In a real implementation, this would return actual search results from a search engine API."

@tool
def calculator(expression: str) -> str:
    """Perform mathematical calculations.

    Args:
        expression: A mathematical expression to evaluate

    Returns:
        The result of the calculation
    """
    try:
        # Clean the expression - only allow numbers, operators, parentheses, and common functions
        allowed = re.compile(r'^[\d\s\+\-\*/\(\)\.\^%]+$')
        if not allowed.match(expression):
            return f"Error: Invalid expression. Only basic mathematical operations are allowed."

        # Replace ^ with ** for exponentiation
        expression = expression.replace('^', '**')

        # Safely evaluate the expression
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return f"The result of {expression.replace('**', '^')} is {result}"
    except Exception as e:
        return f"Error calculating expression: {str(e)}"

@tool
def code_executor(code: str) -> str:
    """Execute Python code safely (demonstration only - not actually executing).

    Args:
        code: Python code to execute

    Returns:
        The output or error from code execution
    """
    # For security reasons, this is a mock implementation
    # In production, you would use a sandboxed environment
    return f"Code execution (demonstration mode):\n\nCode:\n{code}\n\nNote: For security reasons, code execution is disabled in this demo. In a production environment, this would run in a sandboxed container."

@tool
def file_analyzer(filename: str) -> str:
    """Analyze and summarize file contents.

    Args:
        filename: The name of the file to analyze

    Returns:
        Analysis and summary of the file
    """
    # This is a mock implementation
    # In production, you would read and analyze actual files
    return f"File analysis for '{filename}': This is a demonstration. In a real implementation, this would read and analyze the actual file content."

# Map of tool names to tool functions
TOOL_MAP = {
    'web_search': web_search,
    'calculator': calculator,
    'code_executor': code_executor,
    'file_analyzer': file_analyzer
}

def create_mcp_tool_wrapper(tool_config):
    """Create a LangChain tool wrapper for an MCP tool.

    Args:
        tool_config: Tool configuration dictionary

    Returns:
        A LangChain StructuredTool
    """
    server_name = tool_config['mcp_server_name']
    # Extract the actual tool name (remove server prefix)
    tool_name = tool_config['name'].replace(f"{server_name}_", "")

    def sync_mcp_call(**kwargs) -> str:
        """Synchronous wrapper for async MCP tool call."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            mcp_manager.call_mcp_tool(server_name, tool_name, kwargs)
        )
        loop.close()
        return result

    # Parse schema if available
    args_schema = None
    if tool_config.get('tool_schema'):
        try:
            schema_dict = json.loads(tool_config['tool_schema'])
            # The schema can be used to validate arguments
            # For now, we'll use a simple dict-based approach
            args_schema = schema_dict
        except:
            pass

    return StructuredTool.from_function(
        func=sync_mcp_call,
        name=tool_config['name'],
        description=tool_config['description'],
    )

def get_enabled_tools(tool_configs):
    """Get enabled tools with their custom context applied.

    Args:
        tool_configs: List of tool configuration dictionaries

    Returns:
        List of enabled tool functions
    """
    enabled_tools = []
    for config in tool_configs:
        if not config['enabled']:
            continue

        # Handle built-in tools
        if config.get('source') == 'built-in' and config['name'] in TOOL_MAP:
            tool_func = TOOL_MAP[config['name']]
            enabled_tools.append(tool_func)

        # Handle MCP tools
        elif config.get('source') == 'mcp':
            mcp_tool = create_mcp_tool_wrapper(config)
            enabled_tools.append(mcp_tool)

    return enabled_tools

def build_tool_context(tool_configs):
    """Build additional context from custom tool prompts.

    Args:
        tool_configs: List of tool configuration dictionaries

    Returns:
        String containing custom context for all enabled tools
    """
    context_parts = []
    for config in tool_configs:
        if config['enabled'] and config.get('custom_context'):
            context_parts.append(f"{config['name']}: {config['custom_context']}")

    if context_parts:
        return "Tool-specific instructions:\n" + "\n".join(context_parts)
    return ""
