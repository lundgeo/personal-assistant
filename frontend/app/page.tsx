'use client';

import { useState, useRef, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import UserButton from './components/UserButton';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Tool {
  id: number;
  name: string;
  description: string;
  default_context: string;
  custom_context: string | null;
  enabled: boolean;
  source: string;
  mcp_server_name: string | null;
  tool_schema: string | null;
}

interface MCPServer {
  name: string;
  transport: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
}

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [tools, setTools] = useState<Tool[]>([]);
  const [showToolsPanel, setShowToolsPanel] = useState(false);
  const [editingTool, setEditingTool] = useState<Tool | null>(null);
  const [editContext, setEditContext] = useState('');
  const [mcpServers, setMcpServers] = useState<Record<string, MCPServer>>({});
  const [showMcpModal, setShowMcpModal] = useState(false);
  const [newServerName, setNewServerName] = useState('');
  const [newServerTransport, setNewServerTransport] = useState<'stdio' | 'http'>('stdio');
  const [newServerCommand, setNewServerCommand] = useState('');
  const [newServerArgs, setNewServerArgs] = useState('');
  const [newServerUrl, setNewServerUrl] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login');
    }
  }, [status, router]);

  // Helper function to get auth headers
  const getAuthHeaders = () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (session?.idToken) {
      headers['Authorization'] = `Bearer ${session.idToken}`;
    }
    return headers;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchTools = async () => {
    if (!session?.idToken) return;
    try {
      const response = await fetch('http://localhost:3001/tools', {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setTools(data);
      }
    } catch (error) {
      console.error('Error fetching tools:', error);
    }
  };

  const fetchMcpServers = async () => {
    if (!session?.idToken) return;
    try {
      const response = await fetch('http://localhost:3001/mcp-servers', {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setMcpServers(data);
      }
    } catch (error) {
      console.error('Error fetching MCP servers:', error);
    }
  };

  const handleAddMcpServer = async () => {
    if (!newServerName) return;
    if (newServerTransport === 'stdio' && !newServerCommand) return;
    if (newServerTransport === 'http' && !newServerUrl) return;

    try {
      const requestBody: any = {
        name: newServerName,
        transport: newServerTransport,
      };

      if (newServerTransport === 'stdio') {
        const args = newServerArgs ? newServerArgs.split(' ').filter(arg => arg.trim()) : [];
        requestBody.command = newServerCommand;
        requestBody.args = args;
        requestBody.env = {};
      } else if (newServerTransport === 'http') {
        requestBody.url = newServerUrl;
        requestBody.headers = {};
      }

      const response = await fetch('http://localhost:3001/mcp-servers', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        await fetchMcpServers();
        await fetchTools();
        setShowMcpModal(false);
        setNewServerName('');
        setNewServerTransport('stdio');
        setNewServerCommand('');
        setNewServerArgs('');
        setNewServerUrl('');
      }
    } catch (error) {
      console.error('Error adding MCP server:', error);
    }
  };

  const handleDeleteMcpServer = async (serverName: string) => {
    if (!confirm(`Are you sure you want to delete the "${serverName}" MCP server?`)) return;

    try {
      const response = await fetch(`http://localhost:3001/mcp-servers/${serverName}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (response.ok) {
        await fetchMcpServers();
        await fetchTools();
      }
    } catch (error) {
      console.error('Error deleting MCP server:', error);
    }
  };

  const handleSyncMcpTools = async () => {
    try {
      const response = await fetch('http://localhost:3001/mcp-servers/sync', {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (response.ok) {
        await fetchTools();
      }
    } catch (error) {
      console.error('Error syncing MCP tools:', error);
    }
  };

  const handleToolEdit = (tool: Tool) => {
    setEditingTool(tool);
    setEditContext(tool.custom_context || tool.default_context);
  };

  const handleToolSave = async () => {
    if (!editingTool) return;

    try {
      const response = await fetch(`http://localhost:3001/tools/${editingTool.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_context: editContext }),
      });

      if (response.ok) {
        await fetchTools();
        setEditingTool(null);
        setEditContext('');
      }
    } catch (error) {
      console.error('Error updating tool:', error);
    }
  };

  const handleToolToggle = async (tool: Tool) => {
    try {
      const response = await fetch(`http://localhost:3001/tools/${tool.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ enabled: !tool.enabled }),
      });

      if (response.ok) {
        await fetchTools();
      }
    } catch (error) {
      console.error('Error toggling tool:', error);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (session?.idToken) {
      fetchTools();
      fetchMcpServers();
    }
  }, [session?.idToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setIsLoading(true);

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Add empty assistant message that will be filled with streaming content
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const response = await fetch('http://localhost:3001/chat', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ message: userMessage }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                accumulatedContent += parsed.content;
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = {
                    role: 'assistant',
                    content: accumulatedContent,
                  };
                  return newMessages;
                });
              }
              if (parsed.error) {
                console.error('Error from backend:', parsed.error);
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = {
                    role: 'assistant',
                    content: `Error: ${parsed.error}`,
                  };
                  return newMessages;
                });
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = {
          role: 'assistant',
          content: 'Sorry, there was an error processing your request.',
        };
        return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Show loading state while checking authentication
  if (status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  // Don't render if not authenticated (will redirect)
  if (status === 'unauthenticated') {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Tools Panel */}
      <div className={`${showToolsPanel ? 'w-80' : 'w-0'} transition-all duration-300 overflow-hidden border-r border-gray-200 bg-white flex flex-col`}>
        <div className="p-4 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-800">Tools</h2>
            <button
              onClick={handleSyncMcpTools}
              className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
              title="Sync MCP tools"
            >
              Sync
            </button>
          </div>

          {/* Built-in Tools */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Built-in Tools</h3>
            <div className="space-y-3">
              {tools.filter(t => t.source === 'built-in').map(tool => (
                <div key={tool.id} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-800">{tool.name.replace(/_/g, ' ')}</h3>
                      <p className="text-xs text-gray-500 mt-1">{tool.description}</p>
                    </div>
                    <button
                      onClick={() => handleToolToggle(tool)}
                      className={`ml-2 px-2 py-1 rounded text-xs ${
                        tool.enabled
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {tool.enabled ? 'ON' : 'OFF'}
                    </button>
                  </div>
                  <button
                    onClick={() => handleToolEdit(tool)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Edit Context
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* MCP Tools */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">MCP Tools</h3>
            {tools.filter(t => t.source === 'mcp').length === 0 ? (
              <p className="text-xs text-gray-400 italic">No MCP tools available. Add an MCP server below.</p>
            ) : (
              <div className="space-y-3">
                {tools.filter(t => t.source === 'mcp').map(tool => (
                  <div key={tool.id} className="border border-purple-200 rounded-lg p-3 bg-purple-50">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-800">{tool.name.replace(/_/g, ' ')}</h3>
                        <p className="text-xs text-gray-500 mt-1">{tool.description}</p>
                        <p className="text-xs text-purple-600 mt-1">Server: {tool.mcp_server_name}</p>
                      </div>
                      <button
                        onClick={() => handleToolToggle(tool)}
                        className={`ml-2 px-2 py-1 rounded text-xs ${
                          tool.enabled
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {tool.enabled ? 'ON' : 'OFF'}
                      </button>
                    </div>
                    <button
                      onClick={() => handleToolEdit(tool)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Edit Context
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* MCP Servers */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-600">MCP Servers</h3>
              <button
                onClick={() => setShowMcpModal(true)}
                className="text-xs px-2 py-1 bg-purple-50 text-purple-600 rounded hover:bg-purple-100"
              >
                Add Server
              </button>
            </div>
            {Object.keys(mcpServers).length === 0 ? (
              <p className="text-xs text-gray-400 italic">No MCP servers configured</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(mcpServers).map(([name, server]) => (
                  <div key={name} className="border border-gray-200 rounded p-2 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-semibold text-gray-800">{name}</p>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            server.transport === 'http'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-gray-200 text-gray-700'
                          }`}>
                            {server.transport || 'stdio'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {server.transport === 'http' ? server.url : server.command}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDeleteMcpServer(name)}
                        className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit Tool Modal */}
      {editingTool && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4">
            <h3 className="text-xl font-bold text-gray-800 mb-4">
              Edit {editingTool.name.replace(/_/g, ' ')} Context
            </h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Default Context:
              </label>
              <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded border border-gray-200">
                {editingTool.default_context}
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Custom Context:
              </label>
              <textarea
                value={editContext}
                onChange={(e) => setEditContext(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800"
                rows={4}
                placeholder="Enter custom context for this tool..."
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setEditingTool(null);
                  setEditContext('');
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleToolSave}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add MCP Server Modal */}
      {showMcpModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4">
            <h3 className="text-xl font-bold text-gray-800 mb-4">
              Add MCP Server
            </h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Server Name:
              </label>
              <input
                type="text"
                value={newServerName}
                onChange={(e) => setNewServerName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-800"
                placeholder="e.g., filesystem, weather, etc."
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Transport Type:
              </label>
              <select
                value={newServerTransport}
                onChange={(e) => setNewServerTransport(e.target.value as 'stdio' | 'http')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-800"
              >
                <option value="stdio">Local (stdio) - Run command locally</option>
                <option value="http">Remote (HTTP) - Connect to remote MCP server</option>
              </select>
            </div>

            {newServerTransport === 'stdio' ? (
              <>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Command:
                  </label>
                  <input
                    type="text"
                    value={newServerCommand}
                    onChange={(e) => setNewServerCommand(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-800"
                    placeholder="e.g., npx, python, node, etc."
                  />
                </div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Arguments (space-separated):
                  </label>
                  <input
                    type="text"
                    value={newServerArgs}
                    onChange={(e) => setNewServerArgs(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-800"
                    placeholder="e.g., -y @modelcontextprotocol/server-filesystem /path/to/dir"
                  />
                </div>
              </>
            ) : (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Server URL:
                </label>
                <input
                  type="text"
                  value={newServerUrl}
                  onChange={(e) => setNewServerUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-800"
                  placeholder="e.g., http://localhost:8000/mcp or https://mcp.example.com"
                />
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowMcpModal(false);
                  setNewServerName('');
                  setNewServerTransport('stdio');
                  setNewServerCommand('');
                  setNewServerArgs('');
                  setNewServerUrl('');
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleAddMcpServer}
                className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
              >
                Add Server
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col flex-1">
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">AI Chatbot</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowToolsPanel(!showToolsPanel)}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              {showToolsPanel ? 'Hide Tools' : 'Show Tools'}
            </button>
            <UserButton />
          </div>
        </header>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-20">
              <p className="text-lg">Start a conversation with the AI assistant</p>
              <p className="text-sm mt-2">Type your message below to get started</p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${message.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-gray-800 border border-gray-200'
                    }`}
                >
                  {message.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message..."
                disabled={isLoading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed text-gray-800"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
