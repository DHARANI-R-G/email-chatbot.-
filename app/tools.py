import json
from pathlib import Path

from langchain_core.tools import tool


# ============================================================
# TAXONOMY FILE
# ============================================================

TAXONOMY_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "taxonomy_v1.json"
)


# ============================================================
# TOPIC TAXONOMY TOOL
# ============================================================

@tool
def topic_taxonomy_tool() -> str:
    """
    Return the frozen taxonomy v1.

    The taxonomy contains the allowed
    dominant_topic -> subtopics combinations
    that the Topic Agent is allowed to use.
    """

    if not TAXONOMY_FILE.exists():

        raise FileNotFoundError(
            f"Taxonomy file not found: {TAXONOMY_FILE}"
        )

    with TAXONOMY_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        taxonomy = json.load(f)

    return json.dumps(
        taxonomy,
        ensure_ascii=False
    )