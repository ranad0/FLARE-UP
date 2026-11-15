"""Separate official challenge context from the judged PSI flight collection."""
import hashlib,json,pathlib,urllib.parse,urllib.request
from bs4 import BeautifulSoup
from pypdf import PdfReader
from build_corpus import clean, split_text
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'backend/data/supplemental'; RAW=OUT/'raw'
RESOURCES=[
 ('nasa-combustion-science','https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/'),
 ('nasa-researchers-guide','https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/'),
 ('apollo-1','https://sma.nasa.gov/sma-disciplines/accllp/apollo-1'),
 ('apollo-13','https://sma.nasa.gov/sma-disciplines/accllp/apollo-13'),
 ('mir-fire','https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/'),
 ('spinoff-9582','https://spinoff.nasa.gov/node/9582'),
 ('spinoff-9407','https://spinoff.nasa.gov/node/9407'),
 ('spinoff-9918','https://spinoff.nasa.gov/node/9918'),
]
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FLARE-UP research corpus/1.0'}),timeout=60) as r: return r.read(),r.url
def main():
    RAW.mkdir(parents=True,exist_ok=True); catalog=[]; chunks=[]
    def addchunks(row,text,location):
        for i,block in enumerate(split_text(text)):
            if len(block)<70: continue
            chunks.append({'chunk_id':hashlib.sha256((row['id']+location+str(i)+block).encode()).hexdigest()[:24],'resource_id':row['id'],'investigation_id':None,'investigation_title':row['title'],'source_class':'contextual_resource','project_type':None,'judged_eligible':False,'content_type':'supporting_context','evidence_role':'historical_or_educational_context_not_flight_dataset','source_file':row['source_file'],'source_location':location+f'; segment:{i+1}','citation_url':row['url'],'source_sha256':row['sha256'],'doi':None,'text':block,'embedding_text':row['title']+' '+block,'retrieved_date':'2026-11-15'})
    for rid,url in RESOURCES:
        row={'id':rid,'url':url,'source_class':'contextual_resource','judged_eligible':False,'retrieved_date':'2026-11-15'}
        try:
            path=RAW/(rid+'.html')
            body,final=(path.read_bytes(),url) if path.exists() else fetch(url)
            path.write_bytes(body)
            soup=BeautifulSoup(body,'html.parser'); title=clean(soup.title.get_text()) if soup.title else rid
            main=soup.find('article') or soup.find('main') or soup.select_one('.accllp') or soup.body or soup
            pdfs=[]
            if rid=='nasa-researchers-guide':
                for a in main.find_all('a',href=True):
                    href=urllib.parse.urljoin(final,a['href'])
                    if '.pdf' in href.lower() and urllib.parse.urlparse(href).hostname.endswith('nasa.gov'): pdfs.append(href)
            for tag in main.find_all(['script','style','nav','footer','header','noscript','aside']): tag.decompose()
            for tag in main.select('.reveal, input, button, [aria-hidden="true"]'): tag.decompose()
            text=clean(main.get_text(' ',strip=True))
            text=text.split('Keep Exploring Discover More Topics From NASA')[0]
            row.update(title=title,final_url=final,source_file=path.name,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),status='text_ingested' if len(text)>70 else 'metadata_only_no_readable_text',characters=len(text))
            (RAW/(rid+'.txt')).write_text(text,encoding='utf8'); addchunks(row,text,'HTML main/article text')
            for index,pdfurl in enumerate(dict.fromkeys(pdfs)):
                pdfrow={'id':rid+'-pdf-'+str(index+1),'url':pdfurl,'source_class':'contextual_resource','judged_eligible':False,'retrieved_date':'2026-11-15'}
                try:
                    pdfpath=RAW/(pdfrow['id']+'.pdf')
                    pdfbody,pdffinal=(pdfpath.read_bytes(),pdfurl) if pdfpath.exists() else fetch(pdfurl)
                    pdfpath.write_bytes(pdfbody); reader=PdfReader(pdfpath)
                    pdfrow.update(title='NASA researcher guide: Combustion Science (linked PDF)',source_file=pdfpath.name,sha256=hashlib.sha256(pdfbody).hexdigest(),bytes=len(pdfbody),status='page_text_ingested_not_table_validated',pages=len(reader.pages),final_url=pdffinal)
                    for page_no,page in enumerate(reader.pages,1): addchunks(pdfrow,page.extract_text() or '',f'PDF page:{page_no}')
                except Exception as e: pdfrow.update(title=pdfrow['id'],status='inaccessible',error=type(e).__name__)
                catalog.append(pdfrow)
        except Exception as e: row.update(title=rid,status='inaccessible',error=type(e).__name__)
        catalog.append(row);print(rid,row['status'],flush=True)
    catalog.append({'id':'youtube-W1oXykoz9zg','title':'Challenge-linked video W1oXykoz9zg (title not independently verified)','url':'https://www.youtube.com/watch?v=W1oXykoz9zg','source_class':'contextual_resource','status':'metadata_only_no_transcript','judged_eligible':False,'retrieved_date':'2026-11-15'})
    for row in catalog: row['text_chunks']=sum(x['resource_id']==row['id'] for x in chunks)
    (OUT/'resource_catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')
    (OUT/'chunks.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in chunks),encoding='utf8')
    print('Supporting resources',len(catalog),'chunks',len(chunks),flush=True)
if __name__=='__main__': main()
