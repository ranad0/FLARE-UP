import type {VisualMode} from './visualMode';
import { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Compass, RotateCcw } from 'lucide-react';
import { analyzeScenario } from '../services/flareApi';
import type { TranslationBundle } from '../i18n/translations';
import {
  FireLabParams,
  FlareApiError,
  SampleType,
  ScenarioAnalyzeResponse,
} from '../types/flare';
import { FireLabScene } from './FireLabScene';
import { NasaEvidencePanel } from './NasaEvidencePanel';

interface FireLabPageProps {
  t: TranslationBundle;
  mode: VisualMode;
  onModeChange: (mode:VisualMode) => void;
}

const DEFAULT_PARAMS: FireLabParams = {
  gravity: 'microgravity',
  oxygenPercent: 21,
  pressurePsi: 14.7,
  airflow: 0.15,
  airflowDirectionDegrees: 90,
  sampleType: 'gaseous',
};

const SAMPLE_TYPES: SampleType[] = ['gaseous', 'liquid', 'fabric', 'polymer'];

function getAirflowLabel(airflow: number, t: TranslationBundle): string {
  if (airflow <= 0.06) return t.lab.airflowLevels.still;
  if (airflow <= 0.38) return t.lab.airflowLevels.low;
  if (airflow <= 0.72) return t.lab.airflowLevels.moderate;
  return t.lab.airflowLevels.high;
}

