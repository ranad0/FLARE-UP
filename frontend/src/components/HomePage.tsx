import type {VisualMode} from './visualMode';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2, Search, X } from 'lucide-react';
import { askFlareUp } from '../services/flareApi';
import { AskResponse, FlareApiError, SourceItem, StructuredResultRow } from '../types/flare';
import type { TranslationBundle } from '../i18n/translations';
import { HomeFlameScene } from './OrbScene';

interface HomePageProps {
  t: TranslationBundle;
  onOpenLab: () => void;
  mode: VisualMode;
  onModeChange: (mode:VisualMode) => void;
}

function renderSourceEntry(src: SourceItem | string, idx: number) {
  if (typeof src === 'string') {
    return (
      <li key={idx} className="border-b border-[#7A5498]/15 py-2.5 text-xs text-[#D6CBE8] last:border-b-0">
        {src}
      </li>
    );
  }
  const title = src.title || src.investigation_id || src.name || `Source ${idx + 1}`;
  const citation = [src.source_file, src.source_location, src.content_type].filter(Boolean).join(' · ');
  const url = String(src.citation_url || src.url || src.link || '');

  return (
    <li key={idx} className="border-b border-[#7A5498]/15 py-2.5 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium text-[#F5F1FA]">{String(title)}</span>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-1 text-xs text-[#22D3EE] hover:underline"
          >
            <span>Link</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      {citation && <p className="mt-1 text-xs leading-relaxed text-[#B8A9CE]">{String(citation)}</p>}
    </li>
  );
}

export function HomePage({ t, mode, onModeChange, onOpenLab }: HomePageProps) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const answerRef = useRef<HTMLElement | null>(null);
  useEffect(()=>{if(response||errorMessage)answerRef.current?.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});},[response,errorMessage]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const submitQuestion = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setErrorMessage(null);
    setResponse(null);

    try {
      const data = await askFlareUp(trimmed, controller.signal);
      if (abortRef.current === controller) setResponse(data);
    } catch (err) {
      if (abortRef.current !== controller) return;
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (err instanceof FlareApiError && err.kind === 'offline') {
        setErrorMessage(t.offlineMessage);
      } else if (err instanceof Error) {
        setErrorMessage(err.message || t.offlineMessage);
      } else {
        setErrorMessage(t.offlineMessage);
      }
    } finally {
      if (abortRef.current === controller) setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void submitQuestion(question);
  };

  const handleSuggestedClick = (q: string) => {
    setQuestion(q);
    void submitQuestion(q);
  };

  const structuredList: StructuredResultRow[] = Array.isArray(response?.structured_results)
    ? (response.structured_results as StructuredResultRow[])
    : response?.structured_results && typeof response.structured_results === 'object'
      ? Object.entries(response.structured_results).map(
          ([k, v]): StructuredResultRow => ({
            parameter: k,
            value: typeof v === 'object' ? JSON.stringify(v) : String(v),
          })
        )
      : [];

  return (
    <main className="home-page relative z-10 mx-auto flex min-h-[calc(100vh-72px)] w-full max-w-6xl flex-col justify-between px-5 pb-6 pt-4 sm:px-8">
      <div className="hero-layout">
        {/* Primary Focus: Heading + Ask FLARE UP Search + Two Suggested Questions */}
        <section className="hero-copy space-y-6">

          <h1
            className="hero-heading"
          >
            {t.home.heading}
          </h1>

          <form onSubmit={handleSubmit} className="relative">
            <div className="flex flex-col gap-2.5 rounded-xl border border-[#7A5498]/45 bg-[#150D24]/90 p-2 sm:flex-row sm:items-center focus-within:border-[#E1B983]/80 transition-colors">
              <div className="flex flex-1 items-center gap-3 px-2.5">
                <Search className="h-4 w-4 shrink-0 text-[#E1B983]" aria-hidden="true" />
                <input
                  type="text" maxLength={2500} minLength={3} required
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={t.home.searchPlaceholder}
                  aria-label={t.home.searchPlaceholder}
                  className="w-full bg-transparent py-2.5 text-sm text-[#F5F1FA] placeholder:text-[#9887B2] focus:outline-none sm:text-base"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg bg-[#E1B983] px-5 py-2.5 text-sm font-semibold text-[#120A1E] transition-colors duration-150 hover:bg-[#ECCB9D] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983]"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                <span>{loading ? t.home.askingButton : t.home.askButton}</span>
              </button>
            </div>
          </form>

          {/* Exactly two suggested questions only */}
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {t.home.suggestedQuestions.map((sq, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSuggestedClick(sq)}
                className="rounded-lg border border-[#7A5498]/30 bg-[#180F28]/70 px-4 py-3 text-start text-xs leading-relaxed text-[#D6CBE8] transition-colors duration-150 hover:border-[#E1B983]/55 hover:bg-[#231538] hover:text-[#F5F1FA] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] sm:text-sm"
              >
                {sq}
              </button>
            ))}
          </div>

          <button className="lab-link" type="button" onClick={onOpenLab}>{t.home.exploreLabCta} ↗</button>
        </section>

        {/* Single Interactive 3D Flame */}
        <section className="hero-orb flex flex-col items-center">
          <div className="h-[280px] w-full max-w-[420px] sm:h-[310px]">
            <HomeFlameScene mode={mode} hintText={t.home.flameHint} />
          </div>
          <div className="gravity-switch" role="group" aria-label="Gravity visual mode">
            <button type="button" aria-pressed={mode==='earth'} onClick={()=>onModeChange('earth')}>{t.nav.home==='Home'?'Earth':'الأرض'}</button>
            <button type="button" aria-pressed={mode==='micro'} onClick={()=>onModeChange('micro')}>{t.nav.home==='Home'?'Microgravity':'الجاذبية الصغرى'}</button>
          </div>
        </section>
      </div>

      {/* /ask Backend Response or Offline State */}
      {(errorMessage || response) && (
        <section
          ref={answerRef}
          style={{scrollMarginTop:24}}
          aria-live="polite"
          className="mt-6 rounded-xl border border-[#7A5498]/35 bg-[#150D24]/92 p-5 sm:p-6"
        >
          <div className="flex items-center justify-between gap-4 border-b border-[#7A5498]/20 pb-3">
            <div className="flex items-center gap-3 text-xs text-[#B8A9CE]">
              <span className="font-semibold text-[#E1B983]">{t.home.answerHeading}</span>
              {response?.route && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="font-mono-tabular">
                    {t.home.routeLabel}: {response.route}
                  </span>
                </>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setResponse(null);
                setErrorMessage(null);
              }}
              aria-label={t.home.clearAnswer}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#B8A9CE] hover:bg-[#2D1C42] hover:text-[#F5F1FA]"
            >
              <X className="h-3.5 w-3.5" />
              <span>{t.home.clearAnswer}</span>
            </button>
          </div>

          {errorMessage ? (
            <p className="mt-4 text-sm font-medium text-[#E1B983]">{errorMessage}</p>
          ) : (
            <div className="mt-4 space-y-5">
              {response?.answer && (
                <p className="whitespace-pre-line text-sm leading-relaxed text-[#F5F1FA] sm:text-base">
                  {response.answer}
                </p>
              )}

              {structuredList.length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold text-[#E1B983]">
                    {t.home.structuredHeading}
                  </h3>
                  <div className="overflow-x-auto rounded-lg border border-[#7A5498]/20">
                    <table className="w-full text-left text-xs">
                      <tbody className="divide-y divide-[#7A5498]/15">
                        {structuredList.map((row, i) => (
                          <tr key={i} className="bg-[#1B102B]/50">
                            <td className="px-3 py-2 font-medium text-[#D6CBE8]">
                              {String(row.quantity_name || row.title || row.investigation || row.parameter || `Record ${i + 1}`)}
                              {Array.isArray(row.quality_flags) && row.quality_flags.length > 0 && <span className="block mt-1 text-[#E1B983]">{row.quality_flags.map(String).join(' · ')}</span>}
                            </td>
                            <td className="px-3 py-2 font-mono-tabular text-[#22D3EE]">
                              {row.value !== undefined ? `${row.value}${row.unit ? ` ${row.unit}` : ' (unit unknown)'}` : ''}
                            </td>
                            <td className="px-3 py-2 text-[#B8A9CE]">
                              {row.source_file ? `${row.investigation_id} · ${row.source_file} · ${row.source_location}` : row.source
                                ? String(row.source)
                                : typeof row.conditions === 'string'
                                  ? row.conditions
                                  : ''}
                              {typeof row.citation_url === 'string' && <a className="block text-[#22D3EE]" href={row.citation_url} target="_blank" rel="noreferrer">NASA source ↗</a>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {Array.isArray(response?.sources) && response.sources.length > 0 && (
                <div>
                  <h3 className="mb-1.5 text-xs font-semibold text-[#E1B983]">
                    {t.home.sourcesHeading}
                  </h3>
                  <ul>{response.sources.map((src, idx) => renderSourceEntry(src, idx))}</ul>
                </div>
              )}
              <details className="text-xs text-[#B8A9CE]"><summary className="cursor-pointer">Retrieval method & limits</summary><p className="mt-2">{String(response?.routing_reason || '')}</p>{Array.isArray(response?.notes) && response.notes.filter(Boolean).map((note,i)=><p className="mt-2" key={i}>{String(note)}</p>)}</details>
            </div>
          )}
        </section>
      )}

      {/* Unobtrusive Scientific Honesty Statement */}
      <footer className="mt-8 border-t border-[#7A5498]/20 pt-4 text-center">
        <p className="text-xs text-[#9D8EC0]">{t.honestyNotice}</p>
      </footer>
    </main>
  );
}
