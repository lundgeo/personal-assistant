"""
MCP Client Module

Provides functionality to connect to MCP servers via Streamable HTTP transport,
discover available tools, and execute tool calls.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from mcp_storage import get_storage, MCPServer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool with its server context."""
    server_id: str
    server_url: str
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPClientManager:
    """Manages connections to multiple MCP servers and aggregates their tools."""

    def __init__(self):
        self._tool_cache: dict[str, list[MCPTool]] = {}

    async def discover_tools(self, server: MCPServer) -> list[MCPTool]:
        """Discover available tools from an MCP server.

        Args:
            server: MCP server configuration

        Returns:
            List of tools available on the server
        """
        logger.info(f"Connecting to MCP server: {server.name} at {server.url}")
        try:
            async with streamablehttp_client(server.url) as (read_stream, write_stream, _):
                logger.debug(f"Connected to {server.url}, initializing session...")
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.debug("Session initialized, listing tools...")
                    tools_result = await session.list_tools()

                    mcp_tools = []
                    for tool in tools_result.tools:
                        mcp_tools.append(MCPTool(
                            server_id=server.id,
                            server_url=server.url,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        ))

                    self._tool_cache[server.id] = mcp_tools
                    logger.info(f"Discovered {len(mcp_tools)} tools from {server.name}: {[t.name for t in mcp_tools]}")
                    return mcp_tools

        except Exception as e:
            logger.error(f"Failed to discover tools from {server.url}: {e}", exc_info=True)
            return []

    async def get_all_tools(self) -> list[MCPTool]:
        """Get all tools from all registered MCP servers.

        Returns:
            Aggregated list of tools from all servers
        """
        storage = get_storage()
        servers = storage.list_servers()
        logger.info(f"Found {len(servers)} registered MCP server(s)")

        if not servers:
            logger.warning("No MCP servers registered. Register a server via POST /mcp-servers")
            return []

        all_tools = []
        for server in servers:
            logger.info(f"Querying server: {server.name} ({server.url})")
            tools = await self.discover_tools(server)
            all_tools.extend(tools)

        logger.info(f"Total tools discovered: {len(all_tools)}")
        return all_tools

    async def call_tool(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> str:
        """Execute a tool on an MCP server.

        Args:
            server_url: URL of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result as string
        """
        logger.info(f"Calling tool '{tool_name}' on {server_url} with args: {arguments}")
        try:
            async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
                logger.debug(f"Connected to {server_url} for tool call")
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.debug(f"Session initialized, calling tool {tool_name}...")
                    result = await session.call_tool(tool_name, arguments)
                    logger.debug(f"Tool call completed, processing result...")

                    # Extract text content from result
                    if result.content:
                        text_parts = []
                        for content in result.content:
                            if hasattr(content, 'text'):
                                text_parts.append(content.text)
                        output = "\n".join(text_parts)
                        logger.info(f"Tool '{tool_name}' returned {len(output)} chars")
                        return output

                    logger.warning(f"Tool '{tool_name}' returned no content")
                    return "Tool executed successfully (no output)"

        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_url}: {e}", exc_info=True)
            return f"Error executing tool: {str(e)}"


# Singleton instance
_client_manager: Optional[MCPClientManager] = None


def get_mcp_client() -> MCPClientManager:
    """Get the MCP client manager singleton."""
    global _client_manager
    if _client_manager is None:
        _client_manager = MCPClientManager()
    return _client_manager


def run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # We're in an async context, create a task
        return asyncio.ensure_future(coro)
    else:
        # We're in a sync context, run in new loop
        return asyncio.run(coro)
