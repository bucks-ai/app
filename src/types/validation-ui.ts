import type {
  ValidationFeedbackNoteRecord,
  ValidationHypothesisRecord,
  ValidationHypothesisStatus,
  ValidationHypothesisType,
  ValidationLeadRecord,
  ValidationLeadStatus,
  ValidationPersonaRecord,
  ValidationPriority,
  ValidationSignalStrength,
  ValidationSource,
  ValidationStatus,
  ValidationSummary,
  ValidationWorkspace,
} from "@/types/validation";

export type {
  ValidationFeedbackNoteRecord,
  ValidationHypothesisRecord,
  ValidationHypothesisStatus,
  ValidationHypothesisType,
  ValidationLeadRecord,
  ValidationLeadStatus,
  ValidationPersonaRecord,
  ValidationPriority,
  ValidationSignalStrength,
  ValidationSource,
  ValidationStatus,
  ValidationSummary,
  ValidationWorkspace,
};

export type ValidationClientResult<T> =
  | { ok: true; data: T; warning?: string }
  | { ok: false; code: string; error: string };

export type ValidationWorkspaceSeedResult = {
  seeded: boolean;
  personas: number;
  hypotheses: number;
  leads: number;
};

export type ValidationPersonaCreateInput = {
  name: string;
  segment?: string | null;
  description?: string | null;
  pain_points?: string[] | null;
  desired_outcomes?: string[] | null;
  channels?: string[] | null;
  willingness_to_pay?: string | null;
  priority?: ValidationPriority;
  status?: string;
};

export type ValidationPersonaUpdateInput = Partial<ValidationPersonaCreateInput> & {
  id: string;
};

export type ValidationHypothesisCreateInput = {
  title: string;
  description?: string | null;
  type?: ValidationHypothesisType | null;
  assumption?: string | null;
  success_criteria?: string | null;
  status?: ValidationHypothesisStatus;
  confidence?: number | null;
  priority?: ValidationPriority;
};

export type ValidationHypothesisUpdateInput =
  Partial<ValidationHypothesisCreateInput> & {
    id: string;
  };

export type ValidationLeadCreateInput = {
  name: string;
  company?: string | null;
  role?: string | null;
  segment?: string | null;
  source?: ValidationSource;
  contact_url?: string | null;
  email?: string | null;
  status?: ValidationLeadStatus;
  notes?: string | null;
  priority?: ValidationPriority;
};

export type ValidationLeadUpdateInput = Partial<ValidationLeadCreateInput> & {
  id: string;
};

export type ValidationFeedbackCreateInput = {
  lead_id?: string | null;
  hypothesis_id?: string | null;
  summary: string;
  pain_signal?: string | null;
  willingness_to_pay_signal?: string | null;
  objections?: string[] | null;
  quotes?: string[] | null;
  next_step?: string | null;
  signal_strength?: ValidationSignalStrength | null;
};
