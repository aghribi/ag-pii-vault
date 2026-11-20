import json
import logging
from typing import Optional

from presidio_analyzer import (
    AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer, EmailRecognizer, IbanRecognizer, IpRecognizer,
    PhoneRecognizer, UrlRecognizer,
)

from .models import DEFAULT_ENTITIES, Entity

logger = logging.getLogger(__name__)

# spaCy model per language; each must be installed (make spacy).
MODELS = {"en": "en_core_web_lg", "fr": "fr_core_news_lg"}

# Numbers written without a country code are read in these regions.
PHONE_REGIONS = ("FR", "US", "GB", "DE", "CH", "BE", "ES", "IT", "CA")

# French social security number (NIR): sex, year, month, department,
# commune, order, optional key.
NIR = Pattern(
    "NIR",
    r"\b[12]\s?\d{2}\s?(?:0[1-9]|1[0-2])\s?(?:\d{2}|2[AB])"
    r"\s?\d{3}\s?\d{3}(?:\s?\d{2})?\b",
    0.6,
)


def _engine(languages: list[str]) -> AnalyzerEngine:
    """Presidio with the language-free recognizers in every language."""
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": lang, "model_name": MODELS[lang]}
                   for lang in languages],
    }).create_engine()
    registry = RecognizerRegistry(supported_languages=languages)
    registry.load_predefined_recognizers(languages=languages, nlp_engine=nlp)
    shared = (EmailRecognizer, IbanRecognizer, IpRecognizer, UrlRecognizer,
              CreditCardRecognizer, PhoneRecognizer)
    registry.recognizers = [r for r in registry.recognizers
                            if not isinstance(r, shared)]
    for lang in languages:
        for kind in shared[:-1]:
            registry.add_recognizer(kind(supported_language=lang))
        registry.add_recognizer(PhoneRecognizer(
            supported_language=lang, supported_regions=PHONE_REGIONS))
        registry.add_recognizer(PatternRecognizer(
            "FR_NIR", patterns=[NIR], supported_language=lang))
    return AnalyzerEngine(registry=registry, nlp_engine=nlp,
                          supported_languages=languages)


class Detector:
    """
    PII detection using Presidio (spaCy-based) with an optional LLM fallback
    for low-confidence spans.

    Fast path  : Presidio handles ≥ 90 % of cases in < 20 ms.
    Languages  : each text is read in every language of `languages`
                 (default: `language`) and the spans are merged, so
                 mail mixing French and English loses none.
    Fallback   : GPT-4o-mini re-evaluates spans below `llm_threshold`.
                 Only active when llm_fallback=True and openai_api_key is set.
    """

    def __init__(
        self,
        entities:          Optional[list[str]] = None,
        confidence_floor:  float = 0.35,
        llm_fallback:      bool  = False,
        llm_threshold:     float = 0.7,
        openai_api_key:    Optional[str] = None,
        language:          str   = "en",
        languages:         Optional[list[str]] = None,
    ):
        self._languages       = languages or [language]
        self._engine          = (AnalyzerEngine() if self._languages == ["en"]
                                 else _engine(self._languages))
        self._entities        = entities or DEFAULT_ENTITIES
        self._confidence_floor = confidence_floor
        self._llm_fallback    = llm_fallback
        self._llm_threshold   = llm_threshold
        self._openai_api_key  = openai_api_key

    # ── Public API ────────────────────────────────────────────────────────

    def analyze(self, text: str) -> list[Entity]:
        if not text.strip():
            return []

        results = [
            r for lang in self._languages
            for r in self._engine.analyze(
                text=text,
                entities=self._entities,
                language=lang,
                score_threshold=self._confidence_floor,
            )
        ]

        if self._llm_fallback and self._openai_api_key:
            high = [r for r in results if r.score >= self._llm_threshold]
            low  = [r for r in results if r.score <  self._llm_threshold]
            confirmed = self._llm_verify(text, low) if low else []
            results = high + confirmed

        # Deduplicate overlapping spans — keep highest-score span
        results = self._deduplicate(results)

        return [Entity.from_presidio(r, text) for r in results]

    # ── Internal ──────────────────────────────────────────────────────────

    def _deduplicate(self, results):
        """Remove overlapping spans, keeping the longest, then the highest
        score: a shorter span inside a longer one would leave the rest of
        the longer one in clear text."""
        sorted_results = sorted(
            results, key=lambda r: (r.end - r.start, r.score), reverse=True)
        kept = []
        for r in sorted_results:
            if not any(r.start < k.end and r.end > k.start for k in kept):
                kept.append(r)
        return kept

    def _llm_verify(self, text: str, candidates) -> list:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._openai_api_key)
            spans = [
                {"text": text[r.start:r.end], "type": r.entity_type, "start": r.start}
                for r in candidates
            ]
            prompt = (
                f'You are a PII detection assistant. Given this text:\n"{text}"\n\n'
                f"Decide which of these candidate spans are genuine PII:\n{json.dumps(spans)}\n\n"
                'Respond with JSON: {"confirmed_starts": [list of start positions]}'
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            confirmed_starts = set(
                json.loads(response.choices[0].message.content).get("confirmed_starts", [])
            )
            return [r for r in candidates if r.start in confirmed_starts]

        except Exception as exc:
            logger.warning("LLM fallback failed, skipping: %s", exc)
            return []
