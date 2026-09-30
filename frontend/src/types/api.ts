export interface HealthResponse {
  status: string;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export class ForensicApiError extends Error {
  code: string;
  statusCode?: number;

  constructor(message: string, code: string = 'API_ERROR', statusCode?: number) {
    super(message);
    this.name = 'ForensicApiError';
    this.code = code;
    this.statusCode = statusCode;
  }
}
