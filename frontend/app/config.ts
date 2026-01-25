/**
 * Runtime configuration for the frontend.
 * API_BASE_URL is determined at runtime based on the current environment.
 */

function getApiBaseUrl(): string {
  // In browser, use relative path for production (API Gateway proxy)
  // or localhost for development
  if (typeof window !== 'undefined') {
    // Production: API is served from /api on the same domain
    if (window.location.hostname !== 'localhost') {
      return '/api';
    }
  }

  // Development: use localhost backend
  return 'http://localhost:3001';
}

export const config = {
  get apiBaseUrl() {
    return getApiBaseUrl();
  },
};
