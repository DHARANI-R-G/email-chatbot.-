from typing import Any
import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from langfuse import get_client


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# BIGQUERY CONFIGURATION
# ============================================================

PROJECT_ID = "intern-task-483106"

DATASET_ID = "email_ingestion"

ENRICHED_TABLE = "enriched_email_messages_dharani_new"


# ============================================================
# BIGQUERY CLIENT
# ============================================================

bigquery_client = bigquery.Client(
    project=PROJECT_ID
)


# ============================================================
# LANGFUSE CLIENT
# ============================================================

langfuse = get_client()


# ============================================================
# CHATBOT LLM
# ============================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_MODEL = "openai/gpt-5-mini"

chat_llm = ChatOpenAI(
    model=CHAT_MODEL,
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
    max_tokens=1200
)


# ============================================================
# CHATBOT REQUEST MODEL
# ============================================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Email Intelligence API",
    description=(
        "API for email intelligence results "
        "and Langfuse pipeline traces."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://frontend-80n0cx72c-rgdharani44-2692.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# HELPER — CONVERT VALUE TO JSON SAFE VALUE
# ============================================================

def convert_value(value):

    if value is None:
        return None

    # Datetime
    if hasattr(value, "isoformat"):

        try:
            return value.isoformat()
        except Exception:
            pass

    # Pydantic model
    if hasattr(value, "model_dump"):

        try:
            return value.model_dump(
                mode="json"
            )
        except Exception:
            pass

    # Dictionary
    if isinstance(value, dict):

        return {
            str(key): convert_value(value)
            for key, value in value.items()
        }

    # List
    if isinstance(value, list):

        return [
            convert_value(item)
            for item in value
        ]

    # Tuple
    if isinstance(value, tuple):

        return [
            convert_value(item)
            for item in value
        ]

    # Primitive
    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value

    # Last resort
    return str(value)


# ============================================================
# HELPER — PARSE LANGFUSE OUTPUT
# ============================================================

def parse_output(output):

    if output is None:
        return None

    # Already dictionary
    if isinstance(output, dict):
        return output

    # JSON string
    if isinstance(output, str):

        try:

            parsed = json.loads(output)

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            return None

    # Pydantic model
    if hasattr(output, "model_dump"):

        try:

            parsed = output.model_dump(
                mode="json"
            )

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

    return None


# ============================================================
# HELPER — GET OBSERVATION FIELD
# ============================================================

def get_observation_value(
    observation,
    field,
    default=None,
):

    try:

        return getattr(
            observation,
            field,
            default
        )

    except Exception:

        return default


# ============================================================
# HELPER — GET COST
# ============================================================

def get_observation_cost(
    observation
):

    cost_details = get_observation_value(
        observation,
        "cost_details"
    )

    # Langfuse usually returns:
    #
    # {
    #     "input": ...,
    #     "output": ...,
    #     "total": ...
    # }

    if isinstance(
        cost_details,
        dict
    ):

        total = cost_details.get(
            "total"
        )

        if isinstance(
            total,
            (int, float)
        ):

            return total

    # Fallback
    total_cost = get_observation_value(
        observation,
        "total_cost"
    )

    if isinstance(
        total_cost,
        (int, float)
    ):

        return total_cost

    return 0.0


# ============================================================
# HELPER — GET TOKEN USAGE
# ============================================================

def get_token_usage(
    observation
):

    usage = get_observation_value(
        observation,
        "usage_details"
    )

    if not isinstance(
        usage,
        dict
    ):

        return 0, 0, 0

    input_tokens = usage.get(
        "input"
    )

    output_tokens = usage.get(
        "output"
    )

    total_tokens = usage.get(
        "total"
    )

    # Fallback for alternate names
    if input_tokens is None:

        input_tokens = usage.get(
            "input_tokens"
        )

    if output_tokens is None:

        output_tokens = usage.get(
            "output_tokens"
        )

    if total_tokens is None:

        total_tokens = usage.get(
            "total_tokens"
        )

    input_tokens = (
        input_tokens
        if isinstance(
            input_tokens,
            (int, float)
        )
        else 0
    )

    output_tokens = (
        output_tokens
        if isinstance(
            output_tokens,
            (int, float)
        )
        else 0
    )

    total_tokens = (
        total_tokens
        if isinstance(
            total_tokens,
            (int, float)
        )
        else 0
    )

    return (
        input_tokens,
        output_tokens,
        total_tokens
    )


# ============================================================
# FORMAT ONE OBSERVATION
# ============================================================

def format_observation(
    observation
):

    name = get_observation_value(
        observation,
        "name"
    )

    observation_type = get_observation_value(
        observation,
        "type"
    )

    latency = get_observation_value(
        observation,
        "latency"
    )

    level = get_observation_value(
        observation,
        "level"
    )

    status_message = (
        get_observation_value(
            observation,
            "status_message"
        )
    )

    result = {

        "name":
            convert_value(name),

        "type":
            convert_value(
                observation_type
            ),

        "latency":
            convert_value(latency),

    }

    # ========================================================
    # GENERATION
    # ========================================================

    if str(
        observation_type
    ).upper() == "GENERATION":

        prompt_name = (
            get_observation_value(
                observation,
                "prompt_name"
            )
        )

        prompt_version = (
            get_observation_value(
                observation,
                "prompt_version"
            )
        )

        # ----------------------------------------------------
        # Prompt NAME only
        #
        # Actual prompt text is intentionally NOT returned.
        # ----------------------------------------------------

        if prompt_name:

            result["prompt_name"] = (
                convert_value(
                    prompt_name
                )
            )

        if prompt_version is not None:

            result["prompt_version"] = (
                convert_value(
                    prompt_version
                )
            )

        # ----------------------------------------------------
        # Output only
        # ----------------------------------------------------

        output = parse_output(

            get_observation_value(
                observation,
                "output"
            )

        )

        if output is not None:

            result["output"] = (
                convert_value(
                    output
                )
            )

        # ----------------------------------------------------
        # Token usage
        # ----------------------------------------------------

        (
            input_tokens,
            output_tokens,
            total_tokens
        ) = get_token_usage(
            observation
        )

        if input_tokens:

            result["input_tokens"] = (
                input_tokens
            )

        if output_tokens:

            result["output_tokens"] = (
                output_tokens
            )

        if total_tokens:

            result["total_tokens"] = (
                total_tokens
            )

        # ----------------------------------------------------
        # Cost
        # ----------------------------------------------------

        cost = get_observation_cost(
            observation
        )

        if cost:

            result["cost"] = cost

    # ========================================================
    # SPAN
    # ========================================================

    else:

        output = parse_output(

            get_observation_value(
                observation,
                "output"
            )

        )

        if isinstance(
            output,
            dict
        ):

            clean_output = {}

            for key, value in output.items():

                # Never expose cleaned email text
                if key == "cleaned_text":
                    continue

                clean_output[key] = (
                    convert_value(value)
                )

            if clean_output:

                result["output"] = (
                    clean_output
                )

        elif output is not None:

            result["output"] = (
                convert_value(output)
            )

    # ========================================================
    # STATUS
    # ========================================================

    if level:

        result["status"] = (
            convert_value(level)
        )

    if status_message:

        result["error"] = (
            convert_value(
                status_message
            )
        )

    return result


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "status":
            "ok",

        "message":
            "Email Intelligence API is running."

    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status":
            "healthy"

    }


