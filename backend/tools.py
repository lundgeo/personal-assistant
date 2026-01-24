from langchain_core.tools import tool
from typing import Optional
import math
import re

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

def get_enabled_tools(tool_configs):
    """Get enabled tools with their custom context applied.

    Args:
        tool_configs: List of tool configuration dictionaries

    Returns:
        List of enabled tool functions
    """
    enabled_tools = []
    for config in tool_configs:
        if config['enabled'] and config['name'] in TOOL_MAP:
            tool_func = TOOL_MAP[config['name']]
            # The custom context will be included in the system message
            enabled_tools.append(tool_func)

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
