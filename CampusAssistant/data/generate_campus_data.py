import json
import os
import random
from typing import Dict, List, Tuple

BASE_DATA_PATH = os.path.join(os.path.dirname(__file__), "campus_data.json")


# Expand each topic into many valid intent->answer pairs.
TOPIC_TEMPLATES: List[Tuple[str, str]] = [
    ("admission", "Admissions are open from June to August."),
    ("fees", "Semester fee is Rs. 45,000."),
    ("library", "Library timing is 8 AM to 6 PM."),
    ("placement", "Top companies visit during placement drives."),
    ("attendance", "Minimum 75% attendance is required."),
    ("exam", "Semester exams start in December."),
]

# Template variants help the LLM/TFIDF find matches from many phrasings.
INTENT_PATTERNS = {
    "admission": [
        "admission info",
        "admissions open",
        "admission dates",
        "when are admissions open",
        "admissions month",
        "apply for admission",
        "admission process",
        "how to get admission",
        "college admission timeline",
        "application period",
    ],
    "fees": [
        "fees",
        "semester fee",
        "fee structure",
        "tuition fee",
        "campus fees",
        "how much is the fee",
        "fees payment",
        "payment of semester fees",
        "fee amount",
        "tuition cost",
    ],
    "library": [
        "library timing",
        "library hours",
        "when is library open",
        "library timing details",
        "library timings",
        "library working hours",
        "how late library is open",
        "library timings for students",
        "library access timing",
        "library schedule",
    ],
    "placement": [
        "placement",
        "placement companies",
        "placement drives",
        "top companies visit",
        "placement opportunities",
        "companies in placements",
        "how are placements",
        "placement season",
        "placement training",
        "placement cell",
    ],
    "attendance": [
        "attendance",
        "minimum attendance",
        "attendance requirement",
        "attendance percentage required",
        "75 percent attendance",
        "attendance rule",
        "how much attendance required",
        "attendance policy",
        "attendance eligibility",
        "shortage in attendance",
    ],
    "exam": [
        "exam",
        "semester exams",
        "exam schedule",
        "when exams start",
        "semester examination dates",
        "exam month",
        "end semester exams",
        "exam timetable",
        "how are exams conducted",
        "when is the exam",
    ],
}

# For each intent we add many variations by combining keywords.
QUESTION_VARIATIONS = [
    "{base}?",
    "can you tell me about {base}?",
    "i want to know about {base}",
    "please explain {base}",
    "what is {base}",
    "give details on {base}",
    "information about {base}",
    "help me with {base}",
    "where can i find {base}",
    "teach me about {base}",
]


def _make_intent_key(topic: str, base: str, idx: int) -> str:
    # Ensure unique intent keys.
    # We keep them human-readable but stable for debugging.
    return f"{topic}::{base}::{idx}"


def generate_entries(target_count: int = 20000, seed: int = 42) -> Dict[str, str]:
    random.seed(seed)

    # Build an initial list from templates
    base_pairs: List[Tuple[str, str]] = []
    for topic, answer in TOPIC_TEMPLATES:
        for pattern in INTENT_PATTERNS[topic]:
            base_pairs.append((pattern, answer))

    # Now expand until we reach target_count
    intents_answers: Dict[str, str] = {}
    topic_answer = {t: a for t, a in TOPIC_TEMPLATES}

    # We'll repeatedly generate new intent phrases for each topic based on patterns
    idx = 0
    while len(intents_answers) < target_count:
        # pick a topic
        topic = random.choice(list(topic_answer.keys()))
        base = random.choice(INTENT_PATTERNS[topic])

        # create phrase variations
        phrase_template = random.choice(QUESTION_VARIATIONS)
        intent_phrase = phrase_template.format(base=base)

        # Also add some "department"/student context variants (still valid campus questions)
        maybe_suffix = random.choice([
            "",
            " for BCA",
            " for MCA",
            " for CSE students",
            " for students",
            " for department",
            " for 2nd year",
            " for 3rd year",
            " in our college",
        ])
        intent_phrase = intent_phrase + maybe_suffix

        # store as intent key -> answer
        intents_answers[_make_intent_key(topic, intent_phrase, idx)] = topic_answer[topic]
        idx += 1

    return intents_answers


def main():
    target = 20000
    data = generate_entries(target_count=target, seed=42)

    out_path = BASE_DATA_PATH
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(data)} entries and saved to: {out_path}")


if __name__ == "__main__":
    main()