# ============================================================
# STATISTICS
# ============================================================

@app.get("/stats")
def get_stats():

    query = f"""

    SELECT

        COUNT(*) AS total_processed,

        COUNTIF(
            sentiment = 'positive'
        ) AS positive_count,

        COUNTIF(
            sentiment = 'negative'
        ) AS negative_count,

        COUNTIF(
            sentiment = 'neutral'
        ) AS neutral_count,

        COUNTIF(
            urgency = 'high'
        ) AS high_urgency_count,

        COUNTIF(
            urgency = 'medium'
        ) AS medium_urgency_count,

        COUNTIF(
            urgency = 'low'
        ) AS low_urgency_count

    FROM
        `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}`

    """

    try:

        rows = (
            bigquery_client
            .query(query)
            .result()
        )

        row = next(
            iter(rows),
            None
        )

        if row is None:

            return {

                "total_processed": 0,

                "positive_count": 0,

                "negative_count": 0,

                "neutral_count": 0,

                "high_urgency_count": 0,

                "medium_urgency_count": 0,

                "low_urgency_count": 0,

            }

        return {

            "total_processed":
                row.total_processed,

            "positive_count":
                row.positive_count,

            "negative_count":
                row.negative_count,

            "neutral_count":
                row.neutral_count,

            "high_urgency_count":
                row.high_urgency_count,

            "medium_urgency_count":
                row.medium_urgency_count,

            "low_urgency_count":
                row.low_urgency_count,

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# GET PROCESSED EMAILS
# ============================================================

@app.get("/emails")
def get_emails(
    limit: int = 50
):

    if limit < 1:
        limit = 1

    if limit > 500:
        limit = 500

    query = f"""

    SELECT

        message_id,

        sentiment,

        urgency,

        dominant_topic,

        subtopics,

        processed_at

    FROM
        `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}`

    ORDER BY
        processed_at DESC

    LIMIT @limit

    """

    job_config = (
        bigquery.QueryJobConfig(

            query_parameters=[

                bigquery.ScalarQueryParameter(
                    "limit",
                    "INT64",
                    limit
                )

            ]

        )
    )

    try:

        rows = (
            bigquery_client
            .query(
                query,
                job_config=job_config
            )
            .result()
        )

        emails = []

        for row in rows:

            emails.append({

                "message_id":
                    row.message_id,

                "sentiment":
                    row.sentiment,

                "urgency":
                    row.urgency,

                "dominant_topic":
                    row.dominant_topic,

                "subtopics":
                    (
                        list(row.subtopics)
                        if row.subtopics
                        else []
                    ),

                "processed_at":
                    (
                        row.processed_at.isoformat()
                        if row.processed_at
                        else None
                    ),

            })

        return {

            "count":
                len(emails),

            "emails":
                emails,

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# GET ONE PROCESSED EMAIL
# ============================================================

@app.get(
    "/emails/{message_id}"
)
def get_email(
    message_id: str
):

    query = f"""

    SELECT

        message_id,

        sentiment,

        urgency,

        dominant_topic,

        subtopics,

        processed_at

    FROM
        `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}`

    WHERE
        message_id = @message_id

    LIMIT 1

    """

    job_config = (
        bigquery.QueryJobConfig(

            query_parameters=[

                bigquery.ScalarQueryParameter(
                    "message_id",
                    "STRING",
                    message_id
                )

            ]

        )
    )

    try:

        rows = (
            bigquery_client
            .query(
                query,
                job_config=job_config
            )
            .result()
        )

        row = next(
            iter(rows),
            None
        )

        if row is None:

            raise HTTPException(
                status_code=404,
                detail="Email not found."
            )

        return {

            "message_id":
                row.message_id,

            "sentiment":
                row.sentiment,

            "urgency":
                row.urgency,

            "dominant_topic":
                row.dominant_topic,

            "subtopics":
                (
                    list(row.subtopics)
                    if row.subtopics
                    else []
                ),

            "processed_at":
                (
                    row.processed_at.isoformat()
                    if row.processed_at
                    else None
                ),

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# SEARCH EMAILS
# ============================================================

@app.get("/search")
def search_emails(
    q: str,
    limit: int = 50
):

    if limit < 1:
        limit = 1

    if limit > 500:
        limit = 500

    query = f"""

    SELECT

        message_id,

        sentiment,

        urgency,

        dominant_topic,

        subtopics,

        processed_at

    FROM
        `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}`

    WHERE

        LOWER(message_id)
        LIKE LOWER(@search)

        OR LOWER(sentiment)
        LIKE LOWER(@search)

        OR LOWER(urgency)
        LIKE LOWER(@search)

        OR LOWER(dominant_topic)
        LIKE LOWER(@search)

    ORDER BY
        processed_at DESC

    LIMIT @limit

    """

    job_config = (
        bigquery.QueryJobConfig(

            query_parameters=[

                bigquery.ScalarQueryParameter(
                    "search",
                    "STRING",
                    f"%{q}%"
                ),

                bigquery.ScalarQueryParameter(
                    "limit",
                    "INT64",
                    limit
                ),

            ]

        )
    )

    try:

        rows = (
            bigquery_client
            .query(
                query,
                job_config=job_config
            )
            .result()
        )

        results = []

        for row in rows:

            results.append({

                "message_id":
                    row.message_id,

                "sentiment":
                    row.sentiment,

                "urgency":
                    row.urgency,

                "dominant_topic":
                    row.dominant_topic,

                "subtopics":
                    (
                        list(row.subtopics)
                        if row.subtopics
                        else []
                    ),

                "processed_at":
                    (
                        row.processed_at.isoformat()
                        if row.processed_at
                        else None
                    ),

            })

        return {

            "count":
                len(results),

            "results":
                results,

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# LANGFUSE TRACE
# ============================================================

@app.get(
    "/emails/{message_id}/trace"
)
def get_email_trace(
    message_id: str
):

    try:

        # ====================================================
        # DETERMINISTIC TRACE ID
        # ====================================================

        trace_id = (
            langfuse.create_trace_id(
                seed=message_id
            )
        )

        # ====================================================
        # GET TRACE
        # ====================================================

        try:

            trace = (
                langfuse.api.trace.get(
                    trace_id
                )
            )

        except Exception:

            return {

                "found":
                    False,

                "message_id":
                    message_id,

                "trace_id":
                    trace_id,

                "message":
                    "Langfuse trace not found."

            }

        # ====================================================
        # GET OBSERVATIONS
        # ====================================================

        observations_response = (
            langfuse.api.observations.get_many(

                trace_id=trace_id,

                limit=100,

                fields=(
                    "core,"
                    "basic,"
                    "time,"
                    "io,"
                    "metadata,"
                    "model,"
                    "usage,"
                    "prompt,"
                    "metrics,"
                    "trace_context"
                ),

            )
        )

        all_observations = (
            observations_response.data
        )

        # ====================================================
        # FIND SUCCESSFUL PIPELINE ROOT
        # ====================================================

        successful_roots = []

        for observation in all_observations:

            name = get_observation_value(
                observation,
                "name"
            )

            level = get_observation_value(
                observation,
                "level"
            )

            output = parse_output(

                get_observation_value(
                    observation,
                    "output"
                )

            )

            if name != "email-intelligence":
                continue

            if str(level).upper() == "ERROR":
                continue

            if not isinstance(
                output,
                dict
            ):
                continue

            if output.get(
                "message_id"
            ) != message_id:
                continue

            # A completed pipeline should have
            # validation_result in its output.

            if "validation_result" not in output:
                continue

            successful_roots.append(
                observation
            )

        # ====================================================
        # SELECT LATEST SUCCESSFUL ROOT
        # ====================================================

        selected_root = None

        if successful_roots:

            selected_root = max(

                successful_roots,

                key=lambda observation: (
                    get_observation_value(
                        observation,
                        "start_time"
                    )
                    or ""
                )

            )

        # ====================================================
        # COLLECT ONLY THE LATEST PIPELINE RUN
        # ====================================================

        selected_observations = []

        if selected_root is not None:

            root_start = (
                get_observation_value(
                    selected_root,
                    "start_time"
                )
            )

            root_end = (
                get_observation_value(
                    selected_root,
                    "end_time"
                )
            )

            for observation in all_observations:

                start_time = (
                    get_observation_value(
                        observation,
                        "start_time"
                    )
                )

                if (
                    start_time is not None
                    and
                    root_start is not None
                    and
                    root_end is not None
                    and
                    root_start <= start_time <= root_end
                ):

                    selected_observations.append(
                        observation
                    )

        else:

            # No successful execution.
            # Use observations as fallback.

            selected_observations = (
                all_observations
            )

        # ====================================================
        # FORMAT STEPS
        # ====================================================

        steps = []

        for observation in selected_observations:

            steps.append(
                format_observation(
                    observation
                )
            )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        final_result = {

            "message_id":
                message_id,

            "sentiment":
                None,

            "urgency":
                None,

            "dominant_topic":
                None,

            "subtopics":
                [],

            "validation":
                None,

            "retries":
                0,

            "errors":
                [],

        }

        # ====================================================
        # READ RESULT FROM SUCCESSFUL ROOT
        # ====================================================

        if selected_root is not None:

            root_output = parse_output(

                get_observation_value(
                    selected_root,
                    "output"
                )

            )

            if isinstance(
                root_output,
                dict
            ):

                final_result = {

                    "message_id":
                        root_output.get(
                            "message_id",
                            message_id
                        ),

                    "sentiment":
                        root_output.get(
                            "sentiment"
                        ),

                    "urgency":
                        root_output.get(
                            "urgency"
                        ),

                    "dominant_topic":
                        root_output.get(
                            "dominant_topic"
                        ),

                    "subtopics":
                        root_output.get(
                            "subtopics",
                            []
                        ),

                    "validation":
                        root_output.get(
                            "validation_result"
                        ),

                    "retries":
                        root_output.get(
                            "retry_count",
                            0
                        ),

                    "errors":
                        root_output.get(
                            "errors",
                            []
                        ),

                }

        # ====================================================
        # GENERATION STEPS
        # ====================================================

        generation_steps = [

            observation

            for observation
            in selected_observations

            if str(
                get_observation_value(
                    observation,
                    "type"
                )
            ).upper()
            == "GENERATION"

        ]

        # ====================================================
        # ERROR COUNT
        # ====================================================

        error_steps = [

            observation

            for observation
            in selected_observations

            if str(
                get_observation_value(
                    observation,
                    "level"
                )
            ).upper()
            == "ERROR"

        ]

        # ====================================================
        # TOKEN TOTALS
        # ====================================================

        total_input_tokens = 0

        total_output_tokens = 0

        total_tokens = 0

        total_cost = 0.0

        for observation in generation_steps:

            (
                input_tokens,
                output_tokens,
                tokens
            ) = get_token_usage(
                observation
            )

            total_input_tokens += (
                input_tokens
            )

            total_output_tokens += (
                output_tokens
            )

            total_tokens += tokens

            total_cost += (
                get_observation_cost(
                    observation
                )
            )

        # ====================================================
        # TOTAL PIPELINE LATENCY
        #
        # IMPORTANT:
        #
        # Do NOT sum all observation latencies.
        #
        # Parent spans contain child execution time,
        # so summing everything double-counts latency.
        #
        # Use the root email-intelligence span instead.
        # ====================================================

        total_latency = 0.0

        if selected_root is not None:

            root_latency = (
                get_observation_value(
                    selected_root,
                    "latency"
                )
            )

            if isinstance(
                root_latency,
                (int, float)
            ):

                total_latency = (
                    root_latency
                )

        # ====================================================
        # MODEL
        # ====================================================

        model_name = None

        for observation in generation_steps:

            # Different Langfuse versions may expose
            # model information differently.

            model_name = (
                get_observation_value(
                    observation,
                    "provided_model_name"
                )
            )

            if model_name:
                break

        # ====================================================
        # TRACE NAME
        # ====================================================

        trace_name = convert_value(

            getattr(
                trace,
                "name",
                None
            )

        )

        # ====================================================
        # SUMMARY
        # ====================================================

        summary = {

            "steps":
                len(steps),

            "generations":
                len(generation_steps),

            "errors":
                len(error_steps),

            "total_latency":
                round(
                    total_latency,
                    3
                ),

            "total_input_tokens":
                int(
                    total_input_tokens
                ),

            "total_output_tokens":
                int(
                    total_output_tokens
                ),

            "total_tokens":
                int(
                    total_tokens
                ),

            "total_cost":
                round(
                    total_cost,
                    8
                ),

        }

        # Only add model when available.
        # Avoid returning "model": null.

        if model_name:

            summary["model"] = (
                convert_value(
                    model_name
                )
            )

        # ====================================================
        # RETURN CLEAN RESPONSE
        # ====================================================

        return {

            "found":
                True,

            "message_id":
                message_id,

            "trace_id":
                trace_id,

            # ------------------------------------------------
            # Final classification
            # ------------------------------------------------

            "result":
                final_result,

            # ------------------------------------------------
            # Useful metrics only
            # ------------------------------------------------

            "summary":
                summary,

            # ------------------------------------------------
            # Clean pipeline steps
            # ------------------------------------------------

            "steps":
                steps,

        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ============================================================
# TRACE CHATBOT
# ============================================================

@app.post("/emails/{message_id}/chat")
def chat_about_trace(
    message_id: str,
    request: ChatRequest,
):
    try:
        question = request.question.strip()

        if not question:
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty.",
            )

        # ----------------------------------------------------
        # DETERMINISTIC TRACE ID
        # ----------------------------------------------------

        trace_id = langfuse.create_trace_id(
            seed=message_id
        )

        # ----------------------------------------------------
        # GET TRACE
        # ----------------------------------------------------

        try:
            langfuse.api.trace.get(trace_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail="Langfuse trace not found.",
            )

        # ----------------------------------------------------
        # GET OBSERVATIONS
        # ----------------------------------------------------

        observations_response = (
            langfuse.api.observations.get_many(
                trace_id=trace_id,
                limit=100,
                fields=(
                    "core,"
                    "basic,"
                    "time,"
                    "io,"
                    "metadata,"
                    "model,"
                    "usage,"
                    "prompt,"
                    "metrics,"
                    "trace_context"
                ),
            )
        )

        observations = observations_response.data

        # ----------------------------------------------------
        # USE THE SAME CLEAN FORMAT AS THE TRACE UI
        # ----------------------------------------------------

        trace_context = {
            "message_id": message_id,
            "trace_id": trace_id,
            "observations": [
                format_observation(observation)
                for observation in observations
            ],
        }

        # ----------------------------------------------------
        # SYSTEM INSTRUCTIONS
        # ----------------------------------------------------

        system_prompt = """
You are the Trace Assistant for an Email Intelligence
application.

You answer questions about the selected email's Langfuse
pipeline trace.

Use ONLY the trace information provided to you.

You may explain:
- what happened during processing
- pipeline steps
- sentiment
- urgency
- topic and subtopics
- validation
- retries
- errors
- latency
- token usage
- LLM calls
- prompt names and versions
- cost

Do not invent facts.

If the trace does not contain enough information, say that
the information is not available in the trace.

Keep answers concise, clear, and easy to understand.

Never reveal API keys, credentials, hidden prompt text, or
other secrets.
"""

        # ----------------------------------------------------
        # CONVERSATION HISTORY
        # ----------------------------------------------------

        history_text = ""

        for message in request.history[-10:]:
            role = message.role.lower().strip()

            if role not in ("user", "assistant"):
                continue

            history_text += (
                f"{role.upper()}: {message.content}\n"
            )

        # ----------------------------------------------------
        # USER PROMPT
        # ----------------------------------------------------

        user_prompt = f"""
SELECTED EMAIL TRACE:

{json.dumps(
    trace_context,
    indent=2,
    default=str,
)}

PREVIOUS CONVERSATION:

{history_text if history_text else "No previous conversation."}

CURRENT USER QUESTION:

{question}

Answer the current question using only the selected
email trace and the conversation context.
"""

        # ----------------------------------------------------
        # LLM CALL
        # ----------------------------------------------------

        response = chat_llm.invoke(
            [
                ("system", system_prompt),
                ("user", user_prompt),
            ]
        )

        answer = response.content

        if not isinstance(answer, str):
            answer = str(answer)

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return {
            "message_id": message_id,
            "trace_id": trace_id,
            "question": question,
            "answer": answer,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

