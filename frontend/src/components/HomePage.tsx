import type {VisualMode} from './visualMode';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import { askFlareUp } from '../services/flareApi';
import { AskResponse, FlareApiError } from '../types/flare';
import type { TranslationBundle } from '../i18n/translations';
import { HomeFlameScene } from './OrbScene';
import { AnswerPanel } from './AnswerPanel';

interface HomePageProps {
  t: TranslationBundle;
  onOpenLab: () => void;
  mode: VisualMode;
  onModeChange: (mode:VisualMode) => void;
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

  return (
    <main className="home-page relative z-10 mx-auto flex min-h-[calc(100vh-72px)] w-full max-w-6xl flex-col justify-between px-5 pb-6 pt-4 sm:px-8">
      <div className="hero-layout">
        {/* Primary focus: heading and Ask FLARE UP search. */}
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
            response && <AnswerPanel response={response} arabic={t.nav.home !== "Home"} />
          )}
        </section>
      )}

      <section aria-label={t.nav.home==='Home'?'Explore Fire Lab':'استكشف مختبر النار'} className="mt-16 flex flex-col items-start justify-between gap-6 rounded-2xl border px-6 py-8 sm:flex-row sm:items-center sm:px-8" style={{borderColor:'var(--edge)',background:'var(--surface)',transition:'background-color var(--transition), border-color var(--transition)'}}>
        <div className="space-y-2">
          <h2 className="text-xl font-medium text-[#F5F1FA] sm:text-2xl">{t.nav.home==='Home'?'Step into the Fire Lab':'انتقل إلى مختبر النار'}</h2>
          <p className="text-sm leading-6 text-[#B8A9CE]">{t.nav.home==='Home'?'Change the conditions. Explore the NASA evidence.':'غيّر الظروف واستكشف أدلة ناسا المرتبطة بها.'}</p>
        </div>
        <button type="button" onClick={onOpenLab} className="min-h-12 w-full shrink-0 rounded-lg px-6 py-3 text-sm font-semibold text-[#151529] focus-visible:outline-2 focus-visible:outline-offset-4 sm:w-auto" style={{background:'var(--accent)',transition:'background-color var(--transition)'}}>{t.nav.home==='Home'?'Open Fire Lab →':'افتح مختبر النار ←'}</button>
      </section>

      {/* Unobtrusive Scientific Honesty Statement */}
      <footer className="mt-8 border-t border-[#7A5498]/20 pt-4 text-center">
        <p className="text-xs text-[#9D8EC0]">{t.honestyNotice}</p>
      </footer>
    </main>
  );
}
