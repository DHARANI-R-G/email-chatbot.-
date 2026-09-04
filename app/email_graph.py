import os
import json
from typing import TypedDict, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langfuse import get_client

from prompt_loader import get_managed_prompt

from tools import topic_taxonomy_tool

from validator import schema_validator_tool

from bigquery_tools import (
    bigquery_read_tool,
    bigquery_write_tool,
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")

LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")


if not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is missing from .env"
    )

if not LANGFUSE_PUBLIC_KEY:
    raise ValueError(
        "LANGFUSE_PUBLIC_KEY is missing from .env"
    )

if not LANGFUSE_SECRET_KEY:
    raise ValueError(
        "LANGFUSE_SECRET_KEY is missing from .env"
    )


# ============================================================
# LANGFUSE CLIENT
# ============================================================

langfuse = get_client()


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-5-mini",
)


llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)


# ============================================================
# GRAPH STATE
# ============================================================

class EmailState(TypedDict, total=False):

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    message_id: str
    subject: str
    from_email: str

    raw_text: str
    cleaned_text: str

    # --------------------------------------------------------
    # Trace
    # --------------------------------------------------------

    trace_id: str

    # --------------------------------------------------------
    # Supervisor
    # --------------------------------------------------------

    route: str

    # --------------------------------------------------------
    # Sentiment
    # --------------------------------------------------------

    sentiment: str
    urgency: str

    # --------------------------------------------------------
    # Topic
    # --------------------------------------------------------

    dominant_topic: str
    subtopics: List[str]

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validation_result: str
    validation_error: str

    # --------------------------------------------------------
    # Retry
    # --------------------------------------------------------

    retry_count: int

    # --------------------------------------------------------
    # Errors
    # --------------------------------------------------------

    errors: List[str]


# ============================================================
# SAFE JSON CLEANER
# ============================================================

def clean_json_response(content: str) -> str:

    content = content.strip()

    if content.startswith("```json"):
        content = content[7:]

    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    return content.strip()


# ============================================================
# LLM CALL WITH LANGFUSE
# ============================================================

def call_llm_with_prompt(
    *,
    generation_name: str,
    prompt,
    compiled_prompt: str,
):

    """
    Calls the LLM and records useful generation-level
    information in Langfuse.

    The actual prompt text is NOT added to custom
    metadata/output.
    """

    with langfuse.start_as_current_observation(

        as_type="generation",

        name=generation_name,

        model=MODEL_NAME,

        # Keep prompt information in the Langfuse
        # generation itself.
        input=compiled_prompt,

        prompt=prompt,

        metadata={
            "prompt_name": prompt.name,
            "prompt_version": str(prompt.version),
        },

        model_parameters={
            "temperature": 0,
        },

    ) as generation:

        response = llm.invoke(
            compiled_prompt
        )

        output = response.content

        # ----------------------------------------------------
        # TOKEN USAGE
        # ----------------------------------------------------

        usage = getattr(
            response,
            "usage_metadata",
            None,
        )

        if usage:

            usage_details = {}

            if usage.get("input_tokens") is not None:
                usage_details["input_tokens"] = (
                    usage["input_tokens"]
                )

            if usage.get("output_tokens") is not None:
                usage_details["output_tokens"] = (
                    usage["output_tokens"]
                )

            if usage.get("total_tokens") is not None:
                usage_details["total_tokens"] = (
                    usage["total_tokens"]
                )

            if usage_details:

                generation.update(
                    usage_details=usage_details
                )

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        generation.update(
            output=output
        )

        return output


# ============================================================
# 0. SUPERVISOR
# ============================================================

