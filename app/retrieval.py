"""Deterministic lexical TF-IDF retrieval; no remote embeddings or dependencies."""
from __future__ import annotations
from collections import Counter
import json
import math
from pathlib import Path
import re
import unicodedata

BASE = Path(__file__).resolve().parent.parent / 'base'
STOPWORDS = set('a ao aos as com como da das de do dos e em entre essa esse esta este eu isso ja mais me meu minha na nas no nos o os ou para pela pelo por qual quais que se sem seu sua um uma uns umas voce sao ser ter tem e'.split())


def tokenize(text: str) -> list[str]:
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    return [t for t in re.findall(r'[a-z0-9]+', normalized) if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


class Retriever:
    """search applies threshold; rank bypasses it for recall@k measurements.

    Scores are cosine similarities, not calibrated probabilities. Ties sort by id.
    Source text is data only, never executable instructions.
    """
    def __init__(self, threshold: float = 0.12, path: str | Path | None = None):
        if not 0 <= threshold <= 1:
            raise ValueError('threshold must be between 0 and 1')
        self.threshold = threshold
        self.chunks = [json.loads(line) for line in Path(path or BASE / 'chunks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        ids = [c['id'] for c in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate chunk ids')
        counts = [Counter(tokenize(c['title'] + ' ' + c['text'])) for c in self.chunks]
        df = Counter(token for count in counts for token in count)
        self.idf = {term: math.log((1 + len(counts)) / (1 + n)) + 1 for term, n in df.items()}
        self.vectors = [self._vector(count) for count in counts]

    def _vector(self, counts: Counter) -> dict[str, float]:
        vector = {term: (1 + math.log(count)) * self.idf[term] for term, count in counts.items() if term in self.idf}
        norm = math.sqrt(sum(value * value for value in vector.values()))
        return {term: value / norm for term, value in vector.items()} if norm else {}

    def rank(self, question: str, k: int = 3) -> list[dict]:
        if k < 1:
            return []
        query = self._vector(Counter(tokenize(question)))
        scores = [(sum(query.get(term, 0) * value for term, value in vector.items()), chunk) for chunk, vector in zip(self.chunks, self.vectors)]
        scores.sort(key=lambda pair: (-pair[0], pair[1]['id']))
        return [dict(chunk, score=round(score, 8)) for score, chunk in scores[:k]]

    def search(self, question: str, k: int = 3) -> list[dict]:
        return [row for row in self.rank(question, k) if row['score'] >= self.threshold and row['score'] > 0]
