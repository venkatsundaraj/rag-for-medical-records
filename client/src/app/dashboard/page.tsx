"use client";

/**
 * Eval dashboard: compares saved eval runs (eval_runs/*.json) side by side.
 *
 * Reads /api/eval/runs (proxied to FastAPI via a next.config rewrite).
 * No chart library: eight metrics x a handful of configs is a job for
 * plain divs, and one less dependency is one less thing to break.
 */

import { useEffect, useMemo, useState } from "react";

type RunConfig = {
  strategy: string;
  search: string;
  k: number;
  mode: string;
  timestamp: string;
  n_questions?: number;
};

type Run = {
  file: string;
  config: RunConfig;
  aggregates: Record<string, number>;
};

/** Display order + direction. lowerBetter flips the "best" highlight. */
const METRICS: { key: string; label: string; lowerBetter?: boolean }[] = [
  { key: "precision_at_k", label: "Precision@k" },
  { key: "recall_at_k", label: "Recall@k" },
  { key: "mrr", label: "MRR" },
  { key: "faithfulness", label: "Faithfulness" },
  { key: "relevance", label: "Relevance" },
  { key: "citation_precision", label: "Citation precision" },
  {
    key: "hallucinated_citation_rate",
    label: "Hallucinated citations",
    lowerBetter: true,
  },
  { key: "correct_refusal_rate", label: "Correct refusals" },
];

const PALETTE = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#a855f7",
];

const configKey = (c: RunConfig) => `${c.strategy} · ${c.search} · k=${c.k}`;

