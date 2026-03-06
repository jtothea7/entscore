"""
Writing style analysis with formality score (0-1) + style markers.
Uses heuristics, not labels — honest about what it can detect.
"""
from typing import Dict, List
import re
import textstat
from core.logger import setup_logger

logger = setup_logger(__name__)

# Common contractions
CONTRACTIONS = {
    "don't", "doesn't", "didn't", "can't", "couldn't", "won't", "wouldn't",
    "shouldn't", "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't",
    "hadn't", "it's", "that's", "there's", "here's", "what's", "who's",
    "let's", "we're", "they're", "you're", "i'm", "we've", "they've",
    "you've", "i've", "we'll", "they'll", "you'll", "i'll", "he's", "she's",
}


def analyze_style(text: str) -> Dict:
    """
    Analyze writing style using heuristics.

    Returns dict with:
        formality: float (0.0 casual to 1.0 formal)
        readability_grade: float (Flesch-Kincaid grade level)
        flesch_reading_ease: float (0-100, higher = easier)
        avg_sentence_length: float
        avg_word_length: float
        markers: list of detected style markers
        metrics: dict of raw metric values
    """
    if not text or len(text.split()) < 20:
        return {
            "formality": 0.5,
            "readability_grade": 0.0,
            "flesch_reading_ease": 0.0,
            "avg_sentence_length": 0.0,
            "avg_word_length": 0.0,
            "markers": [],
            "metrics": {},
        }

    words = text.split()
    word_count = len(words)
    words_lower = text.lower().split()

    # Sentence detection
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = max(len(sentences), 1)

    avg_sentence_length = word_count / sentence_count

    # Average word length
    avg_word_length = sum(len(w) for w in words) / word_count if word_count else 0

    # Contraction count
    contraction_count = sum(1 for w in words_lower if w in CONTRACTIONS)
    contraction_rate = contraction_count / word_count

    # First/second person pronouns
    first_second_pronouns = {"i", "me", "my", "mine", "myself", "we", "us",
                             "our", "ours", "ourselves", "you", "your",
                             "yours", "yourself", "yourselves"}
    pronoun_count = sum(1 for w in words_lower if w in first_second_pronouns)
    pronoun_rate = pronoun_count / word_count

    # Exclamation marks
    exclamation_count = text.count("!")
    exclamation_rate = exclamation_count / sentence_count

    # Question marks
    question_count = text.count("?")
    question_rate = question_count / sentence_count

    # Readability
    flesch_reading_ease = textstat.flesch_reading_ease(text)
    readability_grade = textstat.flesch_kincaid_grade(text)

    # Formality score (0.0 casual to 1.0 formal)
    formality_signals = []

    # Contractions: high = casual
    if contraction_rate < 0.005:
        formality_signals.append(1.0)
    elif contraction_rate < 0.02:
        formality_signals.append(0.6)
    else:
        formality_signals.append(0.2)

    # Sentence length: long = formal
    if avg_sentence_length > 20:
        formality_signals.append(0.9)
    elif avg_sentence_length > 14:
        formality_signals.append(0.6)
    else:
        formality_signals.append(0.3)

    # Pronouns: high = conversational/casual
    if pronoun_rate < 0.01:
        formality_signals.append(0.9)
    elif pronoun_rate < 0.04:
        formality_signals.append(0.5)
    else:
        formality_signals.append(0.2)

    # Exclamations: high = casual
    if exclamation_rate < 0.02:
        formality_signals.append(0.8)
    elif exclamation_rate < 0.1:
        formality_signals.append(0.5)
    else:
        formality_signals.append(0.2)

    # Questions: moderate = conversational
    if question_rate < 0.02:
        formality_signals.append(0.7)
    elif question_rate < 0.15:
        formality_signals.append(0.5)
    else:
        formality_signals.append(0.3)

    formality = round(sum(formality_signals) / len(formality_signals), 2)

    # Style markers
    markers = []
    if contraction_rate > 0.01:
        markers.append("uses contractions")
    if pronoun_rate > 0.03:
        markers.append("second-person address")
    elif pronoun_rate > 0.01:
        markers.append("some personal pronouns")
    if avg_sentence_length < 12:
        markers.append("short sentences")
    elif avg_sentence_length > 20:
        markers.append("long sentences")
    if exclamation_rate > 0.05:
        markers.append("frequent CTAs/exclamations")
    if question_rate > 0.1:
        markers.append("question-heavy (FAQ style)")
    if readability_grade > 12:
        markers.append("advanced reading level")
    elif readability_grade < 8:
        markers.append("easy reading level")

    metrics = {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "contraction_rate": round(contraction_rate, 4),
        "pronoun_rate": round(pronoun_rate, 4),
        "exclamation_rate": round(exclamation_rate, 4),
        "question_rate": round(question_rate, 4),
    }

    logger.info(
        f"Style analysis: formality={formality}, grade={readability_grade:.1f}, "
        f"markers={markers}"
    )

    return {
        "formality": formality,
        "readability_grade": round(readability_grade, 1),
        "flesch_reading_ease": round(flesch_reading_ease, 1),
        "avg_sentence_length": round(avg_sentence_length, 1),
        "avg_word_length": round(avg_word_length, 1),
        "markers": markers,
        "metrics": metrics,
    }


def detect_brand_phrases(
    client_text: str, competitor_texts: List[str]
) -> List[str]:
    """
    Detect brand phrases in client text.

    A brand phrase must match ALL criteria:
    - Appears 2+ times on the client page
    - Contains a proper noun/capitalized phrase OR matches brand pattern
    - 2-5 words long
    """
    if not client_text:
        return []

    # Extract 2-5 word phrases from client text
    words = client_text.split()
    phrase_counts = {}

    for n in range(2, 6):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            phrase_lower = phrase.lower()
            if phrase_lower not in phrase_counts:
                phrase_counts[phrase_lower] = {"count": 0, "original": phrase}
            phrase_counts[phrase_lower]["count"] += 1

    # Combine all competitor text
    all_competitor_text = " ".join(competitor_texts).lower()

    brand_phrases = []
    for phrase_lower, data in phrase_counts.items():
        # Must appear 2+ times
        if data["count"] < 2:
            continue

        # Must NOT appear in competitor text
        if phrase_lower in all_competitor_text:
            continue

        # Must contain a capitalized word (proper noun indicator)
        original_words = data["original"].split()
        has_capital = any(
            w[0].isupper() and w not in {"I", "A"}
            for w in original_words
            if w
        )

        if has_capital:
            brand_phrases.append(data["original"])

    # Deduplicate (keep shorter if one contains another)
    brand_phrases.sort(key=len)
    final = []
    for phrase in brand_phrases:
        if not any(phrase.lower() in existing.lower() for existing in final):
            final.append(phrase)

    logger.info(f"Detected {len(final)} brand phrases")
    return final[:10]  # Cap at 10
