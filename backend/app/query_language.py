"""Conservative Arabic topic expansion; original questions and source text stay intact."""
import re

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06ff]',text))

def normalize_arabic(text):
    text=re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
    return text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي'}))

def expand_query(question):
    normalized=normalize_arabic(question)
    glossary={
        'حريق':'fire combustion','النار':'fire combustion flame','لهب':'flame',
        'دخان':'smoke','اكسجين':'oxygen','تهويه':'ventilation airflow','تهوية':'ventilation airflow',
        'هواء':'airflow','تدفق':'flow','انطفاء':'extinction','اطفاء':'suppression extinction',
        'جاذبي':'gravity microgravity','فضاء':'microgravity space','وقود':'fuel','ضغط':'pressure',
        'انتشار':'spread','اشتعال':'ignition','احتراق':'combustion','شكل':'shape',
        'كروي':'spherical','ازرق':'blue','يتصرف':'behavior shape spherical','سلوك':'behavior',
        'قماش':'fabric','نسيج':'fabric','بوليمر':'polymer','سائل':'liquid droplet',
        'حرار':'temperature','سبب':'ignition combustion',
    }
    terms=list(dict.fromkeys(v for k,v in glossary.items() if k in normalized))
    if re.search(r'\b(?:look like|looks? in|appearance|shape)\b',question,re.I):
        terms.append('flame shape spherical hemispherical appearance buoyancy')
    if re.search(r'\bin space\b',question,re.I):terms.append('microgravity')
    return question+' '+' '.join(terms) if terms else question