export function FireLabPage({ t, mode, onModeChange }: FireLabPageProps) {
  const [conditions, setParams] = useState<FireLabParams>(DEFAULT_PARAMS);
  const params=useMemo<FireLabParams>(()=>({...conditions,gravity:mode==='earth'?'earth':'microgravity'}),[conditions,mode]);
  const [resetSignal, setResetSignal] = useState(0);

  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const [evidenceData, setEvidenceData] = useState<ScenarioAnalyzeResponse | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // An analysis is tied to its submitted inputs, never to subsequently edited controls.
  useEffect(() => {
    abortRef.current?.abort();
    setEvidenceData(null);
    setEvidenceError(null);
    setAnalyzing(false);
  }, [params]);

  const handleAnalyze = async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setEvidenceOpen(true);
    setAnalyzing(true);
    setEvidenceError(null);
    setLoadingStepIndex(0);

    // Advance elegant 4-step progress sequence smoothly while request runs
    const stepTimer1 = window.setTimeout(() => setLoadingStepIndex(1), 320);
    const stepTimer2 = window.setTimeout(() => setLoadingStepIndex(2), 680);
    const stepTimer3 = window.setTimeout(() => setLoadingStepIndex(3), 1040);

    try {
      const result = await analyzeScenario(params, controller.signal);
      if (!controller.signal.aborted) setEvidenceData(result);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setEvidenceData(null);
      if (err instanceof FlareApiError && err.kind === 'offline') {
        setEvidenceError(t.offlineMessage);
      } else if (err instanceof Error) {
        setEvidenceError(err.message || t.offlineMessage);
      } else {
        setEvidenceError(t.offlineMessage);
      }
    } finally {
      window.clearTimeout(stepTimer1);
      window.clearTimeout(stepTimer2);
      window.clearTimeout(stepTimer3);
      setAnalyzing(false);
    }
  };

  const handleCompassPointer = (svgEl: SVGSVGElement, clientX: number, clientY: number) => {
    const rect = svgEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
    let deg = Math.round((Math.atan2(dx, -dy) * 180) / Math.PI);
    if (deg < 0) deg += 360;
    setParams((prev) => ({ ...prev, airflowDirectionDegrees: deg }));
  };

  const airflowRad = (params.airflowDirectionDegrees * Math.PI) / 180;
  const indicatorX = 32 + Math.sin(airflowRad) * 21;
  const indicatorY = 32 - Math.cos(airflowRad) * 21;

  return (
    <main className="relative z-10 mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-4 px-4 pb-5 pt-1 sm:px-6 lg:h-[calc(100vh-68px)] lg:overflow-hidden">
      <div
        className={`grid flex-1 grid-cols-1 gap-4 lg:min-h-0 ${
          evidenceOpen ? 'lg:grid-cols-12' : 'lg:grid-cols-12'
        }`}
      >
        {/* Left Control Column */}
        <section className="order-2 flex flex-col justify-between rounded-xl border border-[#7A5498]/30 bg-[#130B20]/90 p-4 sm:p-5 lg:order-1 lg:col-span-4 xl:col-span-3 lg:overflow-y-auto flare-scroll">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-[#7A5498]/20 pb-2.5">
              <h1 className="text-sm font-semibold text-[#F5F1FA]">{t.lab.controlsHeading}</h1>
              <button
                type="button"
                onClick={() => {setParams(DEFAULT_PARAMS);onModeChange('micro');}}
                className="text-xs text-[#B8A9CE] transition-colors hover:text-[#E1B983]"
              >
                {t.lab.resetDefaults}
              </button>
            </div>

            {/* 1. Gravity */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-[#D6CBE8]">
                {t.lab.gravityLabel}
              </label>
              <div className="grid grid-cols-2 gap-1.5 rounded-lg bg-[#1D1230] p-1 border border-[#7A5498]/25">
                <button
                  type="button"
                  onClick={() => onModeChange('earth')}
                  className={`whitespace-nowrap rounded-md px-2.5 py-2 text-xs font-medium transition-colors ${
                    params.gravity === 'earth'
                      ? 'bg-[#E1B983] text-[#140B22]'
                      : 'text-[#C7B9DC] hover:text-[#F5F1FA]'
                  }`}
                >
                  {t.lab.gravityEarth}
                </button>
                <button
                  type="button"
                  onClick={() => onModeChange('micro')}
                  className={`whitespace-nowrap rounded-md px-2.5 py-2 text-xs font-medium transition-colors ${
                    params.gravity === 'microgravity'
                      ? 'bg-[#22D3EE] text-[#09131F]'
                      : 'text-[#C7B9DC] hover:text-[#F5F1FA]'
                  }`}
                >
                  {t.lab.gravityMicrogravity}
                </button>
              </div>
            </div>

            {/* 2. Oxygen Percentage (15% - 40%) */}
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between">
                <label htmlFor="oxygen-slider" className="text-xs font-medium text-[#D6CBE8]">
                  {t.lab.oxygenLabel}
                </label>
                <span className="font-mono-tabular text-sm font-semibold text-[#E1B983]">
                  {params.oxygenPercent.toFixed(0)}%
                </span>
              </div>
              <input
                id="oxygen-slider"
                type="range"
                min={15}
                max={40}
                step={1}
                value={params.oxygenPercent}
                onChange={(e) =>
                  setParams((p) => ({ ...p, oxygenPercent: Number(e.target.value) }))
                }
                className="flare-slider"
              />
              <div className="flex justify-between font-mono-tabular text-[11px] text-[#8E7EAC]">
                <span>15%</span>
                <span>21%</span>
                <span>40%</span>
              </div>
            </div>

            {/* 3. Pressure (4.3 psi - 14.7 psi) */}
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between">
                <label htmlFor="pressure-slider" className="text-xs font-medium text-[#D6CBE8]">
                  {t.lab.pressureLabel}
                </label>
                <span className="font-mono-tabular text-sm font-semibold text-[#E1B983]">
                  {params.pressurePsi.toFixed(1)} psi
                </span>
              </div>
              <input
                id="pressure-slider"
                type="range"
                min={4.3}
                max={14.7}
                step={0.1}
                value={params.pressurePsi}
                onChange={(e) =>
                  setParams((p) => ({ ...p, pressurePsi: Number(e.target.value) }))
                }
                className="flare-slider"
              />
              <div className="flex justify-between font-mono-tabular text-[11px] text-[#8E7EAC]">
                <span>4.3 psi</span>
                <span>10.2 psi</span>
                <span>14.7 psi</span>
              </div>
            </div>

            {/* 4. Airflow Magnitude (Still to High) */}
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between">
                <label htmlFor="airflow-slider" className="text-xs font-medium text-[#D6CBE8]">
                  {t.lab.airflowLabel}
                </label>
                <span className="text-xs font-semibold text-[#22D3EE]">
                  {getAirflowLabel(params.airflow, t)}
                </span>
              </div>
              <input
                id="airflow-slider"
                type="range"
                min={0}
                max={1}
                step={0.02}
                value={params.airflow}
                onChange={(e) => setParams((p) => ({ ...p, airflow: Number(e.target.value) }))}
                className="flare-slider"
              />
              <div className="flex justify-between text-[11px] text-[#8E7EAC]">
                <span>{t.lab.airflowLevels.still}</span>
                <span>{t.lab.airflowLevels.moderate}</span>
                <span>{t.lab.airflowLevels.high}</span>
              </div>
            </div>

            {/* 5. Airflow Direction (0 to 360 degrees) */}
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between">
                <label htmlFor="airflow-dir-slider" className="flex items-center gap-1.5 text-xs font-medium text-[#D6CBE8]">
                  <Compass className="h-3.5 w-3.5 text-[#22D3EE]" aria-hidden="true" />
                  <span>{t.lab.airflowDirectionLabel}</span>
                </label>
                <span className="font-mono-tabular text-sm font-semibold text-[#22D3EE]">
                  {params.airflowDirectionDegrees}°
                </span>
              </div>
              <div className="flex items-center gap-3.5">
                <svg
                  width="64"
                  height="64"
                  viewBox="0 0 64 64"
                  role="img"
                  aria-label={`${t.lab.airflowDirectionLabel}: ${params.airflowDirectionDegrees}°`}
                  className="shrink-0 cursor-pointer touch-none rounded-full border border-[#7A5498]/35 bg-[#1B102B]"
                  onPointerDown={(e) => {
                    e.currentTarget.setPointerCapture(e.pointerId);
                    handleCompassPointer(e.currentTarget, e.clientX, e.clientY);
                  }}
                  onPointerMove={(e) => {
                    if (e.buttons === 1) {
                      handleCompassPointer(e.currentTarget, e.clientX, e.clientY);
                    }
                  }}
                >
                  <circle cx="32" cy="32" r="24" stroke="#7A5498" strokeOpacity="0.4" strokeWidth="1" fill="none" />
                  <line x1="32" y1="32" x2={indicatorX} y2={indicatorY} stroke="#22D3EE" strokeWidth="2" />
                  <circle cx="32" cy="32" r="2.8" fill="#E1B983" />
                  <circle cx={indicatorX} cy={indicatorY} r="4" fill="#22D3EE" />
                </svg>
                <input
                  id="airflow-dir-slider"
                  type="range"
                  min={0}
                  max={359}
                  step={1}
                  value={params.airflowDirectionDegrees}
                  onChange={(e) =>
                    setParams((p) => ({ ...p, airflowDirectionDegrees: Number(e.target.value) }))
                  }
                  className="flare-slider"
                />
              </div>
            </div>

            {/* 6. Sample Type */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-[#D6CBE8]">
                {t.lab.sampleTypeLabel}
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                {SAMPLE_TYPES.map((st) => (
                  <button
                    key={st}
                    type="button"
                    onClick={() => setParams((p) => ({ ...p, sampleType: st }))}
                    className={`truncate rounded-lg border px-2.5 py-2 text-xs font-medium transition-colors ${
                      params.sampleType === st
                        ? 'border-[#E1B983]/80 bg-[#2D1C42] text-[#F5F1FA]'
                        : 'border-[#7A5498]/25 bg-[#1A0F2A]/70 text-[#B8A9CE] hover:border-[#7A5498]/60 hover:text-[#F5F1FA]'
                    }`}
                  >
                    {t.lab.sampleTypes[st]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Primary NASA Evidence CTA */}
          <div className="mt-5 space-y-2.5 border-t border-[#7A5498]/20 pt-4">
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={analyzing}
              className="w-full whitespace-nowrap rounded-lg bg-[#E1B983] px-4 py-2.5 text-sm font-semibold text-[#120A1E] transition-colors duration-150 hover:bg-[#ECCB9D] disabled:cursor-wait disabled:opacity-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983]"
            >
              {analyzing ? t.lab.analyzingButton : t.lab.analyzeButton}
            </button>

            {!evidenceOpen && (
              <button
                type="button"
                onClick={() => setEvidenceOpen(true)}
                className="flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-lg border border-[#7A5498]/35 bg-[#1B102B]/70 px-4 py-2 text-xs font-medium text-[#D6CBE8] transition-colors hover:border-[#E1B983]/45 hover:text-[#F5F1FA]"
              >
                <BookOpen className="h-3.5 w-3.5" />
                <span>{t.lab.openEvidenceButton}</span>
              </button>
            )}
          </div>
        </section>

        {/* Central 3D Combustion Chamber Viewport */}
        <section
          className={`order-1 relative flex min-h-[380px] flex-col overflow-hidden rounded-xl border border-[#7A5498]/30 bg-[#0C0715]/60 sm:min-h-[480px] lg:order-2 lg:min-h-0 ${
            evidenceOpen ? 'lg:col-span-4 xl:col-span-5' : 'lg:col-span-8 xl:col-span-9'
          }`}
        >
          {/* Minimal top-overlay bar inside viewport */}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-3 p-3.5">
            <div className="pointer-events-auto rounded-md bg-[#11091D]/80 px-3 py-1.5 border border-[#7A5498]/25">
              <span className="text-xs font-medium text-[#F5F1FA]">{t.lab.title}</span>
            </div>
            <button
              type="button"
              onClick={() => setResetSignal((n) => n + 1)}
              className="pointer-events-auto inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-[#7A5498]/35 bg-[#11091D]/85 px-3 py-1.5 text-xs font-medium text-[#D6CBE8] transition-colors hover:border-[#E1B983]/60 hover:text-[#F5F1FA]"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>{t.lab.resetView}</span>
            </button>
          </div>

          <div className="flex-1 min-h-0">
            <FireLabScene params={params} resetSignal={resetSignal} cursorHint={t.lab.cursorHint} />
          </div>
        </section>

        {/* NASA Evidence Panel */}
        {evidenceOpen && (
          <div className="order-3 min-h-[360px] lg:col-span-4 lg:min-h-0">
            <NasaEvidencePanel
              t={t}
              loading={analyzing}
              loadingStepIndex={loadingStepIndex}
              data={evidenceData}
              errorMessage={evidenceError}
              onClose={() => setEvidenceOpen(false)}
            />
          </div>
        )}
      </div>

      {/* Clear & unobtrusive Scientific Honesty Notice */}
      <footer className="text-center">
        <p className="text-xs text-[#9D8EC0]">{t.honestyNotice}</p>
      </footer>
    </main>
  );
}
