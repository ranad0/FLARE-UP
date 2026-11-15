from __future__ import annotations

from app.config import GROQ_API_KEY, GROQ_MODEL

SYSTEM_PROMPT = """You are FLARE UP, a scientific evidence assistant for NASA microgravity combustion research.
Use ONLY the evidence provided. Respond in the same language as the user's question.

Use these headings exactly (translate the heading text only when the user writes in Arabic):
1. Reported by sources
2. Interpretation
3. Not established
4. Sources

Rules:
- Never invent findings, values, units, experimental conditions, identities, or safety recommendations.
- Dataset-index records provide context, not measurement evidence.
- Structured records apply only to their exact listed conditions.
- Separate model values from experimental values.
- Keep null units unknown.
- Clearly label nearest-sample and calculated-range results.
- Cite file and page/row location.
- PSI-117 is an unverified investigation label. PSI-159 is verified.
- Be concise and understandable to nontechnical users.
"""


def _fallback(question: str, evidence: str) -> str:
    return (
        "1. Reported by sources\n"
        "Evidence was retrieved successfully, but generated interpretation is unavailable. "
        "Inspect the returned source and structured-result cards for the exact records.\n\n"
        "2. Interpretation\nNo generated interpretation is available in fallback mode.\n\n"
        "3. Not established\nNo claim beyond the retrieved records is established.\n\n"
        "4. Sources\nSee the sources and structured_results fields in this response."
    )


def generate_grounded_answer(question: str, evidence_text: str) -> tuple[str, str]:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your"):
        return _fallback(question, evidence_text), "fallback-no-key"
    try:
        from groq import Groq
        response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"QUESTION:\n{question}\n\nRETRIEVED EVIDENCE:\n{evidence_text}"},
            ],
        )
        return response.choices[0].message.content or "", "groq"
    except Exception:
        return _fallback(question, evidence_text), "fallback-connection"
