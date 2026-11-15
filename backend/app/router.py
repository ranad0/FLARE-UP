"""Three-way routing, retaining the original decision fields."""
import re
NUMERIC_TERMS = {'compare','measured','measurements','measurement','values','value','numeric','diameter','dext','dext_cool','dext_hot','dflame','tad','zst','burn time','burn duration','burn rate','burning rate','flow rate','which fuels','what fuels','fuels tested','قارن','قياسات'}
INTERPRETIVE_TERMS = {'why','explain','interpret','implication','implications','meaning','how','لماذا','اشرح','كيف','فسر','ليش'}
def _contains(text,term):
    return bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text))
def route_question(question):
    q=' '.join(question.lower().split())
    hits=sum(_contains(q,term) for term in NUMERIC_TERMS)
    number=bool(re.search(r'\d+(?:\.\d+)?',q))
    unit=bool(re.search(r'\d+(?:\.\d+)?\s*(?:atm|bar|psi|mm|mg/s|%|k\b|seconds?)',q))
    interpretation=any(_contains(q,term) for term in INTERPRETIVE_TERMS)
    quantitative=hits>0 or unit
    route='hybrid' if quantitative and interpretation else 'structured' if quantitative else 'text'
    return {'route':route,'reason':{'text':'Descriptive question: retrieve relevant source passages.','structured':'Quantitative question: filter validated source records.','hybrid':'Quantitative request with interpretation: retrieve records and relevant passages.'}[route], 'numeric_term_hits':hits,'has_number':number,'has_unit':unit,'has_measurement_target':hits>0,'asks_interpretation':interpretation}
