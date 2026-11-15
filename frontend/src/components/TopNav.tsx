import {useState} from 'react';

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

  const [languageOpen,setLanguageOpen]=useState(false);
  return (

    <header className="relative z-20 mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-5 py-4 sm:px-8">

      {/* Zone 1: Brand mark & wordmark */}

      <button

        type="button"

        onClick={() => onNavigate('home')}

        className="flex shrink-0 items-center gap-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-md"

      >

        <span className="brand-flame" aria-hidden="true"><img src="/flare-up-mark-transparent.png" alt="" className="original-brand-mark" data-mode={mode} /></span>

        <span className="whitespace-nowrap text-base font-[550] tracking-[0.015em] text-[#F4EFE5]">

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

              ? 'border-b border-[#E1B983] text-[#F4EFE5]'

              : 'border-b border-transparent text-[#D5CED7] hover:text-[#F4EFE5]'

          }`}

        >

          {t.nav.home}

        </button>

        <button

          type="button"

          onClick={() => onNavigate('lab')}

          className={`whitespace-nowrap shrink-0 pb-1 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-sm ${

            page === 'lab'

              ? 'border-b border-[#E1B983] text-[#F4EFE5]'

              : 'border-b border-transparent text-[#D5CED7] hover:text-[#F4EFE5]'

          }`}

        >

          {t.nav.fireLab}

        </button>

      <button type="button" onClick={()=>onNavigate('research')} className={`whitespace-nowrap shrink-0 pb-1 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E1B983] rounded-sm ${page==='research'?'border-b border-[#E1B983] text-[#F4EFE5]':'border-b border-transparent text-[#D5CED7] hover:text-[#F4EFE5]'}`}>{lang==='ar'?'الأدلة':'Evidence'}</button></nav>



      <div className="language-picker shrink-0" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setLanguageOpen(false);}} onKeyDown={e=>{if(e.key==='Escape'){setLanguageOpen(false);e.currentTarget.querySelector('button')?.focus();}}}>
        <button type="button" className="language-trigger" aria-label={lang==='en'?'Choose language':'اختر اللغة'} aria-expanded={languageOpen} aria-controls="language-options" onClick={()=>setLanguageOpen(v=>!v)}><Globe size={21} strokeWidth={1.6} aria-hidden="true" /></button>
        {languageOpen && <div id="language-options" className="language-options" role="group" aria-label={lang==='en'?'Language':'اللغة'}>
          {([['ar','العربية'],['en','English']] as const).map(([value,label])=><button key={value} type="button" lang={value} aria-pressed={lang===value} onClick={()=>{if(lang!==value)onToggleLang();setLanguageOpen(false);}}><span>{label}</span><span aria-hidden="true">{lang===value?'✓':''}</span></button>)}
        </div>}
      </div>
    </header>

  );

}

