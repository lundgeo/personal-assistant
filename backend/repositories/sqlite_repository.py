"""SQLite implementation of the tool repository using Flask-SQLAlchemy."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from .base import ToolRepository, ToolEntity

db = SQLAlchemy()


class Tool(db.Model):
    """SQLAlchemy model for storing tool definitions."""
    __tablename__ = 'tools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    default_context = db.Column(db.Text, nullable=False)
    custom_context = db.Column(db.Text, nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(50), default='built-in')
    mcp_server_name = db.Column(db.String(100), nullable=True)
    tool_schema = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_entity(self) -> ToolEntity:
        """Convert SQLAlchemy model to ToolEntity."""
        return ToolEntity(
            id=self.id,
            name=self.name,
            description=self.description,
            default_context=self.default_context,
            custom_context=self.custom_context,
            enabled=self.enabled,
            source=self.source,
            mcp_server_name=self.mcp_server_name,
            tool_schema=self.tool_schema,
            created_at=self.created_at,
            updated_at=self.updated_at
        )


class SQLiteToolRepository(ToolRepository):
    """SQLite implementation of ToolRepository using Flask-SQLAlchemy."""

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the repository with a Flask app."""
        self.app = app
        db.init_app(app)
        with app.app_context():
            db.create_all()

    def get_all(self) -> List[ToolEntity]:
        """Retrieve all tools."""
        tools = Tool.query.all()
        return [tool.to_entity() for tool in tools]

    def get_by_id(self, tool_id: int) -> Optional[ToolEntity]:
        """Retrieve a tool by its ID."""
        tool = Tool.query.get(tool_id)
        return tool.to_entity() if tool else None

    def get_by_name(self, name: str) -> Optional[ToolEntity]:
        """Retrieve a tool by its name."""
        tool = Tool.query.filter_by(name=name).first()
        return tool.to_entity() if tool else None

    def get_enabled(self) -> List[ToolEntity]:
        """Retrieve all enabled tools."""
        tools = Tool.query.filter_by(enabled=True).all()
        return [tool.to_entity() for tool in tools]

    def create(self, tool: ToolEntity) -> ToolEntity:
        """Create a new tool."""
        db_tool = Tool(
            name=tool.name,
            description=tool.description,
            default_context=tool.default_context,
            custom_context=tool.custom_context,
            enabled=tool.enabled,
            source=tool.source,
            mcp_server_name=tool.mcp_server_name,
            tool_schema=tool.tool_schema
        )
        db.session.add(db_tool)
        db.session.commit()
        return db_tool.to_entity()

    def update(self, tool_id: int, updates: Dict[str, Any]) -> Optional[ToolEntity]:
        """Update an existing tool."""
        tool = Tool.query.get(tool_id)
        if not tool:
            return None

        for key, value in updates.items():
            if hasattr(tool, key):
                setattr(tool, key, value)

        db.session.commit()
        return tool.to_entity()

    def delete(self, tool_id: int) -> bool:
        """Delete a tool by ID."""
        tool = Tool.query.get(tool_id)
        if not tool:
            return False
        db.session.delete(tool)
        db.session.commit()
        return True

    def delete_by_mcp_server(self, server_name: str) -> int:
        """Delete all tools from a specific MCP server."""
        count = Tool.query.filter_by(source='mcp', mcp_server_name=server_name).delete()
        db.session.commit()
        return count

    def get_by_mcp_server(self, server_name: str) -> List[ToolEntity]:
        """Get all tools from a specific MCP server."""
        tools = Tool.query.filter_by(source='mcp', mcp_server_name=server_name).all()
        return [tool.to_entity() for tool in tools]

    def initialize_defaults(self) -> None:
        """Initialize default built-in tools if they don't exist."""
        default_tools = [
            {
                'name': 'web_search',
                'description': 'Search the web for current information',
                'default_context': 'You are searching the web to find current information. Provide accurate, up-to-date results based on the search query.'
            },
            {
                'name': 'calculator',
                'description': 'Perform mathematical calculations',
                'default_context': 'You are performing mathematical calculations. Calculate the expression accurately and show your work.'
            },
            {
                'name': 'code_executor',
                'description': 'Execute Python code safely',
                'default_context': 'You are executing Python code. Ensure the code is safe and provide the output of the execution.'
            },
            {
                'name': 'file_analyzer',
                'description': 'Analyze and summarize file contents',
                'default_context': 'You are analyzing a file. Provide a comprehensive summary and key insights from the content.'
            }
        ]

        for tool_data in default_tools:
            existing = Tool.query.filter_by(name=tool_data['name']).first()
            if not existing:
                tool = Tool(**tool_data)
                db.session.add(tool)

        db.session.commit()
