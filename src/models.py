"""Shared data models for NoteManager."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.parsers.markdown_parser import Note


@dataclass
class ExternalDocument:
    """External teaching material parsed for Phase 3 RAG workflows."""

    doc_id: str
    source_path: Path
    subject: str | None = None
    doc_type: Literal["PPT", "试卷", "辅导书", "其他"] = "其他"
    chunks: list[str] = field(default_factory=list)
    upload_session_id: str = ""


@dataclass
class TeachSession:
    """One answer with inspectable sources and model-reported differences."""

    user_question: str
    recalled_notes: list[dict] = field(default_factory=list)
    external_chunks: list[dict] = field(default_factory=list)
    final_answer: str = ""
    discrepancies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


__all__ = ["ExternalDocument", "Note", "TeachSession"]
