# Personal Assistant Chatbot

A full-stack chatbot application with a Flask backend using LangChain and a Next.js frontend.

## Project Structure

```
.
├── backend/          # Flask API with LangChain
│   ├── app.py        # Main Flask application
│   ├── pyproject.toml # uv package configuration
│   └── README.md
└── frontend/         # Next.js web application
    ├── app/          # Next.js app directory
    └── README.md
```

## Quick Start

### Backend

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a `.env` file with your OpenAI API key:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. Install dependencies with uv:
```bash
uv sync
```

4. Run the Flask server:
```bash
uv run python app.py
```

The backend will run on http://localhost:5000

### Frontend

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

The frontend will run on http://localhost:3000

## Features

- **Backend**:
  - Flask REST API with CORS support
  - LangChain integration with OpenAI
  - Server-Sent Events (SSE) for streaming responses
  - uv for fast, reliable Python package management

- **Frontend**:
  - Modern Next.js 15 with React 19
  - TypeScript for type safety
  - Tailwind CSS for styling
  - Real-time streaming message display
  - Responsive chat interface

## Tech Stack

- **Backend**: Flask, LangChain, OpenAI, Python 3.11+
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Package Management**: uv (backend), npm (frontend)