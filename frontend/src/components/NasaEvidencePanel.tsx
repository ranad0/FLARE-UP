import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, X } from 'lucide-react';
import type { TranslationBundle } from '../i18n/translations';
import type { EvidenceRecord, ScenarioAnalyzeResponse, SourceItem } from '../types/flare';

interface NasaEvidencePanelProps {
  t: TranslationBundle;
  loading: boolean;
  loadingStepIndex: number;
  data: ScenarioAnalyzeResponse | null;
  errorMessage: string | null;
  onClose?: () => void;
}

function formatKeyValuePairs(obj: Record<string, unknown>): Array<{ label: string; value: string }> {
  return Object.entries(obj)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => ({
      label: k.replace(/_/g, ' '),
      value: typeof v === 'object' ? JSON.stringify(v) : String(v),
    }));
}

function isLimitedEvidence(data: ScenarioAnalyzeResponse): boolean {
  const em = data.evidence_match;
  if (typeof em === 'string') {
    return /limited|partial|none|no direct|not available|insufficient/i.test(em);
  }
  if (em && typeof em === 'object') {
    if (em.limited === true || em.exact_match === false) return true;
    const text = `${em.status || ''} ${em.level || ''} ${em.match_quality || ''} ${em.summary || ''}`;
    if (/limited|partial|none|no direct|not available|insufficient/i.test(text)) return true;
  }
  if (data.analysis && typeof data.analysis === 'object' && data.analysis.limited_evidence === true) {
    return true;
  }
  if (Array.isArray(data.closest_records) && data.closest_records.length === 0) {
    return true;
  }
  return false;
}

