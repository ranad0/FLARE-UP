import {
  AskResponse,
  FireLabParams,
  FlareApiError,
  ScenarioAnalyzeRequest,
  ScenarioAnalyzeResponse,
} from '../types/flare';

export function getApiBaseUrl(): string {
  const runtimeUrl =
    typeof window !== 'undefined' ? window.FLARE_CONFIG?.apiBaseUrl : undefined;
  const envUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const raw = (runtimeUrl || envUrl || (import.meta.env.DEV ? '/api' : window.location.origin)).trim();
  return raw.replace(/\/+$/, '');
}

async function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  const baseUrl = getApiBaseUrl();
  if (!baseUrl) {
    throw new FlareApiError('offline', 'FLARE UP Evidence Engine is not connected.');
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 120000);

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      window.clearTimeout(timeoutId);
      throw new DOMException('Aborted', 'AbortError');
    }
    signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const errJson = (await response.json()) as { detail?: string; message?: string };
        detail = errJson.detail || errJson.message || detail;
      } catch {
        // Ignore non-JSON error bodies
      }
      throw new FlareApiError('http', detail, response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof FlareApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (signal?.aborted) {
        throw error;
      }
      throw new FlareApiError('offline', 'FLARE UP Evidence Engine is not connected.');
    }
    throw new FlareApiError('offline', 'FLARE UP Evidence Engine is not connected.');
  } finally {
    window.clearTimeout(timeoutId);
    if (signal) {
      signal.removeEventListener('abort', onExternalAbort);
    }
  }
}

export async function askFlareUp(question: string, signal?: AbortSignal): Promise<AskResponse> {
  return postJson<AskResponse>('/ask', { question }, signal);
}

const SAMPLE_TYPE_API_MAP: Record<FireLabParams['sampleType'], string> = {
  gaseous: 'Gaseous fuel',
  liquid: 'Liquid fuel',
  fabric: 'Fabric',
  polymer: 'Polymer',
};

export async function analyzeScenario(
  params: FireLabParams,
  signal?: AbortSignal
): Promise<ScenarioAnalyzeResponse> {
  const payload: ScenarioAnalyzeRequest = {
    gravity: params.gravity,
    oxygen_percent: Number(params.oxygenPercent.toFixed(1)),
    pressure_psi: Number(params.pressurePsi.toFixed(1)),
    airflow: Number(params.airflow.toFixed(2)),
    airflow_direction_degrees: Math.round(params.airflowDirectionDegrees),
    sample_type: SAMPLE_TYPE_API_MAP[params.sampleType],
  };

  return postJson<ScenarioAnalyzeResponse>('/scenario/analyze', payload, signal);
}
