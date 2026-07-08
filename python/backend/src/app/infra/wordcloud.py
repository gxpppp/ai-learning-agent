"""Word cloud service — jieba + TF-IDF pipeline with incremental update."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import jieba
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

TFIDF_DB = "tfidf.db"

# Download NLTK stopwords on first import
try:
    import nltk
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True, raise_on_error=False)
    _EN_STOPWORDS = set(nltk.corpus.stopwords.words("english"))
except Exception:
    _EN_STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "this", "that",
        "it", "its", "i", "me", "my", "we", "our", "you", "your", "he", "she",
        "they", "them", "not", "no", "so", "if", "as", "than", "too", "very",
        "just", "about", "also", "into", "over", "after", "before", "between",
    }

_CN_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "什么", "怎么", "如果", "因为", "所以", "但是", "可以", "这个", "那个",
}
_STOPWORDS = _EN_STOPWORDS | _CN_STOPWORDS

# Chinese regex: match Chinese characters
_CN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_EN_PATTERN = re.compile(r"[a-zA-Z]+")


def _load_word_db(vault_path: str) -> dict[str, dict[str, float]]:
    path = os.path.join(vault_path, ".ai-tutor", TFIDF_DB)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_word_db(vault_path: str, db: dict[str, dict[str, float]]) -> None:
    db_dir = os.path.join(vault_path, ".ai-tutor")
    os.makedirs(db_dir, exist_ok=True)
    path = os.path.join(db_dir, TFIDF_DB)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)




def _tokenize(text: str) -> list[str]:
    cn_words = jieba.lcut(text)
    tokens: list[str] = []
    for w in cn_words:
        w = w.strip().lower()
        if len(w) < 2 or w in _STOPWORDS or w.isdigit():
            continue
        tokens.append(w)
    return tokens


def _read_note_content(file_path: str) -> str:
    with open(file_path, encoding="utf-8") as f:
        raw = f.read()
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            return raw[end + 3 :].strip()
    return raw


def update_word_db(
    vault_path: str, note_path: str, operation: str = "add"
) -> dict[str, dict[str, float]]:
    """Incremental update to the word database."""
    full_path = os.path.join(vault_path, note_path)
    db = _load_word_db(vault_path)

    if operation == "delete":
        db.pop(note_path, None)
        _save_word_db(vault_path, db)
        return db

    if not os.path.exists(full_path):
        return db

    text = _read_note_content(full_path)
    tokens = _tokenize(text)
    tf: dict[str, float] = {}
    total = len(tokens) or 1
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    for t in tf:
        tf[t] /= total

    db[note_path] = tf
    _save_word_db(vault_path, db)
    return db


def generate_wordcloud(
    vault_path: str,
    folder: str | None = None,
    top_n: int = 50,
) -> dict[str, Any]:
    """Generate word cloud data from indexed notes."""
    db = _load_word_db(vault_path)

    if not db:
        return {"words": [], "total_notes": 0}

    # Filter by folder
    if folder:
        db = {k: v for k, v in db.items() if k.startswith(folder)}

    if not db:
        return {"words": [], "total_notes": 0}

    # Aggregate TF-IDF across documents
    import numpy as np

    # Build document-term matrix manually from db
    all_terms = sorted({t for tf in db.values() for t in tf})
    if not all_terms:
        return {"words": [], "total_notes": len(db)}

    # Compute document-level TF-IDF
    docs = [" ".join(tf.keys()) for tf in db.values()]
    if not docs:
        return {"words": [], "total_notes": 0}

    try:
        vectorizer = TfidfVectorizer(
            vocabulary=all_terms,
            stop_words=None,
            token_pattern=r"(?u)\b\w+\b",
        )
        tfidf_matrix = vectorizer.fit_transform(docs)
        avg_tfidf = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
        term_scores: dict[str, float] = {
            term: float(avg_tfidf[i])
            for i, term in enumerate(vectorizer.get_feature_names_out())
            if avg_tfidf[i] > 0
        }
    except Exception:
        term_scores = {}
        for tf in db.values():
            for term, weight in tf.items():
                term_scores[term] = term_scores.get(term, 0) + weight

    # Sort and take top N
    sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    max_weight = sorted_terms[0][1] if sorted_terms else 1.0

    words = [
        {
            "word": term,
            "weight": round(score / max_weight, 4),
            "tfidf": round(score, 4),
            "link_count": sum(1 for tf in db.values() if term in tf),
        }
        for term, score in sorted_terms
    ]

    return {
        "words": words,
        "total_notes": len(db),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def build_initial_wordcloud(vault_path: str) -> dict[str, Any]:
    """Build initial word cloud by scanning all notes."""
    from app.infra.indexer import _find_markdown_files

    files = _find_markdown_files(vault_path)
    db: dict[str, dict[str, float]] = {}

    for fpath in files:
        rel = os.path.relpath(fpath, vault_path).replace("\\", "/")
        text = _read_note_content(fpath)
        tokens = _tokenize(text)
        if not tokens:
            continue
        tf: dict[str, float] = {}
        total = len(tokens)
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        for t in tf:
            tf[t] /= total
        db[rel] = tf

    _save_word_db(vault_path, db)
    return generate_wordcloud(vault_path)
