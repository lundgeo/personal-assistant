from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Tool(db.Model):
    """Model for storing tool definitions and custom context."""
    __tablename__ = 'tools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    default_context = db.Column(db.Text, nullable=False)
    custom_context = db.Column(db.Text, nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(50), default='built-in')  # 'built-in' or 'mcp'
    mcp_server_name = db.Column(db.String(100), nullable=True)  # Name of MCP server if source is 'mcp'
    tool_schema = db.Column(db.Text, nullable=True)  # JSON schema for MCP tools
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert tool to dictionary."""
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

    def get_context(self):
        """Get the effective context (custom if set, otherwise default)."""
        return self.custom_context if self.custom_context else self.default_context

def init_db(app):
    """Initialize database and create default tools."""
    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Create default tools if they don't exist
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
            existing_tool = Tool.query.filter_by(name=tool_data['name']).first()
            if not existing_tool:
                tool = Tool(**tool_data)
                db.session.add(tool)

        db.session.commit()
