import {useEffect, useRef, useState} from 'react';
import {getApiBaseUrl} from '../services/flareApi';

type Resource={id:string;title:string;url:string;status:string;text_chunks?:number};
type Passage={chunk_id:string;investigation_title:string;text:string;citation_url:string;source_location:string};

export function ContextResources({ar}:{ar:boolean}) {
  const [resources,setResources]=useState<Resource[]>([]);
  const [question,setQuestion]=useState('What did the Mir fire teach us about spacecraft fire safety?');
  const [results,setResults]=useState<Passage[]>([]),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const active=useRef<AbortController|null>(null);
  useEffect(()=>{const c=new AbortController();fetch(getApiBaseUrl()+'/resources',{signal:c.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>setResources(d.resources)).catch(e=>{if(e.name!=='AbortError')setMessage('Could not load NASA resources.');});return()=>{c.abort();active.current?.abort();};},[]);
  async function search(){
    active.current?.abort();const c=new AbortController();active.current=c;setBusy(true);setResults([]);setMessage('');
    try{const r=await fetch(getApiBaseUrl()+'/resources/search',{method:'POST',signal:c.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});if(!r.ok)throw Error();const d=await r.json();if(!c.signal.aborted){setResults(d.results);if(!d.results.length)setMessage('No relevant supporting passage found.');}}
    catch(e){if(!c.signal.aborted)setMessage('Could not search NASA resources.');}
    finally{if(!c.signal.aborted)setBusy(false);}
  }
  return <section className="research-panel">
    <p className="hero-eyebrow">NASA SPACE APPS RESOURCES</p>
    <h2>{ar?'المعرفة وراء المهمة':'The knowledge behind the mission'}</h2>
    <p>{ar?'أدلة ناسا وتاريخ سلامة الرحلات وموارد التحدي. سياق داعم منفصل عن بيانات التجارب.':'NASA guides, mission safety history, and challenge resources. Supporting context, kept separate from flight measurements.'}</p>
    <form className="compare-form" onSubmit={e=>{e.preventDefault();void search();}}><input aria-label="Search NASA challenge resources" required minLength={3} maxLength={2500} value={question} onChange={e=>setQuestion(e.target.value)}/><button disabled={busy}>{busy?'…':ar?'ابحث في المصادر':'Search resources →'}</button></form>
    {message&&<p role="status" className="notice">{message}</p>}
    {results.map(p=><article className="evidence-card my-4" key={p.chunk_id}><div className="card-meta">SUPPORTING CONTEXT · {p.source_location}</div><h3><a href={p.citation_url} target="_blank" rel="noreferrer">{p.investigation_title} ↗</a></h3><p className="whitespace-pre-line">{p.text}</p></article>)}
    <details className="mt-5"><summary className="cursor-pointer text-[#DAB87B]">{ar?'جميع موارد التحدي':'Browse challenge resources'} ({resources.length})</summary><ul className="mt-4 space-y-3">{resources.map(r=><li key={r.id}><a className="text-[#C5B7DE] hover:text-[#F0DEC2]" href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a><span className="block text-xs opacity-65">{r.text_chunks||0} passages · {r.status.replaceAll('_',' ')}</span></li>)}</ul></details>
  </section>;
}
