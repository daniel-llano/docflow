"""Local document extraction: PII masking, keywords, language, amounts, dates, and a short summary.

Everything runs in-process with the standard library, so documents never leave your servers.
"""

from __future__ import annotations

import re
from collections import Counter

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s\-().]{7,}\d(?!\w)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")
AMOUNT = re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d{2})?|\d[\d,]*(?:\.\d{2})?\s?(?:USD|EUR|GBP))")
DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4})\b")
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")

STOPWORDS = {
    "en": {"the", "and", "for", "that", "with", "this", "from", "are", "was", "were", "have", "has", "had", "will",
           "you", "your", "our", "their", "they", "not", "but", "can", "all", "any", "must", "please", "should", "would",
           "between", "every", "each", "either", "per", "into", "also", "about", "after", "before", "over", "under",
           "than", "then", "there", "these", "those", "which", "when", "where", "who", "what", "its", "his", "her",
           "starts", "via", "upon", "within", "without", "here", "been", "being", "more", "most", "such", "only"},
    "es": {"el", "la", "los", "las", "que", "por", "para", "con", "del", "una", "como", "este", "esta", "pero", "sus"},
    "fr": {"le", "la", "les", "des", "que", "pour", "avec", "une", "dans", "est", "pas", "sur", "par", "nous", "vous"},
    "de": {"der", "die", "das", "und", "mit", "für", "ist", "nicht", "ein", "eine", "auf", "den", "dem", "sie", "wir"},
    "pt": {"o", "os", "as", "que", "para", "com", "uma", "não", "por", "dos", "das", "como", "mais", "seu", "sua"},
}
ALL_STOPWORDS = set().union(*STOPWORDS.values())


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    counts = {"email": 0, "phone": 0, "card": 0, "iban": 0}

    def replace(kind: str, label: str):
        def _sub(match: re.Match) -> str:
            counts[kind] += 1
            return label
        return _sub

    def card(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            counts["card"] += 1
            return "[CARD]"
        return match.group()

    def phone(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 9 <= len(digits) <= 15 and not DATE.fullmatch(match.group().strip()):
            counts["phone"] += 1
            return "[PHONE]"
        return match.group()

    masked = EMAIL.sub(replace("email", "[EMAIL]"), text)
    masked = IBAN.sub(replace("iban", "[IBAN]"), masked)
    masked = CARD.sub(card, masked)
    masked = PHONE.sub(phone, masked)
    return masked, counts


def language_guess(text: str) -> str:
    words = [w.lower() for w in re.findall(r"[^\W\d_]+", text, re.UNICODE)]
    scores = {lang: sum(1 for w in words if w in stops) for lang, stops in STOPWORDS.items()}
    lang, score = max(scores.items(), key=lambda kv: kv[1])
    return lang if score >= 2 else "unknown"


def keywords(text: str, n: int = 10) -> list[str]:
    words = [w.lower() for w in WORD.findall(text)]
    counts = Counter(w for w in words if w not in ALL_STOPWORDS)
    return [w for w, _ in counts.most_common(n)]


def summary(text: str, sentences: int = 2) -> str:
    parts = [s.strip() for s in SENTENCE.split(text.strip()) if s.strip()]
    return " ".join(parts[:sentences])[:400]


def extract(text: str) -> dict:
    body = (text or "").strip()
    if not body:
        raise ValueError("The document has no text.")
    masked, pii = mask_pii(body)
    words = len(body.split())
    return {
        "word_count": words,
        "reading_minutes": max(1, round(words / 220)),
        "language": language_guess(body),
        "keywords": keywords(body),
        "amounts": sorted(set(AMOUNT.findall(body)))[:20],
        "dates": sorted(set(DATE.findall(body)))[:20],
        "pii": pii,
        "pii_masked": any(pii.values()),
        "summary": mask_pii(summary(body))[0],
        "masked_preview": masked[:1000],
    }