def supervisor_agent(
    state: EmailState
) -> EmailState:

    print()
    print("0. Supervisor Agent running...")

    with langfuse.start_as_current_observation(

        as_type="span",

        name="supervisor",

        input={
            "message_id": state["message_id"],
        },

    ) as span:

        # ----------------------------------------------------
        # GET MANAGED PROMPT
        # ----------------------------------------------------

        prompt, compiled_prompt = get_managed_prompt(

            "supervisor-email-router",

            email_text=state["raw_text"],

        )

        # ----------------------------------------------------
        # CALL LLM
        # ----------------------------------------------------

        output = call_llm_with_prompt(

            generation_name="supervisor-llm",

            prompt=prompt,

            compiled_prompt=compiled_prompt,

        )

        # ----------------------------------------------------
        # PARSE RESPONSE
        # ----------------------------------------------------

        try:

            result = json.loads(
                clean_json_response(output)
            )

            route = result.get(
                "route",
                "process",
            )

        except Exception:

            route = "process"

            state.setdefault(
                "errors",
                []
            ).append(
                "Supervisor JSON parsing failed."
            )

        if route not in {
            "process",
            "skip",
        }:

            route = "process"

        state["route"] = route

        span.update(
            output={
                "route": route
            }
        )

        print(
            f"Supervisor decision: {route}"
        )

    return state


# ============================================================
# SUPERVISOR ROUTER
# ============================================================

def supervisor_router(
    state: EmailState
):

    if state.get("route") == "skip":

        print(
            "Supervisor router: SKIP -> END"
        )

        return "end"

    print(
        "Supervisor router: PROCESS -> Preprocess"
    )

    return "process"


# ============================================================
# 1. PREPROCESS
# ============================================================

def preprocess_node(
    state: EmailState
) -> EmailState:

    print()
    print("1. Preprocessing email...")

    with langfuse.start_as_current_observation(

        as_type="span",

        name="preprocess",

        input={
            "message_id": state["message_id"],
        },

    ) as span:

        text = state.get(
            "raw_text",
            ""
        )

        lines = text.splitlines()

        cleaned_lines = []

        for line in lines:

            stripped = line.strip()

            if not stripped:

                cleaned_lines.append("")

                continue

            # Remove quoted email lines
            if stripped.startswith(">"):

                continue

            cleaned_lines.append(
                stripped
            )

        cleaned_text = "\n".join(
            cleaned_lines
        ).strip()

        state["cleaned_text"] = cleaned_text

        # Do NOT put the complete email text into
        # the span output.
        span.update(
            output={
                "status": "completed"
            }
        )

    return state


# ============================================================
# 2. SENTIMENT + URGENCY
# ============================================================

def sentiment_agent(
    state: EmailState
) -> EmailState:

    print()
    print("2. Sentiment Agent running...")

    with langfuse.start_as_current_observation(

        as_type="span",

        name="sentiment-agent",

        input={
            "message_id": state["message_id"],
        },

    ) as span:

        # ----------------------------------------------------
        # GET PROMPT
        # ----------------------------------------------------

        prompt, compiled_prompt = get_managed_prompt(

            "sentiment-urgency-classifier",

            email_text=state["cleaned_text"],

        )

        # ----------------------------------------------------
        # CALL LLM
        # ----------------------------------------------------

        output = call_llm_with_prompt(

            generation_name="sentiment-llm",

            prompt=prompt,

            compiled_prompt=compiled_prompt,

        )

        # ----------------------------------------------------
        # DEFAULT VALUES
        # ----------------------------------------------------

        sentiment = "neutral"

        urgency = "medium"

        # ----------------------------------------------------
        # PARSE
        # ----------------------------------------------------

        for line in output.splitlines():

            line = line.strip()

            if line.lower().startswith(
                "sentiment:"
            ):

                sentiment = (
                    line.split(":", 1)[1]
                    .strip()
                    .lower()
                )

            elif line.lower().startswith(
                "urgency:"
            ):

                urgency = (
                    line.split(":", 1)[1]
                    .strip()
                    .lower()
                )

        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        if sentiment not in {
            "positive",
            "negative",
            "neutral",
        }:

            sentiment = "neutral"

        if urgency not in {
            "high",
            "medium",
            "low",
        }:

            urgency = "medium"

        state["sentiment"] = sentiment

        state["urgency"] = urgency

        # ----------------------------------------------------
        # SPAN OUTPUT
        # ----------------------------------------------------

        span.update(
            output={
                "sentiment": sentiment,
                "urgency": urgency,
            }
        )

    return state


# ============================================================
# 3. TOPIC
# ============================================================

