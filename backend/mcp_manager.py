import json
import os
import asyncio
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

if TYPE_CHECKING:
    from repositories.base import ToolRepository

class MCPManager:
    """Manager for MCP server connections and tool discovery."""

    def __init__(self, config_path='mcp_servers.json'):
        self.config_path = config_path
        self.servers = {}
        self.load_config()

    def load_config(self):
        """Load MCP server configuration from JSON file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.servers = config.get('mcpServers', {})
        else:
            self.servers = {}

    def save_config(self):
        """Save MCP server configuration to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump({'mcpServers': self.servers}, f, indent=2)

    def add_server(self, name: str, transport: str, command: str = None, args: List[str] = None,
                   env: Dict[str, str] = None, url: str = None, headers: Dict[str, str] = None):
        """Add a new MCP server to configuration.

        Args:
            name: Server name
            transport: 'stdio' for local process or 'http' for remote MCP server
            command: Command to run (for stdio transport)
            args: Command arguments (for stdio transport)
            env: Environment variables (for stdio transport)
            url: Server URL (for http transport)
            headers: HTTP headers (for http transport)
        """
        server_config = {'transport': transport}

        if transport == 'stdio':
            if not command:
                raise ValueError("command is required for stdio transport")
            server_config.update({
                'command': command,
                'args': args or [],
                'env': env or {}
            })
        elif transport == 'http':
            if not url:
                raise ValueError("url is required for http transport")
            server_config.update({
                'url': url,
                'headers': headers or {}
            })
        else:
            raise ValueError(f"Unsupported transport: {transport}. Use 'stdio' or 'http'")

        self.servers[name] = server_config
        self.save_config()

    def remove_server(self, name: str):
        """Remove an MCP server from configuration."""
        if name in self.servers:
            del self.servers[name]
            self.save_config()
            return True
        return False

    async def discover_tools_from_server(self, server_name: str, server_config: dict) -> List[dict]:
        """Connect to an MCP server and discover its tools.

        Raises exceptions on failure so callers can handle errors appropriately.
        """
        transport = server_config.get('transport', 'stdio')

        if transport == 'stdio':
            return await self._discover_tools_stdio(server_name, server_config)
        elif transport == 'http':
            return await self._discover_tools_http(server_name, server_config)
        else:
            raise ValueError(f"Unknown transport type: {transport}")

    async def _discover_tools_stdio(self, server_name: str, server_config: dict) -> List[dict]:
        """Discover tools from a stdio-based MCP server."""
        server_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config.get('args', []),
            env=server_config.get('env', {})
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # List available tools
                    tools_result = await session.list_tools()

                    discovered_tools = []
                    for tool in tools_result.tools:
                        discovered_tools.append({
                            'name': tool.name,
                            'description': tool.description or 'No description provided',
                            'server_name': server_name,
                            'schema': json.dumps(tool.inputSchema) if hasattr(tool, 'inputSchema') else None
                        })

                    return discovered_tools
        except ExceptionGroup as eg:
            # Extract the underlying exceptions from TaskGroup failures
            errors = [str(e) for e in eg.exceptions]
            raise ConnectionError(f"Failed to connect to stdio server: {'; '.join(errors)}")

    async def _discover_tools_http(self, server_name: str, server_config: dict) -> List[dict]:
        """Discover tools from a remote HTTP MCP server using streamable HTTP transport."""
        url = server_config['url']
        headers = server_config.get('headers', {}).copy()
        # Ensure required Accept header is present for MCP protocol
        headers.setdefault('Accept', 'application/json, text/event-stream')

        try:
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # List available tools
                    tools_result = await session.list_tools()

                    discovered_tools = []
                    for tool in tools_result.tools:
                        discovered_tools.append({
                            'name': tool.name,
                            'description': tool.description or 'No description provided',
                            'server_name': server_name,
                            'schema': json.dumps(tool.inputSchema) if hasattr(tool, 'inputSchema') else None
                        })

                    return discovered_tools
        except ExceptionGroup as eg:
            # Extract the underlying exceptions from TaskGroup failures
            errors = [str(e) for e in eg.exceptions]
            raise ConnectionError(f"Failed to connect to HTTP server at {url}: {'; '.join(errors)}")

    async def discover_all_tools(self) -> Tuple[List[dict], List[str]]:
        """Discover tools from all configured MCP servers.

        Returns:
            Tuple of (discovered_tools, errors) where errors is a list of error messages
        """
        all_tools = []
        errors = []

        for server_name, server_config in self.servers.items():
            try:
                tools = await self.discover_tools_from_server(server_name, server_config)
                all_tools.extend(tools)
            except Exception as e:
                error_msg = f"Failed to discover tools from {server_name}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)

        return all_tools, errors

    def sync_tools_to_database(self, repository: 'ToolRepository', server_name: str = None) -> dict:
        """Synchronize discovered MCP tools to database.

        Args:
            repository: ToolRepository instance for database operations
            server_name: Optional specific server to sync. If None, syncs all servers.

        Returns:
            Dictionary with 'tools_added', 'tools_removed', and 'errors' keys
        """
        from repositories.base import ToolEntity

        result = {'tools_added': 0, 'tools_removed': 0, 'errors': []}

        # Discover tools synchronously
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                discovered_tools, errors = loop.run_until_complete(self.discover_all_tools())
                result['errors'].extend(errors)
            finally:
                loop.close()
        except Exception as e:
            result['errors'].append(f"Failed to run tool discovery: {str(e)}")
            return result

        # Filter to specific server if requested
        if server_name:
            discovered_tools = [t for t in discovered_tools if t['server_name'] == server_name]

        # Get existing MCP tools from all servers
        all_tools = repository.get_all()
        existing_mcp_tools = [t for t in all_tools if t.source == 'mcp']
        existing_tool_keys = {
            f"{tool.mcp_server_name}:{tool.name.replace(f'{tool.mcp_server_name}_', '')}"
            for tool in existing_mcp_tools
        }

        # Add new MCP tools to database
        for tool_data in discovered_tools:
            tool_key = f"{tool_data['server_name']}:{tool_data['name']}"

            if tool_key not in existing_tool_keys:
                # Create new tool entry
                new_tool = ToolEntity(
                    name=f"{tool_data['server_name']}_{tool_data['name']}",
                    description=tool_data['description'],
                    default_context=f"You are using the {tool_data['name']} tool from {tool_data['server_name']} MCP server.",
                    source='mcp',
                    mcp_server_name=tool_data['server_name'],
                    tool_schema=tool_data.get('schema'),
                    enabled=True
                )
                repository.create(new_tool)
                result['tools_added'] += 1

        # Remove tools from servers that no longer exist
        current_server_names = set(self.servers.keys())
        for tool in existing_mcp_tools:
            if tool.mcp_server_name not in current_server_names:
                repository.delete(tool.id)
                result['tools_removed'] += 1

        return result

    async def call_mcp_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Call a tool on an MCP server."""
        if server_name not in self.servers:
            return f"Error: MCP server '{server_name}' not found"

        server_config = self.servers[server_name]
        transport = server_config.get('transport', 'stdio')

        try:
            if transport == 'stdio':
                return await self._call_tool_stdio(server_config, tool_name, arguments)
            elif transport == 'http':
                return await self._call_tool_http(server_config, tool_name, arguments)
            else:
                return f"Error: Unknown transport type '{transport}'"
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

    async def _call_tool_stdio(self, server_config: dict, tool_name: str, arguments: dict) -> str:
        """Call a tool on a stdio-based MCP server."""
        server_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config.get('args', []),
            env=server_config.get('env', {})
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments)

                # Extract text content from result
                if hasattr(result, 'content') and result.content:
                    return '\n'.join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])

                return str(result)

    async def _call_tool_http(self, server_config: dict, tool_name: str, arguments: dict) -> str:
        """Call a tool on a remote HTTP MCP server using streamable HTTP transport."""
        url = server_config['url']
        headers = server_config.get('headers', {}).copy()
        # Ensure required Accept header is present for MCP protocol
        headers.setdefault('Accept', 'application/json, text/event-stream')

        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments)

                # Extract text content from result
                if hasattr(result, 'content') and result.content:
                    return '\n'.join([
                        item.text if hasattr(item, 'text') else str(item)
                        for item in result.content
                    ])

                return str(result)

# Global MCP manager instance
mcp_manager = MCPManager()
