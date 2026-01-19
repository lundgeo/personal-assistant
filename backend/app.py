from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
import json
import os

app = Flask(__name__)
CORS(app)

# Initialize LangChain LLM with streaming
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

parser = StrOutputParser()

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'healthy'}, 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return {'error': 'No message provided'}, 400

    def generate():
        try:
            messages = [
                SystemMessage(content="You are a helpful AI assistant."),
                HumanMessage(content=user_message)
            ]

            # Stream the response
            for chunk in llm.stream(messages):
                content = chunk.content
                if content:
                    # Send as JSON with newline delimiter
                    yield f"data: {json.dumps({'content': content})}\n\n"

            # Send completion signal
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
