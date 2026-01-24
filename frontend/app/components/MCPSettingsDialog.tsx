'use client';

import { useState, useEffect } from 'react';

interface MCPServer {
  id: string;
  url: string;
  client_id?: string;
  client_secret?: string;
  name?: string;
}

interface MCPTool {
  server_id: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

interface MCPSettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function MCPSettingsDialog({ isOpen, onClose }: MCPSettingsDialogProps) {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set());

  // Form state for adding new server
  const [newUrl, setNewUrl] = useState('');
  const [newClientId, setNewClientId] = useState('');
  const [newClientSecret, setNewClientSecret] = useState('');
  const [newName, setNewName] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const fetchServers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:3001/mcp-servers');
      if (!response.ok) throw new Error('Failed to fetch servers');
      const data = await response.json();
      setServers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load servers');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTools = async () => {
    setIsLoadingTools(true);
    try {
      const response = await fetch('http://localhost:3001/mcp-tools');
      if (!response.ok) throw new Error('Failed to fetch tools');
      const data = await response.json();
      setTools(data);
    } catch (err) {
      console.error('Failed to load tools:', err);
    } finally {
      setIsLoadingTools(false);
    }
  };

  const toggleServerExpanded = (serverId: string) => {
    setExpandedServers(prev => {
      const next = new Set(prev);
      if (next.has(serverId)) {
        next.delete(serverId);
      } else {
        next.add(serverId);
      }
      return next;
    });
  };

  const getToolsForServer = (serverId: string) => {
    return tools.filter(tool => tool.server_id === serverId);
  };

  useEffect(() => {
    if (isOpen) {
      fetchServers();
      fetchTools();
    }
  }, [isOpen]);

  const handleAddServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl.trim()) return;

    setIsAdding(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:3001/mcp-servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: newUrl.trim(),
          client_id: newClientId.trim() || undefined,
          client_secret: newClientSecret.trim() || undefined,
          name: newName.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to add server');
      }

      // Reset form and refresh list
      setNewUrl('');
      setNewClientId('');
      setNewClientSecret('');
      setNewName('');
      await fetchServers();
      await fetchTools();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add server');
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeleteServer = async (serverId: string) => {
    try {
      const response = await fetch(`http://localhost:3001/mcp-servers/${serverId}`, {
        method: 'DELETE',
      });

      if (!response.ok && response.status !== 204) {
        throw new Error('Failed to delete server');
      }

      await fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete server');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-800">MCP Server Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          {/* Existing Servers List */}
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-700 mb-3">Connected Servers</h3>
            {isLoading ? (
              <p className="text-gray-500">Loading...</p>
            ) : servers.length === 0 ? (
              <p className="text-gray-500 italic">No MCP servers configured</p>
            ) : (
              <ul className="space-y-2">
                {servers.map((server) => {
                  const serverTools = getToolsForServer(server.id);
                  const isExpanded = expandedServers.has(server.id);
                  return (
                    <li
                      key={server.id}
                      className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-800 truncate">
                            {server.name || server.url}
                          </p>
                          <p className="text-sm text-gray-500 truncate">{server.url}</p>
                          {server.client_id && (
                            <p className="text-xs text-gray-400">Client ID: {server.client_id}</p>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteServer(server.id)}
                          className="ml-4 px-3 py-1 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
                        >
                          Remove
                        </button>
                      </div>

                      {/* Tools section */}
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <button
                          onClick={() => toggleServerExpanded(server.id)}
                          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800"
                        >
                          <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                            ▶
                          </span>
                          <span>
                            {isLoadingTools ? 'Loading tools...' : `${serverTools.length} tool${serverTools.length !== 1 ? 's' : ''} available`}
                          </span>
                        </button>

                        {isExpanded && serverTools.length > 0 && (
                          <ul className="mt-2 ml-4 space-y-1">
                            {serverTools.map((tool) => (
                              <li key={tool.name} className="text-sm">
                                <span className="font-mono text-blue-600">{tool.name}</span>
                                {tool.description && (
                                  <p className="text-gray-500 text-xs ml-2">{tool.description}</p>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}

                        {isExpanded && serverTools.length === 0 && !isLoadingTools && (
                          <p className="mt-2 ml-4 text-sm text-gray-400 italic">No tools available</p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Add New Server Form */}
          <div className="border-t border-gray-200 pt-6">
            <h3 className="text-lg font-medium text-gray-700 mb-3">Add New Server</h3>
            <form onSubmit={handleAddServer} className="space-y-4">
              <div>
                <label htmlFor="server-url" className="block text-sm font-medium text-gray-700 mb-1">
                  Server URL <span className="text-red-500">*</span>
                </label>
                <input
                  id="server-url"
                  type="url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://mcp.example.com"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800"
                />
              </div>

              <div>
                <label htmlFor="server-name" className="block text-sm font-medium text-gray-700 mb-1">
                  Display Name
                </label>
                <input
                  id="server-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="My MCP Server"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="client-id" className="block text-sm font-medium text-gray-700 mb-1">
                    Client ID
                  </label>
                  <input
                    id="client-id"
                    type="text"
                    value={newClientId}
                    onChange={(e) => setNewClientId(e.target.value)}
                    placeholder="Optional"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800"
                  />
                </div>

                <div>
                  <label htmlFor="client-secret" className="block text-sm font-medium text-gray-700 mb-1">
                    Client Secret
                  </label>
                  <input
                    id="client-secret"
                    type="password"
                    value={newClientSecret}
                    onChange={(e) => setNewClientSecret(e.target.value)}
                    placeholder="Optional"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-800"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isAdding || !newUrl.trim()}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isAdding ? 'Adding...' : 'Add Server'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
