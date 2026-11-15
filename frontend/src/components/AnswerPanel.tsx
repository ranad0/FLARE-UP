import { useState } from 'react';
import type { AskResponse, SourceItem, StructuredResultRow } from '../types/flare';

const text = (value: unknown) => value == null ? '' : String(value);
const roleName = (source: SourceItem) => text(source.content_type || source.evidence_type || 'Source passage').replaceAll('_', ' ');
const describe = (value: unknown): string => value && typeof value === 'object'
  ? Object.entries(value).map(([key, v]) => `${key.replaceAll('_', ' ')}: ${describe(v)}`).join(' · ')
  : value == null ? 'unknown' : String(value);
// Select an existing sentence, never rewrite it. Full context stays one click away.
function previewPassage(passage: string, question: string) {
  const stop = new Set(['how','does','what','which','compare','explain','about','with','from','that','this','the','and','for','space','experiment','psi']);
  const terms = [...new Set(question.toLowerCase().match(/[a-z]{3,}/g) || [])].filter(t => !stop.has(t));
  const sentences = passage.split(/(?<=[.!?])\s+(?=[A-Z])/);
  let best = sentences[0] || passage, bestScore = 0, bestIndex = 0;
  for (const [index, sentence] of sentences.entries()) {
    const score = terms.filter(term => sentence.toLowerCase().includes(term)).length;
    if (score > bestScore) { best = sentence; bestScore = score; bestIndex = index; }
  }
  const next = sentences[bestIndex + 1];
  if (next && /^(However|But|Under|Nevertheless|Although|Only|These|This)\b/.test(next)) best += ' ' + next;
  return best.length > 650 ? best.slice(0,650).replace(/\s+\S*$/, '') + ' […]' : best;
}

