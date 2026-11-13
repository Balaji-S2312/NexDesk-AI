export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface ApiError {
  message: string;
  status?: number;
  details?: unknown;
}
