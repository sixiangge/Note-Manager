"""Session-isolated Chroma collections with offline lexical feature vectors.

No default embedding model is downloaded and no text is sent for embedding.
These vectors measure textual overlap, not neural semantic similarity.
"""

from collections.abc import Callable
import hashlib
import math
from pathlib import Path
import re
from uuid import uuid4

from src.models import ExternalDocument, Note
from src.parsers.external import chunk_text
from src.parsers.markdown_parser import parse_markdown


def text_vector(text: str) -> list[float]:
    """Return a normalized, deterministic bilingual lexical vector.

    Args:
        text: Text to embed locally.

    Returns:
        2048 floating point features (zero for punctuation-only text).
    """
    features = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.lower())
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        if len(run) == 1:
            features.append(run)
        for width in (2, 3):
            features.extend(run[i:i + width] for i in range(len(run) - width + 1))
    vector = [0.0] * 2048
    for token in features:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        vector[int.from_bytes(digest[:4], "little") % len(vector)] += 1 if digest[4] & 1 else -1
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def load_notes(notes_root: Path, subject: str | None = None,
               note_type: str | None = None, include_samples: bool = False,
               warnings: list[str] | None = None,
               checkpoint: Callable[[], None] = lambda: None) -> list[Note]:
    """Read current Markdown, filtering before indexing; never write notes.

    Args:
        notes_root: Markdown root directory.
        subject: Optional exact subject filter.
        note_type: Optional exam/postgraduate filter.
        include_samples: Whether to recall example notes.
        warnings: Optional sink for per-file failures.
        checkpoint: Cooperative cancellation hook.

    Returns:
        Valid notes; malformed files are skipped independently.
    """
    notes = []
    for path in sorted(Path(notes_root).rglob("*.md")):
        checkpoint()
        try:
            if path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("笔记超过 8 MB，请拆分")
            note = parse_markdown(path)
            if subject and note.subject != subject:
                continue
            if note_type and note.note_type != note_type:
                continue
            if not include_samples and "示例" in note.tags:
                continue
            if len(note.body) > 2_000_000:
                raise ValueError("笔记正文过长，请拆分")
            notes.append(note)
        except Exception as exc:
            if warnings is not None:
                warnings.append(f"跳过笔记 {path.name}（{type(exc).__name__}）")
    return notes


class VectorRetriever:
    """Own two disposable collections; use as a context manager."""

    def __init__(self, collection_name: str = "nju_notes", *, client: object = None,
                 chunk_size: int = 500,
                 checkpoint: Callable[[], None] = lambda: None) -> None:
        if client is None:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        self.client = client
        self.chunk_size = chunk_size
        self.checkpoint = checkpoint
        self.session_id = uuid4().hex
        self.collections = {}
        try:
            for kind in ("note", "external"):
                self.collections[kind] = self.client.create_collection(
                    name=f"{collection_name}_{kind}_{self.session_id}",
                    embedding_function=None, metadata={"hnsw:space": "cosine"})
        except Exception:
            self.close()
            raise

    def __enter__(self) -> "VectorRetriever":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _add(self, kind: str, records: list[tuple[str, str, dict]]) -> None:
        collection = self.collections[kind]
        if collection.count() + len(records) > 20_000:
            raise ValueError("本次检索超过 20000 个片段，请缩小科目范围或拆分附件。")
        for start in range(0, len(records), 64):
            self.checkpoint()
            batch = records[start:start + 64]
            collection.upsert(ids=[r[0] for r in batch], documents=[r[1] for r in batch],
                              metadatas=[r[2] for r in batch],
                              embeddings=[text_vector(r[1]) for r in batch])

    def index_notes(self, notes: list[Note]) -> None:
        """Upsert note chunks with stable path/chunk identities."""
        for note in notes:
            self.checkpoint()
            path = str(note.file_path or note.title)
            identity = hashlib.sha256(path.encode("utf-8")).hexdigest()
            self._add("note", [(f"{identity}:{i}", text, {
                "path": path, "title": note.title, "subject": note.subject,
                "note_type": note.note_type, "chunk": i + 1,
            }) for i, text in enumerate(chunk_text(
                f"{note.title}\n{note.chapter}\n{note.body}", self.chunk_size))])

    def index_external(self, docs: list[ExternalDocument]) -> None:
        """Index uploads only in this request's external collection."""
        for doc in docs:
            doc.upload_session_id = self.session_id
            self._add("external", [(f"{doc.doc_id}:{i}", text, {
                "doc_id": doc.doc_id, "path": str(doc.source_path),
                "title": doc.source_path.name, "doc_type": doc.doc_type,
                "session_id": self.session_id, "chunk": i + 1,
            }) for i, text in enumerate(doc.chunks)])

    def query(self, text: str, top_k: int = 5,
              source_type: str | None = None) -> list[dict]:
        """Retrieve relevant chunks, optionally from only one collection.

        Args:
            text: Retrieval question.
            top_k: Maximum returned chunks.
            source_type: note, external, or both when None.

        Returns:
            Content, source metadata and cosine similarity, not probability.
        """
        if top_k < 1 or source_type not in {None, "note", "external"}:
            raise ValueError("无效的检索参数")
        vector = text_vector(text)
        if not any(vector):
            return []
        results = []
        for kind, collection in self.collections.items():
            self.checkpoint()
            count = collection.count()
            if not count or source_type and source_type != kind:
                continue
            data = collection.query(query_embeddings=[vector], n_results=min(top_k, count),
                                    include=["documents", "metadatas", "distances"])
            for content, metadata, distance in zip(data["documents"][0],
                                                   data["metadatas"][0], data["distances"][0]):
                score = max(0.0, min(1.0, 1.0 - float(distance)))
                if score >= 0.08:
                    results.append({"source_type": kind, "content": content,
                                    "metadata": metadata, "path": metadata["path"],
                                    "score": round(score, 4)})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    def clear_external(self) -> None:
        """Remove this request's external collection, never other sessions."""
        collection = self.collections.get("external")
        if collection is not None:
            self.client.delete_collection(collection.name)
            self.collections.pop("external")

    def close(self) -> None:
        """Delete owned collections even after a failed model call."""
        errors = []
        for kind, collection in list(self.collections.items()):
            try:
                self.client.delete_collection(collection.name)
                self.collections.pop(kind)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError("临时向量集合清理失败，请关闭应用释放内存。") from errors[0]
