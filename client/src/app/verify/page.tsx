"use client";

/**
 * /verify — claim-level verification view.
 *
 * Reads /api/verify/runs (list) and /api/verify/runs/{name} (one run),
 * proxied to FastAPI via next.config rewrites. Pick a run, pick an answer,
 * see every claim with its label, the judge's rationale and the passage it
 * cited. This is the view that makes "0 false-supported" inspectable.
 */

import { useEffect, useMemo, useState } from "react";

type RunSummary = {
  name: string;
  kind: string;
  config: Record<string, unknown>;
  aggregates: Record<string, number | Record<string, number>>;
};

type Claim = {
  text: string;
  label: "supported" | "contradicted" | "no_evidence";
  rationale: string;
  evidence: {
    chunk_id: number;
    source: string;
    title: string;
    excerpt: string;
  } | null;
  candidate_ids: number[];
};

type AnswerRow = {
  qid: string;
  question: string;
  answer: string;
  status: "verified" | "unverified" | "contradicted" | "no_claims";
  grounded_rate: number;
  counts: Record<string, number>;
  claims: Claim[];
  skipped: string[];
  timing_ms: Record<string, number>;
  p1?: { faithfulness?: number };
};

type VerifyRun = {
  config: Record<string, unknown>;
  aggregates: Record<string, number>;
  rows: AnswerRow[];
};

const STATUS_COLOR: Record<AnswerRow["status"], string> = {
  verified: "#16a34a",
  unverified: "#ca8a04",
  contradicted: "#dc2626",
  no_claims: "#6b7280",
};
const LABEL_COLOR: Record<Claim["label"], string> = {
  supported: "#16a34a",
  contradicted: "#dc2626",
  no_evidence: "#ca8a04",
};

