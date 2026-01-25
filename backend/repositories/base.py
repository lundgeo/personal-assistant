"""Abstract base repository for tool storage."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolEntity:
    """Data transfer object for tools - decoupled from any storage implementation."""
    name: str
    description: str
    default_context: str
    id: Optional[int] = None
    custom_context: Optional[str] = None
    enabled: bool = True
    source: str = 'built-in'
    mcp_server_name: Optional[str] = None
    tool_schema: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'default_context': self.default_context,
            'custom_context': self.custom_context,
            'enabled': self.enabled,
            'source': self.source,
            'mcp_server_name': self.mcp_server_name,
            'tool_schema': self.tool_schema,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def get_context(self) -> str:
        """Get the effective context (custom if set, otherwise default)."""
        return self.custom_context if self.custom_context else self.default_context

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolEntity':
        """Create a ToolEntity from a dictionary."""
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data.get('id'),
            name=data['name'],
            description=data['description'],
            default_context=data['default_context'],
            custom_context=data.get('custom_context'),
            enabled=data.get('enabled', True),
            source=data.get('source', 'built-in'),
            mcp_server_name=data.get('mcp_server_name'),
            tool_schema=data.get('tool_schema'),
            created_at=created_at,
            updated_at=updated_at
        )


class ToolRepository(ABC):
    """Abstract repository for tool persistence operations."""

    @abstractmethod
    def get_all(self) -> List[ToolEntity]:
        """Retrieve all tools."""
        pass

    @abstractmethod
    def get_by_id(self, tool_id: int) -> Optional[ToolEntity]:
        """Retrieve a tool by its ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[ToolEntity]:
        """Retrieve a tool by its name."""
        pass

    @abstractmethod
    def get_enabled(self) -> List[ToolEntity]:
        """Retrieve all enabled tools."""
        pass

    @abstractmethod
    def create(self, tool: ToolEntity) -> ToolEntity:
        """Create a new tool."""
        pass

    @abstractmethod
    def update(self, tool_id: int, updates: Dict[str, Any]) -> Optional[ToolEntity]:
        """Update an existing tool."""
        pass

    @abstractmethod
    def delete(self, tool_id: int) -> bool:
        """Delete a tool by ID."""
        pass

    @abstractmethod
    def delete_by_mcp_server(self, server_name: str) -> int:
        """Delete all tools from a specific MCP server. Returns count deleted."""
        pass

    @abstractmethod
    def get_by_mcp_server(self, server_name: str) -> List[ToolEntity]:
        """Get all tools from a specific MCP server."""
        pass

    @abstractmethod
    def initialize_defaults(self) -> None:
        """Initialize default built-in tools if they don't exist."""
        pass
