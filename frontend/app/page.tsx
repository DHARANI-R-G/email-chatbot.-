"use client";

import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";


// ============================================================
// TYPES
// ============================================================

type Email = {
  message_id: string;
  sentiment: string;
  urgency: string;
  dominant_topic: string;
  subtopics: string[];
  processed_at: string | null;
};

type TraceStep = {
  name: string;
  type: string;
  latency?: number | null;
  output?: any;
  status?: string;

  prompt_name?: string;
  prompt_version?: number | null;

  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;

  cost?: number | null;

  error?: string;
};

type TraceResult = {
  message_id?: string;
  sentiment?: string | null;
  urgency?: string | null;
  dominant_topic?: string | null;
  subtopics?: string[];
  validation?: string | null;
  retries?: number;
  errors?: string[];
};

type TraceSummary = {
  steps?: number;
  generations?: number;
  errors?: number;

  total_latency?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  total_tokens?: number;
  total_cost?: number;

  model?: string | null;
};

type TraceResponse = {
  found?: boolean;
  message_id?: string;
  trace_id?: string;

  result?: TraceResult | null;

  summary?: TraceSummary | null;

  steps?: TraceStep[];
};


type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};


// ============================================================
// MAIN PAGE
// ============================================================

export default function Home() {
  const [emails, setEmails] = useState<Email[]>([]);

  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(true);

  const [selectedEmail, setSelectedEmail] =
    useState<Email | null>(null);

  const [trace, setTrace] =
    useState<TraceResponse | null>(null);

  const [traceLoading, setTraceLoading] =
    useState(false);

  const [error, setError] = useState("");

  const [chatMessages, setChatMessages] =
    useState<ChatMessage[]>([]);

  const [chatInput, setChatInput] =
    useState("");

  const [chatLoading, setChatLoading] =
    useState(false);


  // ============================================================
  // LOAD EMAILS
  // ============================================================

  async function loadEmails() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/emails?limit=50`
      );

      if (!response.ok) {
        throw new Error("Failed to load emails");
      }

      const data = await response.json();

      setEmails(data.emails || []);

    } catch (err: any) {

      console.error(err);

      setError(
        err?.message || "Failed to load emails"
      );

    } finally {

      setLoading(false);

    }
  }


  // ============================================================
  // SEARCH EMAILS
  // ============================================================

  async function handleSearch() {

    if (!search.trim()) {
      loadEmails();
      return;
    }

    try {

      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/search?q=${encodeURIComponent(
          search
        )}&limit=50`
      );

      if (!response.ok) {
        throw new Error("Search failed");
      }

      const data = await response.json();

      setEmails(data.results || []);

    } catch (err: any) {

      console.error(err);

      setError(
        err?.message || "Search failed"
      );

    } finally {

      setLoading(false);

    }
  }


  // ============================================================
  // LOAD TRACE
  // ============================================================

  async function loadTrace(email: Email) {

    try {

      setSelectedEmail(email);

      setTrace(null);

      setChatMessages([]);

      setChatInput("");

      setTraceLoading(true);

      setError("");

      const response = await fetch(
        `${API_URL}/emails/${encodeURIComponent(
          email.message_id
        )}/trace`
      );

      if (!response.ok) {
        throw new Error(
          "Failed to load trace"
        );
      }

      const data: TraceResponse =
        await response.json();

      console.log("TRACE RESPONSE:", data);

      setTrace(data);

    } catch (err: any) {

      console.error(err);

      setError(
        err?.message ||
          "Failed to load trace"
      );

    } finally {

      setTraceLoading(false);

    }
  }



  // ============================================================
  // TRACE CHATBOT
  // ============================================================

  async function sendChatMessage() {
    const question = chatInput.trim();

    if (!question || !selectedEmail || !trace?.found) {
      return;
    }

    const userMessage: ChatMessage = {
      role: "user",
      content: question,
    };

    const previousMessages = [...chatMessages];

    setChatMessages([
      ...previousMessages,
      userMessage,
    ]);

    setChatInput("");
    setChatLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/emails/${encodeURIComponent(
          selectedEmail.message_id
        )}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question,
            history: previousMessages,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail || "Chat request failed"
        );
      }

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer || "No answer returned.",
      };

      setChatMessages([
        ...previousMessages,
        userMessage,
        assistantMessage,
      ]);

    } catch (err: any) {
      console.error(err);

      setChatMessages([
        ...previousMessages,
        userMessage,
        {
          role: "assistant",
          content:
            err?.message ||
            "Sorry, I could not answer that question.",
        },
      ]);

    } finally {
      setChatLoading(false);
    }
  }

  function handleChatKeyDown(
    event: KeyboardEvent<HTMLInputElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !chatLoading
    ) {
      event.preventDefault();
      sendChatMessage();
    }
  }


  // ============================================================
  // INITIAL LOAD
  // ============================================================

  useEffect(() => {
    loadEmails();
  }, []);


  // ============================================================
  // HELPERS
  // ============================================================

  function sentimentClass(
    sentiment?: string | null
  ) {

    const value =
      sentiment?.toLowerCase();

    if (value === "positive") {
      return "badge positive";
    }

    if (value === "negative") {
      return "badge negative";
    }

    return "badge neutral";
  }


  function urgencyClass(
    urgency?: string | null
  ) {

    const value =
      urgency?.toLowerCase();

    if (value === "high") {
      return "badge high";
    }

    if (value === "medium") {
      return "badge medium";
    }

    return "badge low";
  }


  function formatCost(
    cost?: number | null
  ) {

    if (
      cost === null ||
      cost === undefined
    ) {
      return "-";
    }

    return `$${cost.toFixed(6)}`;
  }


  function formatLatency(
    latency?: number | null
  ) {

    if (
      latency === null ||
      latency === undefined
    ) {
      return "-";
    }

    return `${latency.toFixed(3)}s`;
  }


  function formatNumber(
    value?: number | null
  ) {

    if (
      value === null ||
      value === undefined
    ) {
      return "-";
    }

    return value.toLocaleString();
  }


  // ============================================================
  // UI
  // ============================================================

  return (
    <main className="page">

      {/* ======================================================
          HEADER
      ====================================================== */}

      <header className="header">

        <div>

          <h1>
            Email Intelligence
          </h1>

          <p>
            AI-powered email classification and
            Langfuse pipeline monitoring
          </p>

        </div>

        <button
          className="refreshButton"
          onClick={loadEmails}
        >
          ↻ Refresh
        </button>

      </header>


      {/* ======================================================
          ERROR
      ====================================================== */}

      {error && (

        <div className="error">
          {error}
        </div>

      )}


      {/* ======================================================
          SEARCH
      ====================================================== */}

      <section className="searchSection">

        <input
          type="text"
          placeholder="Search by message ID, sentiment, urgency or topic..."
          value={search}
          onChange={(e) =>
            setSearch(e.target.value)
          }
          onKeyDown={(e) => {

            if (e.key === "Enter") {
              handleSearch();
            }

          }}
        />

        <button
          onClick={handleSearch}
        >
          Search
        </button>


        {search && (

          <button
            className="clearButton"
            onClick={() => {

              setSearch("");

              loadEmails();

            }}
          >
            Clear
          </button>

        )}

      </section>


      {/* ======================================================
          EMAIL LIST
      ====================================================== */}

      <section className="card">

        <div className="cardHeader">

          <div>

            <h2>
              Processed Emails
            </h2>

            <p>
              Click an email to inspect its
              pipeline trace.
            </p>

          </div>

          <span className="count">
            {emails.length} emails
          </span>

        </div>


        {/* ====================================================
            LOADING
        ==================================================== */}

        {loading ? (

          <div className="loading">
            Loading emails...
          </div>


        ) : emails.length === 0 ? (

          <div className="empty">
            No emails found.
          </div>


        ) : (

          <div className="tableWrapper">

            <table>

              <thead>

                <tr>

                  <th>
                    Message ID
                  </th>

                  <th>
                    Sentiment
                  </th>

                  <th>
                    Urgency
                  </th>

                  <th>
                    Topic
                  </th>

                  <th>
                    Subtopics
                  </th>

                  <th>
                    Processed
                  </th>

                </tr>

              </thead>


              <tbody>

                {emails.map(
                  (email) => (

                    <tr
                      key={
                        email.message_id
                      }
                      onClick={() =>
                        loadTrace(email)
                      }
                      className="clickable"
                    >

                      {/* Message ID */}

                      <td>

                        <code>
                          {
                            email.message_id
                          }
                        </code>

                      </td>


                      {/* Sentiment */}

                      <td>

                        <span
                          className={sentimentClass(
                            email.sentiment
                          )}
                        >
                          {
                            email.sentiment ||
                            "-"
                          }
                        </span>

                      </td>


                      {/* Urgency */}

                      <td>

                        <span
                          className={urgencyClass(
                            email.urgency
                          )}
                        >
                          {
                            email.urgency ||
                            "-"
                          }
                        </span>

                      </td>


                      {/* Topic */}

                      <td>

                        {
                          email.dominant_topic ||
                          "-"
                        }

                      </td>


                      {/* Subtopics */}

                      <td>

                        <div className="subtopics">

                          {email.subtopics?.map(
                            (subtopic) => (

                              <span
                                key={subtopic}
                                className="subtopic"
                              >
                                {subtopic}
                              </span>

                            )
                          )}

                        </div>

                      </td>


                      {/* Processed */}

                      <td>

                        {
                          email.processed_at
                            ? new Date(
                                email.processed_at
                              ).toLocaleString()
                            : "-"
                        }

                      </td>

                    </tr>

                  )
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>


      {/* ======================================================
          TRACE PANEL
      ====================================================== */}

      {selectedEmail && (

        <section className="traceSection">

          {/* ==================================================
              TRACE HEADER
          ================================================== */}

          <div className="cardHeader">

            <div>

              <h2>
                Pipeline Trace
              </h2>

              <p>

                Message ID:{" "}

                <code>
                  {
                    selectedEmail.message_id
                  }
                </code>

              </p>


              {trace?.trace_id && (

                <p>

                  Trace ID:{" "}

                  <code>
                    {trace.trace_id}
                  </code>

                </p>

              )}

            </div>


            <button
              className="closeButton"
              onClick={() => {

                setSelectedEmail(null);

                setTrace(null);

              }}
            >
              ✕ Close
            </button>

          </div>


          {/* ==================================================
              TRACE LOADING
          ================================================== */}

          {traceLoading ? (

            <div className="loading">

              Loading Langfuse trace...

            </div>


          ) : !trace ? (

            <div className="empty">

              Trace unavailable.

            </div>


          ) : (

            <>

              {/* =================================================
                  FINAL RESULT
              ================================================= */}

              {trace.result ? (

                <div className="resultCard">

                  <h3>
                    Final Result
                  </h3>


                  <div className="resultGrid">


                    {/* Sentiment */}

                    <div>

                      <label>
                        Sentiment
                      </label>

                      <span
                        className={sentimentClass(
                          trace.result
                            ?.sentiment
                        )}
                      >
                        {
                          trace.result
                            ?.sentiment ||
                          "-"
                        }
                      </span>

                    </div>


                    {/* Urgency */}

                    <div>

                      <label>
                        Urgency
                      </label>

                      <span
                        className={urgencyClass(
                          trace.result
                            ?.urgency
                        )}
                      >
                        {
                          trace.result
                            ?.urgency ||
                          "-"
                        }
                      </span>

                    </div>


                    {/* Topic */}

                    <div>

                      <label>
                        Topic
                      </label>

                      <strong>

                        {
                          trace.result
                            ?.dominant_topic ||
                          "-"
                        }

                      </strong>

                    </div>


                    {/* Validation */}

                    <div>

                      <label>
                        Validation
                      </label>

                      <span className="badge valid">

                        {
                          trace.result
                            ?.validation ||
                          "-"
                        }

                      </span>

                    </div>


                    {/* Retries */}

                    <div>

                      <label>
                        Retries
                      </label>

                      <strong>

                        {
                          trace.result
                            ?.retries ??
                          0
                        }

                      </strong>

                    </div>

                  </div>


                  {/* Subtopics */}

                  <div className="subtopicResult">

                    <label>
                      Subtopics
                    </label>


                    <div className="subtopics">

                      {trace.result
                        ?.subtopics
                        ?.length ? (

                        trace.result.subtopics.map(
                          (subtopic) => (

                            <span
                              key={subtopic}
                              className="subtopic"
                            >
                              {subtopic}
                            </span>

                          )
                        )

                      ) : (

                        <span>
                          -
                        </span>

                      )}

                    </div>

                  </div>

                </div>

              ) : (

                /* =================================================
                   NO RESULT
                ================================================= */

                <div className="resultCard">

                  <h3>
                    Final Result
                  </h3>

                  <div className="empty">

                    Final result is not available
                    for this trace.

                  </div>

                </div>

              )}


              {/* =================================================
                  TRACE SUMMARY
              ================================================= */}

              {trace.summary && (

                <div className="summaryGrid">


                  <SummaryCard
                    title="Steps"
                    value={
                      trace.summary.steps ??
                      0
                    }
                  />


                  <SummaryCard
                    title="LLM Calls"
                    value={
                      trace.summary.generations ??
                      0
                    }
                  />


                  <SummaryCard
                    title="Latency"
                    value={
                      trace.summary
                        .total_latency !==
                        undefined
                        ? `${trace.summary.total_latency.toFixed(
                            3
                          )}s`
                        : "-"
                    }
                  />


                  <SummaryCard
                    title="Input Tokens"
                    value={formatNumber(
                      trace.summary
                        .total_input_tokens
                    )}
                  />


                  <SummaryCard
                    title="Output Tokens"
                    value={formatNumber(
                      trace.summary
                        .total_output_tokens
                    )}
                  />


                  <SummaryCard
                    title="Total Tokens"
                    value={formatNumber(
                      trace.summary
                        .total_tokens
                    )}
                  />


                  <SummaryCard
                    title="Cost"
                    value={formatCost(
                      trace.summary
                        .total_cost
                    )}
                  />

                </div>

              )}


              {/* =================================================
                  PIPELINE STEPS
              ================================================= */}

              <div className="stepsCard">

                <h3>
                  Pipeline Steps
                </h3>


                {trace.steps?.length ? (

                  <div className="steps">

                    {trace.steps.map(
                      (step, index) => (

                        <div
                          className="step"
                          key={`${step.name}-${index}`}
                        >

                          {/* ======================================
                              STEP HEADER
                          ====================================== */}

                          <div className="stepHeader">

                            <div>

                              <span className="stepNumber">
                                {index + 1}
                              </span>


                              <strong>
                                {step.name}
                              </strong>


                              <span className="stepType">
                                {step.type}
                              </span>

                            </div>


                            <div className="stepRight">

                              <span>
                                {formatLatency(
                                  step.latency
                                )}
                              </span>


                              <span
                                className={
                                  step.status ===
                                  "ERROR"
                                    ? "status errorStatus"
                                    : "status"
                                }
                              >
                                {
                                  step.status ||
                                  "DEFAULT"
                                }
                              </span>

                            </div>

                          </div>


                          {/* ======================================
                              GENERATION INFO
                          ====================================== */}

                          {step.type ===
                            "GENERATION" && (

                            <div className="generationInfo">


                              {/* Prompt */}

                              {step.prompt_name && (

                                <div>

                                  <label>
                                    Prompt
                                  </label>

                                  <span>

                                    {
                                      step.prompt_name
                                    }

                                    {step.prompt_version
                                      ? ` v${step.prompt_version}`
                                      : ""}

                                  </span>

                                </div>

                              )}


                              {/* Input Tokens */}

                              <div>

                                <label>
                                  Input Tokens
                                </label>

                                <span>
                                  {
                                    step.input_tokens ??
                                    "-"
                                  }
                                </span>

                              </div>


                              {/* Output Tokens */}

                              <div>

                                <label>
                                  Output Tokens
                                </label>

                                <span>
                                  {
                                    step.output_tokens ??
                                    "-"
                                  }
                                </span>

                              </div>


                              {/* Total Tokens */}

                              <div>

                                <label>
                                  Total Tokens
                                </label>

                                <span>
                                  {
                                    step.total_tokens ??
                                    "-"
                                  }
                                </span>

                              </div>


                              {/* Cost */}

                              <div>

                                <label>
                                  Cost
                                </label>

                                <span>
                                  {formatCost(
                                    step.cost
                                  )}
                                </span>

                              </div>

                            </div>

                          )}


                          {/* ======================================
                              OUTPUT
                          ====================================== */}

                          {step.output !==
                            undefined &&
                            step.output !==
                              null && (

                            <div className="stepOutput">

                              <label>
                                Output
                              </label>


                              <pre>

                                {
                                  typeof step.output ===
                                  "string"

                                    ? step.output

                                    : JSON.stringify(
                                        step.output,
                                        null,
                                        2
                                      )
                                }

                              </pre>

                            </div>

                          )}


                          {/* ======================================
                              ERROR
                          ====================================== */}

                          {step.error && (

                            <div className="stepError">

                              <strong>
                                Error
                              </strong>

                              <span>
                                {step.error}
                              </span>

                            </div>

                          )}

                        </div>

                      )
                    )}

                  </div>

                ) : (

                  <div className="empty">

                    No pipeline steps available
                    for this trace.

                  </div>

                )}

              </div>

              {/* =================================================
                  TRACE CHATBOT
              ================================================= */}

              {trace.found && (
                <div className="chatCard">

                  <div className="chatHeader">
                    <div>
                      <h3>Trace Assistant</h3>
                      <p>
                        Ask questions about this email's
                        Langfuse trace.
                      </p>
                    </div>
                  </div>

                  <div className="chatMessages">

                    {chatMessages.length === 0 ? (
                      <div className="chatEmpty">
                        <strong>Trace Assistant</strong>
                        <span>
                          Try asking:
                        </span>

                        <div className="chatSuggestions">
                          <button
                            type="button"
                            onClick={() =>
                              setChatInput(
                                "Explain this trace."
                              )
                            }
                          >
                            Explain this trace
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              setChatInput(
                                "Why did this email take so long?"
                              )
                            }
                          >
                            Why did this take so long?
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              setChatInput(
                                "Did this email require a retry?"
                              )
                            }
                          >
                            Did it require a retry?
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              setChatInput(
                                "Which LLM call used the most tokens?"
                              )
                            }
                          >
                            Which LLM used most tokens?
                          </button>
                        </div>
                      </div>
                    ) : (
                      chatMessages.map(
                        (message, index) => (
                          <div
                            key={`${message.role}-${index}`}
                            className={
                              message.role === "user"
                                ? "chatMessage userMessage"
                                : "chatMessage assistantMessage"
                            }
                          >
                            <div className="chatRole">
                              {message.role === "user"
                                ? "You"
                                : "Trace Assistant"}
                            </div>

                            <div className="chatBubble">
                              {message.content}
                            </div>
                          </div>
                        )
                      )
                    )}

                    {chatLoading && (
                      <div className="chatMessage assistantMessage">
                        <div className="chatRole">
                          Trace Assistant
                        </div>

                        <div className="chatBubble chatTyping">
                          Thinking...
                        </div>
                      </div>
                    )}

                  </div>

                  <div className="chatInputRow">

                    <input
                      type="text"
                      value={chatInput}
                      placeholder="Ask about this trace..."
                      onChange={(event) =>
                        setChatInput(
                          event.target.value
                        )
                      }
                      onKeyDown={handleChatKeyDown}
                      disabled={chatLoading}
                    />

                    <button
                      type="button"
                      onClick={sendChatMessage}
                      disabled={
                        chatLoading ||
                        !chatInput.trim()
                      }
                    >
                      {chatLoading
                        ? "..."
                        : "Send"}
                    </button>

                  </div>

                </div>
              )}

            </>

          )}

        </section>

      )}

    </main>
  );
}


// ============================================================
// SUMMARY CARD
// ============================================================

function SummaryCard({
  title,
  value,
}: {
  title: string;
  value: string | number;
}) {

  return (

    <div className="summaryCard">

      <span>
        {title}
      </span>

      <strong>
        {value}
      </strong>

    </div>

  );
}