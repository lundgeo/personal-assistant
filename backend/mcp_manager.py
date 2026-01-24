import json
import os
import asyncio
from typing import Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from database import db, Tool

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

    def add_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """Add a new MCP server to configuration."""
        self.servers[name] = {
            'command': command,
            'args': args or [],
            'env': env or {}
        }
        self.save_config()

    def remove_server(self, name: str):
        """Remove an MCP server from configuration."""
        if name in self.servers:
            del self.servers[name]
            self.save_config()
            return True
        return False

    async def discover_tools_from_server(self, server_name: str, server_config: dict) -> List[dict]:
        """Connect to an MCP server and discover its tools."""
        try:
            server_params = StdioServerParameters(
                command=server_config['command'],
                args=server_config.get('args', []),
                env=server_config.get('env', {})
            )

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
        except Exception as e:
            print(f"Error discovering tools from {server_name}: {str(e)}")
            return []

    async def discover_all_tools(self) -> List[dict]:
        """Discover tools from all configured MCP servers."""
        all_tools = []

        for server_name, server_config in self.servers.items():
            tools = await self.discover_tools_from_server(server_name, server_config)
            all_tools.extend(tools)

        return all_tools

    def sync_tools_to_database(self, app):
        """Synchronize discovered MCP tools to database."""
        with app.app_context():
            # Discover all tools synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            discovered_tools = loop.run_until_complete(self.discover_all_tools())
            loop.close()

            # Get existing MCP tools from database
            existing_mcp_tools = Tool.query.filter_by(source='mcp').all()
            existing_tool_names = {f"{tool.mcp_server_name}:{tool.name}" for tool in existing_mcp_tools}

            # Add new MCP tools to database
            for tool_data in discovered_tools:
                tool_key = f"{tool_data['server_name']}:{tool_data['name']}"

                if tool_key not in existing_tool_names:
                    # Create new tool entry
                    new_tool = Tool(
                        name=f"{tool_data['server_name']}_{tool_data['name']}",
                        description=tool_data['description'],
                        default_context=f"You are using the {tool_data['name']} tool from {tool_data['server_name']} MCP server.",
                        source='mcp',
                        mcp_server_name=tool_data['server_name'],
                        tool_schema=tool_data.get('schema'),
                        enabled=True
                    )
                    db.session.add(new_tool)

            # Remove tools from servers that no longer exist
            current_server_names = set(self.servers.keys())
            for tool in existing_mcp_tools:
                if tool.mcp_server_name not in current_server_names:
                    db.session.delete(tool)

            db.session.commit()

    async def call_mcp_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Call a tool on an MCP server."""
        if server_name not in self.servers:
            return f"Error: MCP server '{server_name}' not found"

        server_config = self.servers[server_name]

        try:
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
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

# Global MCP manager instance
mcp_manager = MCPManager()