export default function VerifyDashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runName, setRunName] = useState<string | null>(null);
  const [run, setRun] = useState<VerifyRun | null>(null);
  const [qid, setQid] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "flagged">("flagged");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/verify/runs`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then((all: RunSummary[]) => {
        const verifyRuns = all.filter((r) => r.name.includes("_verify_"));
        setRuns(verifyRuns);
        if (verifyRuns.length && !runName) setRunName(verifyRuns[0].name);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!runName) return;
    setRun(null);
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/verify/runs/${runName}`)
      .then((r) => r.json())
      .then((data: VerifyRun) => {
        setRun(data);
        const first =
          data.rows.find((r) => r.status === "contradicted") ?? data.rows[0];
        setQid(first?.qid ?? null);
      })
      .catch((e) => setError(String(e)));
  }, [runName]);

  const rows = useMemo(() => {
    if (!run) return [];
    return filter === "flagged"
      ? run.rows.filter(
          (r) => r.status === "contradicted" || r.status === "unverified",
        )
      : run.rows;
  }, [run, filter]);

  const current = run?.rows.find((r) => r.qid === qid) ?? null;

  if (error) {
    return (
      <main style={{ padding: 24, fontFamily: "system-ui" }}>
        Could not load runs: {error}. Is the FastAPI server running, and the
        /api/verify rewrite in next.config?
      </main>
    );
  }

  return (
    <main
      className="text-black min-w-screen min-h-screen"
      style={{
        padding: 24,
        fontFamily: "system-ui",
        maxWidth: 1200,
        margin: "0 auto",
        backgroundColor: "white",
      }}
    >
      <h1 style={{ fontSize: 22, marginBottom: 12 }}>
        Verification — claim level
      </h1>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <select
          value={runName ?? ""}
          onChange={(e) => setRunName(e.target.value)}
        >
          {runs.map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <label>
          <input
            type="radio"
            checked={filter === "flagged"}
            onChange={() => setFilter("flagged")}
          />{" "}
          flagged only
        </label>
        <label>
          <input
            type="radio"
            checked={filter === "all"}
            onChange={() => setFilter("all")}
          />{" "}
          all answers
        </label>
      </div>

      {run && (
        <div
          style={{
            display: "flex",
            gap: 16,
            flexWrap: "wrap",
            marginBottom: 16,
            fontSize: 14,
          }}
        >
          {(
            ["verified", "unverified", "contradicted", "no_claims"] as const
          ).map((s) => (
            <span key={s} style={{ color: STATUS_COLOR[s] }}>
              {s}: <b>{run.aggregates[`status_${s}`]}</b>
            </span>
          ))}
          <span>
            grounded rate:{" "}
            <b>{(run.aggregates.mean_grounded_rate as number).toFixed(3)}</b>
          </span>
          <span>
            median:{" "}
            <b>
              {((run.aggregates.latency_ms_median as number) / 1000).toFixed(1)}{" "}
              s
            </b>
            /answer
          </span>
          <span>
            judge calls: <b>{run.aggregates.judge_calls}</b>
          </span>
          <span>
            extractor: <b>{String(run.config.extraction_model ?? "—")}</b>
          </span>
        </div>
      )}

      <div
        style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20 }}
      >
        {/* answer list */}
        <div
          style={{
            borderRight: "1px solid #e5e7eb",
            paddingRight: 12,
            maxHeight: "75vh",
            overflowY: "auto",
          }}
        >
          {rows.map((r) => (
            <div
              key={r.qid}
              onClick={() => setQid(r.qid)}
              style={{
                padding: "8px 10px",
                cursor: "pointer",
                borderRadius: 6,
                background: r.qid === qid ? "#f3f4f6" : "transparent",
                borderLeft: `4px solid ${STATUS_COLOR[r.status]}`,
                marginBottom: 4,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {r.qid}{" "}
                <span style={{ color: STATUS_COLOR[r.status] }}>
                  {r.status}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "#4b5563" }}>
                S{r.counts.supported}/C{r.counts.contradicted}/N
                {r.counts.no_evidence}
                {r.p1?.faithfulness !== undefined && (
                  <> · P1 {r.p1.faithfulness}</>
                )}
              </div>
            </div>
          ))}
          {rows.length === 0 && (
            <div style={{ fontSize: 13, color: "#6b7280" }}>
              no flagged answers
            </div>
          )}
        </div>

        {/* claim detail */}
        {current && (
          <div>
            <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 4 }}>
              {current.qid}
            </div>
            <h2 style={{ fontSize: 17, margin: "0 0 8px" }}>
              {current.question}
            </h2>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                fontSize: 13,
                background: "#f9fafb",
                padding: 12,
                borderRadius: 6,
              }}
            >
              {current.answer}
            </pre>
            <div style={{ fontSize: 13, margin: "12px 0" }}>
              status{" "}
              <b style={{ color: STATUS_COLOR[current.status] }}>
                {current.status}
              </b>{" "}
              · grounded {current.grounded_rate.toFixed(2)} ·{" "}
              {(current.timing_ms.total / 1000).toFixed(1)} s (extract{" "}
              {(current.timing_ms.extract / 1000).toFixed(1)}, retrieve{" "}
              {(current.timing_ms.retrieve / 1000).toFixed(1)}, judge{" "}
              {(current.timing_ms.judge / 1000).toFixed(1)})
            </div>

            {current.claims.map((c, i) => (
              <details
                key={i}
                open={c.label !== "supported"}
                style={{
                  marginBottom: 8,
                  borderLeft: `4px solid ${LABEL_COLOR[c.label]}`,
                  paddingLeft: 10,
                }}
              >
                <summary style={{ cursor: "pointer", fontSize: 14 }}>
                  <span
                    style={{ color: LABEL_COLOR[c.label], fontWeight: 600 }}
                  >
                    {c.label}
                  </span>{" "}
                  — {c.text}
                </summary>
                <div
                  style={{ fontSize: 13, color: "#374151", margin: "6px 0" }}
                >
                  {c.rationale}
                </div>
                {c.evidence && (
                  <div
                    style={{
                      fontSize: 12,
                      background: "#f9fafb",
                      padding: 8,
                      borderRadius: 4,
                    }}
                  >
                    <b>{c.evidence.source}</b> — {c.evidence.title} (chunk{" "}
                    {c.evidence.chunk_id})
                    <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>
                      {c.evidence.excerpt}
                    </div>
                  </div>
                )}
                <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>
                  candidates: {c.candidate_ids.join(", ")}
                </div>
              </details>
            ))}
            {current.skipped.length > 0 && (
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 8 }}>
                not judged (verifiable=false): {current.skipped.join(" · ")}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
