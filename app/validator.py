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
# LOAD TAXONOMY
# ============================================================

def load_taxonomy():

    with TAXONOMY_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# SCHEMA VALIDATOR TOOL
# ============================================================

@tool
def schema_validator_tool(
    dominant_topic: str,
    subtopics: list[str]
) -> str:
    """
    Validate Topic Agent output.

    Checks:
    1. dominant_topic exists
    2. dominant_topic is a string
    3. subtopics exists
    4. subtopics is a list
    5. every subtopic is a string
    6. subtopics is not empty
    7. exact topic/subtopic pair exists in taxonomy v1
    """

    # ========================================================
    # CHECK 1 — dominant_topic exists
    # ========================================================

    if dominant_topic is None:

        return json.dumps({
            "valid": False,
            "error": "dominant_topic is missing"
        })


    # ========================================================
    # CHECK 2 — dominant_topic must be string
    # ========================================================

    if not isinstance(
        dominant_topic,
        str
    ):

        return json.dumps({
            "valid": False,
            "error":
                "dominant_topic must be a string"
        })


    # ========================================================
    # CHECK 3 — dominant_topic cannot be empty
    # ========================================================

    if not dominant_topic.strip():

        return json.dumps({
            "valid": False,
            "error":
                "dominant_topic cannot be empty"
        })


    # ========================================================
    # CHECK 4 — subtopics exists
    # ========================================================

    if subtopics is None:

        return json.dumps({
            "valid": False,
            "error":
                "subtopics is missing"
        })


    # ========================================================
    # CHECK 5 — subtopics must be a list
    # ========================================================

    if not isinstance(
        subtopics,
        list
    ):

        return json.dumps({
            "valid": False,
            "error":
                "subtopics must be a list"
        })


    # ========================================================
    # CHECK 6 — subtopics cannot be empty
    # ========================================================

    if len(subtopics) == 0:

        return json.dumps({
            "valid": False,
            "error":
                "subtopics cannot be empty"
        })


    # ========================================================
    # CHECK 7 — every subtopic must be a string
    # ========================================================

    for subtopic in subtopics:

        if not isinstance(
            subtopic,
            str
        ):

            return json.dumps({
                "valid": False,
                "error":
                    "Every subtopic must be a string"
            })


        if not subtopic.strip():

            return json.dumps({
                "valid": False,
                "error":
                    "Subtopics cannot contain empty values"
            })


    # ========================================================
    # LOAD TAXONOMY
    # ========================================================

    taxonomy = load_taxonomy()


    # ========================================================
    # CHECK EXACT TAXONOMY PAIR
    # ========================================================

    for pair in taxonomy["pairs"]:

        if pair["dominant_topic"] != dominant_topic:
            continue


        # Ground truth stores subtopics as:
        #
        # "Topic A, Topic B, Topic C"
        #
        # Convert it into:
        #
        # ["Topic A", "Topic B", "Topic C"]

        allowed_subtopics = [

            item.strip()

            for item in pair["subtopics"].split(",")

        ]


        # Compare exact list
        if allowed_subtopics == subtopics:

            return json.dumps({

                "valid": True,

                "error": None

            })


    # ========================================================
    # TAXONOMY VALIDATION FAILED
    # ========================================================

    return json.dumps({

        "valid": False,

        "error":
            "The dominant_topic and subtopics "
            "combination does not exist in taxonomy v1."

    })