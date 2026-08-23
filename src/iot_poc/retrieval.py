from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile
import xml.etree.ElementTree as ET


@dataclass
class Chunk:
    source: str
    chunk_id: str
    text: str


class StandardsRetriever:
    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("No standards chunks were loaded.")
        self.chunks = chunks
        self._backend = "keyword"
        self._vectorizer = None
        self._matrix = None
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            self._matrix = self._vectorizer.fit_transform([chunk.text for chunk in chunks])
            self._backend = "tfidf"
        except Exception:
            self._backend = "keyword"

    @property
    def backend(self) -> str:
        return self._backend

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        if self._backend == "tfidf":
            return self._retrieve_tfidf(query, top_k)
        return self._retrieve_keyword(query, top_k)

    def _retrieve_tfidf(self, query: str, top_k: int) -> list[dict[str, Any]]:
        from sklearn.metrics.pairwise import cosine_similarity

        query_vector = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self._matrix).ravel()
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [self._format_result(index, float(score), query) for index, score in ranked]

    def _retrieve_keyword(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        scored = []
        for index, chunk in enumerate(self.chunks):
            chunk_terms = {term.lower().strip(".,:;()[]{}") for term in chunk.text.split()}
            score = len(query_terms & chunk_terms) / max(len(query_terms), 1)
            scored.append((index, score))
        ranked = sorted(scored, key=lambda item: item[1], reverse=True)[:top_k]
        return [self._format_result(index, float(score), query) for index, score in ranked]

    def _format_result(self, index: int, score: float, query: str) -> dict[str, Any]:
        chunk = self.chunks[index]
        return {
            "source": chunk.source,
            "chunk_id": chunk.chunk_id,
            "score": round(score, 6),
            "excerpt": compact_excerpt(chunk.text, query=query),
        }


def load_standards_corpus(
    standards_dir: str | Path,
    chunk_chars: int = 1400,
    chunk_overlap: int = 180,
) -> list[Chunk]:
    base = Path(standards_dir)
    files = sorted(
        path
        for path in base.glob("**/*")
        if path.is_file()
        and path.name.lower() != "readme.md"
        and path.suffix.lower() in {".md", ".txt", ".pdf", ".docx"}
    )
    chunks: list[Chunk] = []
    for path in files:
        text = extract_text(path)
        if not text.strip():
            continue
        for idx, chunk_text in enumerate(chunk_text_blocks(text, chunk_chars, chunk_overlap)):
            chunks.append(
                Chunk(
                    source=str(path),
                    chunk_id=f"{path.stem}-{idx:04d}",
                    text=chunk_text,
                )
            )
    return chunks


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError("Install pypdf to read PDF standards.") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        return extract_docx_text(path)
    return ""


def extract_docx_text(path: Path) -> str:
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for para in root.findall(".//w:p", namespaces):
        runs = [node.text or "" for node in para.findall(".//w:t", namespaces)]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def chunk_text_blocks(text: str, chunk_chars: int, chunk_overlap: int) -> list[str]:
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(cleaned) <= chunk_chars:
        return [cleaned]
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_chars, len(cleaned))
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def compact_excerpt(text: str, max_chars: int = 650, query: str | None = None) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_chars:
        return one_line
    if not query:
        return one_line[: max_chars - 3] + "..."

    ignored = {
        "iot",
        "gateway",
        "predicted",
        "threat",
        "protocol",
        "protocols",
        "network",
        "device",
    }
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9-]+", query)
        if len(term) >= 3 and term.lower() not in ignored
    }
    lowered = one_line.lower()
    positions = [
        position
        for term in terms
        for position in [lowered.find(term)]
        if position >= 0
    ]
    if not positions:
        return one_line[: max_chars - 3] + "..."

    candidates = []
    for position in positions:
        start = max(0, min(position - max_chars // 3, len(one_line) - max_chars))
        end = start + max_chars
        window = lowered[start:end]
        score = sum(window.count(term) for term in terms)
        candidates.append((score, -start, start, end))
    _, _, start, end = max(candidates)
    excerpt = one_line[start:end]
    if start > 0:
        excerpt = "..." + excerpt[3:]
    if end < len(one_line):
        excerpt = excerpt[:-3] + "..."
    return excerpt
