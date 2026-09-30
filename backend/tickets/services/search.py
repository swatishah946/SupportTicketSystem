"""Similar-ticket retrieval: lexical TF-IDF cosine, optionally hybrid with embeddings.

Used for:
  * duplicate detection while a customer is typing a new ticket
  * retrieving similar *resolved* tickets to ground the AI reply draft (RAG)

Lexical retrieval needs no model or key, is deterministic (so it is unit
tested) and always available. It misses paraphrases that share no words
("charged twice" vs "two debits"), which is what the semantic path fixes: when
Gemini embeddings are available, the final score is a weighted blend of both.
Both scores are cosine similarities in [0, 1], so thresholds are comparable
across queries. `evals/run_eval.py --retriever {lexical,hybrid}` measures both.

Scale note: the index is built per request over a bounded candidate set
(<= 1000 rows), which is fine at helpdesk scale. Beyond that, move lexical to
Postgres full-text search and embeddings to pgvector behind the same functions.
"""

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can cannot could did do does doing down during each few for from further had has
    have having he her here hers herself him himself his how i if in into is it its itself just me more
    most my myself no nor not now of off on once only or other our ours ourselves out over own same she
    should so some such than that the their theirs them themselves then there these they this those through
    to too under until up very was we were what when where which while who whom why will with would you
    your yours yourself yourselves please hi hello thanks thank regards dear team help issue problem get
    got getting im ive dont cant wont also still even""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")
SEMANTIC_WEIGHT = 0.7  # blend weight of the embedding score in hybrid mode


def _stem(token):
    # Tiny suffix stripper: enough to match "charged"/"charge", "payments"/"payment".
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text):
    return [_stem(t) for t in _TOKEN.findall((text or "").lower()) if t not in STOPWORDS and len(t) > 1]


class TfidfIndex:
    """Sublinear TF-IDF vectors, L2-normalised, cosine similarity."""

    def __init__(self, docs):
        counts = [Counter(tokenize(d)) for d in docs]
        n = len(counts)
        df = Counter()
        for c in counts:
            df.update(c.keys())
        self._unseen_idf = math.log(1 + n) + 1
        self.idf = {t: math.log((1 + n) / (1 + f)) + 1 for t, f in df.items()}
        self.vectors = [self._vector(c) for c in counts]

    def _vector(self, counts):
        vec = {t: (1 + math.log(tf)) * self.idf.get(t, self._unseen_idf) for t, tf in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def similarities(self, query):
        q = self._vector(Counter(tokenize(query)))
        return [sum(q[t] * w for t, w in doc.items() if t in q) for doc in self.vectors]


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rank(query, candidates, text_of, top_k=5, min_score=0.0, query_embedding=None, embedding_of=None):
    """Return [(candidate, score)] best-first, score in [0, 1].

    With `query_embedding` and `embedding_of`, candidates that have an embedding
    are scored as a blend of semantic and lexical similarity.
    """
    candidates = list(candidates)
    if not candidates or not tokenize(query) and query_embedding is None:
        return []
    lexical = TfidfIndex([text_of(c) for c in candidates]).similarities(query)
    scored = []
    for cand, lex in zip(candidates, lexical, strict=True):
        score = lex
        emb = embedding_of(cand) if (query_embedding and embedding_of) else None
        if emb:
            score = SEMANTIC_WEIGHT * max(cosine(query_embedding, emb), 0.0) + (1 - SEMANTIC_WEIGHT) * lex
        if score > 0 and score >= min_score:
            scored.append((cand, round(score, 3)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def ticket_text(ticket):
    # Title is a dense summary; repeat it to weight it above the body.
    return f"{ticket.title} {ticket.title} {ticket.description}"