export function NasaEvidencePanel({
  t,
  loading,
  loadingStepIndex,
  data,
  errorMessage,
  onClose,
}: NasaEvidencePanelProps) {
  const arabic=/[\u0600-\u06ff]/.test(t.evidence.panelTitle);
  const choose=(en:string,ar:string)=>arabic?ar:en;
  const renderRecordNumericalRows = (records: EvidenceRecord[]) => {
    return records.map((rec, idx) => {
      const sourceLabel =
        rec.investigation || rec.title || rec.mission || rec.experiment || rec.source || `${t.evidence.sourceRowPrefix} ${idx + 1}`;
      const metrics: Array<{ label: string; value: string }> = [];

      if (rec.gravity !== undefined) metrics.push({ label: 'gravity', value: String(rec.gravity) });
      if (rec.oxygen_percent !== undefined) metrics.push({ label: 'oxygen', value: `${rec.oxygen_percent}%` });
      if (rec.pressure_psi !== undefined) metrics.push({ label: 'pressure', value: `${rec.pressure_psi} psi` });
      if (rec.airflow !== undefined) metrics.push({ label: 'airflow', value: String(rec.airflow) });
      if (rec.sample_type !== undefined) metrics.push({ label: 'sample', value: String(rec.sample_type) });

      if (rec.reported_values && typeof rec.reported_values === 'object' && !Array.isArray(rec.reported_values)) {
        metrics.push(...formatKeyValuePairs(rec.reported_values));
      }

      const findingsText = Array.isArray(rec.findings)
        ? rec.findings.join(' · ')
        : rec.findings || rec.summary || '';

      return (
        <div
          key={idx}
          className="rounded-lg border border-[#7A5498]/25 bg-[#19102A]/80 p-3.5 space-y-2"
        >
          <div className="flex items-start justify-between gap-2">
            <span className="text-xs font-semibold text-[#F5F1FA]">{String(sourceLabel)}</span>
            {rec.url && (
              <a
                href={String(rec.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex shrink-0 items-center gap-1 text-xs text-[#22D3EE] hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          {metrics.length > 0 && (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[#7A5498]/15 pt-2 text-xs">
              {metrics.map((m, mIdx) => (
                <div key={mIdx} className="flex items-baseline justify-between gap-2">
                  <span className="text-[#9D8EC0] capitalize">{m.label}</span>
                  <span className="font-mono-tabular text-[#E1B983]">{m.value}</span>
                </div>
              ))}
            </div>
          )}

          {findingsText && (
            <p className="text-xs leading-relaxed text-[#D6CBE8]">{String(findingsText)}</p>
          )}

          {rec.citation && (
            <p className="text-[11px] text-[#9D8EC0]">{String(rec.citation)}</p>
          )}
          {rec.source && <p className="text-[11px] text-[#9D8EC0]">{String(rec.source)}</p>}
          {Boolean(rec.match_basis) && <p className="text-[11px] text-[#E1B983]">{String(rec.match_basis)}</p>}
        </div>
      );
    });
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div className="py-6 space-y-4" aria-live="polite">
          {t.evidence.loadingSteps.map((step, idx) => {
            const isDone = idx < loadingStepIndex;
            const isActive = idx === loadingStepIndex;
            return (
              <div
                key={step}
                className={`flex items-center gap-3 rounded-lg border px-3.5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'border-[#E1B983]/50 bg-[#231538] text-[#F5F1FA]'
                    : isDone
                      ? 'border-[#7A5498]/25 bg-[#19102A]/60 text-[#B8A9CE]'
                      : 'border-[#7A5498]/15 bg-transparent text-[#7D6E99]'
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-[#22D3EE]" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#E1B983]" />
                ) : (
                  <span className="h-4 w-4 shrink-0 rounded-full border border-[#7A5498]/40" />
                )}
                <span>{step}</span>
              </div>
            );
          })}
        </div>
      );
    }

    if (errorMessage) {
      return (
        <div className="rounded-lg border border-[#E1B983]/45 bg-[#23142E] p-4 space-y-2">
          <div className="flex items-center gap-2 text-[#E1B983]">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="text-sm font-semibold">{errorMessage}</span>
          </div>
        </div>
      );
    }

    if (!data) {
      return <p className="py-4 text-sm leading-relaxed text-[#B8A9CE]">{t.evidence.emptyPrompt}</p>;
    }

    const limited = isLimitedEvidence(data);
    const analysisObj = data.analysis && typeof data.analysis === 'object' ? data.analysis : null;
    const analysisStr = typeof data.analysis === 'string' ? data.analysis : null;
    const records = Array.isArray(data.closest_records) ? data.closest_records : [];
    const relatedSources=(data.sources || []).filter((s):s is SourceItem=>typeof s!=='string');
    const relatedIds=[...new Set(relatedSources.map(s=>String(s.investigation_id || s.investigation || '')).filter(Boolean))];

    // 1. Evidence Match
    const evidenceMatchText =
      typeof data.evidence_match === 'string'
        ? data.evidence_match
        : data.evidence_match?.summary ||
          data.evidence_match?.level ||
          data.evidence_match?.status ||
          data.evidence_match?.match_quality ||
          t.evidence.notSpecified;

    // 2. Closest NASA investigation
    const closestInvestigation =
      analysisObj?.closest_investigation ||
      records[0]?.investigation ||
      records[0]?.title ||
      records[0]?.mission ||
      t.evidence.notSpecified;

    // 3. Closest experimental conditions
    const closestConditionsRaw =
      analysisObj?.closest_experimental_conditions ||
      records[0]?.conditions ||
      (records[0]
        ? {
            gravity: records[0].gravity,
            oxygen_percent: records[0].oxygen_percent !== undefined ? `${records[0].oxygen_percent}%` : undefined,
            pressure_psi: records[0].pressure_psi !== undefined ? `${records[0].pressure_psi} psi` : undefined,
            airflow: records[0].airflow,
            sample_type: records[0].sample_type,
          }
        : null);

    // 4. Reported by Sources
    const reportedBySources = analysisObj?.reported_by_sources;

    // 5. Interpretation
    const interpretation = analysisObj?.interpretation || analysisStr;

    // 6. Not Established
    const notEstablished = analysisObj?.not_established;

    // 7. Sources
    const sourceList: Array<SourceItem | string> = Array.isArray(data.sources)
      ? data.sources
      : records.map((r) => ({
          title: r.investigation || r.title || r.source,
          citation: r.citation,
          url: r.url,
        }));

    return (
      <div className="space-y-5">
        {relatedSources.length > 0 && <div className="rounded-lg border border-[#22D3EE]/25 bg-[#22D3EE]/5 p-4 space-y-2">
          <p className="text-sm font-medium text-[#F5F1FA]">{choose('Related NASA evidence found', 'تم العثور على أدلة ناسا مرتبطة')}</p>
          <p className="text-xs leading-6 text-[#B8A9CE]">{choose(`${relatedSources.length} passages · ${relatedIds.join(', ')}`, `${relatedSources.length} مقاطع · ${relatedIds.join('، ')}`)}</p>
          <p className="text-xs leading-6 text-[#D6CBE8]">{records.length ? choose('Reported pressure records are available. Oxygen, fuel composition and airflow are not matched.', 'تتوفر سجلات ضغط منشورة. لم تتم مطابقة الأكسجين وتركيب الوقود وتدفق الهواء.') : choose('These studies relate to the selected material. Your combined settings are not an experimentally validated match.', 'تتعلق هذه الدراسات بنوع العينة المختار، لكن مجموعة إعداداتك لا تطابق تجربة متحققاً منها.')}</p>
        </div>}

        {/* Evidence Match */}
        <section className="space-y-1 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {t.evidence.sections.evidenceMatch}
          </h3>
          <p className="text-sm leading-6 text-[#F5F1FA]">{arabic && relatedSources.length ? (records.length ? 'أدلة مرتبطة مع سجلات ضغط قريبة؛ لا يوجد تطابق كامل للشروط.' : 'أدلة مرتبطة بنوع العينة؛ لا يوجد تطابق كامل للشروط.') : String(evidenceMatchText)}</p>
        </section>

        {/* Closest NASA investigation */}
        <section className="space-y-1 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {records.length ? t.evidence.sections.closestInvestigation : choose('Related NASA investigations', 'تحقيقات ناسا المرتبطة')}
          </h3>
          <p className="text-sm font-medium text-[#F5F1FA]">{records.length ? String(closestInvestigation) : relatedIds.join(' · ') || t.evidence.notSpecified}</p>
        </section>

        {/* Closest experimental conditions */}
        <section className="space-y-2 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {t.evidence.sections.closestConditions}
          </h3>
          {typeof closestConditionsRaw === 'string' ? (
            <p className="text-xs leading-relaxed text-[#D6CBE8]">{closestConditionsRaw}</p>
          ) : Array.isArray(closestConditionsRaw) ? (
            <ul className="space-y-1 text-xs text-[#D6CBE8]">
              {closestConditionsRaw.map((item, idx) => (
                <li key={idx}>• {String(item)}</li>
              ))}
            </ul>
          ) : closestConditionsRaw && typeof closestConditionsRaw === 'object' ? (
            <div className="grid grid-cols-1 gap-1.5 text-xs">
              {formatKeyValuePairs(closestConditionsRaw as Record<string, unknown>).map((pair, idx) => (
                <div key={idx} className="flex items-baseline justify-between gap-3">
                  <span className="capitalize text-[#B8A9CE]">{pair.label}</span>
                  <span className="font-mono-tabular text-[#F5F1FA]">{pair.value}</span>
                </div>
              ))}
              {formatKeyValuePairs(closestConditionsRaw as Record<string, unknown>).length === 0 && (
                <p className="text-xs text-[#9D8EC0]">{t.evidence.notSpecified}</p>
              )}
            </div>
          ) : (
            <p className="text-xs leading-6 text-[#9D8EC0]">{choose('The selected oxygen, pressure and airflow combination is not matched. See the source passages for their experimental scope.', 'لم تتم مطابقة مجموعة الأكسجين والضغط وتدفق الهواء المختارة. راجع المقاطع المصدرية لمعرفة نطاق تجاربها.')}</p>
          )}
        </section>

        {/* Reported by Sources (numerical values tied directly to source rows) */}
        <section className="space-y-2.5 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {t.evidence.sections.reportedBySources}
          </h3>
          {records.length > 0 && <div className="space-y-2.5">{renderRecordNumericalRows(records)}</div>}
          {Array.isArray(reportedBySources) ? (
            <ul className="space-y-1.5 text-xs text-[#D6CBE8]">
              {reportedBySources.map((item, idx) => (
                <li key={idx} className="rounded-md bg-[#1B102B]/60 px-3 py-2">
                  {typeof item === 'string' ? item : item.passage ? <div className="space-y-2 leading-6">
                    <p className="font-semibold text-[#78CFFF]">{String(item.investigation || '')}</p>
                    <p className="text-[11px] text-[#B8A9CE]">{String(item.evidence_type || '').replaceAll('_',' ')}</p>
                    <p>{String(item.passage).length > 320 ? String(item.passage).slice(0,320).replace(/\s+\S*$/, '')+' […]' : String(item.passage)}</p>
                    <details><summary className="cursor-pointer text-[#78CFFF]">{choose('Read full source passage', 'قراءة المقطع المصدري الكامل')}</summary><p className="mt-2">{String(item.passage)}</p></details>
                    <p className="break-words text-[11px] text-[#9D8EC0]">{String(item.source || '')} · {String(item.location || '')}</p>
                  </div> : formatKeyValuePairs(item).map(p=>`${p.label}: ${p.value}`).join(' · ')}
                </li>
              ))}
            </ul>
          ) : typeof reportedBySources === 'string' && reportedBySources ? (
            <p className="text-xs leading-relaxed text-[#D6CBE8]">{reportedBySources}</p>
          ) : records.length === 0 ? (
            <p className="text-xs text-[#9D8EC0]">{t.evidence.notSpecified}</p>
          ) : null}
        </section>

        {/* Interpretation */}
        <section className="space-y-1.5 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {t.evidence.sections.interpretation}
          </h3>
          {Array.isArray(interpretation) ? (
            <ul className="space-y-1 text-xs leading-relaxed text-[#D6CBE8]">
              {interpretation.map((line, i) => (
                <li key={i}>• {String(line)}</li>
              ))}
            </ul>
          ) : (
            <p className="whitespace-pre-line text-xs leading-relaxed text-[#D6CBE8] sm:text-sm">
              {interpretation ? String(interpretation) : t.evidence.notSpecified}
            </p>
          )}
        </section>

        {/* Not Established */}
        <section className="space-y-1.5 border-b border-[#7A5498]/20 pb-3.5">
          <h3 className="text-xs font-semibold text-[#E1B983]">
            {t.evidence.sections.notEstablished}
          </h3>
          {limited && <p className="text-xs leading-6 text-[#E1B983]">{t.evidence.limitedEvidenceBanner}</p>}
          {Array.isArray(notEstablished) ? (
            <ul className="space-y-1 text-xs leading-relaxed text-[#D6CBE8]">
              {notEstablished.filter(line => !limited || String(line)!=='Direct evidence for this exact scenario is not available.').map((line, i) => (
                <li key={i}>• {String(line)}</li>
              ))}
            </ul>
          ) : (
            <p className="whitespace-pre-line text-xs leading-relaxed text-[#D6CBE8]">
              {notEstablished ? String(notEstablished) : t.evidence.notSpecified}
            </p>
          )}
        </section>

        {/* Sources */}
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-[#E1B983]">{t.evidence.sections.sources}</h3>
          {sourceList.length > 0 ? (
            <ul className="space-y-2">
              {sourceList.map((s, idx) => {
                if (typeof s === 'string') {
                  return (
                    <li key={idx} className="text-xs text-[#D6CBE8]">
                      {s}
                    </li>
                  );
                }
                const label = s.title || s.name || s.investigation || s.document || `${t.evidence.sourceRowPrefix} ${idx + 1}`;
                const url = typeof s.url === 'string' ? s.url : typeof s.link === 'string' ? s.link : undefined;
                return (
                  <li key={idx} className="flex items-start justify-between gap-2 text-xs text-[#D6CBE8]">
                    <div>
                      <span className="font-medium text-[#F5F1FA]">{String(label)}</span>
                      {s.citation && <p className="text-[#9D8EC0]">{String(s.citation)}</p>}
                    </div>
                    {url && (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex shrink-0 items-center gap-1 text-[#22D3EE] hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-xs text-[#9D8EC0]">{t.evidence.notSpecified}</p>
          )}
        </section>

        {data.scientific_disclaimer && (
          <p className="border-t border-[#7A5498]/20 pt-3 text-[11px] leading-relaxed text-[#9D8EC0]">
            {data.scientific_disclaimer}
          </p>
        )}
      </div>
    );
  };

  return (
    <aside className="flex h-full flex-col rounded-xl border border-[#7A5498]/35 bg-[#130B20]/95">
      <div className="flex items-center justify-between gap-4 border-b border-[#7A5498]/25 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-[#F5F1FA]">{t.evidence.panelTitle}</h2>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t.lab.closeEvidenceButton}
            className="rounded-md p-1 text-[#B8A9CE] transition-colors hover:bg-[#2D1C42] hover:text-[#F5F1FA]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="flare-scroll flex-1 overflow-y-auto px-5 py-4">{renderContent()}</div>
    </aside>
  );
}