def topic_agent(
    state: EmailState
) -> EmailState:

    print()
    print("3. Topic Agent running...")

    retry_count = state.get(
        "retry_count",
        0
    )

    # --------------------------------------------------------
    # TAXONOMY
    # --------------------------------------------------------

    taxonomy_result = (
        topic_taxonomy_tool.invoke({})
    )

    # --------------------------------------------------------
    # PREVIOUS VALIDATION ERROR
    # --------------------------------------------------------

    previous_error = state.get(
        "validation_error",
        ""
    )

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------

    prompt, compiled_prompt = get_managed_prompt(

        "topic-classifier",

        email_text=state["cleaned_text"],

        previous_error=previous_error,

        taxonomy=taxonomy_result,

    )

    # --------------------------------------------------------
    # CALL LLM
    # --------------------------------------------------------

    output = call_llm_with_prompt(

        generation_name="topic-llm",

        prompt=prompt,

        compiled_prompt=compiled_prompt,

    )

    # --------------------------------------------------------
    # PARSE
    # --------------------------------------------------------

    try:

        result = json.loads(
            clean_json_response(output)
        )

        dominant_topic = result.get(
            "dominant_topic",
            "other"
        )

        subtopics = result.get(
            "subtopics",
            ["other"]
        )

        if not isinstance(
            subtopics,
            list
        ):

            subtopics = ["other"]

    except Exception as e:

        print(
            "Topic JSON parsing error:",
            e
        )

        dominant_topic = "other"

        subtopics = ["other"]

        state.setdefault(
            "errors",
            []
        ).append(
            "Topic JSON parsing failed."
        )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state["dominant_topic"] = (
        dominant_topic
    )

    state["subtopics"] = subtopics

    print(
        "Topic retry count:",
        retry_count
    )

    return state


# ============================================================
# 4. VALIDATOR
# ============================================================