export default function EvalDashboard() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/eval/runs`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then((data: { runs: Run[] }) => {
        console.log(data.runs);
        setRuns(data.runs);
        // Default selection: the LATEST full run per config. Older runs of
        // the same config stay listed but unchecked -- history, not noise.
        const latestPerConfig = new Map<string, string>();
        for (const run of data.runs) {
          // runs arrive newest-first; first hit per config wins
          const key = configKey(run.config);
          if (run.config.mode === "full" && !latestPerConfig.has(key)) {
            latestPerConfig.set(key, run.file);
          }
        }
        setSelected(new Set(latestPerConfig.values()));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const chosen = useMemo(
    () => runs.filter((r) => selected.has(r.file)),
    [runs, selected],
  );

  const toggle = (file: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  };

  if (error)
    return (
      <main style={{ padding: 32, fontFamily: "ui-sans-serif, system-ui" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Eval dashboard</h1>
        <p style={{ color: "#ef4444", marginTop: 12 }}>
          Could not load runs: {error}. Is the FastAPI server running on :8000,
          and the /api/eval rewrite in next.config?
        </p>
      </main>
    );

  return (
    <main
      style={{
        backgroundColor: "white",
        maxWidth: 960,
        margin: "0 auto",
        padding: "40px 24px",
        fontFamily: "ui-sans-serif, system-ui",
        color: "#111827",
      }}
    >
      <h1 style={{ fontSize: 24, fontWeight: 800 }}>RAG eval dashboard</h1>
      <p style={{ color: "#6b7280", marginTop: 4, fontSize: 14 }}>
        {runs.length} saved runs in <code>eval_runs/</code> · comparing{" "}
        {chosen.length} config{chosen.length === 1 ? "" : "s"} · 58-question
        frozen benchmark
      </p>

      {/* ---- run picker ---- */}
      <section style={{ marginTop: 24 }}>
        <h2
          style={{
            fontSize: 13,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "#6b7280",
          }}
        >
          Runs
        </h2>
        <div
          style={{
            marginTop: 8,
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {runs.map((run) => (
            <label
              key={run.file}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 13,
                padding: "6px 10px",
                borderRadius: 8,
                background: selected.has(run.file) ? "#eef2ff" : "transparent",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={selected.has(run.file)}
                onChange={() => toggle(run.file)}
              />
              <span style={{ fontWeight: 600 }}>{configKey(run.config)}</span>
              <span style={{ color: "#9ca3af" }}>
                {run.config.mode} ·{" "}
                {run.config.timestamp?.slice(0, 16).replace("T", " ")}
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* ---- summary table ---- */}
      {chosen.length > 0 && (
        <section style={{ marginTop: 32, overflowX: "auto" }}>
          <h2
            style={{
              fontSize: 13,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: 1,
              color: "#6b7280",
            }}
          >
            Summary
          </h2>
          <table
            style={{
              marginTop: 8,
              borderCollapse: "collapse",
              width: "100%",
              fontSize: 13,
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: "left",
                    padding: "6px 10px",
                    borderBottom: "2px solid #e5e7eb",
                  }}
                >
                  Config
                </th>
                {METRICS.map((m) => (
                  <th
                    key={m.key}
                    style={{
                      textAlign: "right",
                      padding: "6px 10px",
                      borderBottom: "2px solid #e5e7eb",
                    }}
                  >
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {chosen.map((run, i) => (
                <tr key={run.file}>
                  <td
                    style={{
                      padding: "6px 10px",
                      borderBottom: "1px solid #f3f4f6",
                      fontWeight: 600,
                    }}
                  >
                    <span
                      style={{
                        display: "inline-block",
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        background: PALETTE[i % PALETTE.length],
                        marginRight: 8,
                      }}
                    />
                    {configKey(run.config)}
                  </td>
                  {METRICS.map((m) => {
                    const v = run.aggregates[m.key];
                    const values = chosen
                      .map((r) => r.aggregates[m.key])
                      .filter((x) => typeof x === "number");
                    const best =
                      values.length > 1 &&
                      typeof v === "number" &&
                      v ===
                        (m.lowerBetter
                          ? Math.min(...values)
                          : Math.max(...values));
                    return (
                      <td
                        key={m.key}
                        style={{
                          textAlign: "right",
                          padding: "6px 10px",
                          borderBottom: "1px solid #f3f4f6",
                          fontVariantNumeric: "tabular-nums",
                          fontWeight: best ? 700 : 400,
                          color: best ? "#047857" : "#111827",
                        }}
                      >
                        {typeof v === "number" ? v.toFixed(3) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ---- per-metric bars ---- */}
      {chosen.length > 0 && (
        <section
          style={{
            marginTop: 32,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))",
            gap: 24,
          }}
        >
          {METRICS.map((m) => {
            const rows = chosen
              .map((run, i) => ({ run, i, value: run.aggregates[m.key] }))
              .filter((r) => typeof r.value === "number");
            if (rows.length === 0) return null;
            return (
              <div
                key={m.key}
                style={{
                  border: "1px solid #e5e7eb",
                  borderRadius: 12,
                  padding: 16,
                }}
              >
                <h3 style={{ fontSize: 13, fontWeight: 700 }}>
                  {m.label}
                  {m.lowerBetter && (
                    <span style={{ color: "#9ca3af", fontWeight: 400 }}>
                      {" "}
                      (lower is better)
                    </span>
                  )}
                </h3>
                <div
                  style={{
                    marginTop: 10,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  {rows.map(({ run, i, value }) => (
                    <div key={run.file}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 11,
                          color: "#6b7280",
                        }}
                      >
                        <span>
                          {run.config.search} · {run.config.strategy}
                        </span>
                        <span
                          style={{
                            fontVariantNumeric: "tabular-nums",
                            fontWeight: 600,
                            color: "#111827",
                          }}
                        >
                          {value.toFixed(4)}
                        </span>
                      </div>
                      <div
                        style={{
                          height: 8,
                          background: "#f3f4f6",
                          borderRadius: 4,
                          marginTop: 3,
                        }}
                      >
                        <div
                          style={{
                            height: 8,
                            width: `${Math.min(100, value * 100)}%`,
                            background: PALETTE[i % PALETTE.length],
                            borderRadius: 4,
                            transition: "width 300ms",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </main>
  );
}
