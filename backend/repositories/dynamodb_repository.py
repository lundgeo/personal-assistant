"""DynamoDB implementation of the tool repository for AWS deployment."""
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from .base import ToolRepository, ToolEntity


class DynamoDBToolRepository(ToolRepository):
    """DynamoDB implementation of ToolRepository for AWS Lambda deployment."""

    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or os.environ.get('DYNAMODB_TABLE_NAME', 'personal-assistant-tools')
        self._table = None
        self._counter_table = None

    @property
    def table(self):
        """Lazy initialization of DynamoDB table resource."""
        if self._table is None:
            dynamodb = boto3.resource('dynamodb')
            self._table = dynamodb.Table(self.table_name)
        return self._table

    @property
    def counter_table(self):
        """Table for managing auto-increment IDs."""
        if self._counter_table is None:
            dynamodb = boto3.resource('dynamodb')
            self._counter_table = dynamodb.Table(f"{self.table_name}-counters")
        return self._counter_table

    def _get_next_id(self) -> int:
        """Get the next auto-increment ID."""
        response = self.counter_table.update_item(
            Key={'counter_name': 'tool_id'},
            UpdateExpression='SET counter_value = if_not_exists(counter_value, :start) + :inc',
            ExpressionAttributeValues={':start': 0, ':inc': 1},
            ReturnValues='UPDATED_NEW'
        )
        return int(response['Attributes']['counter_value'])

    def _item_to_entity(self, item: Dict[str, Any]) -> ToolEntity:
        """Convert a DynamoDB item to a ToolEntity."""
        return ToolEntity(
            id=int(item['id']),
            name=item['name'],
            description=item['description'],
            default_context=item['default_context'],
            custom_context=item.get('custom_context'),
            enabled=item.get('enabled', True),
            source=item.get('source', 'built-in'),
            mcp_server_name=item.get('mcp_server_name'),
            tool_schema=item.get('tool_schema'),
            created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
            updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
        )

    def _entity_to_item(self, entity: ToolEntity) -> Dict[str, Any]:
        """Convert a ToolEntity to a DynamoDB item."""
        item = {
            'id': entity.id,
            'name': entity.name,
            'description': entity.description,
            'default_context': entity.default_context,
            'enabled': entity.enabled,
            'source': entity.source,
            'created_at': entity.created_at.isoformat() if entity.created_at else datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        if entity.custom_context:
            item['custom_context'] = entity.custom_context
        if entity.mcp_server_name:
            item['mcp_server_name'] = entity.mcp_server_name
        if entity.tool_schema:
            item['tool_schema'] = entity.tool_schema

        return item

    def get_all(self) -> List[ToolEntity]:
        """Retrieve all tools."""
        response = self.table.scan()
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        return [self._item_to_entity(item) for item in items]

    def get_by_id(self, tool_id: int) -> Optional[ToolEntity]:
        """Retrieve a tool by its ID."""
        response = self.table.query(
            KeyConditionExpression=Key('id').eq(tool_id)
        )
        items = response.get('Items', [])
        return self._item_to_entity(items[0]) if items else None

    def get_by_name(self, name: str) -> Optional[ToolEntity]:
        """Retrieve a tool by its name."""
        response = self.table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(name)
        )
        items = response.get('Items', [])
        return self._item_to_entity(items[0]) if items else None

    def get_enabled(self) -> List[ToolEntity]:
        """Retrieve all enabled tools."""
        response = self.table.scan(
            FilterExpression=Attr('enabled').eq(True)
        )
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(
                FilterExpression=Attr('enabled').eq(True),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        return [self._item_to_entity(item) for item in items]

    def create(self, tool: ToolEntity) -> ToolEntity:
        """Create a new tool."""
        tool.id = self._get_next_id()
        tool.created_at = datetime.utcnow()
        tool.updated_at = datetime.utcnow()

        item = self._entity_to_item(tool)
        self.table.put_item(Item=item)
        return tool

    def update(self, tool_id: int, updates: Dict[str, Any]) -> Optional[ToolEntity]:
        """Update an existing tool."""
        existing = self.get_by_id(tool_id)
        if not existing:
            return None

        updates['updated_at'] = datetime.utcnow().isoformat()

        update_expression_parts = []
        expression_values = {}
        expression_names = {}

        for key, value in updates.items():
            safe_key = f"#{key}"
            expression_names[safe_key] = key
            expression_values[f":{key}"] = value
            update_expression_parts.append(f"{safe_key} = :{key}")

        update_expression = "SET " + ", ".join(update_expression_parts)

        self.table.update_item(
            Key={'id': tool_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values
        )

        return self.get_by_id(tool_id)

    def delete(self, tool_id: int) -> bool:
        """Delete a tool by ID."""
        try:
            self.table.delete_item(Key={'id': tool_id})
            return True
        except Exception:
            return False

    def delete_by_mcp_server(self, server_name: str) -> int:
        """Delete all tools from a specific MCP server."""
        tools = self.get_by_mcp_server(server_name)
        count = 0
        for tool in tools:
            if self.delete(tool.id):
                count += 1
        return count

    def get_by_mcp_server(self, server_name: str) -> List[ToolEntity]:
        """Get all tools from a specific MCP server."""
        response = self.table.scan(
            FilterExpression=Attr('source').eq('mcp') & Attr('mcp_server_name').eq(server_name)
        )
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(
                FilterExpression=Attr('source').eq('mcp') & Attr('mcp_server_name').eq(server_name),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        return [self._item_to_entity(item) for item in items]

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
            existing = self.get_by_name(tool_data['name'])
            if not existing:
                entity = ToolEntity(
                    name=tool_data['name'],
                    description=tool_data['description'],
                    default_context=tool_data['default_context'],
                    source='built-in'
                )
                self.create(entity)