def validator_agent(
    state: EmailState
) -> EmailState:

    print()
    print("4. Validator Agent running...")

    with langfuse.start_as_current_observation(

        as_type="span",

        name="validator-agent",

        input={
            "message_id": state["message_id"],
            "dominant_topic": state.get(
                "dominant_topic",
                ""
            ),
            "subtopics": state.get(
                "subtopics",
                []
            ),
        },

    ) as span:

        # ----------------------------------------------------
        # VALIDATOR PROMPT
        # ----------------------------------------------------

        prompt, compiled_prompt = (
            get_managed_prompt(

                "validator-agent",

                dominant_topic=state.get(
                    "dominant_topic",
                    ""
                ),

                subtopics=json.dumps(
                    state.get(
                        "subtopics",
                        []
                    ),
                    ensure_ascii=False,
                ),

            )
        )

        # ----------------------------------------------------
        # CALL VALIDATOR LLM
        # ----------------------------------------------------

        output = call_llm_with_prompt(

            generation_name="validator-llm",

            prompt=prompt,

            compiled_prompt=compiled_prompt,

        )

        # ----------------------------------------------------
        # SCHEMA VALIDATOR
        # ----------------------------------------------------

        validation_result = (
            schema_validator_tool.invoke(
                {
                    "dominant_topic": state.get(
                        "dominant_topic",
                        ""
                    ),
                    "subtopics": state.get(
                        "subtopics",
                        []
                    ),
                }
            )
        )

        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        if isinstance(
            validation_result,
            str
        ):

            try:

                validation_result = json.loads(
                    validation_result
                )

            except Exception:

                validation_result = {
                    "valid": False,
                    "error": (
                        "Validator returned invalid JSON."
                    ),
                }

        valid = validation_result.get(
            "valid",
            False
        )

        error = validation_result.get(
            "error"
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if valid:

            state["validation_result"] = "valid"

            state["validation_error"] = ""

        else:

            state["validation_result"] = "invalid"

            state["validation_error"] = (
                error or "Validation failed."
            )

            state.setdefault(
                "errors",
                []
            ).append(
                state["validation_error"]
            )

        # ----------------------------------------------------
        # SPAN OUTPUT
        # ----------------------------------------------------

        span.update(
            output={
                "valid": valid,
                "error": error,
            }
        )

    return state


# ============================================================
# VALIDATION ROUTER
# ============================================================

def validation_router(
    state: EmailState
):

    if (
        state.get(
            "validation_result"
        )
        == "valid"
    ):

        print(
            "Validation router: VALID -> Writer"
        )

        return "valid"

    retry_count = state.get(
        "retry_count",
        0
    )

    if retry_count < 2:

        state["retry_count"] = (
            retry_count + 1
        )

        print(
            "Validation router: INVALID -> Retry Topic"
        )

        print(
            "Retry count:",
            state["retry_count"]
        )

        return "retry"

    print(
        "Validation router: INVALID -> END"
    )

    print(
        "Maximum retries reached."
    )

    return "end"


# ============================================================
# 5. WRITER
# ============================================================

def writer_node(
    state: EmailState
) -> EmailState:

    print()
    print("5. Writer running...")

    with langfuse.start_as_current_observation(

        as_type="span",

        name="writer",

        input={
            "message_id": state["message_id"],
        },

    ) as span:

        # ----------------------------------------------------
        # WRITE TO NEW BIGQUERY TABLE
        # ----------------------------------------------------

        result = bigquery_write_tool.invoke(

            {
                "message_id": state[
                    "message_id"
                ],

                "sentiment": state.get(
                    "sentiment",
                    "neutral"
                ),

                "urgency": state.get(
                    "urgency",
                    "medium"
                ),

                "dominant_topic": state.get(
                    "dominant_topic",
                    "other"
                ),

                "subtopics": state.get(
                    "subtopics",
                    ["other"]
                ),

                "validation": state.get(
                    "validation_result",
                    "invalid"
                ),

                "retries": state.get(
                    "retry_count",
                    0
                ),

                "errors": state.get(
                    "errors",
                    []
                ),

                "trace_id": state.get(
                    "trace_id",
                    ""
                ),
            }

        )

        # ----------------------------------------------------
        # TRACE OUTPUT
        # ----------------------------------------------------

        span.update(
            output={
                "write_result": result
            }
        )

        print(
            "BigQuery write completed."
        )

    return state


# ============================================================
# BUILD LANGGRAPH
# ============================================================

def build_graph():

    graph = StateGraph(
        EmailState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    graph.add_node(
        "supervisor",
        supervisor_agent,
    )

    graph.add_node(
        "preprocess",
        preprocess_node,
    )

    graph.add_node(
        "sentiment",
        sentiment_agent,
    )

    graph.add_node(
        "topic",
        topic_agent,
    )

    graph.add_node(
        "validator",
        validator_agent,
    )

    graph.add_node(
        "writer",
        writer_node,
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "supervisor",
    )

    # --------------------------------------------------------
    # SUPERVISOR
    # --------------------------------------------------------

    graph.add_conditional_edges(

        "supervisor",

        supervisor_router,

        {
            "process": "preprocess",
            "end": END,
        }

    )

    # --------------------------------------------------------
    # MAIN PIPELINE
    # --------------------------------------------------------

    graph.add_edge(
        "preprocess",
        "sentiment",
    )

    graph.add_edge(
        "sentiment",
        "topic",
    )

    graph.add_edge(
        "topic",
        "validator",
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    graph.add_conditional_edges(

        "validator",

        validation_router,

        {
            "valid": "writer",
            "retry": "topic",
            "end": END,
        }

    )

    # --------------------------------------------------------
    # WRITER
    # --------------------------------------------------------

    graph.add_edge(
        "writer",
        END,
    )

    return graph.compile()


# ============================================================
# READ EMAILS FROM BIGQUERY
# ============================================================

def get_emails():

    print()
    print("=" * 60)
    print("READING EMAILS FROM BIGQUERY")
    print("=" * 60)

    result = bigquery_read_tool.invoke({})

    # --------------------------------------------------------
    # STRING
    # --------------------------------------------------------

    if isinstance(
        result,
        str
    ):

        try:

            result = json.loads(result)

        except Exception:

            return []

    # --------------------------------------------------------
    # DICT
    # --------------------------------------------------------

    if isinstance(
        result,
        dict
    ):

        if "emails" in result:

            return result["emails"]

        if "rows" in result:

            return result["rows"]

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------

    if isinstance(
        result,
        list
    ):

        return result

    return []


# ============================================================
# PROCESS ONE EMAIL
# ============================================================

def process_email(
    email,
    graph,
):

    # --------------------------------------------------------
    # EMAIL FIELDS
    # --------------------------------------------------------

    message_id = str(
        email.get(
            "message_id",
            ""
        )
    )

    subject = email.get(
        "message_subject",
        email.get(
            "subject",
            ""
        )
    )

    from_email = email.get(
        "from_email",
        ""
    )

    raw_text = email.get(
        "body_text",
        email.get(
            "body_plain",
            ""
        )
    )

    # --------------------------------------------------------
    # CREATE DETERMINISTIC TRACE ID
    # --------------------------------------------------------

    trace_id = langfuse.create_trace_id(
        seed=message_id
    )

    print()
    print(
        "Langfuse Trace ID:",
        trace_id
    )

    # --------------------------------------------------------
    # INITIAL STATE
    # --------------------------------------------------------

    state: EmailState = {

        "message_id": message_id,

        "subject": subject,

        "from_email": from_email,

        "raw_text": raw_text,

        "cleaned_text": "",

        "trace_id": trace_id,

        "route": "process",

        "sentiment": "neutral",

        "urgency": "medium",

        "dominant_topic": "other",

        "subtopics": ["other"],

        "validation_result": "invalid",

        "validation_error": "",

        "retry_count": 0,

        "errors": [],

    }

    # --------------------------------------------------------
    # START TRACE
    # --------------------------------------------------------

    with langfuse.start_as_current_observation(

        as_type="span",

        name="email-intelligence",

        trace_context={
            "trace_id": trace_id
        },

        input={
            "message_id": message_id,
        },

        metadata={
            "message_id": message_id,
            "agent_name": "email-intelligence",
            "model": MODEL_NAME,
        },

    ) as trace:

        # ----------------------------------------------------
        # RUN GRAPH
        # ----------------------------------------------------

        final_state = graph.invoke(
            state
        )

        # ----------------------------------------------------
        # TRACE OUTPUT
        # ----------------------------------------------------

        trace.update(

            output={

                "message_id": final_state.get(
                    "message_id"
                ),

                "sentiment": final_state.get(
                    "sentiment"
                ),

                "urgency": final_state.get(
                    "urgency"
                ),

                "dominant_topic": final_state.get(
                    "dominant_topic"
                ),

                "subtopics": final_state.get(
                    "subtopics"
                ),

                "validation_result": final_state.get(
                    "validation_result"
                ),

                "retry_count": final_state.get(
                    "retry_count",
                    0
                ),

                "errors": final_state.get(
                    "errors",
                    []
                ),
            },

            metadata={
                "message_id": message_id,
                "agent_name": "email-intelligence",
                "model": MODEL_NAME,
            },

        )

    return final_state


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # BUILD GRAPH
    # --------------------------------------------------------

    graph = build_graph()

    # --------------------------------------------------------
    # GET EMAILS
    # --------------------------------------------------------

    emails = get_emails()

    print()
    print(
        "Emails received:",
        len(emails)
    )

    if not emails:

        print(
            "No emails found."
        )

        langfuse.flush()

        return

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    for email in emails:

        print()
        print("=" * 60)
        print("PROCESSING EMAIL")
        print("=" * 60)

        print(
            "Message ID:",
            email.get("message_id")
        )

        try:

            final_state = process_email(
                email,
                graph
            )

            print()
            print(
                "FINAL RESULT"
            )

            print(
                "------------------------------"
            )

            print(
                "Message ID:",
                final_state.get(
                    "message_id"
                )
            )

            print(
                "Trace ID:",
                final_state.get(
                    "trace_id"
                )
            )

            print(
                "Sentiment:",
                final_state.get(
                    "sentiment"
                )
            )

            print(
                "Urgency:",
                final_state.get(
                    "urgency"
                )
            )

            print(
                "Topic:",
                final_state.get(
                    "dominant_topic"
                )
            )

            print(
                "Subtopics:",
                final_state.get(
                    "subtopics"
                )
            )

            print(
                "Validation:",
                final_state.get(
                    "validation_result"
                )
            )

            print(
                "Retries:",
                final_state.get(
                    "retry_count"
                )
            )

            print(
                "Errors:",
                final_state.get(
                    "errors"
                )
            )

            print(
                "------------------------------"
            )

        except Exception as e:

            print()
            print(
                "ERROR PROCESSING EMAIL:"
            )

            print(e)

    # --------------------------------------------------------
    # FLUSH
    # --------------------------------------------------------

    langfuse.flush()

    print()
    print(
        "Langfuse data flushed successfully."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()