"""AWS Lambda handler for the Flask application.

This module provides the Lambda entry point that wraps the Flask application
for deployment behind API Gateway.
"""
import os
import json
import base64
from io import BytesIO
from urllib.parse import urlencode

# Set environment variables before importing app
os.environ.setdefault('DATABASE_TYPE', 'dynamodb')


def create_wsgi_environ(event, context):
    """Create a WSGI-compatible environ dict from API Gateway event."""
    # Handle both API Gateway v1 and v2 (HTTP API) formats
    is_v2 = event.get('version', '1.0') == '2.0'

    if is_v2:
        # HTTP API (API Gateway v2) format
        request_context = event.get('requestContext', {})
        http = request_context.get('http', {})

        method = http.get('method', 'GET')
        path = event.get('rawPath', '/')
        query_string = event.get('rawQueryString', '')

        # Headers are lowercase in v2
        headers = event.get('headers', {})
    else:
        # REST API (API Gateway v1) format
        method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')

        # Build query string from multiValueQueryStringParameters or queryStringParameters
        query_params = event.get('multiValueQueryStringParameters') or event.get('queryStringParameters') or {}
        if isinstance(query_params, dict):
            if event.get('multiValueQueryStringParameters'):
                # Multi-value format
                parts = []
                for key, values in query_params.items():
                    for value in values:
                        parts.append(f"{key}={value}")
                query_string = '&'.join(parts)
            else:
                # Single value format
                query_string = urlencode(query_params) if query_params else ''
        else:
            query_string = ''

        # Headers may be mixed case in v1
        headers = {}
        for key, value in (event.get('headers') or {}).items():
            headers[key.lower()] = value

    # Handle body
    body = event.get('body', '') or ''
    is_base64 = event.get('isBase64Encoded', False)

    if is_base64 and body:
        body = base64.b64decode(body)
    elif isinstance(body, str):
        body = body.encode('utf-8')

    content_length = len(body)
    body_file = BytesIO(body)

    # Build WSGI environ
    environ = {
        'REQUEST_METHOD': method,
        'SCRIPT_NAME': '',
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'CONTENT_TYPE': headers.get('content-type', ''),
        'CONTENT_LENGTH': str(content_length),
        'SERVER_NAME': headers.get('host', 'localhost'),
        'SERVER_PORT': headers.get('x-forwarded-port', '443'),
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https'),
        'wsgi.input': body_file,
        'wsgi.errors': BytesIO(),
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': True,
    }

    # Add HTTP headers
    for key, value in headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            environ[f'HTTP_{key}'] = value

    return environ


def handler(event, context):
    """AWS Lambda handler function.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response dict
    """
    # Import app here to ensure env vars are set
    from app import app

    # Create WSGI environ
    environ = create_wsgi_environ(event, context)

    # Response accumulator
    response_started = False
    response_headers = []
    status_code = 500
    response_body = []

    def start_response(status, headers, exc_info=None):
        nonlocal response_started, response_headers, status_code
        response_started = True
        status_code = int(status.split(' ')[0])
        response_headers = headers
        return response_body.append

    # Call the Flask application
    try:
        response = app.wsgi_app(environ, start_response)

        # Collect response body
        for chunk in response:
            if isinstance(chunk, bytes):
                response_body.append(chunk)
            else:
                response_body.append(chunk.encode('utf-8'))

        if hasattr(response, 'close'):
            response.close()

    except Exception as e:
        # Handle errors
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

    # Build response headers dict
    headers_dict = {}
    for name, value in response_headers:
        headers_dict[name] = value

    # Combine body
    body = b''.join(response_body)

    # Check if response should be base64 encoded
    content_type = headers_dict.get('Content-Type', '')
    is_binary = not (
        content_type.startswith('text/') or
        content_type.startswith('application/json') or
        'charset' in content_type.lower()
    )

    if is_binary:
        return {
            'statusCode': status_code,
            'headers': headers_dict,
            'body': base64.b64encode(body).decode('utf-8'),
            'isBase64Encoded': True
        }
    else:
        return {
            'statusCode': status_code,
            'headers': headers_dict,
            'body': body.decode('utf-8')
        }
