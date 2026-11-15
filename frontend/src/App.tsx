import {LabBoundary} from './components/LabBoundary';
import { lazy, Suspense, useEffect, useState } from 'react';
const FireLabPage=lazy(()=>import('./components/FireLabPage').then(m=>({default:m.FireLabPage})));
import { HomePage } from './components/HomePage';
import { CursorAtmosphere } from './components/CursorAtmosphere';
import type { VisualMode } from './components/visualMode';
import { StarfieldBackground } from './components/StarfieldBackground';
import { TopNav } from './components/TopNav';
import { ResearchPage } from './components/ResearchPage';
import { TRANSLATIONS } from './i18n/translations';
import type { Language, PageView } from './types/flare';

export default function App() {
  const [mode, setMode] = useState<VisualMode>('micro');
  const [page, setPage] = useState<PageView>('home');
  const [lang, setLang] = useState<Language>('en');

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const t = TRANSLATIONS[lang];

  return (
    <div data-visual-mode={mode} className="flare-app relative flex min-h-screen flex-col text-[#F5F1FA]">
      <StarfieldBackground />
      <CursorAtmosphere mode={mode} />
      <TopNav
        mode={mode}
        page={page}
        onNavigate={setPage}
        lang={lang}
        onToggleLang={() => setLang((prev) => (prev === 'en' ? 'ar' : 'en'))}
        t={t}
      />
      {page === 'home' ? (
        <HomePage t={t} onOpenLab={()=>setPage('lab')} mode={mode} onModeChange={setMode} />
      ) : page === 'research' ? (
        <ResearchPage lang={lang} />
      ) : (
        <LabBoundary><Suspense fallback={<p className="relative z-10 p-12 text-center">{lang==='ar'?'جارٍ تحميل المختبر…':'Preparing the Fire Lab…'}</p>}><FireLabPage t={t} mode={mode} onModeChange={setMode} /></Suspense></LabBoundary>
      )}
    </div>
  );
}
