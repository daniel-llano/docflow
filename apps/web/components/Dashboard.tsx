"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, api, type Job, type JobPage, type JobStatus } from "@/lib/api";

const pageSize = 10;
const statuses: (JobStatus | "")[] = ["", "queued", "processing", "completed", "failed"];

function errorText(err: unknown) {
  return err instanceof ApiError ? err.message : "Something went wrong.";
}

export function Dashboard({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [page, setPage] = useState<JobPage>({ items: [], total: 0 });
  const [status, setStatus] = useState<JobStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPage(await api.jobs(status, offset, pageSize));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onUnauthorized();
      else setError(errorText(err));
    }
  }, [status, offset, onUnauthorized]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll while anything is still in flight.
  const busy = page.items.some((j) => j.status === "queued" || j.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const id = window.setInterval(() => void load(), 1500);
    return () => window.clearInterval(id);
  }, [busy, load]);

  const job = page.items.find((j) => j.id === selected) ?? null;

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      <Submit
        onSubmitted={async (created) => {
          setStatus("");
          setOffset(0);
          setSelected(created.id);
          await load();
        }}
      />

      <section className="panel">
        <div className="row spread">
          <h2>Documents</h2>
          <select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value as JobStatus | ""); setOffset(0); }}>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s ? s[0].toUpperCase() + s.slice(1) : "All statuses"}
              </option>
            ))}
          </select>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {page.items.length === 0 ? (
          <p className="muted">No documents yet. Upload one above.</p>
        ) : (
          <ul className="jobs">
            {page.items.map((j) => (
              <li key={j.id} className={j.id === selected ? "selected" : ""}>
                <button type="button" className="job" onClick={() => setSelected(j.id === selected ? null : j.id)}>
                  <span className="title">{j.title}</span>
                  <span className={`pill ${j.status}`}>{j.status}</span>
                  <span className="muted small">{new Date(j.createdAt).toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {page.total > pageSize && (
          <div className="row spread">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>
              Previous
            </button>
            <span className="muted small">
              {offset + 1}-{Math.min(offset + pageSize, page.total)} of {page.total}
            </span>
            <button type="button" disabled={offset + pageSize >= page.total} onClick={() => setOffset(offset + pageSize)}>
              Next
            </button>
          </div>
        )}
      </section>

      {job && (
        <JobDetail
          job={job}
          onDelete={() => act(async () => { await api.remove(job.id); setSelected(null); })}
          onRetry={() => act(() => api.retry(job.id))}
        />
      )}
    </>
  );
}

function Submit({ onSubmitted }: { onSubmitted: (job: Job) => Promise<void> }) {
  const [mode, setMode] = useState<"file" | "text">("file");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "file" && !file) return setError("Choose a file first.");
    if (mode === "text" && (!title.trim() || !text.trim())) return setError("Add a title and some text.");
    setBusy(true);
    try {
      const job = mode === "file" ? await api.submitFile(file!, title) : await api.submitText(title.trim(), text);
      setTitle("");
      setText("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await onSubmitted(job);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <div className="row spread">
        <h2>New document</h2>
        <div className="tabs small" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "file"} className={mode === "file" ? "active" : ""} onClick={() => setMode("file")}>
            Upload file
          </button>
          <button type="button" role="tab" aria-selected={mode === "text"} className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>
            Paste text
          </button>
        </div>
      </div>
      <label htmlFor="title">Title {mode === "file" && <span className="muted">(optional, defaults to the file name)</span>}</label>
      <input id="title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      {mode === "file" ? (
        <>
          <label htmlFor="file">File (.pdf, .txt, .md, .csv, up to 5 MB)</label>
          <input id="file" ref={fileInput} type="file" accept=".pdf,.txt,.md,.csv,.log" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </>
      ) : (
        <>
          <label htmlFor="text">Text</label>
          <textarea id="text" rows={6} value={text} onChange={(e) => setText(e.target.value)} />
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="primary" disabled={busy}>
        {busy ? "Sending…" : "Process document"}
      </button>
    </form>
  );
}

function JobDetail({ job, onDelete, onRetry }: { job: Job; onDelete: () => void; onRetry: () => void }) {
  const r = job.result;
  return (
    <section className="panel detail" aria-label={`Details for ${job.title}`}>
      <div className="row spread">
        <h2>{job.title}</h2>
        <div className="row">
          {job.status === "failed" && (
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          )}
          <button type="button" className="danger" onClick={() => confirm(`Delete "${job.title}"?`) && onDelete()}>
            Delete
          </button>
        </div>
      </div>
      {job.filename && <p className="muted small">From {job.filename}</p>}
      {job.status === "failed" && <p className="error">Processing failed after {job.attempts} attempt(s): {job.error}</p>}
      {!r && job.status !== "failed" && <p className="muted">Processing…</p>}
      {r && (
        <>
          <p>{r.summary}</p>
          <dl className="facts">
            <div><dt>Language</dt><dd>{r.language}</dd></div>
            <div><dt>Words</dt><dd>{r.word_count.toLocaleString()} ({r.reading_minutes} min read)</dd></div>
            <div><dt>Amounts</dt><dd>{r.amounts.join(", ") || "None found"}</dd></div>
            <div><dt>Dates</dt><dd>{r.dates.join(", ") || "None found"}</dd></div>
            <div>
              <dt>Personal data masked</dt>
              <dd>{r.pii_masked ? Object.entries(r.pii).filter(([, n]) => n > 0).map(([k, n]) => `${n} ${k}`).join(", ") : "None found"}</dd>
            </div>
          </dl>
          <div className="keywords">
            {r.keywords.map((k) => (
              <span className="kw" key={k}>
                {k}
              </span>
            ))}
          </div>
          <h3>Masked preview</h3>
          <pre>{r.masked_preview}</pre>
        </>
      )}
    </section>
  );
}
