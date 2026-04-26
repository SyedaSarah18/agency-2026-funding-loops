"""Knowledge base reader tool for the Conductor agent.

The kb/ directory at the project root contains markdown documents the
Conductor can pull into its context to answer methodology / scope /
data-source questions. Examples:
  - 01-the-challenge.md    What does the challenge ask?
  - 02-the-data.md         Which tables / columns / quality issues?
  - 03-methodology.md      How is concentration computed? Why these thresholds?
  - 04-key-findings.md     What did the Atlas surface?
  - 05-architecture.md     How is the system built?
"""
from __future__ import annotations

import json
from pathlib import Path

from strands import tool

# Deployment-flat layout: kb docs at <package_root>/kb/.
ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "kb"


@tool
def list_kb() -> str:
    """List the available knowledge-base documents.

    Use this when the user asks a meta question (about the data, the
    methodology, the scope, or the architecture) and you want to see
    which document to read before answering.

    Returns:
        JSON list of {filename, title} for each kb/*.md file. The title
        is the first H1 in the file (line starting with '# ').
    """
    docs = []
    if not KB_DIR.exists():
        return json.dumps({"error": f"kb dir does not exist at {KB_DIR}"})
    for f in sorted(KB_DIR.glob("*.md")):
        title = ""
        try:
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("# "):
                        title = line[2:]
                        break
        except Exception as e:
            title = f"<read error: {e}>"
        docs.append({"filename": f.name, "title": title})
    return json.dumps({"docs": docs})


@tool
def read_kb(filename: str) -> str:
    """Read a knowledge-base document by filename (e.g. '02-the-data.md').

    Use this AFTER list_kb() identifies the relevant doc, OR when the
    user's question references concepts you suspect are documented
    (data sources, scope limitations, methodology, known findings).

    Args:
        filename: The filename (with .md). Must be inside kb/ — no
            path traversal allowed.

    Returns:
        JSON object with keys: filename, content (the full markdown text),
        char_count. Returns an error if the filename isn't a kb/ doc.
    """
    if "/" in filename or "\\" in filename or filename.startswith("."):
        return json.dumps({"error": "filename must be a plain kb/*.md name"})
    path = KB_DIR / filename
    if not path.exists() or not path.is_file():
        return json.dumps({"error": f"file not found: {filename}"})
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
    return json.dumps({"filename": filename, "content": text, "char_count": len(text)})
