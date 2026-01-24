"""
MCP Server Storage Module

This module provides an abstracted storage interface for MCP server configurations.
Currently uses in-memory storage, but the interface is designed to be easily
swapped for a more durable storage solution (e.g., SQLite, PostgreSQL, Redis).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional
import uuid


@dataclass
class MCPServer:
    """Represents an MCP server configuration."""
    id: str
    url: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self, include_secret: bool = False) -> dict:
        """Convert to dictionary, optionally excluding the client secret."""
        data = asdict(self)
        if not include_secret and data.get('client_secret'):
            data['client_secret'] = '********'
        return data


class MCPStorageBackend(ABC):
    """Abstract base class for MCP server storage backends."""

    @abstractmethod
    def list_servers(self) -> list[MCPServer]:
        """List all stored MCP servers."""
        pass

    @abstractmethod
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """Get a specific MCP server by ID."""
        pass

    @abstractmethod
    def add_server(self, url: str, client_id: Optional[str] = None,
                   client_secret: Optional[str] = None, name: Optional[str] = None) -> MCPServer:
        """Add a new MCP server configuration."""
        pass

    @abstractmethod
    def update_server(self, server_id: str, url: Optional[str] = None,
                      client_id: Optional[str] = None, client_secret: Optional[str] = None,
                      name: Optional[str] = None) -> Optional[MCPServer]:
        """Update an existing MCP server configuration."""
        pass

    @abstractmethod
    def delete_server(self, server_id: str) -> bool:
        """Delete an MCP server configuration. Returns True if deleted."""
        pass


class InMemoryMCPStorage(MCPStorageBackend):
    """In-memory storage backend for MCP servers.

    Note: Data is lost when the application restarts.
    For production use, implement a persistent backend like SQLiteMCPStorage.
    """

    def __init__(self):
        self._servers: dict[str, MCPServer] = {}

    def list_servers(self) -> list[MCPServer]:
        return list(self._servers.values())

    def get_server(self, server_id: str) -> Optional[MCPServer]:
        return self._servers.get(server_id)

    def add_server(self, url: str, client_id: Optional[str] = None,
                   client_secret: Optional[str] = None, name: Optional[str] = None) -> MCPServer:
        server_id = str(uuid.uuid4())
        server = MCPServer(
            id=server_id,
            url=url,
            client_id=client_id,
            client_secret=client_secret,
            name=name or url
        )
        self._servers[server_id] = server
        return server

    def update_server(self, server_id: str, url: Optional[str] = None,
                      client_id: Optional[str] = None, client_secret: Optional[str] = None,
                      name: Optional[str] = None) -> Optional[MCPServer]:
        server = self._servers.get(server_id)
        if not server:
            return None

        if url is not None:
            server.url = url
        if client_id is not None:
            server.client_id = client_id
        if client_secret is not None:
            server.client_secret = client_secret
        if name is not None:
            server.name = name

        return server

    def delete_server(self, server_id: str) -> bool:
        if server_id in self._servers:
            del self._servers[server_id]
            return True
        return False


# Default storage instance - can be replaced with a different backend
_storage: MCPStorageBackend = InMemoryMCPStorage()


def get_storage() -> MCPStorageBackend:
    """Get the current storage backend instance."""
    return _storage


def set_storage(storage: MCPStorageBackend) -> None:
    """Set a different storage backend (e.g., for testing or switching to persistent storage)."""
    global _storage
    _storage = storage
