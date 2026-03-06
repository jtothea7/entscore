"""
Entity extraction with spaCy NER + 5-factor salience scoring + 5-step deduplication
"""
from typing import List, Dict
import spacy
from collections import Counter
import re
from core.logger import setup_logger

logger = setup_logger(__name__)

# Relevant NER types for SEO entity analysis
RELEVANT_ENTITY_TYPES = {
    "PERSON",
    "ORG",
    "GPE",
    "PRODUCT",
    "EVENT",
    "WORK_OF_ART",
    "LAW",
    "LANGUAGE",
    "FAC",
    "LOC",
}


class EntityExtractor:
    def __init__(self, model_name: str = "en_core_web_sm"):
        """Load spaCy model once at init."""
        logger.info(f"Loading spaCy model: {model_name}")
        self.nlp = spacy.load(model_name)

    def extract_entities(
        self,
        text: str,
        html: str = None,
        title: str = "",
        meta_description: str = "",
        headings: List[Dict] = None,
    ) -> List[Dict]:
        """
        Extract entities with 5-factor weighted salience scoring.

        Salience formula:
            salience = (
                (mention_count * 0.3) +
                (heading_presence * 0.25) +
                (first_paragraph_presence * 0.2) +
                (title_meta_presence * 0.15) +
                (bold_emphasis_presence * 0.1)
            ) / max_possible_score

        Returns:
            List of dicts with: text, type, count, salience
        """
        if not text:
            return []

        headings = headings or []

        # Process text with spaCy
        doc = self.nlp(text)

        # Extract and count entities
        entity_counts = Counter()
        entity_types = {}

        for ent in doc.ents:
            if ent.label_ in RELEVANT_ENTITY_TYPES:
                normalized = ent.text.lower().strip()
                entity_counts[normalized] += 1
                if normalized not in entity_types:
                    entity_types[normalized] = ent.label_

        if not entity_counts:
            return []

        # Get first 100 words for "first paragraph" detection
        first_100_words = " ".join(text.split()[:100]).lower()

        # Concatenate all headings
        heading_text = " ".join([h.get("text", "") for h in headings]).lower()

        # Title + meta combined
        title_meta_text = f"{title} {meta_description}".lower()

        # Bold/emphasis detection (if HTML provided)
        bold_text = ""
        if html:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            bold_tags = soup.find_all(["b", "strong", "em"])
            bold_text = " ".join([tag.get_text() for tag in bold_tags]).lower()

        # Calculate salience for each entity
        max_count = max(entity_counts.values())

        entities = []
        for entity_text, count in entity_counts.items():
            # Mention count score (normalized 0-1)
            mention_score = count / max_count if max_count > 0 else 0

            # Heading presence (1.0 if present, 0.0 if not)
            heading_score = 1.0 if entity_text in heading_text else 0.0

            # First paragraph presence
            first_para_score = 1.0 if entity_text in first_100_words else 0.0

            # Title/meta presence
            title_meta_score = 1.0 if entity_text in title_meta_text else 0.0

            # Bold/emphasis presence
            bold_score = 1.0 if entity_text in bold_text else 0.0

            # Weighted salience (max possible = 1.0)
            salience = (
                (mention_score * 0.3)
                + (heading_score * 0.25)
                + (first_para_score * 0.2)
                + (title_meta_score * 0.15)
                + (bold_score * 0.1)
            )

            entities.append(
                {
                    "text": entity_text,
                    "type": entity_types.get(entity_text),
                    "count": count,
                    "salience": round(salience, 3),
                }
            )

        # Sort by salience descending
        entities.sort(key=lambda x: x["salience"], reverse=True)

        logger.info(
            f"Extracted {len(entities)} entities from text ({len(text.split())} words)"
        )

        return entities

    def deduplicate_entities(
        self, entities: List[Dict], similarity_threshold: float = 0.92
    ) -> List[Dict]:
        """
        5-step entity deduplication pipeline.

        Step 1: Normalize (lowercase, strip articles, strip punctuation)
        Step 2: Exact match dedup (merge identical after normalization)
        Step 3: Lemmatization (spaCy lemmatizer)
        Step 4: BERT similarity merge (cosine > threshold)
        Step 5: Substring absorption (longer absorbed into shorter if similar)

        Returns:
            Deduplicated entity list with counts summed
        """
        if not entities:
            return []

        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")

        # Step 1: Normalize
        def normalize(text: str) -> str:
            text = text.lower().strip()
            text = re.sub(r"^(the|a|an)\s+", "", text)
            text = re.sub(r"[^\w\s-]$", "", text)
            return text

        normalized_entities = []
        for ent in entities:
            normalized_entities.append(
                {**ent, "normalized": normalize(ent["text"])}
            )

        # Step 2: Exact match dedup
        exact_match_groups = {}
        for ent in normalized_entities:
            key = ent["normalized"]
            if key in exact_match_groups:
                exact_match_groups[key]["count"] += ent["count"]
                exact_match_groups[key]["salience"] = max(
                    exact_match_groups[key]["salience"], ent["salience"]
                )
            else:
                exact_match_groups[key] = ent.copy()

        entities_step2 = list(exact_match_groups.values())

        # Step 3: Lemmatization
        for ent in entities_step2:
            doc = self.nlp(ent["normalized"])
            ent["lemma"] = " ".join([token.lemma_ for token in doc])

        lemma_groups = {}
        for ent in entities_step2:
            key = ent["lemma"]
            if key in lemma_groups:
                lemma_groups[key]["count"] += ent["count"]
                lemma_groups[key]["salience"] = max(
                    lemma_groups[key]["salience"], ent["salience"]
                )
            else:
                lemma_groups[key] = ent.copy()

        entities_step3 = list(lemma_groups.values())

        # Step 4: BERT similarity merge
        if len(entities_step3) > 1:
            texts = [ent["lemma"] for ent in entities_step3]
            embeddings = model.encode(texts)
            similarities = cosine_similarity(embeddings)

            merged = []
            skip_indices = set()

            for i, ent_i in enumerate(entities_step3):
                if i in skip_indices:
                    continue

                for j in range(i + 1, len(entities_step3)):
                    if j in skip_indices:
                        continue
                    if similarities[i][j] > similarity_threshold:
                        ent_i["count"] += entities_step3[j]["count"]
                        ent_i["salience"] = max(
                            ent_i["salience"], entities_step3[j]["salience"]
                        )
                        skip_indices.add(j)

                merged.append(ent_i)

            entities_step4 = merged
        else:
            entities_step4 = entities_step3

        # Step 5: Substring absorption
        final_entities = []
        skip_indices = set()

        sorted_entities = sorted(
            enumerate(entities_step4), key=lambda x: len(x[1]["lemma"])
        )

        for i, (idx_i, ent_i) in enumerate(sorted_entities):
            if idx_i in skip_indices:
                continue

            for j, (idx_j, ent_j) in enumerate(
                sorted_entities[i + 1 :], start=i + 1
            ):
                if idx_j in skip_indices:
                    continue

                if ent_i["lemma"] in ent_j["lemma"]:
                    sim = cosine_similarity(
                        [model.encode(ent_i["lemma"])],
                        [model.encode(ent_j["lemma"])],
                    )[0][0]

                    if sim > 0.85:
                        ent_i["count"] += ent_j["count"]
                        ent_i["salience"] = max(
                            ent_i["salience"], ent_j["salience"]
                        )
                        skip_indices.add(idx_j)

            final_entities.append(ent_i)

        result = []
        for ent in final_entities:
            result.append(
                {
                    "text": ent["text"],
                    "type": ent.get("type"),
                    "count": ent["count"],
                    "salience": ent["salience"],
                }
            )

        logger.info(f"Deduplicated {len(entities)} -> {len(result)} entities")

        return result