/** Presentation only: source wording, numeric values and backend routing are unchanged. */
export function AnswerPanel({ response, arabic }: { response: AskResponse; arabic: boolean }) {
  const [allRows, setAllRows] = useState(false);
  const sources = (response.sources || []).filter((s): s is SourceItem => typeof s !== 'string');
  const rows = (Array.isArray(response.structured_results) ? response.structured_results : []) as StructuredResultRow[];
  const answer = text(response.answer);
  // Keep abstentions, exclusions and quality warnings visible; the repeated record/passage prose lives below.
  const notices = answer.split(/\n\n/).filter(p => /^(No validated|No sufficiently|Source quality notes:|The supplied PSI-117)/.test(p));
  const choose = (en: string, ar: string) => arabic ? ar : en;
  const sourceUrl = (source: SourceItem) => text(source.citation_url || source.url || source.link);
  return <div className="answer-reading mt-6 space-y-6">
    <header className="space-y-2">
      <h2 className="text-lg font-medium leading-relaxed text-[#F5F1FA] sm:text-xl">{text(response.question) || choose('Your evidence', 'الأدلة المسترجعة')}</h2>
      <p className="text-sm text-[#B8A9CE]">{choose(`${sources.length} source passages · ${rows.length} records returned`, `${sources.length} مقاطع مصدرية · ${rows.length} سجلات مسترجعة`)}</p>
    </header>
    {notices.map((notice, i) => <p key={i} className="rounded-lg border border-amber-200/20 bg-amber-200/5 p-4 text-sm leading-7 text-[#F5D6A3]">{notice}</p>)}
    {rows.length > 0 && <section aria-label="Reported measurements">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-[#E1B983]">{choose('Reported measurements', 'القياسات الواردة في المصادر')}</h3>
        <span className="text-xs text-[#B8A9CE]">{choose('Source records, not predictions', 'سجلات مصدرية وليست تنبؤات')}</span>
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#7A5498]/25">
        <table className="w-full text-start text-sm">
          <thead className="bg-white/5 text-xs text-[#B8A9CE]"><tr>
            <th className="p-3 text-start font-medium">{choose('Measurement', 'القياس')}</th>
            <th className="p-3 text-start font-medium">{choose('Value', 'القيمة')}</th>
            <th className="p-3 text-start font-medium">{choose('Evidence', 'الدليل')}</th>
          </tr></thead>
          <tbody className="divide-y divide-white/5">{(allRows ? rows : rows.slice(0, 4)).map((row, i) => <tr key={i}>
            <td className="p-3 align-top text-[#D6CBE8]">{text(row.quantity_name || row.parameter || row.facet || row.title || 'Record')}
              {Array.isArray(row.quality_flags) && row.quality_flags.map((flag, n) => <span key={n} className="mt-1 block text-xs text-[#E1B983]">{text(flag)}</span>)}
            </td>
            <td className="p-3 align-top font-mono text-[#78CFFF]">{text(row.value)} <span className="text-xs">{row.kind === 'facet' ? choose('(category)', '(فئة)') : text(row.unit) || choose('(unit unknown)', '(الوحدة غير معروفة)')}</span></td>
            <td className="min-w-36 p-3 align-top text-xs text-[#B8A9CE]">
              <details><summary className="cursor-pointer leading-6 text-[#D6CBE8]">{text(row.investigation_id || row.investigation)} · {text(row.source_location) || choose('Provenance', 'المصدر')}</summary>
                <div className="mt-2 space-y-2 break-words leading-6">
                  <p>{text(row.source_file)}</p>
                  <p>{text(row.record_type || row.evidence_type || row.source_type)}</p>
                  {row.conditions && <dl>{typeof row.conditions === 'object' ? Object.entries(row.conditions).map(([k, v]) => <div key={k}><dt className="inline text-[#D6CBE8]">{k}: </dt><dd className="inline">{v == null ? 'unknown' : text(v)}</dd></div>) : <dd>{row.conditions}</dd>}</dl>}
                  {typeof row.citation_url === 'string' && <a className="text-[#78CFFF] underline" href={row.citation_url} target="_blank" rel="noreferrer">{choose('Open NASA source ↗', 'فتح مصدر ناسا ↗')}</a>}
                </div>
              </details>
            </td>
          </tr>)}</tbody>
        </table>
      </div>
      {rows.length > 4 && <button type="button" className="mt-3 rounded-md px-2 py-1 text-sm text-[#78CFFF] hover:underline" onClick={() => setAllRows(!allRows)} aria-expanded={allRows}>{allRows ? choose('Show fewer records', 'عرض سجلات أقل') : choose(`Show all ${rows.length} returned records`, `عرض جميع السجلات المسترجعة (${rows.length})`)}</button>}
      <p className="mt-2 text-xs leading-6 text-[#B8A9CE]">{choose('Different rows may have different fuels or conditions. Open Evidence before comparing values.', 'قد تختلف أنواع الوقود والظروف بين الصفوف. افتح الدليل قبل مقارنة القيم.')}</p>
    </section>}
    {sources.length > 0 && <section>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-sm font-semibold text-[#E1B983]">{choose('What the sources say', 'ما تقوله المصادر')}</h3><span className="text-xs text-[#B8A9CE]">{choose('Ranked by query relevance', 'مرتبة حسب صلتها بالسؤال')}</span></div>
      <p className="mb-4 text-xs leading-6 text-[#B8A9CE]">{choose('Source excerpts, not an AI-generated conclusion. Objectives and hypotheses are research intent—not established findings.', 'مقتطفات مصدرية وليست استنتاجاً مولداً. الأهداف والفرضيات تعبّر عن نية البحث ولا تمثل نتائج مثبتة.')}</p>
      <div className="space-y-3">{sources.slice(0, 3).map((source, i) => {
        const quote = text(source.excerpt || source.text || source.summary);
        return <article key={i} className="rounded-xl border border-white/10 bg-white/[0.025] p-4 sm:p-5">
          <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1"><span className="text-xs font-medium text-[#78CFFF]">{text(source.investigation_id)} · {i + 1}</span><span className="text-xs text-[#B8A9CE]">{roleName(source)}</span></div>
          <h4 className="text-sm font-medium leading-6 text-[#EEE7F7]">{text(source.title || source.investigation_title)}</h4>
          <blockquote className="mt-3 text-sm leading-7 text-[#D6CBE8]">“{previewPassage(quote, text(response.question))}”</blockquote>
          <details className="mt-3 text-xs text-[#B8A9CE]"><summary className="cursor-pointer py-1 text-[#78CFFF]">{choose('Read full passage & citation', 'قراءة المقطع الكامل والاستشهاد')}</summary>
            <blockquote className="my-3 whitespace-pre-line border-s-2 border-[#78CFFF]/30 ps-4 text-sm leading-7 text-[#D6CBE8]">{quote}</blockquote>
            <p className="break-words leading-6">{text(source.source_file)} · {text(source.source_location)}</p>
            {sourceUrl(source) && <a className="mt-2 inline-block text-[#78CFFF] underline" href={sourceUrl(source)} target="_blank" rel="noreferrer">{choose('Open NASA source ↗', 'فتح مصدر ناسا ↗')}</a>}
          </details>
        </article>;
      })}</div>
    </section>}
    <details className="rounded-xl border border-[#78CFFF]/20 p-4 text-sm text-[#B8A9CE]"><summary className="cursor-pointer text-[#D6CBE8]">{choose('Why these results?', 'لماذا ظهرت هذه النتائج؟')}</summary>
      <div className="mt-4 space-y-4 text-xs leading-6">
        <div><h4 className="font-semibold text-[#E1B983]">{choose('Search path', 'مسار البحث')}</h4><p>{text(response.routing_reason)}</p></div>
        {response.structured_query && typeof response.structured_query === 'object' && Object.values(response.structured_query).some(Boolean) ? <div><h4 className="font-semibold text-[#E1B983]">{choose('Recognized filters', 'عوامل التصفية المعروفة')}</h4><dl>{Object.entries(response.structured_query).filter(([, v]) => v != null && v !== false).map(([key,v]) => <div key={key}><dt className="inline">{key.replaceAll('_',' ')}: </dt><dd className="inline text-[#EEE7F7]">{describe(v)}</dd></div>)}</dl></div> : null}
        <div><h4 className="font-semibold text-[#E1B983]">{choose('Ranking & limits', 'الترتيب والحدود')}</h4><p>{choose('Text passages follow the backend’s query-relevance order. Numeric records follow recognized filters. Relevance is not scientific confidence, and returned records do not establish causation or safe operating limits.', 'تتبع المقاطع ترتيب الصلة بالسؤال من المحرك، وتتبع السجلات عوامل التصفية المعروفة. الصلة ليست ثقة علمية، ولا تثبت السجلات السببية أو حدود التشغيل الآمن.')}</p></div>
        <p>{choose('Only the verified judged corpus is searched here. Supporting NASA resources are separate; ground investigations are excluded.', 'يقتصر البحث هنا على مجموعة الأدلة المتحقق منها. موارد ناسا الداعمة منفصلة، والتحقيقات الأرضية مستبعدة.')}</p>
      </div>
    </details>
    <details className="border-t border-white/10 pt-4 text-sm text-[#B8A9CE]"><summary className="cursor-pointer py-1">{choose(`All sources & retrieval details (${sources.length})`, `جميع المصادر وتفاصيل الاسترجاع (${sources.length})`)}</summary>
      <ol className="mt-4 space-y-4">{(response.sources || []).map((source, i) => <li key={i} className="text-xs leading-6">{typeof source === 'string' ? source : <><a className="text-[#78CFFF] underline" href={sourceUrl(source)} target="_blank" rel="noreferrer">{text(source.title || source.investigation_id)}</a><p>{roleName(source)} · {text(source.source_file)} · {text(source.source_location)}</p><details><summary className="cursor-pointer">{choose('Full source passage', 'المقطع المصدري الكامل')}</summary><p className="mt-2 whitespace-pre-line">{text(source.excerpt || source.text)}</p></details></>}</li>)}</ol>
      <p className="mt-4 text-xs leading-6">{text(response.routing_reason)}</p>
      {Array.isArray(response.notes) && response.notes.filter(Boolean).map((note, i) => <p key={i} className="mt-2 text-xs leading-6">{text(note)}</p>)}
      <details className="mt-4"><summary className="cursor-pointer text-xs">{choose('Original backend response text', 'نص الاستجابة الأصلي')}</summary><p className="mt-3 whitespace-pre-line text-xs leading-6">{answer}</p></details>
    </details>
    {!sources.length && !rows.length && !notices.length && <p className="whitespace-pre-line text-sm leading-7 text-[#D6CBE8]">{answer}</p>}
  </div>;
}
