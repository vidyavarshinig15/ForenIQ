export type CaseStatus = 'OPEN' | 'IN_PROGRESS' | 'CLOSED' | 'ARCHIVED';

export type CaseAccessRole = 'LEAD' | 'CONTRIBUTOR' | 'ANALYST' | 'VIEWER';

export interface CaseMember {
  id: string;
  case_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  access_role: CaseAccessRole;
  created_at: string;
}

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description?: string | null;
  status: CaseStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
  current_user_role?: string | null;
  members?: CaseMember[];
}

export interface CaseCreatePayload {
  title: string;
  description?: string;
  case_number?: string;
}

export interface CaseUpdatePayload {
  title?: string;
  description?: string;
  status?: CaseStatus;
}
