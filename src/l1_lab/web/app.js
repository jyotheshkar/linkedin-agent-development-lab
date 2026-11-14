"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = { token: "", config: null, run: null, evidence: null, artifacts: [], gates: null, reporting: null, approval: null, busy: false,
    lessons: null, selectedLesson: null, knowledge: null, practice: null, questionIndex: 0, drafts: new Map(), hintExposed: new Set(), answers: new Map() };
  const icons = { application: "\u2197", outreach: "\u2197", storage: "\u25a3", commit: "\u2713", delivery: "\u2192" };
  const humanize = (value) => String(value ?? "unknown").replace(/_/g, " ");
  const json = (value) => JSON.stringify(value, null, 2);
  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }
  function append(parent, ...children) { children.filter(Boolean).forEach((child) => parent.append(child)); return parent; }
  function clear(element) { element.replaceChildren(); return element; }
  function button(text, className, handler) {
    const result = node("button", `button ${className || "secondary"}`, text);
    result.type = "button"; result.addEventListener("click", handler); return result;
  }
  function codeDetails(title, value, open = false) {
    const details = node("details", "details"); details.open = open;
    append(details, node("summary", "", title), node("pre", "code-block", typeof value === "string" ? value : json(value)));
    return details;
  }
  function keyValues(data) {
    const list = node("dl", "key-value");
    Object.entries(data).forEach(([key, value]) => { append(list, node("dt", "", key), node("dd", "", value)); });
    return list;
  }
  function toast(message) {
    $("toast").textContent = message; $("toast").classList.remove("hidden");
    window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => $("toast").classList.add("hidden"), 4000);
  }
  function alert(message, kind = "error", source = "workflow") {
    state.alertSource = source;
    $("global-alert").textContent = message;
    $("global-alert").className = `banner ${kind}`;
  }
  function hideAlert() { $("global-alert").classList.add("hidden"); }
  function setBusy(value) {
    state.busy = value;
    document.querySelectorAll("[data-request], #run-button, #recover-button").forEach((item) => { item.disabled = value; });
    $("run-button").textContent = value ? "Working\u2026" : "Prepare run";
  }
  function detailText(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => `${(item.loc || []).join(".")}: ${item.msg || json(item)}`).join("; ");
    if (detail && typeof detail === "object") return detail.message || detail.error || json(detail);
    return "The server could not complete this request.";
  }
  async function request(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    let response;
    try { response = await fetch(path, { ...options, headers, credentials: "same-origin", cache: "no-store" }); }
    catch (_) { throw new Error("The lab server is unreachable. Check the connection and retry. No substitute run has been created."); }
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* An error page is not a successful lab response. */ }
    if (!response.ok) {
      const hints = { 401: "Access requires a valid session token. Add it under Connection.",
        404: "This run could not be found. Check the run ID and storage connection.",
        409: "The request is blocked by a workflow, version, or review boundary.",
        422: "The input does not match the lab contract.", 429: "The lab is limiting requests. Wait a moment before trying again.",
        503: "A required service is unavailable. No simulated fallback was run." };
      const error = new Error(`${hints[response.status] || `The request failed (${response.status}).`} ${detailText(payload?.detail ?? payload)}`);
      error.status = response.status; error.payload = payload; throw error;
    }
    if (payload === null) throw new Error("The server returned an unexpected response. No result is being inferred.");
    return payload;
  }
  async function act(action) {
    if (state.busy) return;
    hideAlert(); setBusy(true);
    try { await action(); }
    catch (error) {
      if (error.status === 401) { showView("settings"); $("token").focus(); }
      alert(error.message, error.status === 409 ? "warning" : "error");
    }
    finally { setBusy(false); }
  }
  function rememberId(id) {
    if (!id) return;
    $("recover-id").value = id;
    try { localStorage.setItem("atlas-fieldwork:last-run-id", id); } catch (_) { /* Storage is optional. */ }
  }
  function showView(name) {
    if (state.alertSource === "workflow") hideAlert();
    document.querySelectorAll(".view").forEach((view) => { view.classList.toggle("hidden", view.id !== `view-${name}`); });
    document.querySelectorAll("[data-view]").forEach((item) => {
      const active = item.dataset.view === name; item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
    });
    if (name === "practice" && !state.practice) loadPractice();
    if (name === "knowledge" && !state.knowledge) loadKnowledge();
    if (name === "learn" && !state.lessons) loadLessons();
    if (name === "coverage" && !state.lessons) loadLessons();
  }
  function switchTab(name, focus = false) {
    document.querySelectorAll("[data-tab]").forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active); tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1;
      $("panel-" + tab.dataset.tab).classList.toggle("hidden", !active);
      if (active && focus) tab.focus();
    });
  }
  function renderConfig(config) {
    state.config = config;
    $("mode-badge").textContent = config.mode === "complete" ? "Complete MVP" : config.mode === "reference" ? "Reference workspace" : config.mode === "student" ? "Historical scaffold" : humanize(config.mode || "Mode unconfirmed");
    $("source-badge").textContent = humanize(config.source || "synthetic");
    $("auth-badge").textContent = config.auth_required ? "Token required" : "Local access";
    clear($("connection-status")); append($("connection-status"), node("span", "status-dot"), node("span", "", config.configuration_ready === false ? "Connected \u00b7 configuration incomplete" : `Connected \u00b7 ${humanize(config.storage || "local")} storage`));
    clear($("config-details")).append(keyValues({ "Workspace": humanize(config.mode), "Effects": humanize(config.effects), "Source": humanize(config.source), "Storage": humanize(config.storage), "Release checks": config.release_ready ? "Ready" : "Not yet ready" }));
    if (config.mode === "student" && config.unfinished_tasks?.length) {
      const names = config.unfinished_tasks.map((item) => typeof item === "string" ? item : `${item.milestone || "Task"} \u00b7 ${item.file || ""} :: ${item.function || item.symbol || item.id || "Unfinished task"}`);
      append($("config-details"), codeDetails(`${names.length} unfinished functions in this checkout`, names));
      alert(`This checkout reports ${names.length} unfinished functions. The complete MVP belongs on main; inspect the actual branch before changing files.`, "info", "configuration");
    }
    if (config.blockers?.length) {
      append($("config-details"), codeDetails("Configuration blockers", config.blockers, true));
      alert("The console is connected, but server configuration is incomplete. Open Connection to inspect the reported blockers. No workflow has been executed.", "warning", "configuration");
    }
  }
  async function loadConfig() {
    try { renderConfig(await request("/api/config")); }
    catch (error) { $("mode-badge").textContent = "Connection needed"; $("connection-status").textContent = "Lab connection unavailable"; alert(error.message, "error", "configuration"); }
  }
  function receive(payload) {
    const run = payload.run ?? payload;
    if (!run || typeof run !== "object" || !run.run_id) throw new Error("The server did not return a valid run. No state has been inferred.");
    state.run = run; state.evidence = payload.evidence ?? inferEvidence(run);
    state.artifacts = payload.artifacts ?? run.artifacts ?? [];
    state.gates = payload.gates ?? run.gates ?? null;
    state.reporting = payload.reporting ?? run.reporting ?? null;
    state.approval = payload.approval ?? run.approval ?? null;
    rememberId(run.run_id); renderRun();
  }
  function inferEvidence(run) {
    for (const output of [...(run.outputs || [])].reverse()) {
      if (output && output.evidence) return output.evidence;
      if (output && output.retrieved_chunks) return output;
      if (output && output.answer) return { answer: output.answer, context_chunk_ids: output.source_ids || [], source_kind: output.kind };
    }
    return null;
  }
  function renderRun() {
    const run = state.run; if (!run) return;
    $("run-status").textContent = humanize(run.status);
    $("run-status").className = `badge ${run.status === "completed" ? "teal" : run.status === "blocked" || run.status === "pending" ? "warning" : "muted"}`;
    renderOverview(run); renderPlan(run); renderEvidence(state.evidence); renderArtifacts(); renderTrace(run);
  }
  function renderOverview(run) {
    const panel = clear($("panel-overview"));
    const header = node("div", "run-banner");
    append(header, keyValues({ "Run": run.run_id, "Tool calls": `${run.calls ?? 0} / ${run.max_calls ?? "\u2014"}`, "Current step": `${Math.min((run.index ?? 0) + 1, run.plan?.length || 0)} / ${run.plan?.length || 0}`, "State": humanize(run.status) }), button("Copy run ID", "ghost", () => copy(run.run_id)));
    append(panel, header);
    if (run.status === "awaiting_review") {
      const approval = node("section", "approval-card");
      append(approval, node("div", "eyebrow", "REVIEW EXACT MATERIAL AND ACTIONS"), node("h3", "", "Inspect the artifacts before approving."), node("p", "", "Approval permits only the displayed simulated actions using these artifact versions. It does not send an employer application or email."), planList(run.plan), codeDetails("Exact plan and approval hash", { plan_hash: run.plan_hash, approval: state.approval, artifact_hashes: state.artifacts.map((item) => item.sha256), plan: run.plan }, false));
      const artifactPreview = button(`Inspect ${state.artifacts.length} draft artifacts`, "secondary", () => switchTab("artifacts"));
      const actions = node("div", "review-actions");
      const approve = button("Approve simulation", "primary", () => resumeRun(true, "approve")); approve.dataset.request = "true";
      const revise = button("Return for revision", "secondary", () => resumeRun(false, "revise")); revise.dataset.request = "true";
      const reject = button("Reject this run", "danger", () => resumeRun(false, "reject")); reject.dataset.request = "true";
      append(actions, approve, revise, reject); append(approval, artifactPreview, actions); append(panel, approval);
    } else if (run.status === "pending") {
      const pending = node("div", "banner warning");
      append(pending, node("strong", "", "Outcome pending. Reconcile before repeating."), node("p", "", "Capacity stays reserved while the independent provider receipt is checked. This action does not approve a new plan."));
      const retry = button("Reconcile saved receipts", "secondary", () => resumeRun(false)); retry.dataset.request = "true"; append(pending, retry); append(panel, pending);
    } else if (run.status === "blocked") {
      append(panel, node("div", "banner warning", `The workflow is blocked. ${run.error || "Inspect the trace and correct the underlying contract before continuing."}`));
    } else if (["rejected", "revision_requested"].includes(run.status)) {
      append(panel, node("div", "banner warning", run.status === "rejected" ? "The proposed simulation was rejected. This run remains in the evidence trail." : "Revision was requested. Edit the role or goal and prepare a fresh reviewed run; the previous artifacts remain identifiable."));
    }
    const complete = run.completion?.full_unit === true || state.gates?.complete === true;
    if (run.status === "completed") append(panel, node("div", `banner ${complete ? "success" : "info"}`, complete ? "All five simulated evidence gates are verified. This is a completed simulated unit." : "The plan has finished. Full unit completion has not been established by all five evidence gates."));
    append(panel, node("h3", "subheading", "Completion requires evidence"));
    const receipts = node("div", "receipt-grid");
    const gateNames = { application: "APPLICATION_VERIFIED", outreach: "OUTREACH_VERIFIED", storage: "CV_SAVED", commit: "ATLAS_COMMITTED", delivery: "DASHBOARD_VERIFIED" };
    const observedGates = state.gates?.gates ?? state.gates ?? {};
    ["application", "outreach", "storage", "commit", "delivery"].forEach((gate) => {
      const receipt = run.receipts?.[gate]; const verified = observedGates[gate] === true || observedGates[gateNames[gate]] === true;
      const card = node("div", `receipt ${verified ? "verified" : "pending"}`);
      append(card, node("span", "receipt-icon", icons[gate]), node("strong", "", humanize(gate)), node("span", "meta", verified ? "Evidence gate verified" : receipt?.status ? `Receipt ${humanize(receipt.status)}; gate not established` : "Not verified"));
      if (receipt) append(card, codeDetails("Inspect receipt", receipt)); append(receipts, card);
    });
    append(panel, receipts);
    if (state.reporting) append(panel, codeDetails("Ledger and projected membership", state.reporting, false));
    append(panel, button("Learn the recovery boundary", "ghost", () => openLesson("WORKFLOW-01")));
    if (run.outputs?.length) append(panel, codeDetails(`Accepted outputs \u00b7 ${run.outputs.length}`, run.outputs));
    append(panel, codeDetails("Full saved state", run));
  }
  function planList(plan) {
    const list = node("ol", "plan-list");
    (plan || []).forEach((call, index) => {
      const item = node("li", "plan-item"); append(item, node("span", "plan-number", String(index + 1).padStart(2, "0")), node("div", "", humanize(call.tool || "unknown tool")), codeDetails("Arguments", call.args || {})); append(list, item);
    }); return list;
  }
  function renderPlan(run) {
    const panel = clear($("panel-plan"));
    append(panel, node("p", "help-text", "The planner proposes calls. Deterministic validation controls tool names, schemas, permissions, and the execution budget."), planList(run.plan), codeDetails("Plan hash", run.plan_hash || "No hash returned"));
  }
  function renderEvidence(evidence) {
    const panel = clear($("panel-evidence"));
    if (!evidence) { append(panel, node("div", "empty-state", "No evidence payload has been returned for this run. Load or execute a retrieval step to inspect actual results.")); return; }
    append(panel, keyValues({ "Source": evidence.source_kind || "Unspecified", "Generation": evidence.generation || "Adapter not reported", "Retrieval": evidence.retrieval?.model_id || "Model not reported" }));
    const answer = evidence.answer || {};
    append(panel, node("h3", "subheading", "Grounded response"), node("span", "badge muted", humanize(answer.status || "status not reported")));
    (answer.claims || []).forEach((claim) => {
      const card = node("div", "evidence-claim"); append(card, node("p", "", claim.text || ""), node("p", "meta", `Evidence: ${(claim.evidence_ids || []).join(" \u00b7 ") || "No identifiers returned"}`));
      if (claim.quote) append(card, node("blockquote", "source-quote", claim.quote)); append(panel, card);
    });
    if (answer.gaps?.length) {
      append(panel, node("h3", "subheading", "Unresolved gaps")); const gaps = node("ul", "gap-list"); answer.gaps.forEach((gap) => append(gaps, node("li", "", gap))); append(panel, gaps);
    }
    append(panel, node("p", "help-text", "Citation membership and exact quotes are structural checks. They do not prove semantic truth or personal contribution."));
    const chunks = evidence.retrieved_chunks || [];
    if (chunks.length) {
      append(panel, node("h3", "subheading", `Retrieved chunks \u00b7 ${chunks.length}`));
      chunks.forEach((chunk) => { const card = node("article", "source-card"); append(card, node("div", "eyebrow", chunk.record_id || "Source record"), node("p", "", chunk.text || ""), node("p", "meta", `Score ${typeof chunk.score === "number" ? chunk.score.toFixed(4) : "unreported"} \u00b7 ${chunk.chunk_id || "No chunk ID"}`), codeDetails("Provenance and raw hashes", chunk)); append(panel, card); });
    } else append(panel, node("p", "help-text", "The server did not return raw retrieved chunks for this saved run."));
    append(panel, codeDetails("Full evidence response", evidence));
    append(panel, button("Learn context and citation validation", "ghost", () => openLesson("GROUNDING-01")));
  }

  function renderArtifacts() {
    const panel = clear($("panel-artifacts"));
    append(panel, node("p", "help-text", "These are the actual returned draft bytes and immutable identities. Reviewed versions must flow into storage and dependent simulated actions."));
    if (!state.artifacts.length) { append(panel, node("div", "empty-state", "This run has not returned application material. Inspect-only plans can finish without draft artifacts.")); return; }
    state.artifacts.forEach((artifact) => {
      const card = node("article", "artifact-card");
      append(card, node("div", "eyebrow", humanize(artifact.kind)), node("h3", "", artifact.name || artifact.kind || "Artifact"),
        keyValues({ "Version": String(artifact.version ?? "unreported"), "Review": humanize(artifact.review_state ?? artifact.metadata?.review_state ?? "unreported"), "Content type": artifact.content_type || "unreported", "Bytes": String(artifact.byte_size ?? "unreported"), "Stored": artifact.stored === true ? "Stored bytes reported" : "Storage not yet verified" }),
        node("p", "artifact-hash", `SHA-256: ${artifact.sha256 || "Not returned"}`));
      if (typeof artifact.content === "string") append(card, codeDetails("Read exact artifact content", artifact.content, true));
      else append(card, node("p", "help-text", "The API did not inline artifact content; download it to inspect the bytes."));
      const actions = node("div", "artifact-actions");
      if (/^[a-f0-9]{64}$/.test(artifact.sha256 || "")) {
        const download = button("Download server artifact", "secondary", () => act(() => downloadArtifact(artifact)));
        download.disabled = artifact.stored !== true;
        if (download.disabled) download.title = "Available after reviewed bytes are stored";
        append(actions, download);
      }
      if (artifact.stored !== true) append(card, node("p", "help-text", "Download is available after reviewed bytes are stored. The exact draft content above is available for review now."));
      append(actions, button("Learn the evidence store", "ghost", () => openLesson("ATLAS-01")));
      append(card, actions, codeDetails("Artifact manifest", artifact)); append(panel, card);
    });
  }

  async function downloadArtifact(artifact) {
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    const response = await fetch(`/api/artifacts/${encodeURIComponent(artifact.sha256)}`, { headers, credentials: "same-origin", cache: "no-store" });
    if (!response.ok) { const error = new Error(`The server artifact is unavailable (${response.status}). Its bytes were not substituted locally.`); error.status = response.status; throw error; }
    const blob = await response.blob(), url = URL.createObjectURL(blob), link = node("a");
    link.href = url; link.download = String(artifact.name || `${artifact.kind || "artifact"}.md`).replace(/[^a-zA-Z0-9_.-]/g, "_");
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); toast("Artifact downloaded from the lab server.");
  }
  function renderTrace(run) {
    const panel = clear($("panel-trace")); const trace = run.trace || [];
    append(panel, node("p", "help-text", "Observed events from this run. Attempts, accepted outputs, and reconciled receipts are distinct."));
    if (!trace.length) { append(panel, node("div", "empty-state", "No trace events have been recorded.")); return; }
    const list = node("ol", "trace-list"); trace.forEach((event, i) => {
      const item = node("li", "trace-event");
      append(item, node("span", "trace-dot", String(i + 1).padStart(2, "0")), node("div", "trace-content"));
      const content = item.lastChild; append(content, node("strong", "", humanize(event.status)), node("p", "meta", `${event.tool || "workflow"} \u00b7 ${event.step_id || "review"} \u00b7 attempt ${event.attempt ?? "\u2014"}`));
      if (event.source_ids?.length) append(content, node("p", "meta", `Sources: ${event.source_ids.join(" \u00b7 ")}`)); append(content, codeDetails("Event data", event)); append(list, item);
    }); append(panel, list);
  }
  async function resumeRun(approve, decision) {
    const run = state.run; if (!run) return;
    const payload = { approve, plan_hash: run.plan_hash };
    if (decision) payload.decision = decision;
    await act(async () => receive(await request(`/api/runs/${encodeURIComponent(run.run_id)}/resume`, { method: "POST", body: json(payload) })));
  }
  async function copy(value) {
    try { await navigator.clipboard.writeText(String(value)); toast("Run ID copied."); }
    catch (_) { toast("Select the run ID above to copy it."); }
  }

  async function loadKnowledge() {
    const box = clear($("knowledge-state")); append(box, node("p", "help-text", "Reading Atlas Lab knowledge…"));
    try {
      const data = await request("/api/knowledge"); state.knowledge = data; clear(box);
      const snapshot = data.snapshot || data.provenance || {};
      append(box, node("h2", "card-title", "Observed source snapshot"), keyValues({ "Kind": snapshot.kind || data.kind || "unreported", "Revision": String(snapshot.revision ?? data.revision ?? "unreported"), "Retrieval time": snapshot.retrieved_at || "unreported", "Records": String(data.records?.length ?? 0) }), codeDetails("Snapshot and coverage", snapshot));
      const records = Array.isArray(data.records) ? data.records : [];
      if (!records.length) append(box, node("p", "help-text", "No records were returned. The view does not invent source coverage."));
      records.forEach((record) => {
        const card = node("article", "knowledge-record");
        append(card, node("h3", "", record.record_id || record.id || "Unnamed record"), node("span", "badge muted", `Version ${record.record_version ?? record.version ?? "unreported"}`), node("span", "badge teal", record.approval_status || record.approval || "Approval unreported"), node("span", "badge muted", record.table || "Source table unreported"), node("p", "", typeof record.text === "string" ? record.text : json(record.payload?.value ?? record.value ?? {})), codeDetails("Source, content hashes and record metadata", record)); append(box, card);
      });
      append(box, node("p", "help-text", "A record approval or index entry is not proof of personal engineering authorship. Refresh/revocation behavior is demonstrated by the linked tests and lesson."));
      loadDashboard();
    } catch (error) { clear(box).append(node("div", "banner error", error.message)); }
  }

  async function loadDashboard() {
    const box = clear($("dashboard-state")); append(box, node("p", "help-text", "Reading derived projection…"));
    try {
      const data = await request("/api/dashboard"); clear(box);
      const projection = data.projection || data;
      const metrics = node("div", "read-model-metrics");
      const values = { "Ledger revision": data.ledger_revision ?? projection.ledger_revision, "Projected revision": projection.revision ?? data.projected_revision, "Verified members": projection.record_ids?.length ?? projection.event_ids?.length ?? projection.members?.length };
      Object.entries(values).forEach(([name, value]) => { if (typeof value === "number") append(metrics, append(node("div", "metric"), node("strong", "", value), node("small", "", name))); });
      append(box, metrics, codeDetails("Exact reporting response", data, true));
    } catch (error) { clear(box).append(node("div", "banner error", error.message)); }
  }

  function renderLessonList() {
    const list = clear($("lesson-list"));
    (state.lessons?.lessons || []).forEach((lesson) => {
      const item = button(lesson.title || lesson.id, "lesson-button", () => openLesson(lesson.id));
      item.className = `lesson-button ${state.selectedLesson === lesson.id ? "active" : ""}`;
      item.setAttribute("aria-current", state.selectedLesson === lesson.id ? "page" : "false");
      append(item, node("small", "", lesson.id)); append(list, item);
    });
  }

  async function loadLessons() {
    if (state.learningLoading) return;
    state.learningLoading = true;
    try {
      state.lessons = await request("/api/learning");
      if (!state.lessons.lessons?.length) throw new Error("The server returned no lesson entries.");
      state.selectedLesson = state.selectedLesson || (state.lessons.lessons.some((item) => item.id === "ANATOMY-01") ? "ANATOMY-01" : state.lessons.lessons[0].id);
      renderLessonList(); await showLesson(state.selectedLesson);
      renderCoverage();
    } catch (error) { clear($("lesson-list")).append(node("p", "help-text", error.message)); }
    finally { state.learningLoading = false; }
  }

  async function openLesson(id) {
    state.selectedLesson = id; showView("learn");
    if (state.lessons) await showLesson(id);
  }

  function markdownText(text) {
    // Lesson text is rendered with DOM text nodes. Embedded HTML cannot execute.
    const box = node("div", "lesson-prose"), lines = String(text || "").split(/\r?\n/);
    let code = null, paragraph = [], list = null;
    const flush = () => { if (paragraph.length) { append(box, node("p", "", paragraph.join("\n"))); paragraph = []; } };
    lines.forEach((line) => {
      if (line.startsWith("```")) {
        flush(); list = null;
        if (code === null) code = []; else { append(box, node("pre", "code-block", code.join("\n"))); code = null; }
      } else if (code !== null) code.push(line);
      else if (/^#{1,4}\s+/.test(line)) { flush(); list = null; const level = Math.min(line.match(/^#+/)[0].length + 1, 4); append(box, node("h" + level, "", line.replace(/^#+\s+/, ""))); }
      else if (/^\s*[-*]\s+/.test(line)) { flush(); if (!list) { list = node("ul"); append(box, list); } append(list, node("li", "", line.replace(/^\s*[-*]\s+/, ""))); }
      else if (!line.trim()) { flush(); list = null; }
      else { list = null; paragraph.push(line); }
    });
    flush(); if (code !== null) append(box, node("pre", "code-block", code.join("\n")));
    return box;
  }

  async function showLesson(id) {
    state.selectedLesson = id; renderLessonList();
    const panel = clear($("lesson-detail")); append(panel, node("p", "help-text", `Reading ${id} and its actual source…`));
    try {
      const data = await request(`/api/learning/${encodeURIComponent(id)}`);
      if (state.selectedLesson !== id) return;
      clear(panel); const lesson = data.lesson;
      append(panel, node("div", "eyebrow lesson-kicker", lesson.id), node("h2", "", lesson.title), node("p", "help-text", data.learning_evidence || "Reference material; no grade assigned."));
      const diagrams = data.diagrams || (data.diagram_url ? [{ name: "Component diagram", url: data.diagram_url }] : []);
      if (diagrams.length) {
        const image = node("img", "lesson-diagram"); image.alt = `${lesson.title} — code-derived diagram`; image.src = diagrams[0].url;
        image.addEventListener("error", () => { image.hidden = true; toast("The declared diagram could not be loaded. Inspect the lesson resource map."); });
        append(panel, image);
        if (diagrams.length > 1) { const choices = node("div", "diagram-actions"); diagrams.forEach((item) => append(choices, button(humanize(item.name.replace(/\.svg$/, "")), "ghost", () => { image.hidden = false; image.src = item.url; }))); append(panel, choices); }
      }
      append(panel, markdownText(data.content));
      if (lesson.experiment) {
        const experiment = node("section", "approval-card");
        append(experiment, node("div", "eyebrow", "ONE SMALL EXPERIMENT"), node("h3", "", lesson.experiment.id || "Experiment"), node("p", "", lesson.experiment.summary || "Read the lesson's experiment specification."), node("p", "help-text", lesson.experiment.safe_boundary || "Use an isolated experiment; preserve unrelated work."));
        if (lesson.experiment.test_command) append(experiment, codeDetails("Exact test command", lesson.experiment.test_command, true)); append(panel, experiment);
      }
      (data.source_excerpts || []).forEach((source) => append(panel, codeDetails(`${source.path} :: ${source.symbol}`, source.content)));
      if (lesson.tests?.length) append(panel, codeDetails("Linked executable tests", lesson.tests, true));
      append(panel, button("Copy component handover", "secondary", () => copy(`This is my LinkedIn Agent Development Lab. Repository: ${state.lessons.project?.repository_url || "use the verified repository"}. I am studying ${lesson.id}: ${lesson.title}. Read the lesson and exact source symbols ${json(lesson.symbols || [])}, then the linked tests ${json(lesson.tests || [])}. Explain one mechanism, trace one input, and give me one small experiment. The baseline was built with assistance; do not infer mastery. Source shown in the app was read at ${data.read_at || "request time"}; distinguish it from committed or unsaved work.`)));
    } catch (error) { if (state.selectedLesson === id) clear(panel).append(node("div", "banner error", error.message)); }
  }
  async function loadPractice() {
    try { state.practice = await request("/api/practice"); renderPractice(); }
    catch (error) { clear($("practice-state")).append(node("div", "banner error", error.message)); }
  }
  function currentQuestion() { return state.practice?.questions?.[state.questionIndex]; }
  function saveDraft() {
    const question = currentQuestion(); if (!question || !$("practice-answer")) return;
    state.drafts.set(question.id, { answer: $("practice-answer").value, assisted: $("practice-assisted").checked });
  }
  function renderPractice() {
    const box = clear($("practice-state")); const question = currentQuestion();
    if (!question) { append(box, node("p", "help-text", "No public practice questions are available.")); return; }
    const questions = state.practice.questions, draft = state.drafts.get(question.id), saved = state.answers.get(question.id);
    const header = node("div", "card-header"); append(header, node("div", "question-number", `QUESTION ${String(state.questionIndex + 1).padStart(2, "0")} / ${String(questions.length).padStart(2, "0")}`), node("span", "badge muted", humanize(question.topic))); append(box, header);
    const track = node("div", "progress-track"), fill = node("div", "progress-fill"); fill.style.width = `${100 * (state.questionIndex + 1) / questions.length}%`; append(track, fill); append(box, track);
    append(box, node("h2", "question-prompt", question.prompt), node("p", "meta", `${question.source_file || "Source file unspecified"}${question.symbol ? " :: " + question.symbol : ""}`));
    if (question.required_categories?.length) { append(box, node("div", "eyebrow", "REASONING TO MAKE VISIBLE")); const required = node("div", "required-grid"); question.required_categories.forEach((category) => append(required, node("span", "required-item", humanize(category)))); append(box, required); }
    const label = node("label", "label", "Your explanation"); label.htmlFor = "practice-answer"; const answer = node("textarea", "input"); answer.id = "practice-answer"; answer.rows = 7; answer.maxLength = 20000; answer.placeholder = "Explain the behavior, why it works, and one boundary you would verify."; answer.value = draft?.answer ?? saved?.answer ?? ""; append(box, label, answer);
    const assistLabel = node("label", "checkbox-label"), check = node("input"); check.type = "checkbox"; check.id = "practice-assisted"; check.checked = Boolean(draft?.assisted ?? saved?.assisted ?? false); append(assistLabel, check, node("span", "", "I used help, a reference solution, or copied code for this attempt.")); append(box, assistLabel);
    const actions = node("div", "practice-actions");
    if (question.hint) {
      const hint = button(state.hintExposed.has(question.id) ? "Hint exposed" : "Show a hint", "ghost", () => {
        saveDraft(); state.hintExposed.add(question.id); renderPractice();
      }); append(actions, hint);
    }
    append(actions, button("Save ungraded answer", "primary", () => {
      saveDraft(); const current = state.drafts.get(question.id);
      if (!current.answer.trim()) { toast("Add an answer before saving it."); return; }
      state.answers.set(question.id, { question_id: question.id, variant_id: question.id, topic: question.topic, prompt: question.prompt,
        answer: current.answer, assisted: current.assisted || state.hintExposed.has(question.id), hint_exposed: state.hintExposed.has(question.id),
        hints: state.hintExposed.has(question.id) ? [question.hint] : [],
        is_transfer: Boolean(question.is_transfer), graded: false, rubric: null, source_ids: [question.source_file, question.symbol].filter(Boolean),
        saved_at: new Date().toISOString(), next_action: "Coach review of this ungraded answer" });
      toast("Ungraded answer saved in this page session. Export it before leaving."); renderPractice();
    })); append(box, actions);
    if (state.hintExposed.has(question.id)) append(box, node("div", "banner info", question.hint));
    const footer = node("div", "practice-meta");
    const previous = button("\u2190 Previous", "ghost", () => { saveDraft(); state.questionIndex--; renderPractice(); $("practice-state").scrollIntoView({ block: "start" }); }); previous.disabled = state.questionIndex === 0;
    const next = button("Next prompt \u2192", "secondary", () => { saveDraft(); state.questionIndex++; renderPractice(); $("practice-state").scrollIntoView({ block: "start" }); }); next.disabled = state.questionIndex >= questions.length - 1;
    append(footer, previous, node("span", "help-text", `${state.answers.size} saved drafts \u00b7 scores N/A`), next); append(box, footer);
    append(box, node("p", "help-text", "Answers stay in this page session until exported. Changing prompts retains drafts; closing this page clears them."));
  }
  function downloadPractice() {
    saveDraft();
    const record = { schema_version: 1, created_at: new Date().toISOString(), kind: "ungraded_practice_export", source: state.practice?.source || null,
      rubric: state.practice?.rubric || { correctness: 4, reasoning: 2, boundaries: 2, explanation: 2 }, attempts: [...state.answers.values()],
      unsaved_drafts: [...state.drafts.entries()].filter(([id, value]) => !state.answers.has(id) || state.answers.get(id).answer !== value.answer || state.answers.get(id).assisted !== (value.assisted || state.hintExposed.has(id))).map(([id, value]) => ({ question_id: id, ...value, assisted: value.assisted || state.hintExposed.has(id), graded: false, hint_exposed: state.hintExposed.has(id) })),
      metrics: { knowledge_accuracy: null, independent_accuracy: null, mastery: null, status: "ungraded" }, next_action: "Import into coaching chat for review; do not infer scores from this export" };
    const url = URL.createObjectURL(new Blob([json(record)], { type: "application/json" }));
    const link = node("a"); link.href = url; link.download = "linkedin-agent-development-practice.json"; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Practice record exported. No scores were assigned.");
  }
  function renderCoverage() {
    const grid = clear($("coverage-grid"));
    if (!state.lessons?.lessons?.length) { append(grid, node("p", "help-text", "Coverage comes from the versioned lesson manifest. Open this view to read the actual map.")); return; }
    state.lessons.lessons.forEach((lesson) => {
      const card = node("article", "card coverage-item");
      append(card, node("div", "eyebrow", lesson.id), node("h2", "card-title", lesson.title),
        node("p", "card-description", `JD areas: ${(lesson.jd_areas || []).join(", ") || "See the source-backed coverage document"}`),
        node("p", "coverage-file", (lesson.source_files || []).join(" · ")),
        node("p", "meta", (lesson.symbols || []).map((item) => item.symbol).join(" · ")),
        codeDetails("Linked verification targets", lesson.tests || []),
        button("Learn this component", "ghost", () => openLesson(lesson.id)));
      append(grid, card);
    });
  }

  document.querySelector(".brand").addEventListener("click", (event) => { event.preventDefault(); showView("workspace"); });
  document.querySelectorAll("[data-view]").forEach((item) => item.addEventListener("click", () => showView(item.dataset.view)));
  document.querySelectorAll("[data-learn]").forEach((item) => item.addEventListener("click", () => openLesson(item.dataset.learn)));
  $("refresh-knowledge").addEventListener("click", loadKnowledge);
  $("refresh-dashboard").addEventListener("click", loadDashboard);
  document.querySelectorAll("[data-tab]").forEach((item) => {
    item.addEventListener("click", () => switchTab(item.dataset.tab));
    item.addEventListener("keydown", (event) => { const tabs = [...document.querySelectorAll("[data-tab]")], index = tabs.indexOf(item); let target;
      if (event.key === "ArrowRight") target = tabs[(index + 1) % tabs.length]; if (event.key === "ArrowLeft") target = tabs[(index + tabs.length - 1) % tabs.length]; if (event.key === "Home") target = tabs[0]; if (event.key === "End") target = tabs[tabs.length - 1];
      if (target) { event.preventDefault(); switchTab(target.dataset.tab, true); }
    });
  });
  document.querySelectorAll("[data-goal]").forEach((item) => item.addEventListener("click", () => { $("goal").value = item.dataset.goal; $("goal").focus(); }));
  $("run-form").addEventListener("submit", (event) => {
    event.preventDefault();
    act(async () => {
      const payload = { goal: $("goal").value.trim(), retrieval: $("retrieval-mode").value, planner: $("planner-mode").value, generation: $("generation-mode").value };
      if ($("include-job").checked) payload.job = { title: $("job-title").value.trim(), company: $("job-company").value.trim(), requisition_id: $("job-id").value.trim(), skills: $("job-skills").value.split(",").map((item) => item.trim()).filter(Boolean), max_calls: Number($("job-budget").value) };
      receive(await request("/api/runs", { method: "POST", body: json(payload) })); switchTab("overview");
    });
  });
  $("recover-button").addEventListener("click", () => act(async () => {
    const id = $("recover-id").value.trim(); if (!id) throw new Error("Enter the saved run ID to recover it.");
    if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("A run ID contains exactly 32 lowercase hexadecimal characters. Copy it from the saved run response.");
    receive(await request(`/api/runs/${encodeURIComponent(id)}`)); toast("Saved run loaded.");
  }));
  $("token-form").addEventListener("submit", (event) => { event.preventDefault(); state.token = $("token").value.trim(); $("token").value = ""; $("token-status").textContent = state.token ? "Token set for this page session only." : "No token is set."; loadConfig(); });
  $("clear-token").addEventListener("click", () => { state.token = ""; $("token").value = ""; $("token-status").textContent = "Token cleared from this page session."; toast("Session token cleared."); });
  $("download-practice").addEventListener("click", downloadPractice);
  try { $("recover-id").value = localStorage.getItem("atlas-fieldwork:last-run-id") || ""; } catch (_) { /* No storage required. */ }
  renderCoverage(); loadConfig();
})();
