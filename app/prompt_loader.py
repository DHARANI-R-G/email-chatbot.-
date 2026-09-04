import os

from dotenv import load_dotenv
from langfuse import get_client


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# LANGFUSE CLIENT
# ============================================================

langfuse = get_client()


# ============================================================
# GET MANAGED PROMPT
# ============================================================

def get_managed_prompt(
    prompt_name: str,
    **variables
):

    # Get prompt from Langfuse

    prompt = langfuse.get_prompt(
        prompt_name,
        label="production"
    )

    # Fill {{variables}}

    compiled_prompt = prompt.compile(
        **variables
    )

    return (
        prompt,
        compiled_prompt
    )