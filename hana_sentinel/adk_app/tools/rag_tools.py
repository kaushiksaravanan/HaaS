"""
RAG Engine Tools — ADK-compatible tool functions.
Implements local file-based RAG for SAP knowledge base.
PRD Section 9 — Dual-role: agent grounding + support assistant.

NO MOCK — Real local file search or explicit error.
Uses local file-based search as the primary RAG backend.
"""

import os
import glob
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _search_local_knowledge_base(question: str) -> dict:
    """Search local document store for SAP knowledge.
    Searches .txt, .md, .csv files in the configured knowledge base directory.
    This is NOT mock data — it searches real local files.
    """
    kb_dir = os.getenv("RAG_LOCAL_KB_DIR", "")
    if not kb_dir or not os.path.isdir(kb_dir):
        return {
            "status": "error",
            "error_message": (
                "Local knowledge base not available. "
                "Set RAG_LOCAL_KB_DIR environment variable to point to your knowledge base directory."
            ),
        }

    try:
        q_lower = question.lower()
        keywords = [w for w in q_lower.split() if len(w) > 3]
        matches = []

        for ext in ["*.txt", "*.md", "*.csv"]:
            for filepath in glob.glob(os.path.join(kb_dir, "**", ext), recursive=True):
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    content_lower = content.lower()
                    score = sum(content_lower.count(kw) for kw in keywords)
                    if score > 0:
                        # Extract relevant snippet (first matching paragraph)
                        snippet = ""
                        for para in content.split("\n\n"):
                            if any(kw in para.lower() for kw in keywords):
                                snippet = para.strip()[:500]
                                break
                        matches.append(
                            {
                                "file": filepath,
                                "score": score,
                                "snippet": snippet,
                            }
                        )
                except Exception:
                    continue

        if not matches:
            return {
                "status": "success",
                "source": "local_kb",
                "answer": f"No matching documents found in local knowledge base for: {question}",
                "sources": [],
                "confidence": 0.0,
            }

        matches.sort(key=lambda x: x["score"], reverse=True)
        top = matches[:5]

        combined = "\n\n---\n\n".join(f"[{m['file']}]\n{m['snippet']}" for m in top)

        return {
            "status": "success",
            "source": "local_kb",
            "answer": combined,
            "sources": [m["file"] for m in top],
            "confidence": min(0.7, top[0]["score"] / 10),
            "matches_found": len(matches),
        }
    except Exception as e:
        return {"status": "error", "error_message": f"Local KB search failed: {e}"}


# ──────────────────────────────────────────────
# ADK Tool Functions — NO MOCK
# ──────────────────────────────────────────────


def rag_query(question: str) -> dict:
    """Query the SAP HANA knowledge base using RAG (Retrieval-Augmented Generation).
    Searches SAP Notes, EWA reports, admin guides, and Patch Day bulletins.
    PRD Section 9.

    Uses local file-based search.
    NEVER returns fabricated/mock answers.

    Args:
        question (str): Natural language question about SAP HANA operations.

    Returns:
        dict: answer grounded in real documentation with source citations and confidence score.
    """
    return _search_local_knowledge_base(question)


def rag_ingest(document_path: str, document_type: str = "sap_note") -> dict:
    """Ingest a document into the RAG knowledge base.
    Supports SAP Notes, EWA reports, admin guides, Patch Day bulletins.
    PRD Section 9.

    Copies document to local KB directory.

    Args:
        document_path (str): Path to the document (local path).
        document_type (str): Type: sap_note, ewa_report, admin_guide, patch_day_bulletin, runbook.

    Returns:
        dict: status of the ingestion operation.
    """
    kb_dir = os.getenv("RAG_LOCAL_KB_DIR", "")
    if not kb_dir:
        return {
            "status": "error",
            "error_message": (
                "No RAG backend available. Set RAG_LOCAL_KB_DIR for local file-based knowledge base."
            ),
        }

    try:
        import shutil

        os.makedirs(os.path.join(kb_dir, document_type), exist_ok=True)
        dest = os.path.join(kb_dir, document_type, os.path.basename(document_path))
        if os.path.exists(document_path):
            shutil.copy2(document_path, dest)
            return {
                "status": "success",
                "source": "local_kb",
                "message": f"Document copied to local KB: {dest}",
            }
        else:
            return {
                "status": "error",
                "error_message": f"Source file not found: {document_path}",
            }
    except Exception as e:
        return {"status": "error", "error_message": f"Local KB ingest failed: {e}"}
