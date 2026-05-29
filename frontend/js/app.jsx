const { useState, useEffect, useRef, useCallback } = React;

if (typeof Chart !== "undefined" && typeof zoomPlugin !== "undefined") {
  try {
    Chart.register(zoomPlugin);
  } catch (_) {
    /* already registered */
  }
}

const API = "";
const AGENTS = [
  { id: "query_agent", name: "Data Query Agent", icon: "📊" },
  { id: "query_executor", name: "Query Executor", icon: "⚡" },
  { id: "anomaly_detector", name: "Anomaly Detector", icon: "🔍" },
  { id: "root_cause_agent", name: "Root Cause Agent", icon: "🧠" },
  { id: "reporter_agent", name: "Reporter Agent", icon: "📝" },
  { id: "qa_agent", name: "QA Reviewer", icon: "✓" },
];

async function api(path, options = {}, token) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      onLogin(data.token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1>Data Anomaly Agent</h1>
        <p>Multi-agent anomaly detection for store sales time series</p>
        {error && <div className="error-banner">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

function SettingsModal({ token, config, onClose, onSave }) {
  const [form, setForm] = useState({ ...config });
  const [rangeInfo, setRangeInfo] = useState(null);
  const [rangeError, setRangeError] = useState("");
  const [rangeLoading, setRangeLoading] = useState(false);
  const [applyNotice, setApplyNotice] = useState("");

  const save = async () => {
    await api("/api/config", { method: "PUT", body: JSON.stringify(form) }, token);
    onSave(form);
    onClose();
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const fetchDateRange = async () => {
    setRangeLoading(true);
    setRangeError("");
    setApplyNotice("");
    try {
      const data = await api("/api/data/date-range", {}, token);
      if (!data.available) {
        setRangeInfo(null);
        setRangeError(data.message || "No date range available. Load CSV files in data/.");
        return data;
      }
      setRangeInfo(data);
      return data;
    } catch (err) {
      setRangeError(err.message);
      return null;
    } finally {
      setRangeLoading(false);
    }
  };

  const showDateRange = () => fetchDateRange();

  const applyDateRange = async () => {
    const data = rangeInfo?.available ? rangeInfo : await fetchDateRange();
    if (!data?.available) return;
    const updated = {
      ...form,
      custom_start: data.min_date,
      custom_end: data.max_date,
    };
    setForm(updated);
    try {
      await api(
        "/api/config",
        {
          method: "PUT",
          body: JSON.stringify({
            custom_start: data.min_date,
            custom_end: data.max_date,
          }),
        },
        token
      );
      onSave(updated);
      setApplyNotice(
        `Saved custom range: ${data.min_date} → ${data.max_date}. You can run Investigate now.`
      );
    } catch (err) {
      setRangeError(err.message);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Settings</h2>
        <div className="form-group">
          <label>LLM Provider</label>
          <select value={form.llm_provider} onChange={(e) => set("llm_provider", e.target.value)}>
            <option value="openai">OpenAI</option>
            <option value="deepseek">DeepSeek</option>
          </select>
        </div>
        <div className="form-group">
          <label>Analysis window (days)</label>
          <input type="number" min={7} max={365} value={form.window_days} onChange={(e) => set("window_days", +e.target.value)} />
        </div>
        <div className="form-group">
          <label>Grace period (days)</label>
          <input type="number" min={0} max={14} value={form.grace_days} onChange={(e) => set("grace_days", +e.target.value)} />
        </div>
        <div className="form-group date-range-section">
          <label>Custom analysis dates</label>
          <p className="field-hint">Use a range that overlaps your loaded sales data (see available range below).</p>
          <div className="date-range-actions">
            <button
              className="btn btn-ghost"
              type="button"
              disabled={rangeLoading}
              onClick={showDateRange}
            >
              {rangeLoading ? "Loading…" : "Show available date range"}
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              disabled={rangeLoading}
              onClick={applyDateRange}
            >
              Apply range to custom dates
            </button>
          </div>
          {rangeInfo?.available && (
            <div className="date-range-banner">
              <strong>Loaded data:</strong> {rangeInfo.min_date} → {rangeInfo.max_date}
              <span className="date-range-meta">
                ({rangeInfo.rows.toLocaleString()} rows
                {rangeInfo.store_count != null ? `, ${rangeInfo.store_count} stores` : ""})
              </span>
            </div>
          )}
          {rangeError && <div className="error-banner" style={{ marginTop: 10 }}>{rangeError}</div>}
          {applyNotice && <div className="apply-notice">{applyNotice}</div>}
        </div>
        <div className="form-group">
          <label>Custom start (optional, YYYY-MM-DD)</label>
          <input value={form.custom_start || ""} onChange={(e) => set("custom_start", e.target.value || null)} placeholder="Leave empty for default" />
        </div>
        <div className="form-group">
          <label>Custom end (optional)</label>
          <input value={form.custom_end || ""} onChange={(e) => set("custom_end", e.target.value || null)} />
        </div>
        <div className="form-group">
          <label>Holiday exclusion logic</label>
          <select value={form.holiday_logic} onChange={(e) => set("holiday_logic", e.target.value)}>
            <option value="ecuador">Ecuador (holidays_events.csv)</option>
            <option value="us_federal">US Federal</option>
            <option value="none">None</option>
          </select>
        </div>
        <div className="form-group">
          <label>Months of train data to load</label>
          <input type="number" min={6} max={60} value={form.train_months_back} onChange={(e) => set("train_months_back", +e.target.value)} />
        </div>
        <div className="modal-actions">
          <button className="btn btn-ghost" type="button" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" type="button" onClick={save} style={{ width: "auto" }}>Save</button>
        </div>
      </div>
    </div>
  );
}

function DetectionSettingsModal({ token, config, onClose, onSave }) {
  const defaults = config.detection_defaults || {};
  const [form, setForm] = useState({ ...(config.detection || defaults) });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const setDet = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        ...form,
        rolling_window_fixed: form.rolling_window_fixed === "" || form.rolling_window_fixed == null
          ? null
          : parseInt(form.rolling_window_fixed, 10),
      };
      const updated = await api(
        "/api/config",
        { method: "PUT", body: JSON.stringify({ detection: payload }) },
        token
      );
      onSave(updated);
      setNotice("Detection settings saved.");
    } catch (err) {
      setNotice(err.message);
    } finally {
      setSaving(false);
    }
  };

  const resetDefaults = async () => {
    setSaving(true);
    try {
      const updated = await api("/api/detection/reset", { method: "POST" }, token);
      setForm({ ...updated.detection });
      onSave(updated);
      setNotice("Restored factory detection defaults.");
    } catch (err) {
      setNotice(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h2>Anomaly detection parameters</h2>
        <p className="field-hint" style={{ marginBottom: 16 }}>
          Changes apply to the next investigation. Use Reset to restore original defaults.
        </p>
        <div className="detection-grid">
          <div className="form-group">
            <label>Z-score threshold</label>
            <input type="number" step="0.1" min={0.5} max={10} value={form.z_threshold}
              onChange={(e) => setDet("z_threshold", parseFloat(e.target.value))} />
            <p className="param-hint">Default: {defaults.z_threshold}</p>
          </div>
          <div className="form-group">
            <label>IQR factor</label>
            <input type="number" step="0.1" min={0.5} max={5} value={form.iqr_factor}
              onChange={(e) => setDet("iqr_factor", parseFloat(e.target.value))} />
            <p className="param-hint">Default: {defaults.iqr_factor}</p>
          </div>
          <div className="form-group">
            <label>MAD scale factor</label>
            <input type="number" step="0.0001" min={0.1} max={2} value={form.mad_scale_factor}
              onChange={(e) => setDet("mad_scale_factor", parseFloat(e.target.value))} />
            <p className="param-hint">Default: {defaults.mad_scale_factor}</p>
          </div>
          <div className="form-group">
            <label>Vote minimum (of 3 methods)</label>
            <input type="number" min={1} max={3} value={form.vote_min}
              onChange={(e) => setDet("vote_min", parseInt(e.target.value, 10))} />
            <p className="param-hint">Default: {defaults.vote_min}</p>
          </div>
          <div className="form-group">
            <label>Rolling window cap</label>
            <input type="number" min={3} max={60} value={form.rolling_window_cap}
              onChange={(e) => setDet("rolling_window_cap", parseInt(e.target.value, 10))} />
            <p className="param-hint">Default: {defaults.rolling_window_cap}</p>
          </div>
          <div className="form-group">
            <label>Rolling window floor</label>
            <input type="number" min={2} max={30} value={form.rolling_window_floor}
              onChange={(e) => setDet("rolling_window_floor", parseInt(e.target.value, 10))} />
            <p className="param-hint">Default: {defaults.rolling_window_floor}</p>
          </div>
          <div className="form-group">
            <label>Rolling window divisor (n÷)</label>
            <input type="number" min={1} max={20} value={form.rolling_window_divisor}
              onChange={(e) => setDet("rolling_window_divisor", parseInt(e.target.value, 10))} />
            <p className="param-hint">Auto: min(cap, max(floor, n÷{form.rolling_window_divisor}))</p>
          </div>
          <div className="form-group">
            <label>Rolling window fixed (optional)</label>
            <input type="number" min={0} placeholder="Auto"
              value={form.rolling_window_fixed ?? ""}
              onChange={(e) => setDet("rolling_window_fixed", e.target.value === "" ? null : parseInt(e.target.value, 10))} />
            <p className="param-hint">Leave empty for dynamic window</p>
          </div>
          <div className="form-group">
            <label>Rolling std factor (detection)</label>
            <input type="number" step="0.1" min={0.5} max={5} value={form.rolling_detection_std_factor}
              onChange={(e) => setDet("rolling_detection_std_factor", parseFloat(e.target.value))} />
            <p className="param-hint">Default: {defaults.rolling_detection_std_factor} — flags rolling outliers</p>
          </div>
        </div>
        {notice && <div className="apply-notice" style={{ marginTop: 14 }}>{notice}</div>}
        <div className="modal-actions">
          <button className="btn btn-ghost" type="button" onClick={resetDefaults} disabled={saving}>
            Reset to defaults
          </button>
          <button className="btn btn-ghost" type="button" onClick={onClose}>Close</button>
          <button className="btn btn-primary" type="button" style={{ width: "auto" }} onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DataExplorerModal({ token, config, onClose }) {
  const [tables, setTables] = useState([]);
  const [table, setTable] = useState("sales");
  const [limit, setLimit] = useState(config?.sample_rows || 100);
  const [offset, setOffset] = useState(0);
  const [sample, setSample] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/data/tables", {}, token).then((r) => {
      setTables(r.tables || []);
      if (r.tables?.length) setTable(r.tables[0].id);
    }).catch(() => {});
  }, [token]);

  const loadSample = async (newOffset = offset) => {
    setLoading(true);
    setError("");
    try {
      const data = await api(
        `/api/data/sample?table=${encodeURIComponent(table)}&limit=${limit}&offset=${newOffset}`,
        {},
        token
      );
      setSample(data);
      setOffset(newOffset);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (table) loadSample(0);
  }, [table, limit]);

  const total = sample?.total_rows || 0;
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
        <h2>Data explorer</h2>
        <p className="field-hint">Browse a sample of loaded data (not the full dataset).</p>
        <div className="explorer-toolbar">
          <div className="form-group">
            <label>Table</label>
            <select value={table} onChange={(e) => setTable(e.target.value)}>
              {tables.map((t) => (
                <option key={t.id} value={t.id}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Rows per page</label>
            <input type="number" min={10} max={500} value={limit} onChange={(e) => setLimit(+e.target.value)} />
          </div>
          <button className="btn btn-ghost" type="button" onClick={() => loadSample(offset)} disabled={loading}>
            Refresh
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {sample?.available && (
          <>
            <p className="field-hint">
              Showing {offset + 1}–{Math.min(offset + limit, total)} of {total.toLocaleString()} rows
            </p>
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {sample.columns.map((c) => <th key={c}>{c}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {sample.rows.map((row, i) => (
                    <tr key={i}>
                      {sample.columns.map((c) => (
                        <td key={c}>{row[c] != null ? String(row[c]) : "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="modal-actions" style={{ marginTop: 12 }}>
              <button className="btn btn-ghost" type="button" disabled={!canPrev || loading}
                onClick={() => loadSample(Math.max(0, offset - limit))}>Previous</button>
              <button className="btn btn-ghost" type="button" disabled={!canNext || loading}
                onClick={() => loadSample(offset + limit)}>Next</button>
              <button className="btn btn-primary" type="button" style={{ width: "auto" }} onClick={onClose}>Close</button>
            </div>
          </>
        )}
        {!sample?.available && !loading && (
          <p className="empty-state">No data available. Load CSV files first.</p>
        )}
      </div>
    </div>
  );
}

function buildAnomalyMap(listItems, anomalyRows, dateCol, metricCol, dimensionCol) {
  const map = {};
  listItems.forEach((item) => {
    map[item.date] = { ...item, is_anomaly: true };
  });
  anomalyRows.forEach((row, i) => {
    const d = String(row[dateCol]).slice(0, 10);
    map[d] = {
      id: map[d]?.id ?? i + 1,
      date: d,
      category: row.anomaly_methods || map[d]?.category || "Statistical outlier",
      description: map[d]?.description || `Anomaly score ${row.anomaly_score ?? "—"}`,
      severity: map[d]?.severity || "medium",
      metric_value: row[metricCol] ?? map[d]?.metric_value,
      anomaly_score: row.anomaly_score,
      anomaly_methods: row.anomaly_methods,
      rolling_mean: row.rolling_mean,
      rolling_std: row.rolling_std,
      rolling_upper: row.rolling_upper,
      rolling_lower: row.rolling_lower,
      dimension: dimensionCol ? row[dimensionCol] : null,
      is_anomaly: true,
      raw: row,
    };
  });
  return map;
}

function AnomalyDetailModal({ detail, onClose }) {
  if (!detail) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal anomaly-detail-modal" onClick={(e) => e.stopPropagation()}>
        <button
          className="icon-btn"
          type="button"
          style={{ position: "absolute", top: 16, right: 16 }}
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
        <span className="anomaly-badge-lg">Anomaly detected</span>
        <h2>Anomaly #{detail.id}: {detail.date}</h2>
        <div className="detail-grid">
          <div className="detail-item">
            <label>Category</label>
            <span>{detail.category || "—"}</span>
          </div>
          <div className="detail-item">
            <label>Severity</label>
            <span>{detail.severity || "—"}</span>
          </div>
          <div className="detail-item">
            <label>Metric value</label>
            <span>{detail.metric_value ?? "—"}</span>
          </div>
          <div className="detail-item">
            <label>Anomaly score</label>
            <span>{detail.anomaly_score ?? "—"}</span>
          </div>
          {detail.expected_range && (
            <div className="detail-item">
              <label>Expected range</label>
              <span>{detail.expected_range}</span>
            </div>
          )}
          {detail.dimension && (
            <div className="detail-item">
              <label>Dimension</label>
              <span>{detail.dimension}</span>
            </div>
          )}
          {detail.flagged_by && (
            <div className="detail-item">
              <label>Flagged by</label>
              <span>{detail.flagged_by}</span>
            </div>
          )}
          {detail.rolling_mean != null && (
            <>
              <div className="detail-item">
                <label>Rolling mean</label>
                <span>{Number(detail.rolling_mean).toFixed(2)}</span>
              </div>
              <div className="detail-item">
                <label>Expected band</label>
                <span>
                  {Number(detail.rolling_lower).toFixed(2)} – {Number(detail.rolling_upper).toFixed(2)}
                </span>
              </div>
            </>
          )}
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 8 }}>Description</p>
        <div className="detail-desc">{detail.description || "No description available."}</div>
        <div className="modal-actions">
          <button className="btn btn-primary" type="button" style={{ width: "auto" }} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function formatQueryPlanAsSql(plan) {
  if (!plan) return "";
  const table = plan.table || "sales";
  const lines = [
    `-- Data Query Agent (pandas plan → SQL-style view)`,
    `-- ${plan.explanation || ""}`,
    "",
  ];
  const groupBy = plan.group_by || [];
  const aggParts = (plan.aggregations || []).map((agg) => {
    const fn = String(agg.agg || "sum").toUpperCase();
    return `  ${fn}(${agg.column}) AS ${agg.as || agg.column}`;
  });
  let selectClause = aggParts.length ? aggParts.join(",\n") : "  *";
  if (groupBy.length) {
    selectClause = groupBy.map((c) => `  ${c}`).join(",\n") + ",\n" + selectClause;
  }
  lines.push(`SELECT\n${selectClause}`, `FROM ${table}`);
  (plan.filters || []).forEach((filt) => {
    const col = filt.column;
    const op = filt.op;
    const val = filt.value;
    if (op === "between" && Array.isArray(val)) {
      lines.push(`WHERE ${col} BETWEEN '${val[0]}' AND '${val[1]}'`);
    } else {
      lines.push(`WHERE ${col} ${op} ${JSON.stringify(val)}`);
    }
  });
  if (groupBy.length) lines.push(`GROUP BY ${groupBy.join(", ")}`);
  (plan.sort_by || []).forEach((s) => {
    if (typeof s === "object" && s.column) {
      lines.push(`ORDER BY ${s.column} ${s.ascending !== false ? "ASC" : "DESC"}`);
    }
  });
  if (plan.limit) lines.push(`LIMIT ${plan.limit}`);
  lines.push(
    "",
    `-- metric_col: ${plan.metric_col}`,
    `-- date_col: ${plan.date_col}`,
    `-- dimension_col: ${plan.dimension_col}`,
    "",
    "-- Raw JSON:",
    JSON.stringify(plan, null, 2)
  );
  return lines.join("\n");
}

function formatErrorDetailText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  const lines = [
    "=== Agent Error Details ===",
    `Agent: ${detail.agent || "unknown"}`,
    `Type: ${detail.error_type || "Error"}`,
    `Message: ${detail.message || ""}`,
  ];
  if (detail.question) lines.push("", `Question: ${detail.question}`);
  if (detail.query_plan) {
    lines.push("", "Query plan (JSON):", JSON.stringify(detail.query_plan, null, 2));
  }
  if (detail.traceback) lines.push("", "Traceback:", detail.traceback);
  return lines.join("\n");
}

function CopyableTextModal({ title, subtitle, text, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
    }
  };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {subtitle && <p className="field-hint">{subtitle}</p>}
        <div className="copyable-code-wrap">
          <textarea className="copyable-code" readOnly value={text} />
        </div>
        <div className="modal-actions">
          <button className="btn btn-ghost" type="button" onClick={onClose}>Close</button>
          <button className="btn btn-primary" type="button" style={{ width: "auto" }} onClick={copy}>
            Copy to clipboard
          </button>
          {copied && <span className="copy-toast">Copied!</span>}
        </div>
      </div>
    </div>
  );
}

function QuerySqlModal({ text, onClose }) {
  return (
    <CopyableTextModal
      title="Generated query"
      subtitle="SQL-style view of the Data Query Agent plan. Copy and reuse as needed."
      text={text}
      onClose={onClose}
    />
  );
}

async function downloadReportFile(filename, token) {
  const res = await fetch(`/api/reports/download/${encodeURIComponent(filename)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function AboutModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h2>About Data Anomaly Agent</h2>
        <div className="detail-desc" style={{ marginBottom: 16 }}>
          <p style={{ marginBottom: 12 }}>
            <strong>Data Anomaly Agent</strong> is a multi-agent AI application for detecting,
            explaining, and reporting anomalies in retail store sales time series (Kaggle
            Store Sales — Favorita Ecuador dataset).
          </p>
          <p style={{ marginBottom: 12 }}><strong>What it does</strong></p>
          <ul style={{ marginLeft: 20, marginBottom: 12, lineHeight: 1.7 }}>
            <li>Accepts natural-language questions about sales, families, stores, cities, and transactions</li>
            <li>Runs a pipeline of specialized agents: query design → execution → statistical detection → root cause → report → QA</li>
            <li>Highlights anomalies on an interactive chart with zoom and detail pop-ups</li>
            <li>Produces an executive report validated by a QA agent and saved under <code>Reports/</code></li>
          </ul>
          <p style={{ marginBottom: 12 }}><strong>Detection methods</strong></p>
          <ul style={{ marginLeft: 20, marginBottom: 12, lineHeight: 1.7 }}>
            <li>Modified Z-score (MAD-based)</li>
            <li>IQR fences</li>
            <li>Rolling window deviation (2-of-3 vote)</li>
            <li>Configurable parameters via the Detection menu</li>
          </ul>
          <p style={{ marginBottom: 12 }}><strong>Data & configuration</strong></p>
          <ul style={{ marginLeft: 20, lineHeight: 1.7 }}>
            <li>CSV files in the <code>data/</code> folder (train, stores, holidays; optional oil & transactions)</li>
            <li>Analysis date window, holiday logic, and LLM provider in Settings</li>
            <li>Powered by OpenAI or DeepSeek</li>
          </ul>
        </div>
        <div className="modal-actions">
          <button className="btn btn-primary" type="button" style={{ width: "auto" }} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function ReviseModal({ onClose, onSubmit, loading }) {
  const [feedback, setFeedback] = useState("");
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Revise Report</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: 16, fontSize: "0.9rem" }}>
          Describe what to change. The Reporter Agent will regenerate the report.
        </p>
        <div className="form-group">
          <label>Your feedback</label>
          <textarea rows={5} value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="e.g. Focus on California spikes and add more detail on external causes…" />
        </div>
        <div className="modal-actions">
          <button className="btn btn-ghost" type="button" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" type="button" style={{ width: "auto" }} disabled={loading || feedback.length < 3} onClick={() => onSubmit(feedback)}>
            {loading ? "Revising…" : "Submit revision"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AgentPipeline({ agentStates, logs, onViewQuery, onDownloadReport, onViewError }) {
  return (
    <div className="agent-panel">
      <div className="agent-pipeline">
        {AGENTS.map((a) => {
          const st = agentStates[a.id] || {};
          const cls = st.status === "running" ? "running" : st.status === "done" ? "done" : st.status === "error" ? "error" : st.status === "warning" ? "error" : "";
          const showQueryBtn = a.id === "query_agent" && st.status === "done" && st.plan;
          const showReportBtn = a.id === "qa_agent" && st.report_file;
          const showErrorBtn = st.status === "error" && st.error_detail;
          return (
            <div key={a.id} className={`agent-card ${cls}`}>
              <div className="agent-icon">{a.icon}</div>
              <div className="agent-info">
                <h4>{a.name}</h4>
                <p>{st.message || "Waiting…"}</p>
                {showQueryBtn && (
                  <div className="agent-card-actions">
                    <button
                      className="agent-mini-btn"
                      type="button"
                      onClick={() => onViewQuery(st.plan, st.query_sql)}
                    >
                      View SQL
                    </button>
                  </div>
                )}
                {showReportBtn && (
                  <div className="agent-card-actions">
                    <button
                      className="agent-mini-btn report-btn"
                      type="button"
                      onClick={() => onDownloadReport(st.report_file)}
                    >
                      Download report
                    </button>
                  </div>
                )}
                {showErrorBtn && (
                  <div className="agent-card-actions">
                    <button
                      className="agent-mini-btn error-btn"
                      type="button"
                      onClick={() => onViewError(st.error_detail)}
                    >
                      View error details
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {logs.length > 0 && (
        <div className="agent-log">
          {logs.slice(-12).map((l, i) => (
            <div key={i}>[{l.agent}] {l.message}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function TimeSeriesChart({
  series,
  anomalies,
  dateCol,
  metricCol,
  selectedDate,
  anomalyByDate,
  onAnomalyClick,
  chartParams,
  onChartParamsChange,
  token,
}) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  const anomalyByDateRef = useRef(anomalyByDate);
  const onAnomalyClickRef = useRef(onAnomalyClick);

  useEffect(() => {
    anomalyByDateRef.current = anomalyByDate;
    onAnomalyClickRef.current = onAnomalyClick;
  }, [anomalyByDate, onAnomalyClick]);

  useEffect(() => {
    if (!canvasRef.current || !series?.length) return;
    const labels = series.map((r) => String(r[dateCol]).slice(0, 10));
    const values = series.map((r) => Number(r[metricCol]));
    const anomalyDates = new Set(
      (anomalies || []).map((a) => String(a[dateCol]).slice(0, 10))
    );

    const pointColors = labels.map((d) =>
      anomalyDates.has(d) ? "#ff4757" : "#4dc3ff"
    );
    const pointRadii = labels.map((d) =>
      d === selectedDate ? 9 : anomalyDates.has(d) ? 7 : 3
    );
    const pointBorderWidth = labels.map((d) => (anomalyDates.has(d) ? 2 : 0));

    const showBands = chartParams?.show_std_bands !== false;
    const bandFactor = parseFloat(chartParams?.band_std_factor) || 1.5;

    const rollingMean = series.map((r) => {
      const v = r.rolling_mean;
      return v != null && !Number.isNaN(Number(v)) ? Number(v) : null;
    });
    const hasRolling = rollingMean.some((v) => v != null);

    const upperBand = series.map((r) => {
      const mean = r.rolling_mean;
      const std = r.rolling_std;
      if (mean == null || std == null || Number.isNaN(Number(mean))) return null;
      return Number(mean) + bandFactor * Number(std || 0);
    });
    const lowerBand = series.map((r) => {
      const mean = r.rolling_mean;
      const std = r.rolling_std;
      if (mean == null || std == null || Number.isNaN(Number(mean))) return null;
      return Number(mean) - bandFactor * Number(std || 0);
    });

    const datasets = [
      {
        label: metricCol,
        data: values,
        borderColor: "#4dc3ff",
        backgroundColor: "rgba(77, 195, 255, 0.12)",
        fill: true,
        tension: 0.3,
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors,
        pointRadius: pointRadii,
        pointBorderWidth: pointBorderWidth,
        pointHoverRadius: 10,
        pointHitRadius: anomalyDates.size ? 12 : 6,
        order: 1,
      },
    ];

    if (showBands && hasRolling) {
      datasets.push({
        label: `Upper (+${bandFactor}σ)`,
        data: upperBand,
        borderColor: "rgba(255, 165, 2, 0.85)",
        backgroundColor: "transparent",
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.3,
        fill: false,
        order: 2,
      });
      datasets.push({
        label: `Lower (−${bandFactor}σ)`,
        data: lowerBand,
        borderColor: "rgba(255, 165, 2, 0.85)",
        backgroundColor: "transparent",
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.3,
        fill: false,
        order: 2,
      });
      datasets.push({
        label: "Rolling mean",
        data: rollingMean,
        borderColor: "rgba(139, 156, 179, 0.7)",
        backgroundColor: "transparent",
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.3,
        fill: false,
        order: 3,
      });
    }

    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: "line",
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: true },
        onHover: (event, elements) => {
          const canvas = event.native?.target;
          if (!canvas || !chartRef.current) return;
          if (elements?.length) {
            const dateKey = chartRef.current.data.labels[elements[0].index];
            canvas.style.cursor = anomalyByDateRef.current?.[dateKey] ? "pointer" : "crosshair";
          } else {
            canvas.style.cursor = "crosshair";
          }
        },
        onClick: (_evt, elements) => {
          if (!elements?.length || !chartRef.current) return;
          const idx = elements[0].index;
          const dateKey = chartRef.current.data.labels[idx];
          const detail = anomalyByDateRef.current?.[dateKey];
          if (detail) onAnomalyClickRef.current?.(detail);
        },
        plugins: {
          legend: { display: showBands && hasRolling, position: "bottom", labels: { boxWidth: 12, font: { size: 10 } } },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => {
                const d = ctx.label;
                return anomalyByDateRef.current?.[d] ? "Click for details" : "";
              },
            },
          },
          zoom: {
            pan: {
              enabled: true,
              mode: "x",
              modifierKey: "shift",
            },
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              drag: {
                enabled: true,
                backgroundColor: "rgba(59, 158, 255, 0.12)",
                borderColor: "rgba(59, 158, 255, 0.5)",
                borderWidth: 1,
              },
              mode: "x",
            },
            limits: {
              x: { min: "original", max: "original" },
              y: { min: "original", max: "original" },
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(128,128,128,0.1)" },
            ticks: { color: "#8b9cb3", maxTicksLimit: 12, font: { size: 10 } },
          },
          y: {
            grid: { color: "rgba(128,128,128,0.1)" },
            ticks: { color: "#8b9cb3" },
          },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [series, anomalies, dateCol, metricCol, selectedDate, chartParams]);

  const saveChartParams = async (next) => {
    onChartParamsChange?.(next);
    if (token) {
      try {
        await api("/api/config", { method: "PUT", body: JSON.stringify({ chart: next }) }, token);
      } catch (_) { /* local preview still works */ }
    }
  };

  const handleZoom = (factor) => {
    const chart = chartRef.current;
    if (!chart?.zoom) return;
    chart.zoom(factor);
  };

  const resetZoom = () => chartRef.current?.resetZoom?.();

  const cp = chartParams || { show_std_bands: false, band_std_factor: 1.5 };

  return (
    <>
      <div className="chart-toolbar">
        <span className="chart-toolbar-hint">
          Scroll to zoom · Shift+drag to pan · Click red points for details
        </span>
        <div className="chart-zoom-btns">
          <button className="btn btn-ghost" type="button" onClick={() => handleZoom(1.35)} title="Zoom in">
            Zoom in
          </button>
          <button className="btn btn-ghost" type="button" onClick={() => handleZoom(0.75)} title="Zoom out">
            Zoom out
          </button>
          <button className="btn btn-ghost" type="button" onClick={resetZoom} title="Reset view">
            Reset zoom
          </button>
        </div>
      </div>
      <div className="chart-band-controls">
        <label>
          <input
            type="checkbox"
            checked={cp.show_std_bands !== false}
            onChange={(e) => saveChartParams({ ...cp, show_std_bands: e.target.checked })}
          />
          Show rolling std bands
        </label>
        <label>
          Band factor (×σ)
          <input
            type="number"
            step="0.1"
            min={0.5}
            max={5}
            value={cp.band_std_factor ?? 1.5}
            disabled={cp.show_std_bands === false}
            onChange={(e) => saveChartParams({ ...cp, band_std_factor: parseFloat(e.target.value) || 1.5 })}
          />
        </label>
        <span className="param-hint">Bands use rolling mean ± factor × rolling σ (varies per point)</span>
      </div>
      <div className="chart-wrap">
        <canvas ref={canvasRef} />
      </div>
    </>
  );
}

function Dashboard({ token, theme, setTheme }) {
  const [config, setConfig] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);
  const [question, setQuestion] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [running, setRunning] = useState(false);
  const [agentStates, setAgentStates] = useState({});
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [investigationId, setInvestigationId] = useState(null);
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);
  const [anomalyDetail, setAnomalyDetail] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showDetection, setShowDetection] = useState(false);
  const [showExplorer, setShowExplorer] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const [chartParams, setChartParams] = useState({ show_std_bands: false, band_std_factor: 1.5 });
  const [queryModalText, setQueryModalText] = useState(null);
  const [errorModalText, setErrorModalText] = useState(null);
  const [reviseLoading, setReviseLoading] = useState(false);
  const [error, setError] = useState("");

  const loadMeta = useCallback(async () => {
    const [cfg, health, sug] = await Promise.all([
      api("/api/config", {}, token),
      api("/api/health", {}, token).catch(() => ({ data: {} })),
      api("/api/suggestions", {}, token),
    ]);
    setConfig(cfg);
    setDataStatus(health.data || health);
    setSuggestions(sug.questions || []);
    if (cfg.chart) setChartParams(cfg.chart);
  }, [token]);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  const updateAgent = (event) => {
    const { agent, status, message } = event;
    if (!agent || agent === "orchestrator" || agent === "result") return;
    setAgentStates((s) => ({
      ...s,
      [agent]: {
        ...(s[agent] || {}),
        status: status || "done",
        message: message || "",
        plan: event.plan ?? s[agent]?.plan,
        query_sql: event.query_sql ?? s[agent]?.query_sql,
        report_file: event.report_file ?? s[agent]?.report_file,
        approved: event.approved ?? s[agent]?.approved,
        error_detail: event.error_detail ?? s[agent]?.error_detail,
      },
    }));
    if (message) setLogs((l) => [...l, { agent, message }]);
  };

  const openQueryModal = (plan, querySql) => {
    const text = querySql || plan?.sql || formatQueryPlanAsSql(plan);
    setQueryModalText(text);
  };

  const openErrorModal = (detail) => {
    setErrorModalText(formatErrorDetailText(detail));
  };

  const handleDownloadReport = async (filename) => {
    try {
      await downloadReportFile(filename, token);
    } catch (err) {
      setError(err.message);
    }
  };

  const runInvestigation = async () => {
    if (!question.trim() || running) return;
    setRunning(true);
    setError("");
    setResult(null);
    setAgentStates({});
    setLogs([]);
    setSelectedAnomaly(null);
    setAnomalyDetail(null);

    try {
      const { investigation_id } = await api(
        "/api/investigate",
        { method: "POST", body: JSON.stringify({ question }) },
        token
      );
      setInvestigationId(investigation_id);

      const url = `/api/investigate/stream?investigation_id=${investigation_id}&question=${encodeURIComponent(question)}&token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);

      es.onmessage = (msg) => {
        const event = JSON.parse(msg.data);
        if (event.agent === "result") {
          const inv = event.result;
          setResult(inv);
          if (inv?.query_plan) {
            setAgentStates((s) => ({
              ...s,
              query_agent: {
                ...(s.query_agent || {}),
                status: "done",
                plan: inv.query_plan,
                message: s.query_agent?.message || inv.query_plan?.explanation,
              },
            }));
          }
          if (inv?.report_file) {
            setAgentStates((s) => ({
              ...s,
              qa_agent: {
                ...(s.qa_agent || {}),
                status: "done",
                approved: true,
                report_file: inv.report_file,
                message: (s.qa_agent?.message || "") + " · Report saved",
              },
            }));
          }
          setRunning(false);
          es.close();
        } else if (event.agent === "error") {
          setError(event.message);
          setRunning(false);
          es.close();
        } else {
          updateAgent(event);
        }
      };

      es.onerror = () => {
        setError("Connection lost during investigation");
        setRunning(false);
        es.close();
      };
    } catch (err) {
      setError(err.message);
      setRunning(false);
    }
  };

  const handleRevise = async (feedback) => {
    setReviseLoading(true);
    try {
      const updated = await api(
        "/api/revise",
        { method: "POST", body: JSON.stringify({ investigation_id: investigationId, feedback }) },
        token
      );
      setResult(updated);
      setShowRevise(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setReviseLoading(false);
    }
  };

  const meta = result?._meta || {};
  const dateCol = meta.date_col || "date";
  const metricCol = meta.metric_col || "sales";
  const fullSeries = result?.anomaly_results?.full_df || [];
  const anomalyRows = result?.anomaly_results?.anomalies_df || [];
  const reportAnomalies = result?.report?.anomalies_found || [];

  const dimensionCol = meta.dimension_col || null;

  const listItems = reportAnomalies.length
    ? reportAnomalies.map((a, i) => ({
        id: i + 1,
        date: String(a.date).slice(0, 10),
        category: a.category || "Anomaly",
        description: a.description,
        severity: a.severity,
        metric_value: a.metric_value,
        expected_range: a.expected_range,
        flagged_by: a.flagged_by,
        is_anomaly: true,
      }))
    : anomalyRows.map((a, i) => ({
        id: i + 1,
        date: String(a[dateCol]).slice(0, 10),
        category: a.anomaly_methods || "Statistical outlier",
        description: `Statistical outlier (score ${a.anomaly_score})`,
        severity: "medium",
        metric_value: a[metricCol],
        anomaly_score: a.anomaly_score,
        anomaly_methods: a.anomaly_methods,
        rolling_mean: a.rolling_mean,
        rolling_std: a.rolling_std,
        rolling_upper: a.rolling_upper,
        rolling_lower: a.rolling_lower,
        dimension: dimensionCol ? a[dimensionCol] : null,
        is_anomaly: true,
      }));

  const anomalyByDate = buildAnomalyMap(
    listItems,
    anomalyRows,
    dateCol,
    metricCol,
    dimensionCol
  );

  const openAnomalyDetail = (item) => {
    setSelectedAnomaly(item);
    setAnomalyDetail(anomalyByDate[item.date] || item);
  };

  const selected = selectedAnomaly || listItems[0];
  const dataReady = dataStatus?.ready;

  return (
    <>
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">◆</span>
          Data Anomaly Agent
        </div>
        <div className="header-actions">
          <span className={`status-pill ${dataReady ? "ready" : "warn"}`} title={dataStatus?.available ? "Loaded sales date range" : ""}>
            {dataReady && dataStatus?.min_date
              ? `Data: ${dataStatus.min_date} → ${dataStatus.max_date}`
              : dataReady
                ? "Data ready"
                : "Awaiting CSV files"}
          </span>
          <button className="header-menu-btn" type="button" onClick={() => setShowAbout(true)}>
            About
          </button>
          <button className="header-menu-btn" type="button" onClick={() => setShowExplorer(true)} disabled={!dataReady}>
            Explore data
          </button>
          <button className="header-menu-btn" type="button" onClick={() => setShowDetection(true)}>
            Detection
          </button>
          <button className="icon-btn" type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Toggle theme">
            {theme === "dark" ? "☀" : "☽"}
          </button>
          <button className="icon-btn" type="button" onClick={() => setShowSettings(true)} title="Settings">⚙</button>
        </div>
      </header>

      <div className="query-bar">
        <div className="form-group">
          <label>Investigation question</label>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Find anomalies in daily sales by state…"
            onKeyDown={(e) => e.key === "Enter" && runInvestigation()}
          />
        </div>
        <button className="btn btn-primary" style={{ width: "auto", minWidth: 140 }} disabled={running || !dataReady} onClick={runInvestigation}>
          {running ? "Agents working…" : "Investigate"}
        </button>
      </div>

      {suggestions.length > 0 && (
        <div className="chip-row">
          {suggestions.map((q) => (
            <span key={q} className="chip" onClick={() => setQuestion(q)}>{q}</span>
          ))}
        </div>
      )}

      {error && <div className="error-banner" style={{ margin: "0 24px 16px" }}>{error}</div>}

      {!dataReady && (
        <div className="empty-state">
          <div className="icon">📁</div>
          <p>Place Kaggle CSV files in the <code>data/</code> folder (see data/README.md)</p>
        </div>
      )}

      <div className="main-layout">
        <div>
          <div className="panel chart-panel">
            <div className="panel-header">
              <span>Time series & anomaly highlights</span>
              {config && (
                <span className="status-pill">
                  {config.analysis_start} → {config.analysis_end}
                </span>
              )}
            </div>
            {fullSeries.length ? (
              <TimeSeriesChart
                series={fullSeries}
                anomalies={anomalyRows}
                dateCol={dateCol}
                metricCol={metricCol}
                selectedDate={selected?.date}
                anomalyByDate={anomalyByDate}
                onAnomalyClick={openAnomalyDetail}
                chartParams={chartParams}
                onChartParamsChange={(c) => { setChartParams(c); setConfig((cfg) => cfg ? { ...cfg, chart: c } : cfg); }}
                token={token}
              />
            ) : (
              <div className="empty-state">
                <div className="icon">📈</div>
                <p>Run an investigation to visualize anomalies</p>
              </div>
            )}
          </div>

          {result?.report && (
            <div className="report-section panel" style={{ marginTop: 20 }}>
              <h2>{result.report.title}</h2>
              <p>{result.report.executive_summary}</p>
              {result.report.recommendation && (
                <p style={{ marginTop: 12 }}><strong>Recommendation:</strong> {result.report.recommendation}</p>
              )}
              {result.status === "anomalies_found" && (
                <button className="btn btn-ghost" style={{ marginTop: 16 }} type="button" onClick={() => setShowRevise(true)}>
                  Revise report
                </button>
              )}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">Agent pipeline</div>
          <AgentPipeline
            agentStates={agentStates}
            logs={logs}
            onViewQuery={openQueryModal}
            onDownloadReport={handleDownloadReport}
            onViewError={openErrorModal}
          />
        </div>
      </div>

      {listItems.length > 0 && (
        <div className="anomaly-layout">
          <div className="panel">
            <div className="panel-header">Anomaly Detection</div>
            <div className="anomaly-list">
              {listItems.map((item) => (
                <div
                  key={item.id}
                  className={`anomaly-item ${selected?.id === item.id ? "selected" : ""}`}
                  onClick={() => openAnomalyDetail(item)}
                >
                  <div className="id">Anomaly #{item.id}: {item.date}</div>
                  <span className="cat">{item.category}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="panel anomaly-detail">
            {selected ? (
              <>
                <h3>Anomaly #{selected.id}</h3>
                <p><strong>Date:</strong> {selected.date}</p>
                <p><strong>Value:</strong> {selected.metric_value}</p>
                <p><strong>Severity:</strong> {selected.severity}</p>
                <p style={{ marginTop: 12 }}><strong>Description</strong></p>
                <p>{selected.description || "No description available."}</p>
              </>
            ) : (
              <p className="empty-state">Select an anomaly</p>
            )}
          </div>
        </div>
      )}

      {showAbout && (
        <AboutModal onClose={() => setShowAbout(false)} />
      )}
      {showSettings && config && (
        <SettingsModal
          token={token}
          config={config}
          onClose={() => setShowSettings(false)}
          onSave={(c) => { setConfig(c); if (c.chart) setChartParams(c.chart); loadMeta(); }}
        />
      )}
      {showDetection && config && (
        <DetectionSettingsModal
          token={token}
          config={config}
          onClose={() => setShowDetection(false)}
          onSave={(c) => { setConfig(c); }}
        />
      )}
      {showExplorer && config && (
        <DataExplorerModal
          token={token}
          config={config}
          onClose={() => setShowExplorer(false)}
        />
      )}
      {queryModalText && (
        <QuerySqlModal text={queryModalText} onClose={() => setQueryModalText(null)} />
      )}
      {errorModalText && (
        <CopyableTextModal
          title="Error details"
          subtitle="Copy this block to share with support or debugging."
          text={errorModalText}
          onClose={() => setErrorModalText(null)}
        />
      )}
      {anomalyDetail && (
        <AnomalyDetailModal detail={anomalyDetail} onClose={() => setAnomalyDetail(null)} />
      )}
      {showRevise && (
        <ReviseModal onClose={() => setShowRevise(false)} onSubmit={handleRevise} loading={reviseLoading} />
      )}
    </>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("daa_token"));
  const [theme, setTheme] = useState(() => localStorage.getItem("daa_theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("daa_theme", theme);
  }, [theme]);

  const onLogin = (t) => {
    localStorage.setItem("daa_token", t);
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem("daa_token");
    setToken(null);
  };

  if (!token) return <LoginScreen onLogin={onLogin} />;

  return (
    <>
      <button
        className="btn btn-ghost"
        style={{ position: "fixed", bottom: 16, right: 16, zIndex: 50, fontSize: "0.75rem" }}
        type="button"
        onClick={logout}
      >
        Sign out
      </button>
      <Dashboard token={token} theme={theme} setTheme={setTheme} />
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
