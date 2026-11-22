import json
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _load_dataset(dataset_path: str) -> Dict[str, str]:
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Chat dataset not found at: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Dataset JSON must be an object mapping intent->answer")
    cleaned: Dict[str, str] = {}
    for k, v in data.items():
        if v is None:
            continue
        cleaned[str(k)] = str(v)
    return cleaned


def _parse_intent_key(intent_key: str) -> Tuple[str, str]:
    """Return (topic, phrase) from keys like topic::phrase::idx"""
    parts = str(intent_key).split("::")
    topic = parts[0] if len(parts) > 0 else ""
    phrase = parts[1] if len(parts) > 1 else intent_key
    return _normalize(topic), _normalize(phrase)


def _detect_category(msg: str) -> Optional[str]:
    """Rule-based category detection to prevent intent-collision."""
    if not msg:
        return None

    rules = [
        ("fees", {"fee", "fees", "tuition", "tuition fee", "semester fee", "payment", "cost"}),
        ("attendance", {"attendance", "attend"}),
        ("subjects", {"subject", "subjects", "syllabus", "semester subjects"}),
        ("placement", {"placement", "placements", "company", "companies"}),
        ("exam", {"exam", "exams", "semester exam", "examination", "timetable", "schedule"}),
        ("library", {"library", "books", "book"}),
        ("admission", {"admission", "admissions", "apply", "application", "enrollment"}),
    ]

    for cat, needles in rules:
        if any(n in msg for n in needles):
            return cat
    return None


@lru_cache(maxsize=1)
def _get_model():
    """Build cached TF-IDF index from topic+phrase, grouped by category."""
    dataset_path = os.path.join(os.path.dirname(__file__), "data", "campus_data.json")
    dataset = _load_dataset(dataset_path)

    intents: List[str] = list(dataset.keys())
    answers: List[str] = [dataset[i] for i in intents]

    # Build per-intent training text and per-intent category (topic)
    topic_list: List[str] = []
    train_texts: List[str] = []
    for intent_key in intents:
        topic, phrase = _parse_intent_key(intent_key)
        topic_list.append(topic)
        # include answer also so similarity prefers correct FAQ text
        train_texts.append(f"{topic} {phrase}. {dataset[intent_key]}")

    # TF-IDF index
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 3), stop_words=None)
        X = vectorizer.fit_transform(train_texts)

        # Precompute mapping from category->indices to restrict search space
        cat_to_indices: Dict[str, List[int]] = {}
        for idx, topic in enumerate(topic_list):
            cat_to_indices.setdefault(topic, []).append(idx)

        return {
            "type": "tfidf",
            "intents": intents,
            "answers": answers,
            "topic_list": topic_list,
            "train_texts": train_texts,
            "vectorizer": vectorizer,
            "X": X,
            "cosine_similarity": cosine_similarity,
            "cat_to_indices": cat_to_indices,
        }
    except Exception:
        # fallback: still keep topic_list to support category filtering with naive keyword.
        cat_to_indices: Dict[str, List[int]] = {}
        for idx, topic in enumerate(topic_list):
            cat_to_indices.setdefault(topic, []).append(idx)
        return {
            "type": "keyword",
            "intents": intents,
            "answers": answers,
            "topic_list": topic_list,
            "cat_to_indices": cat_to_indices,
        }


def get_chatbot_response(user_message: str) -> str:
    model = _get_model()
    msg = _normalize(user_message)
    if not msg:
        return "Sorry, I don't understand."

    category = _detect_category(msg)

    # Choose search subset indices
    if category and model.get("type") == "tfidf":
        indices = model["cat_to_indices"].get(category, [])
        if not indices:
            # fall back to all
            indices = list(range(len(model["answers"])))
    else:
        indices = list(range(len(model["answers"])))

    if model["type"] == "tfidf":
        vectorizer = model["vectorizer"]
        X = model["X"]
        cosine_similarity = model["cosine_similarity"]

        q = vectorizer.transform([msg])
        # restrict by slicing rows (indices)
        X_sub = X[indices]
        sims_sub = cosine_similarity(q, X_sub).flatten()
        best_sub = int(sims_sub.argmax())
        best_score = float(sims_sub[best_sub])
        best_idx = indices[best_sub]

        # Safer thresholding to reduce wrong answers.
        # If we detect a category, require higher confidence.
        threshold = 0.10 if category else 0.14
        if best_score < threshold:
            return "Sorry, I don't understand."
        return model["answers"][best_idx]

    # keyword fallback
    best_score = -1.0
    best_answer = "Sorry, I don't understand."
    msg_tokens = set(msg.split())

    for idx in indices:
        topic = model["topic_list"][idx]
        answer = model["answers"][idx]
        score = 0.0
        if category and topic == category:
            score += 2.0
        # token overlap with topic tokens
        topic_tokens = set(topic.split()) if topic else set()
        if topic_tokens:
            score += len(msg_tokens & topic_tokens) / len(topic_tokens)
        if score > best_score:
            best_score = score
            best_answer = answer

    if best_score < 1.0:
        return "Sorry, I don't understand."
    return best_answer


