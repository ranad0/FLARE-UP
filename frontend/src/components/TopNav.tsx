import {HomeFlameScene} from './OrbScene';
import { Globe } from 'lucide-react';
import type {VisualMode} from './visualMode';
import type { Language, PageView } from '../types/flare';
import type { TranslationBundle } from '../i18n/translations';

interface TopNavProps {
  mode: VisualMode;
  page: PageView;
  onNavigate: (page: PageView) => void;
  lang: Language;
  onToggleLang: () => void;
  t: TranslationBundle;
}

export function TopNav({ mode, page, onNavigate, lang, onToggleLang, t }: TopNavProps) {
  return (
    <header className="relative z-20 mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-5 py-4 sm:px-8">
      {/* Zone 1: Brand mark & wordmark */}
      <button
        type="button"
        onClick={() => onNavigate('home')}
        className="flex shrink-0 items-center gap-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-md"
      >
        <span className="brand-flame" aria-hidden="true"><HomeFlameScene mode={mode} compact hintText="" /></span>
        <span className="whitespace-nowrap text-base font-semibold tracking-wider text-[#F5F1FA]">
          {t.brand}
        </span>
      </button>

      {/* Zone 2: Minimal navigation */}
      <nav aria-label="Primary" className="flex items-center gap-3 sm:gap-8">
        <button
          type="button"
          onClick={() => onNavigate('home')}
          className={`whitespace-nowrap shrink-0 pb-1 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-sm ${
            page === 'home'
              ? 'border-b border-[#E1B983] text-[#F5F1FA]'
              : 'border-b border-transparent text-[#B8A9CE] hover:text-[#F5F1FA]'
          }`}
        >
          {t.nav.home}
        </button>
        <button
          type="button"
          onClick={() => onNavigate('lab')}
          className={`whitespace-nowrap shrink-0 pb-1 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-sm ${
            page === 'lab'
              ? 'border-b border-[#E1B983] text-[#F5F1FA]'
              : 'border-b border-transparent text-[#B8A9CE] hover:text-[#F5F1FA]'
          }`}
        >
          {t.nav.fireLab}
        </button>
      <button type="button" onClick={()=>onNavigate('research')} className={`text-sm whitespace-nowrap ${page==='research'?'text-[#E1B983]':'text-[#B8A9CE]'}`}>{lang==='ar'?'الأدلة':'Evidence'}</button></nav>

      {/* Zone 3: Language toggle */}
      <div className="shrink-0">
        <button
          type="button"
          onClick={onToggleLang}
          aria-label={lang === 'en' ? 'Switch language to Arabic' : 'Switch language to English'}
          title={lang === 'en' ? 'Switch language to Arabic' : 'Switch language to English'}
          className="flex h-11 w-11 items-center justify-center rounded-lg border border-[#7A5498]/40 bg-[#1B102B]/80 text-[#E1B983] transition-colors duration-150 hover:border-[#E1B983]/60 hover:bg-[#2D1C42] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983]"
        >
          <Globe size={20} strokeWidth={1.7} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
