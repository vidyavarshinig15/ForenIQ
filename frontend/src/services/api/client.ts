import { ForensicApiError } from '../../types/api';
import type { ApiErrorResponse, HealthResponse } from '../../types/api';
import type { LoginPayload, TokenResponse, User } from '../../types/auth';
import type { Case, CaseCreatePayload, CaseMember, CaseUpdatePayload } from '../../types/case';
import type {
  CanonicalEvidence,
  CanonicalEvidenceListResponse,
  CustodyChainVerificationResult,
  Evidence,
  EvidenceCustodyEvent,
  EvidenceUploadProgress,
  IntegrityVerificationResult,
  ProcessingJob,
  RawArtifact,
  RawArtifactListResponse,
} from '../../types/evidence';
import type { ForensicSearchResponse, SearchHistoryResponse } from '../../types/search';
import type {
  AnomalyDetectionRequest,
  AnomalyDetectionResponse,
  AnomalyJobStatusResponse,
  AnomalyResult,
  TimelineFilterRequest,
  TimelineResponse,
} from '../../types/timeline_anomaly';
import type {
  ForensicReportDocument,
  ReportCreateRequest,
  ReportGenerationJobResponse,
  ReportListSummary,
  ReportUpdateRequest,
} from '../../types/report';


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

  // --- Evidence Management (Phase 3) ---
  async listEvidence(caseId: string): Promise<Evidence[]> {
    return this.request<Evidence[]>(`/cases/${caseId}/evidence`);
  }

  async getEvidence(caseId: string, evidenceId: string): Promise<Evidence> {
    return this.request<Evidence>(`/cases/${caseId}/evidence/${evidenceId}`);
  }

  async quarantineEvidence(caseId: string, evidenceId: string): Promise<Evidence> {
    return this.request<Evidence>(`/cases/${caseId}/evidence/${evidenceId}`, {
      method: 'DELETE',
    });
  }

  async uploadEvidence(
    caseId: string,
    file: File,
    onProgress?: (progress: EvidenceUploadProgress) => void
  ): Promise<Evidence> {
    const url = `${this.baseUrl}/cases/${caseId}/evidence`;
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);

      if (this.token) {
        xhr.setRequestHeader('Authorization', `Bearer ${this.token}`);
      }

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percentage = Math.round((event.loaded / event.total) * 100);
            onProgress({
              loaded: event.loaded,
              total: event.total,
              percentage,
            });
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText) as Evidence;
            resolve(data);
          } catch {
            reject(new ForensicApiError('Invalid JSON response from server', 'INVALID_RESPONSE'));
          }
        } else {
          let code = 'UPLOAD_ERROR';
          let message = `Upload failed with HTTP ${xhr.status}`;
          try {
            const errJson = JSON.parse(xhr.responseText);
            if (errJson?.error) {
              code = errJson.error.code || code;
              message = errJson.error.message || message;
            }
          } catch {
            // fallback
          }
          reject(new ForensicApiError(message, code, xhr.status));
        }
      };

      xhr.onerror = () => {
        reject(new ForensicApiError('Network connection failed during upload', 'NETWORK_ERROR'));
      };

      xhr.onabort = () => {
        reject(new ForensicApiError('Upload cancelled by user', 'UPLOAD_ABORTED'));
      };

      const formData = new FormData();
      formData.append('file', file);
      xhr.send(formData);
    });
  }

  async downloadEvidence(caseId: string, evidenceId: string, filename: string): Promise<void> {
    const url = `${this.baseUrl}/cases/${caseId}/evidence/${evidenceId}/download`;
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new ForensicApiError('Failed to download evidence file', 'DOWNLOAD_ERROR', response.status);
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    document.body.removeChild(a);
  }

  async verifyIntegrity(caseId: string, evidenceId: string): Promise<IntegrityVerificationResult> {
    return this.request<IntegrityVerificationResult>(`/cases/${caseId}/evidence/${evidenceId}/verify-integrity`, {
      method: 'POST',
    });
  }

  async getCustodyHistory(caseId: string, evidenceId: string): Promise<EvidenceCustodyEvent[]> {
    return this.request<EvidenceCustodyEvent[]>(`/cases/${caseId}/evidence/${evidenceId}/custody`);
  }

  async verifyCustodyChain(caseId: string, evidenceId: string): Promise<CustodyChainVerificationResult> {
    return this.request<CustodyChainVerificationResult>(`/cases/${caseId}/evidence/${evidenceId}/verify-custody-chain`);
  }

  // --- Forensic Processing & Raw Artifacts ---
  async triggerParsing(caseId: string, evidenceId: string, priority?: string): Promise<ProcessingJob> {
    return this.request<ProcessingJob>(`/cases/${caseId}/evidence/${evidenceId}/parse`, {
      method: 'POST',
      body: priority ? JSON.stringify({ priority }) : undefined,
    });
  }

  async cancelProcessingJob(caseId: string, jobId: string): Promise<ProcessingJob> {
    return this.request<ProcessingJob>(`/cases/${caseId}/processing-jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  async retryProcessingJob(caseId: string, jobId: string): Promise<ProcessingJob> {
    return this.request<ProcessingJob>(`/cases/${caseId}/processing-jobs/${jobId}/retry`, {
      method: 'POST',
    });
  }

  async getProcessingJob(caseId: string, jobId: string): Promise<ProcessingJob> {
    return this.request<ProcessingJob>(`/cases/${caseId}/processing-jobs/${jobId}`);
  }

  async listProcessingJobs(caseId: string, evidenceId: string): Promise<ProcessingJob[]> {
    return this.request<ProcessingJob[]>(`/cases/${caseId}/evidence/${evidenceId}/processing-jobs`);
  }

  async listRawArtifacts(
    caseId: string,
    evidenceId: string,
    artifactType?: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<RawArtifactListResponse> {
    let url = `/cases/${caseId}/evidence/${evidenceId}/artifacts?page=${page}&page_size=${pageSize}`;
    if (artifactType && artifactType !== 'ALL') {
      url += `&artifact_type=${artifactType}`;
    }
    return this.request<RawArtifactListResponse>(url);
  }

  async getRawArtifact(caseId: string, artifactId: string): Promise<RawArtifact> {
    return this.request<RawArtifact>(`/cases/${caseId}/artifacts/${artifactId}`);
  }

  // --- Phase 7 Evidence Normalization & Canonical Evidence ---
  async normalizeEvidence(caseId: string, evidenceId: string, priority?: string): Promise<ProcessingJob> {
    return this.request<ProcessingJob>(`/cases/${caseId}/evidence/${evidenceId}/normalize`, {
      method: 'POST',
      body: priority ? JSON.stringify({ priority }) : undefined,
    });
  }

  async listCanonicalRecords(
    caseId: string,
    evidenceId: string,
    filters?: {
      artifactType?: string;
      application?: string;
      dataQualityStatus?: string;
      page?: number;
      pageSize?: number;
    }
  ): Promise<CanonicalEvidenceListResponse> {
    const page = filters?.page || 1;
    const pageSize = filters?.pageSize || 50;
    let url = `/cases/${caseId}/evidence/${evidenceId}/canonical-records?page=${page}&page_size=${pageSize}`;
    if (filters?.artifactType && filters.artifactType !== 'ALL') {
      url += `&artifact_type=${encodeURIComponent(filters.artifactType)}`;
    }
    if (filters?.application && filters.application.trim() !== '') {
      url += `&application=${encodeURIComponent(filters.application.trim())}`;
    }
    if (filters?.dataQualityStatus && filters.dataQualityStatus !== 'ALL') {
      url += `&data_quality_status=${encodeURIComponent(filters.dataQualityStatus)}`;
    }
    return this.request<CanonicalEvidenceListResponse>(url);
  }

  async getCanonicalRecord(caseId: string, recordId: string): Promise<CanonicalEvidence> {
    return this.request<CanonicalEvidence>(`/cases/${caseId}/canonical-records/${recordId}`);
  }

  async getCanonicalRecordOriginatingRaw(caseId: string, recordId: string): Promise<RawArtifact> {
    return this.request<RawArtifact>(`/cases/${caseId}/canonical-records/${recordId}/raw`);
  }

  // --- Phase 9 & Phase 10 Forensic Search Engine ---
  async searchEvidence(
    caseId: string,
    params: {
      q?: string;
      mode?: string;
      artifact_type?: string;
      evidence_id?: string;
      device_id?: string;
      application?: string;
      source_file?: string;
      record_identifier?: string;
      entity_value?: string;
      start_date?: string;
      end_date?: string;
      data_quality_status?: string;
      sort?: string;
      page_size?: number;
      cursor?: string;
      facets?: boolean;
    } = {}
  ): Promise<ForensicSearchResponse> {
    const queryParams = new URLSearchParams();
    if (params.q !== undefined && params.q !== '') queryParams.append('q', params.q);
    if (params.mode) queryParams.append('mode', params.mode);
    if (params.artifact_type && params.artifact_type !== 'ALL') queryParams.append('artifact_type', params.artifact_type);
    if (params.evidence_id) queryParams.append('evidence_id', params.evidence_id);
    if (params.device_id) queryParams.append('device_id', params.device_id);
    if (params.application) queryParams.append('application', params.application);
    if (params.source_file) queryParams.append('source_file', params.source_file);
    if (params.record_identifier) queryParams.append('record_identifier', params.record_identifier);
    if (params.entity_value) queryParams.append('entity_value', params.entity_value);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.data_quality_status && params.data_quality_status !== 'ALL') queryParams.append('data_quality_status', params.data_quality_status);
    if (params.sort) queryParams.append('sort', params.sort);
    if (params.page_size) queryParams.append('page_size', String(params.page_size));
    if (params.cursor) queryParams.append('cursor', params.cursor);
    if (params.facets !== undefined) queryParams.append('facets', String(params.facets));

    const qs = queryParams.toString();
    return this.request<ForensicSearchResponse>(`/cases/${caseId}/search${qs ? `?${qs}` : ''}`);
  }

  async getSearchHistory(caseId: string, limit: number = 20): Promise<SearchHistoryResponse> {
    return this.request<SearchHistoryResponse>(`/cases/${caseId}/search/history?limit=${limit}`);
  }

  // --- Phase 10 Vector Embeddings & Semantic Index ---
  async getEmbeddingStats(caseId: string): Promise<any> {
    return this.request<any>(`/cases/${caseId}/embeddings/stats`);
  }

  async generateEmbeddings(caseId: string, batchSize: number = 64): Promise<{ job_id: string; message: string }> {
    return this.request<{ job_id: string; message: string }>(`/cases/${caseId}/embeddings/generate`, {
      method: 'POST',
      body: JSON.stringify({ batch_size: batchSize }),
    });
  }

  async rebuildEmbeddings(caseId: string): Promise<{ job_id: string; message: string }> {
    return this.request<{ job_id: string; message: string }>(`/cases/${caseId}/embeddings/rebuild`, {
      method: 'POST',
    });
  }

  // --- Phase 11 NLP Investigation Query & Intent ---
  async executeInvestigationQuery(
    caseId: string,
    payload: {
      query: string;
      retrieval_mode?: string;
      page_size?: number;
      cursor?: string | null;
      include_facets?: boolean;
    }
  ): Promise<any> {
    return this.request<any>(`/cases/${caseId}/investigation/query`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async parseInvestigationQuery(
    caseId: string,
    payload: {
      query: string;
      retrieval_mode?: string;
    }
  ): Promise<any> {
    return this.request<any>(`/cases/${caseId}/investigation/parse`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Phase 12 Retrieval-Augmented Generation (RAG) & Investigator Assistant ---
  async executeRAGQuery(
    caseId: string,
    payload: {
      query: string;
      conversation_id?: string | null;
      max_context_records?: number | null;
      include_citations?: boolean;
      focus_artifact_types?: string[] | null;
      provider_override?: string | null;
    }
  ): Promise<any> {
    return this.request<any>(`/cases/${caseId}/rag/query`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getRAGConversationHistory(caseId: string, conversationId: string): Promise<any> {
    return this.request<any>(`/cases/${caseId}/rag/conversations/${conversationId}`);
  }

  async clearRAGConversation(caseId: string, conversationId: string): Promise<{ message: string; cleared: boolean }> {
    return this.request<{ message: string; cleared: boolean }>(`/cases/${caseId}/rag/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  }

  // --- Phase 13 Communication Graph Analysis & Social Network Analytics ---
  async getCommunicationGraph(
    caseId: string,
    params?: {
      center_node?: string;
      depth?: number;
      min_weight?: number;
      max_nodes?: number;
    }
  ): Promise<any> {
    let url = `/cases/${caseId}/graph?depth=${params?.depth || 2}&min_weight=${params?.min_weight || 1}&max_nodes=${params?.max_nodes || 500}`;
    if (params?.center_node) {
      url += `&center_node=${encodeURIComponent(params.center_node)}`;
    }
    return this.request<any>(url);
  }

  async queryCommunicationGraph(caseId: string, payload: any): Promise<any> {
    return this.request<any>(`/cases/${caseId}/graph/query`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getGraphNode(caseId: string, nodeId: string): Promise<any> {
    return this.request<any>(`/cases/${caseId}/graph/nodes/${encodeURIComponent(nodeId)}`);
  }

  async getGraphEdge(caseId: string, edgeId: string): Promise<any> {
    return this.request<any>(`/cases/${caseId}/graph/edges/${encodeURIComponent(edgeId)}`);
  }

  async createGraphSnapshot(caseId: string, payload: { title: string; query_params: any }): Promise<any> {
    return this.request<any>(`/cases/${caseId}/graph/snapshots`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listGraphSnapshots(caseId: string): Promise<any[]> {
    return this.request<any[]>(`/cases/${caseId}/graph/snapshots`);
  }

  async getGraphSnapshot(caseId: string, snapshotId: string): Promise<any> {
    return this.request<any>(`/cases/${caseId}/graph/snapshots/${encodeURIComponent(snapshotId)}`);
  }

  // --- Phase 14 Forensic Timeline & Anomaly Detection ---
  async getTimeline(caseId: string, params?: {
    start_time?: string;
    end_time?: string;
    entity_value?: string;
    device_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<TimelineResponse> {
    const query = new URLSearchParams();
    if (params?.start_time) query.set('start_time', params.start_time);
    if (params?.end_time) query.set('end_time', params.end_time);
    if (params?.entity_value) query.set('entity_value', params.entity_value);
    if (params?.device_id) query.set('device_id', params.device_id);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return this.request<TimelineResponse>(`/cases/${caseId}/timeline${qs ? `?${qs}` : ''}`);
  }

  async queryTimeline(caseId: string, payload: TimelineFilterRequest): Promise<TimelineResponse> {
    return this.request<TimelineResponse>(`/cases/${caseId}/timeline/query`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async detectAnomalies(caseId: string, payload: AnomalyDetectionRequest): Promise<AnomalyDetectionResponse> {
    return this.request<AnomalyDetectionResponse>(`/cases/${caseId}/anomalies/detect`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getAnomalyDetails(caseId: string, anomalyId: string): Promise<AnomalyResult> {
    return this.request<AnomalyResult>(`/cases/${caseId}/anomalies/${encodeURIComponent(anomalyId)}`);
  }

  async submitAnomalyJob(caseId: string, payload: AnomalyDetectionRequest): Promise<AnomalyJobStatusResponse> {
    return this.request<AnomalyJobStatusResponse>(`/cases/${caseId}/anomalies/jobs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getAnomalyJobStatus(caseId: string, jobId: string): Promise<AnomalyJobStatusResponse> {
    return this.request<AnomalyJobStatusResponse>(`/cases/${caseId}/anomalies/jobs/${encodeURIComponent(jobId)}`);
  }

  // --- Reports (Phase 15) ---
  async createReport(caseId: string, payload: ReportCreateRequest): Promise<ForensicReportDocument> {
    return this.request<ForensicReportDocument>(`/cases/${caseId}/reports`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listReports(caseId: string): Promise<ReportListSummary[]> {
    return this.request<ReportListSummary[]>(`/cases/${caseId}/reports`);
  }

  async getReport(caseId: string, reportId: string): Promise<ForensicReportDocument> {
    return this.request<ForensicReportDocument>(`/cases/${caseId}/reports/${encodeURIComponent(reportId)}`);
  }

  async updateReport(caseId: string, reportId: string, payload: ReportUpdateRequest): Promise<ForensicReportDocument> {
    return this.request<ForensicReportDocument>(`/cases/${caseId}/reports/${encodeURIComponent(reportId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async approveReport(caseId: string, reportId: string): Promise<ForensicReportDocument> {
    return this.request<ForensicReportDocument>(`/cases/${caseId}/reports/${encodeURIComponent(reportId)}/approve`, {
      method: 'POST',
    });
  }

  getReportPdfExportUrl(caseId: string, reportId: string): string {
    const token = this.getToken();
    return `${this.baseUrl}/cases/${caseId}/reports/${encodeURIComponent(reportId)}/export/pdf${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  getReportJsonExportUrl(caseId: string, reportId: string): string {
    const token = this.getToken();
    return `${this.baseUrl}/cases/${caseId}/reports/${encodeURIComponent(reportId)}/export/json${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  getReportCsvExportUrl(caseId: string, reportId: string): string {
    const token = this.getToken();
    return `${this.baseUrl}/cases/${caseId}/reports/${encodeURIComponent(reportId)}/export/csv${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  async submitReportJob(caseId: string, payload: ReportCreateRequest): Promise<ReportGenerationJobResponse> {
    return this.request<ReportGenerationJobResponse>(`/cases/${caseId}/reports/jobs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getReportJobStatus(caseId: string, jobId: string): Promise<ReportGenerationJobResponse> {
    return this.request<ReportGenerationJobResponse>(`/cases/${caseId}/reports/jobs/${encodeURIComponent(jobId)}`);
  }

  // --- Users ---
  async listUsers(): Promise<User[]> {
    return this.request<User[]>('/users');
  }
}


export const apiClient = new ForensicApiClient(API_BASE_URL);
