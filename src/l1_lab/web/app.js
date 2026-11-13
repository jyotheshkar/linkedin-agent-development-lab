"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = { token: "", config: null, run: null, evidence: null, busy: false,
    practice: null, questionIndex: 0, drafts: new Map(), hintExposed: new Set(), answers: new Map() };
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
    $("run-button").textContent = value ? "Working\u2026" : "Run workflow \u2192";
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
        409: "The request is blocked by an unfinished task or a workflow boundary.",
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
    $("mode-badge").textContent = config.mode === "reference" ? "Reference workspace" : config.mode === "student" ? "Student workspace" : "Mode unconfirmed";
    $("source-badge").textContent = humanize(config.source || "synthetic");
    $("auth-badge").textContent = config.auth_required ? "Token required" : "Local access";
    clear($("connection-status")); append($("connection-status"), node("span", "status-dot"), node("span", "", config.configuration_ready === false ? "Connected \u00b7 configuration incomplete" : `Connected \u00b7 ${humanize(config.storage || "local")} storage`));
    clear($("config-details")).append(keyValues({ "Workspace": humanize(config.mode), "Effects": humanize(config.effects), "Source": humanize(config.source), "Storage": humanize(config.storage), "Release checks": config.release_ready ? "Ready" : "Not yet ready" }));
    if (config.mode === "student" && config.unfinished_tasks?.length) {
      const names = config.unfinished_tasks.map((item) => typeof item === "string" ? item : `${item.milestone || "Task"} \u00b7 ${item.file || ""} :: ${item.function || item.symbol || item.id || "Unfinished task"}`);
      append($("config-details"), codeDetails(`${names.length} deliberate student tasks`, names));
      alert(`Student workspace: ${names.length} task functions are deliberately unfinished. Start with ${names[0]}. The workflow will report its actual missing task until you implement the required functions.`, "info", "configuration");
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
    renderOverview(run); renderPlan(run); renderEvidence(state.evidence); renderTrace(run);
  }
  function renderOverview(run) {
    const panel = clear($("panel-overview"));
    const header = node("div", "run-banner");
    append(header, keyValues({ "Run": run.run_id, "Tool calls": `${run.calls ?? 0} / ${run.max_calls ?? "\u2014"}`, "Current step": `${Math.min((run.index ?? 0) + 1, run.plan?.length || 0)} / ${run.plan?.length || 0}`, "State": humanize(run.status) }), button("Copy run ID", "ghost", () => copy(run.run_id)));
    append(panel, header);
    if (run.status === "awaiting_review") {
      const approval = node("section", "approval-card");
      append(approval, node("div", "eyebrow", "HUMAN REVIEW CHECKPOINT"), node("h3", "", "Review the exact plan before continuing."), node("p", "", "This approves only the simulated actions shown below. The plan hash binds your decision to these precise steps."), planList(run.plan), codeDetails("Exact plan and approval hash", { plan_hash: run.plan_hash, plan: run.plan }, false));
      const approve = button("Approve simulated plan \u2192", "primary", () => resumeRun(true)); approve.dataset.request = "true";
      append(approval, approve); append(panel, approval);
    } else if (run.status === "pending") {
      const pending = node("div", "banner warning");
      append(pending, node("strong", "", "Outcome pending. Reconcile before repeating."), node("p", "", "Capacity stays reserved while the independent provider receipt is checked. This action does not approve a new plan."));
      const retry = button("Reconcile saved receipts", "secondary", () => resumeRun(false)); retry.dataset.request = "true"; append(pending, retry); append(panel, pending);
    } else if (run.status === "blocked") {
      append(panel, node("div", "banner warning", `The workflow is blocked. ${run.error || "Inspect the trace and correct the underlying contract before continuing."}`));
    }
    const complete = run.completion?.full_unit === true || run.gates?.complete === true;
    if (run.status === "completed") append(panel, node("div", `banner ${complete ? "success" : "info"}`, complete ? "All five simulated evidence gates are verified. This is a completed simulated unit." : "The plan has finished. Full unit completion has not been established by all five evidence gates."));
    append(panel, node("h3", "subheading", "Completion requires evidence"));
    const receipts = node("div", "receipt-grid");
    ["application", "outreach", "storage", "commit", "delivery"].forEach((gate) => {
      const receipt = run.receipts?.[gate]; const verified = run.gates?.[gate] === true || (receipt?.status === "VERIFIED" && receipt.gate === gate && String(receipt.receipt_id || "").startsWith("sim:"));
      const card = node("div", `receipt ${verified ? "verified" : "pending"}`);
      append(card, node("span", "receipt-icon", icons[gate]), node("strong", "", humanize(gate)), node("span", "meta", verified ? "Verified receipt" : receipt?.status ? humanize(receipt.status) : "Not verified"));
      if (receipt) append(card, codeDetails("Inspect receipt", receipt)); append(receipts, card);
    });
    append(panel, receipts);
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
  async function resumeRun(approve) {
    const run = state.run; if (!run) return;
    await act(async () => receive(await request(`/api/runs/${encodeURIComponent(run.run_id)}/resume`, { method: "POST", body: json({ approve, plan_hash: run.plan_hash }) })));
  }
  async function copy(value) {
    try { await navigator.clipboard.writeText(String(value)); toast("Run ID copied."); }
    catch (_) { toast("Select the run ID above to copy it."); }
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
    const link = node("a"); link.href = url; link.download = "atlas-fieldwork-practice.json"; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Practice record exported. No scores were assigned.");
  }
  function renderCoverage() {
    const coverage = [
      ["01", "Python & strict contracts", "JSON shape, typed validation, identity normalization, and useful exceptions.", "contracts.py", "parse_job \u00b7 normalize_identity"],
      ["02", "Agent control", "Structured proposals pass through tool permissions, schemas, and a bounded executor.", "agent.py \u00b7 workflow.py", "validate_tool_call \u00b7 Workflow._graph_step"],
      ["03", "Safe failure & recovery", "Separate transient errors, unknown outcomes, human review, and provider receipts.", "provider.py \u00b7 workflow.py", "FakeProvider.reconcile \u00b7 Workflow.resume"],
      ["04", "Read-only knowledge", "Approved records retain provenance, source versions, hashes, and snapshot boundaries.", "knowledge.py", "select_records \u00b7 chunk_records"],
      ["05", "Retrieval & relevance", "Inspect model identity, top-k ranking, metadata filters, and insufficient evidence.", "retrieval.py", "VectorIndex.search \u00b7 rank_hits"],
      ["06", "Grounded responses", "Bound context, check citations and exact quotes, and preserve unresolved gaps.", "grounding.py", "build_context \u00b7 validate_answer"],
      ["07", "Evaluation & tracing", "Stable case IDs, separate denominators, and inspectable attempt-level events.", "evaluation.py \u00b7 progress.py", "compare_runs \u00b7 compute_metrics"],
      ["08", "REST, auth & delivery", "Request contracts, bearer boundaries, CI, containers, and durable state.", "api.py \u00b7 docs/DELIVERY.md", "API routes \u00b7 delivery review"],
      ["09", "LLM & MCP awareness", "Planning differs from execution. A file snapshot differs from a connected protocol.", "openai_adapter.py \u00b7 docs/DELIVERY.md", "OpenAIPlanner \u00b7 OpenAIAnswerGenerator"]
    ];
    const grid = clear($("coverage-grid")); coverage.forEach(([number, title, description, file, symbol]) => {
      const card = node("article", "card coverage-item"); append(card, node("span", "eyebrow", number + " / PRACTICE SURFACE"), node("h2", "card-title", title), node("p", "card-description", description), node("p", "coverage-file", file.split(" \u00b7 ").map((item) => item.startsWith("docs/") ? item : `src/l1_lab/${item}`).join(" \u00b7 ")), node("p", "meta", symbol)); append(grid, card);
    });
  }

  document.querySelector(".brand").addEventListener("click", (event) => { event.preventDefault(); showView("workspace"); });
  document.querySelectorAll("[data-view]").forEach((item) => item.addEventListener("click", () => showView(item.dataset.view)));
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
      const payload = { goal: $("goal").value.trim() };
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
