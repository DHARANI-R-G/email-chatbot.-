from typing import Any

from google.cloud import bigquery
from langchain_core.tools import tool


# ============================================================
# BIGQUERY CONFIGURATION
# ============================================================

PROJECT_ID = "intern-task-483106"

DATASET_ID = "email_ingestion"

RAW_TABLE = "raw_email_messages_csv"

ENRICHED_TABLE = "enriched_email_messages_dharani_new"


# ============================================================
# BIGQUERY CLIENT
# ============================================================

client = bigquery.Client(
    project=PROJECT_ID
)


# ============================================================
# BIGQUERY READ TOOL
# ============================================================

@tool
def bigquery_read_tool(
    limit: int = 10
) -> list[dict[str, Any]]:
    """
    Read unprocessed emails from the raw BigQuery table.

    Only emails that do not already exist in the
    enriched table are returned.
    """

    query = f"""
    SELECT
        r.provider,
        r.thread_id,
        r.m365_conversation_id,
        r.thread_subject,
        r.thread_first_message_at,
        r.thread_last_message_at,
        r.thread_message_count,
        r.from_name,
        r.from_email,
        r.to_names,
        r.to_emails,
        r.message_id,
        r.internet_message_id,
        r.message_sent_at,
        r.message_subject,
        r.body_mime_type,
        r.body_text

    FROM `{PROJECT_ID}.{DATASET_ID}.{RAW_TABLE}` AS r

    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}` AS e
        ON r.message_id = e.message_id

    WHERE
        r.message_id IS NOT NULL
        AND e.message_id IS NULL

    ORDER BY r.message_sent_at

    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "limit",
                "INT64",
                limit
            )
        ]
    )

    rows = client.query(
        query,
        job_config=job_config
    ).result()

    emails = []

    for row in rows:

        emails.append({

            "message_id":
                row.message_id,

            "conversation_id":
                row.thread_id,

            "internet_message_id":
                row.internet_message_id,

            "provider":
                row.provider,

            "subject":
                row.message_subject,

            "from_name":
                row.from_name,

            "from_email":
                row.from_email,

            "to_name":
                row.to_names,

            "to_email":
                row.to_emails,

            "date":
                row.message_sent_at,

            "body_plain":
                row.body_text,

            "thread_message_count":
                row.thread_message_count
        })

    return emails


# ============================================================
# BIGQUERY WRITE TOOL
# ============================================================

@tool
def bigquery_write_tool(
    message_id: str,
    sentiment: str,
    urgency: str,
    dominant_topic: str,
    subtopics: list[str],
    validation: str,
    retries: int,
    errors: list[str],
    trace_id: str
) -> str:
    """
    Write the complete enriched email result to BigQuery.

    Table:
        enriched_email_messages_dharani_new

    Uses MERGE so the same message_id is not duplicated.
    """

    query = f"""
    MERGE `{PROJECT_ID}.{DATASET_ID}.{ENRICHED_TABLE}` AS target

    USING (
        SELECT
            @message_id AS message_id,
            @sentiment AS sentiment,
            @urgency AS urgency,
            @dominant_topic AS dominant_topic,
            @subtopics AS subtopics,
            @validation AS validation,
            @retries AS retries,
            @errors AS errors,
            @trace_id AS trace_id
    ) AS source

    ON target.message_id = source.message_id

    WHEN MATCHED THEN

        UPDATE SET

            sentiment = source.sentiment,

            urgency = source.urgency,

            dominant_topic =
                source.dominant_topic,

            subtopics =
                source.subtopics,

            validation =
                source.validation,

            retries =
                source.retries,

            errors =
                source.errors,

            trace_id =
                source.trace_id,

            processed_at =
                CURRENT_TIMESTAMP()

    WHEN NOT MATCHED THEN

        INSERT (
            message_id,
            sentiment,
            urgency,
            dominant_topic,
            subtopics,
            validation,
            retries,
            errors,
            trace_id,
            processed_at
        )

        VALUES (
            source.message_id,
            source.sentiment,
            source.urgency,
            source.dominant_topic,
            source.subtopics,
            source.validation,
            source.retries,
            source.errors,
            source.trace_id,
            CURRENT_TIMESTAMP()
        )
    """

    # ========================================================
    # QUERY PARAMETERS
    # ========================================================

    job_config = bigquery.QueryJobConfig(
        query_parameters=[

            # -----------------------------------------------
            # MESSAGE ID
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "message_id",
                "STRING",
                message_id
            ),

            # -----------------------------------------------
            # SENTIMENT
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "sentiment",
                "STRING",
                sentiment
            ),

            # -----------------------------------------------
            # URGENCY
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "urgency",
                "STRING",
                urgency
            ),

            # -----------------------------------------------
            # TOPIC
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "dominant_topic",
                "STRING",
                dominant_topic
            ),

            # -----------------------------------------------
            # SUBTOPICS
            # ARRAY<STRING>
            # -----------------------------------------------

            bigquery.ArrayQueryParameter(
                "subtopics",
                "STRING",
                subtopics
            ),

            # -----------------------------------------------
            # VALIDATION
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "validation",
                "STRING",
                validation
            ),

            # -----------------------------------------------
            # RETRIES
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "retries",
                "INT64",
                retries
            ),

            # -----------------------------------------------
            # ERRORS
            # ARRAY<STRING>
            # -----------------------------------------------

            bigquery.ArrayQueryParameter(
                "errors",
                "STRING",
                errors
            ),

            # -----------------------------------------------
            # TRACE ID
            # -----------------------------------------------

            bigquery.ScalarQueryParameter(
                "trace_id",
                "STRING",
                trace_id
            ),
        ]
    )

    # ========================================================
    # EXECUTE
    # ========================================================

    client.query(
        query,
        job_config=job_config
    ).result()

    return (
        f"Message {message_id} "
        f"processed successfully."
    )