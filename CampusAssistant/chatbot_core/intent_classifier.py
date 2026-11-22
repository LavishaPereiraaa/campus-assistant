"""Intent detection + confidence scoring.

No LLM calls. Uses keyword/synonym + lightweight normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class IntentResult:
    intent: str | None
    confidence: float


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _tokenize(text: str) -> List[str]:
    t = _normalize(text)
    # keep words/numbers
    return re.findall(r"[a-z0-9]+", t)


def _overlap_score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(candidate_tokens)


class IntentClassifier:
    """Lightweight NL intent classifier (no LLM).

    Enhancements over pure token-overlap:
    - token normalization + n-gram overlap boost (captures phrasing variants)
    - very small fuzzy matching for common misspellings/variants
    - confidence calibration so we avoid wrong intents when query is ambiguous
    
    knowledge entries should provide Keywords and Synonyms.
    """

    def __init__(self, intent_definitions: Dict[str, Dict[str, List[str]]]):
        self._intent_to_tokens: Dict[str, set[str]] = {}
        self._intent_to_ngrams: Dict[str, set[str]] = {}

        for intent, payload in intent_definitions.items():
            kws = payload.get("Keywords", []) or payload.get("keywords", [])
            syn = payload.get("Synonyms", []) or payload.get("synonyms", [])

            tokens: set[str] = set()
            for item in kws + syn:
                tokens.update(_tokenize(item))
            self._intent_to_tokens[intent] = tokens

            # Build simple character-free word bigrams from keyword tokens (order-agnostic)
            # This improves similarity when phrasing changes but key tokens remain.
            ngrams: set[str] = set()
            for phrase in kws + syn:
                words = _tokenize(phrase)
                if len(words) == 1:
                    ngrams.add(words[0])
                else:
                    for i in range(len(words) - 1):
                        ngrams.add(words[i] + "_" + words[i + 1])
            self._intent_to_ngrams[intent] = ngrams

    def _fuzzy_expand(self, q_tokens: set[str]) -> set[str]:
        """Tiny fuzzy expansion for typical variants.

        Note: kept intentionally small to avoid false matches.
        """
        # Common shorthand normalization
        repl = {
            "attnd": "attendance",
            "att": "attendance",
            "subj": "subject",
            "cgpa": "cgpa",
            "sgpa": "sgpa",
            "tut": "timetable",
        }

        expanded = set(q_tokens)
        for t in list(q_tokens):
            if t in repl:
                expanded.add(repl[t])

            # Light typo handling: strip common suffixes
            if len(t) > 4 and (t.endswith('s') or t.endswith('es')):
                expanded.add(t.rstrip('s'))
        return expanded

    def classify(self, message: str) -> IntentResult:
        q_tokens = set(_tokenize(message))
        if not q_tokens:
            return IntentResult(None, 0.0)

        q_tokens = self._fuzzy_expand(q_tokens)

        # word bigram set from the query
        q_words = list(_tokenize(message))
        q_ngrams: set[str] = set()
        if len(q_words) <= 1:
            q_ngrams = set(q_tokens)
        else:
            for i in range(len(q_words) - 1):
                q_ngrams.add(q_words[i] + "_" + q_words[i + 1])

        best_intent: str | None = None
        best_conf: float = 0.0

        for intent, cand_tokens in self._intent_to_tokens.items():
            # Token overlap
            tok_score = _overlap_score(q_tokens, cand_tokens)

            # N-gram overlap
            cand_ngrams = self._intent_to_ngrams.get(intent) or set()
            if cand_ngrams:
                ng_score = _overlap_score(q_ngrams, cand_ngrams)
            else:
                ng_score = 0.0

            # Weighted blend
            score = (0.75 * tok_score) + (0.25 * ng_score)

            # small bonus if exact phrase tokens exist
            if tok_score > 0.0 and len(q_tokens & cand_tokens) >= 2:
                score += 0.05

            if score > best_conf:
                best_conf = score
                best_intent = intent

        if best_conf <= 0.0:
            return IntentResult(None, 0.0)

        # Confidence calibration: keep in [0,1]
        best_conf = min(1.0, max(0.0, float(best_conf)))
        return IntentResult(best_intent, best_conf)


