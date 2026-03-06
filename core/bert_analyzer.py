"""
KeyBERT keyword extraction + sentence-transformer embeddings + cosine similarity
"""
from typing import List, Dict, Tuple
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from core.logger import setup_logger

logger = setup_logger(__name__)


class BERTAnalyzer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Load BERT model once at init."""
        logger.info(f"Loading BERT model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.kw_model = KeyBERT(model=self.model)

    def extract_keywords(
        self, text: str, top_n: int = 20, ngram_range: Tuple[int, int] = (1, 3)
    ) -> List[Dict]:
        """
        Extract keywords using KeyBERT.

        Returns:
            List of dicts with: keyword, score
        """
        if not text or len(text.split()) < 10:
            return []

        keywords = self.kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=ngram_range,
            stop_words="english",
            top_n=top_n,
            use_mmr=True,
            diversity=0.5,
        )

        result = [
            {"keyword": kw, "score": round(score, 4)} for kw, score in keywords
        ]

        logger.info(f"Extracted {len(result)} keywords from text")
        return result

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts using BERT embeddings.

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not text1 or not text2:
            return 0.0

        embeddings = self.model.encode([text1, text2])
        sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return round(float(sim), 4)

    def compute_content_similarity_matrix(
        self, texts: List[str]
    ) -> np.ndarray:
        """
        Compute pairwise similarity matrix for multiple texts.

        Returns:
            NxN numpy array of similarity scores
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(texts)
        return cosine_similarity(embeddings)

    def find_topic_gaps(
        self,
        client_keywords: List[Dict],
        competitor_keywords: List[Dict],
        similarity_threshold: float = 0.75,
    ) -> List[Dict]:
        """
        Find keywords/topics present in competitor content but missing from client.

        Returns:
            List of dicts with: keyword, score, similar_client_keyword (if partial match)
        """
        if not competitor_keywords:
            return []

        client_texts = [kw["keyword"] for kw in client_keywords]
        comp_texts = [kw["keyword"] for kw in competitor_keywords]

        if not client_texts:
            return [
                {"keyword": kw["keyword"], "score": kw["score"], "status": "missing"}
                for kw in competitor_keywords
            ]

        # Encode all at once
        client_embeddings = self.model.encode(client_texts) if client_texts else []
        comp_embeddings = self.model.encode(comp_texts)

        gaps = []
        for i, comp_kw in enumerate(competitor_keywords):
            if len(client_embeddings) == 0:
                gaps.append(
                    {
                        "keyword": comp_kw["keyword"],
                        "score": comp_kw["score"],
                        "status": "missing",
                    }
                )
                continue

            similarities = cosine_similarity(
                [comp_embeddings[i]], client_embeddings
            )[0]
            max_sim = float(np.max(similarities))
            best_match_idx = int(np.argmax(similarities))

            if max_sim < similarity_threshold:
                gaps.append(
                    {
                        "keyword": comp_kw["keyword"],
                        "score": comp_kw["score"],
                        "status": "missing",
                    }
                )
            elif max_sim < 0.9:
                gaps.append(
                    {
                        "keyword": comp_kw["keyword"],
                        "score": comp_kw["score"],
                        "status": "weak",
                        "similar_client_keyword": client_texts[best_match_idx],
                        "similarity": max_sim,
                    }
                )

        logger.info(
            f"Found {len(gaps)} topic gaps ({len([g for g in gaps if g['status'] == 'missing'])} missing, "
            f"{len([g for g in gaps if g['status'] == 'weak'])} weak)"
        )

        return gaps
