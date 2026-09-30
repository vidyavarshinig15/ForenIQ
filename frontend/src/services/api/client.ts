import { ForensicApiError } from '../../types/api';
import type { ApiErrorResponse, HealthResponse } from '../../types/api';
import type { LoginPayload, TokenResponse, User } from '../../types/auth';
import type { Case, CaseCreatePayload, CaseMember, CaseUpdatePayload } from '../../types/case';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ForensicApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = sessionStorage.getItem('ufdr_auth_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      sessionStorage.setItem('ufdr_auth_token', token);
    } else {
      sessionStorage.removeItem('ufdr_auth_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        let errorCode = 'HTTP_ERROR';
        let errorMessage = `HTTP error ${response.status}: ${response.statusText}`;

        try {
          const errorData: ApiErrorResponse = await response.json();
          if (errorData?.error) {
            errorCode = errorData.error.code || errorCode;
            errorMessage = errorData.error.message || errorMessage;
          }
        } catch {
          // If response body is not JSON, use default status text
        }

        throw new ForensicApiError(errorMessage, errorCode, response.status);
      }

      // Check if response has content
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return (await response.json()) as T;
      }
      return {} as T;
    } catch (err: unknown) {
      if (err instanceof ForensicApiError) {
        throw err;
      }
      throw new ForensicApiError(
        err instanceof Error ? err.message : 'Network communication failure',
        'NETWORK_ERROR'
      );
    }
  }

  // --- Health ---
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // --- Authentication ---
  async login(payload: LoginPayload): Promise<TokenResponse> {
    const res = await this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    this.setToken(res.access_token);
    return res;
  }

  async logout(): Promise<void> {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // --- Cases ---
  async listCases(status?: string): Promise<Case[]> {
    const query = status && status !== 'ALL' ? `?status=${encodeURIComponent(status)}` : '';
    return this.request<Case[]>(`/cases${query}`);
  }

  async getCase(caseId: string): Promise<Case> {
    return this.request<Case>(`/cases/${caseId}`);
  }

  async createCase(payload: CaseCreatePayload): Promise<Case> {
    return this.request<Case>('/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateCase(caseId: string, payload: CaseUpdatePayload): Promise<Case> {
    return this.request<Case>(`/cases/${caseId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async listMembers(caseId: string): Promise<CaseMember[]> {
    return this.request<CaseMember[]>(`/cases/${caseId}/members`);
  }

  async addMember(
    caseId: string,
    payload: { email?: string; user_id?: string; access_role: string }
  ): Promise<CaseMember> {
    return this.request<CaseMember>(`/cases/${caseId}/members`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateMemberRole(
    caseId: string,
    userId: string,
    accessRole: string
  ): Promise<CaseMember> {
    return this.request<CaseMember>(`/cases/${caseId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ access_role: accessRole }),
    });
  }

  async removeMember(caseId: string, userId: string): Promise<void> {
    await this.request(`/cases/${caseId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // --- Users ---
  async listUsers(): Promise<User[]> {
    return this.request<User[]>('/users');
  }
}

export const apiClient = new ForensicApiClient(API_BASE_URL);
