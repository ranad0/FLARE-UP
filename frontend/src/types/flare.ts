export type Language = 'en' | 'ar';
export type PageView = 'home' | 'lab' | 'research';
export type GravityMode = 'earth' | 'microgravity';
export type SampleType = 'gaseous' | 'liquid' | 'fabric' | 'polymer';

export interface FireLabParams {
  gravity: GravityMode;
  oxygenPercent: number; // 15 to 40
  pressurePsi: number; // 4.3 to 14.7
  airflow: number; // 0 to 1 (Still to High)
  airflowDirectionDegrees: number; // 0 to 360
  sampleType: SampleType;
}

export interface AskRequest {
  question: string;
}

export interface SourceItem {
  title?: string;
  name?: string;
  investigation?: string;
  experiment?: string;
  document?: string;
  url?: string;
  link?: string;
  citation?: string;
  year?: string | number;
  summary?: string;
  excerpt?: string;
  conditions?: Record<string, unknown> | string;
  metrics?: Record<string, unknown> | Array<{ label?: string; name?: string; value?: unknown; unit?: string }>;
  [key: string]: unknown;
}

export interface StructuredResultRow {
  title?: string;
  investigation?: string;
  parameter?: string;
  value?: string | number;
  unit?: string;
  conditions?: string | Record<string, unknown>;
  source?: string;
  [key: string]: unknown;
}

export interface AskResponse {
  route?: string;
  answer?: string;
  sources?: Array<SourceItem | string>;
  structured_results?: Array<StructuredResultRow | Record<string, unknown>> | Record<string, unknown>;
  [key: string]: unknown;
}

export interface ScenarioAnalyzeRequest {
  gravity: GravityMode;
  oxygen_percent: number;
  pressure_psi: number;
  airflow: number;
  airflow_direction_degrees: number;
  sample_type: string;
}

export interface EvidenceRecord {
  investigation?: string;
  title?: string;
  mission?: string;
  experiment?: string;
  gravity?: string;
  oxygen_percent?: number | string;
  pressure_psi?: number | string;
  airflow?: number | string;
  sample_type?: string;
  conditions?: Record<string, unknown> | string;
  reported_values?: Record<string, unknown> | Array<Record<string, unknown>>;
  findings?: string | string[];
  summary?: string;
  source?: string;
  citation?: string;
  url?: string;
  [key: string]: unknown;
}

export interface ScenarioAnalyzeResponse {
  scenario?: Record<string, unknown>;
  evidence_match?:
    | string
    | {
        status?: string;
        level?: string;
        match_quality?: string;
        summary?: string;
        limited?: boolean;
        exact_match?: boolean;
        [key: string]: unknown;
      };
  closest_records?: Array<EvidenceRecord>;
  visual_state?: Record<string, unknown>;
  analysis?:
    | string
    | {
        closest_investigation?: string;
        closest_experimental_conditions?: Record<string, unknown> | string | string[];
        reported_by_sources?: Array<Record<string, unknown> | string> | string;
        interpretation?: string | string[];
        not_established?: string | string[];
        limited_evidence?: boolean;
        [key: string]: unknown;
      };
  scientific_disclaimer?: string;
  sources?: Array<SourceItem | string>;
  [key: string]: unknown;
}

export type ApiErrorKind = 'offline' | 'http' | 'invalid';

export class FlareApiError extends Error {
  public readonly kind: ApiErrorKind;
  public readonly status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'FlareApiError';
    this.kind = kind;
    this.status = status;
  }
}

declare global {
  interface Window {
    FLARE_CONFIG?: {
      apiBaseUrl?: string;
    };
  }
}
