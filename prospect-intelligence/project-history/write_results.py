new_results = open("ui/templates/results_new.html", "w", encoding="utf-8")
new_results.write("""{% extends "base.html" %}
{% block title %}Research Results \u2014 Coextend PI{% endblock %}

{% block content %}
<style>
/* =============================================
   CHAT LAYOUT  (ParcelPilot-inspired)
   Left sidebar: workflow steps
   Right main:   chat message thread
   ============================================= */

.chat-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  grid-template-rows: auto 1fr;
  gap: 0;
  min-height: calc(100vh - 120px);
  background: var(--bg-secondary);
}

/* ---- HEADER BAR ---- */
.chat-header {
  grid-column: 1 / -1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.chat-header-title { font-weight: 600; font-size: 15px; color: var(--text-primary); }
.chat-header-sub   { font-size: 13px; color: var(--text-muted); margin-left: 4px; }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #d1d5db; flex-shrink: 0;
}
.status-dot.running { background: #f59e0b; animation: blink 1.2s ease-in-out infinite; }
.status-dot.done    { background: #10b981; animation: none; }
.status-dot.failed  { background: #ef4444; animation: none; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

.live-badge {
  margin-left: auto;
  font-size: 11px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px;
  background: #ecfdf5; color: #065f46;
  border: 1px solid #a7f3d0;
}
.live-badge.running { background:#fffbeb; color:#92400e; border-color:#fcd34d; }
.live-badge.failed  { background:#fef2f2; color:#991b1b; border-color:#fecaca; }

/* ---- LEFT SIDEBAR (workflow steps) ---- */
.chat-sidebar {
  background: var(--surface);
  border-left: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  border-radius: 0 0 0 var(--radius-lg);
  padding: 16px 0;
  overflow-y: auto;
}

.sidebar-section-label {
  font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .06em;
  color: var(--text-muted);
  padding: 0 16px 8px;
}

.wf-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-tertiary);
  cursor: default;
  transition: background .1s;
  border-left: 3px solid transparent;
}
.wf-step.done    { color: var(--text-secondary); }
.wf-step.running { color: var(--text-primary); font-weight: 500;
                   background: var(--accent-lighter); border-left-color: var(--accent-primary); }
.wf-step.failed  { color: #dc2626; }

.wf-icon {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid var(--border-strong);
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; flex-shrink: 0; margin-top: 1px;
  background: var(--surface);
}
.wf-step.done    .wf-icon { background:#ecfdf5; border-color:#34d399; color:#065f46; }
.wf-step.running .wf-icon { background:#fffbeb; border-color:#f59e0b; color:#92400e;
                             animation: blink 1.2s ease-in-out infinite; }
.wf-step.failed  .wf-icon { background:#fef2f2; border-color:#f87171; color:#991b1b; }
.wf-step.pending .wf-icon { background: var(--bg-tertiary); }

.wf-label { flex: 1; line-height: 1.35; }
.wf-time  { font-size: 11px; color: var(--text-muted); white-space: nowrap; margin-top:1px; }

.sidebar-divider {
  height: 1px; background: var(--border); margin: 12px 16px;
}

/* score summary in sidebar */
.sidebar-score {
  padding: 12px 16px;
}
.sidebar-score-row {
  display: flex; align-items: center; gap: 10px;
}
.sidebar-score-num {
  font-size: 28px; font-weight: 700; color: var(--accent-primary); line-height: 1;
}
.sidebar-score-label {
  font-size: 11px; color: var(--text-muted);
}
.sidebar-score-band {
  font-size: 12px; font-weight: 600; margin-top: 2px;
}

/* ---- MAIN CHAT AREA ---- */
.chat-main {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  border-radius: 0 0 var(--radius-lg) 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Tab bar */
.chat-tabs {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 0;
  padding: 0 4px;
  flex-shrink: 0;
}
.chat-tab {
  padding: 12px 18px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  cursor: pointer;
  font-size: 13px; font-weight: 500;
  color: var(--text-muted);
  transition: color .15s, border-color .15s;
  margin-bottom: -1px;
  font-family: var(--font-stack);
}
.chat-tab:hover { color: var(--text-secondary); }
.chat-tab.active { color: var(--accent-primary); border-bottom-color: var(--accent-primary); }

/* Message thread */
.chat-thread {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---- MESSAGE BUBBLES ---- */
.msg {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 100%;
}
.msg-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--accent-primary);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
  flex-shrink: 0;
}
.msg-avatar.user { background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border); }
.msg-body { flex: 1; min-width: 0; }
.msg-meta {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px;
}
.msg-name   { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.msg-time   { font-size: 12px; color: var(--text-muted); }
.msg-tag    {
  font-size: 10px; font-weight: 600; padding: 2px 7px;
  border-radius: 999px; background: var(--accent-lighter);
  color: var(--accent-primary); letter-spacing: .03em;
}

/* Workflow complete tag */
.wf-complete-tag {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: var(--verified);
  background: var(--high-bg); border: 1px solid var(--high-border);
  border-radius: 4px; padding: 3px 8px; margin-bottom: 10px;
}

/* The actual response card */
.msg-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-lg) var(--radius-lg) var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

/* sections within a message */
.msg-section {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.msg-section:last-child { border-bottom: none; }

.msg-section-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .05em; color: var(--text-muted); margin-bottom: 10px;
}

/* KV inside message */
.msg-kv { display: flex; flex-direction: column; gap: 6px; }
.msg-kv-row { display: flex; gap: 10px; font-size: 13px; align-items: baseline; }
.msg-kv-key { color: var(--text-muted); font-weight: 500; min-width: 140px; flex-shrink: 0; }
.msg-kv-val { color: var(--text-primary); }

/* Score bar in message */
.score-bar-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.score-bar-bg {
  flex: 1; height: 6px; background: var(--bg-tertiary);
  border-radius: 999px; overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 999px; transition: width .6s ease; }

/* inline code reference */
.ref-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--bg-tertiary); border: 1px solid var(--border);
  border-radius: 4px; font-size: 12px; font-family: monospace;
  padding: 2px 6px; color: var(--text-secondary); cursor: default;
}

/* Thinking step inside a msg */
.think-step {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--text-tertiary);
  padding: 6px 18px;
  border-bottom: 1px solid var(--border);
}
.think-step .chk { color: var(--verified); font-size: 12px; }
.think-step .dur { font-size: 12px; color: var(--text-muted); margin-left: auto; }

/* pre inside message */
.msg-pre {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  font-size: 13px;
  font-family: 'SF Mono', Monaco, monospace;
  white-space: pre-wrap; word-break: break-word;
  line-height: 1.55;
  color: var(--text-primary);
}

/* inline table */
.msg-table { width:100%; border-collapse:collapse; font-size:13px; }
.msg-table th {
  text-align:left; padding:8px 10px;
  border-bottom:1px solid var(--border);
  font-size:11px; font-weight:600; text-transform:uppercase;
  letter-spacing:.03em; color:var(--text-muted);
  background:var(--bg-tertiary);
}
.msg-table td {
  padding:8px 10px; border-bottom:1px solid var(--border);
  vertical-align:top;
}
.msg-table tbody tr:last-child td { border-bottom:none; }

/* ---- FEEDBACK inside chat ---- */
.feedback-msg .msg-card { border-top: 3px solid var(--accent-primary); }
.fb-btn-group { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
.fb-btn {
  padding: 6px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  font-size: 13px; font-weight: 500; cursor: pointer;
  color: var(--text-secondary); transition: all .15s;
  font-family: var(--font-stack);
}
.fb-btn:hover { border-color: var(--accent-primary); color: var(--accent-primary); }
.fb-btn.selected {
  background: var(--accent-lighter);
  border-color: var(--accent-primary);
  color: var(--accent-primary); font-weight: 600;
}

/* ---- WAITING / progress in chat ---- */
.think-bubble {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-lg) var(--radius-lg) var(--radius-lg);
  padding: 14px 18px;
  display: flex; flex-direction: column; gap: 10px;
}
.think-row {
  display: flex; align-items: center; gap: 10px; font-size: 13px;
}
.think-spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid var(--border);
  border-top-color: var(--accent-primary);
  animation: spin .8s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.think-circle-done {
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--high-bg); border: 1px solid var(--high-border);
  color: var(--verified); font-size: 9px;
  display: flex; align-items:center; justify-content:center;
  flex-shrink: 0;
}
.think-circle-pending {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid var(--border-strong);
  flex-shrink: 0;
}

/* ---- RESPONSIVE ---- */
@media (max-width: 767px) {
  .chat-layout { grid-template-columns: 1fr; }
  .chat-sidebar { display: none; }
  .chat-header { border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
  .chat-main { border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
  .chat-thread { padding: 14px; }
  .msg-kv-key { min-width: 100px; }
  .chat-tab { padding: 10px 12px; font-size: 12px; }
}
</style>

<!-- OUTER CHAT LAYOUT -->
<div class="chat-layout">

  <!-- HEADER -->
  <div class="chat-header">
    <span class="status-dot running" id="hdr-dot"></span>
    <span class="chat-header-title" id="hdr-company">Researching&hellip;</span>
    <span class="chat-header-sub">— Prospect Research</span>
    <span class="live-badge running" id="hdr-badge">WORKING</span>
  </div>

  <!-- LEFT SIDEBAR -->
  <div class="chat-sidebar">
    <div class="sidebar-section-label">Workflow Steps</div>
    <div id="sidebar-steps"></div>

    <div class="sidebar-divider" id="score-divider" style="display:none"></div>
    <div class="sidebar-score" id="sidebar-score" style="display:none"></div>
  </div>

  <!-- RIGHT MAIN -->
  <div class="chat-main">
    <!-- Tabs (hidden until complete) -->
    <div class="chat-tabs" id="chat-tabs" style="display:none">
      <button class="chat-tab active" onclick="switchTab('brief',this)">Brief</button>
      <button class="chat-tab" onclick="switchTab('score',this)">Lead Score</button>
      <button class="chat-tab" onclick="switchTab('crm',this)">CRM Export</button>
      <button class="chat-tab" onclick="switchTab('outreach',this)">Outreach</button>
      <button class="chat-tab" onclick="switchTab('proposal',this)">Proposal</button>
    </div>

    <!-- Thread -->
    <div class="chat-thread" id="chat-thread">
      <!-- user query bubble -->
      <div class="msg" id="user-msg">
        <div class="msg-avatar user">You</div>
        <div class="msg-body">
          <div class="msg-meta">
            <span class="msg-name">You</span>
          </div>
          <div class="msg-card" style="border-radius: var(--radius-lg)">
            <div class="msg-section" style="font-size:14px; color:var(--text-primary)">
              Research prospect: <strong id="user-company-name">Loading&hellip;</strong>
            </div>
          </div>
        </div>
      </div>

      <!-- AI thinking / response bubble -->
      <div class="msg" id="ai-msg">
        <div class="msg-avatar">C</div>
        <div class="msg-body">
          <div class="msg-meta">
            <span class="msg-name">Coextend AI</span>
            <span class="msg-tag" id="ai-wf-tag">RESEARCHING</span>
          </div>
          <div id="ai-bubble">
            <!-- filled by JS -->
          </div>
        </div>
      </div>
    </div>
  </div>

</div><!-- end chat-layout -->

<!-- Hidden tab panels (rendered outside visible thread once complete) -->
<div id="tab-score"    class="tab-content-panel" style="display:none;padding:0 0 16px 0;"></div>
<div id="tab-crm"      class="tab-content-panel" style="display:none;padding:0 0 16px 0;"></div>
<div id="tab-outreach" class="tab-content-panel" style="display:none;padding:0 0 16px 0;"></div>
<div id="tab-proposal" class="tab-content-panel" style="display:none;padding:0 0 16px 0;"></div>

<script>
const jobId = {{ job_id | tojson }};
const POLL_MS = 3000;
const TIMEOUT_MS = 300000;

const STEPS = [
  { status:"researching", label:"Searching the web for company information", dur:null },
  { status:"scoring",     label:"Scoring against Coextend ICP rubric",        dur:null },
  { status:"drafting",    label:"Generating founder-ready research brief",     dur:null },
  { status:"complete",    label:"Research complete",                           dur:null },
];

let startTime     = Date.now();
let stepTimes     = {};
let currentBrief  = null;
let currentCrm    = null;
let currentJob    = null;
let activeTab     = "brief";

// ---- sidebar step renderer ----
function renderSidebar(currentStatus) {
  const order = ["pending","researching","scoring","drafting","complete"];
  const idx   = order.indexOf(currentStatus);
  const el    = document.getElementById("sidebar-steps");
  el.innerHTML = STEPS.map(step => {
    const si = order.indexOf(step.status);
    const state = si < idx ? "done" : si === idx ? "running" : "pending";
    const icon  = state==="done" ? "\\u2713" : state==="running" ? "\\u25CF" : "";
    const elapsed = stepTimes[step.status]
      ? ((Date.now()-stepTimes[step.status])/1000).toFixed(1)+"s" : "";
    return \`<div class="wf-step \${state}">
      <div class="wf-icon">\${icon}</div>
      <div class="wf-label">\${esc(step.label)}</div>
      <div class="wf-time">\${state==="done"?"done":state==="running"?elapsed:""}</div>
    </div>\`;
  }).join("");
}

// ---- AI thinking bubble (in-progress) ----
function renderThinking(currentStatus) {
  const order = ["pending","researching","scoring","drafting","complete"];
  const idx   = order.indexOf(currentStatus);
  const aiBubble = document.getElementById("ai-bubble");
  aiBubble.innerHTML = \`<div class="think-bubble">
    \${STEPS.map(step=>{
      const si = order.indexOf(step.status);
      const state = si < idx ? "done" : si === idx ? "running" : "pending";
      const icon = state==="done"
        ? \`<div class="think-circle-done">\\u2713</div>\`
        : state==="running"
          ? \`<div class="think-spinner"></div>\`
          : \`<div class="think-circle-pending"></div>\`;
      const elapsed = stepTimes[step.status]
        ? ((Date.now()-stepTimes[step.status])/1000).toFixed(1)+"s" : "";
      return \`<div class="think-row">
        \${icon}
        <span style="flex:1">\${esc(step.label)}</span>
        <span class="wf-time">\${state==="done"?elapsed:state==="running"?elapsed:""}</span>
      </div>\`;
    }).join("")}
  </div>\`;
}

// ---- poll ----
async function poll() {
  if (Date.now()-startTime > TIMEOUT_MS) {
    setHeader("failed","TIMEOUT"); return;
  }
  try {
    const res = await fetch(\`/api/v1/prospects/\${jobId}\`);
    if (!res.ok) { setTimeout(poll,POLL_MS); return; }
    const job = await res.json();
    currentJob = job;

    const name = job.company_name || "Prospect";
    document.getElementById("hdr-company").textContent = name;
    document.getElementById("user-company-name").textContent = name;

    if (!stepTimes[job.status]) stepTimes[job.status] = Date.now();
    renderSidebar(job.status);
    renderThinking(job.status);

    if (job.status==="failed") {
      setHeader("failed","FAILED");
      document.getElementById("ai-bubble").innerHTML =
        \`<div class="msg-card"><div class="msg-section" style="color:#dc2626">
          Research failed: \${esc(job.error_message||"Unknown error")}
        </div></div>\`;
      return;
    }
    if (job.status==="complete") {
      setHeader("done","COMPLETE");
      await loadResults(job);
      return;
    }
    setTimeout(poll,POLL_MS);
  } catch(e) { setTimeout(poll,POLL_MS*2); }
}

function setHeader(state, label) {
  const dot   = document.getElementById("hdr-dot");
  const badge = document.getElementById("hdr-badge");
  dot.className   = "status-dot " + state;
  badge.className = "live-badge " + (state==="done"?"":"running");
  badge.textContent = label;
}

async function loadResults(job) {
  const [bRes, cRes] = await Promise.all([
    fetch(\`/api/v1/prospects/\${jobId}/brief\`),
    fetch(\`/api/v1/prospects/\${jobId}/crm-export\`),
  ]);
  currentBrief = bRes.ok ? await bRes.json() : null;
  currentCrm   = cRes.ok ? await cRes.json() : null;

  renderComplete();
  document.getElementById("chat-tabs").style.display = "flex";
  document.getElementById("ai-wf-tag").textContent = "WORKFLOW COMPLETE";
}

// ---- MAIN RESPONSE RENDER ----
function renderComplete() {
  const brief = currentBrief;
  const crm   = currentCrm;
  const job   = currentJob;
  if (!brief) {
    document.getElementById("ai-bubble").innerHTML =
      \`<div class="msg-card"><div class="msg-section">Brief unavailable.</div></div>\`;
    return;
  }

  const score   = brief.lead_score || {};
  const band    = (score.band||"low").toLowerCase();
  const snap    = brief.snapshot || {};
  const contact = brief.contact  || {};
  const cr      = brief.company_research || {};
  const companyName = snap.company_name || job.company_name || "Unknown";

  // Score color
  const scoreColor = band==="high" ? "var(--high)" : band==="medium" ? "var(--medium)" : "var(--low)";

  // ---- Show score in sidebar ----
  document.getElementById("score-divider").style.display = "block";
  document.getElementById("sidebar-score").style.display = "block";
  document.getElementById("sidebar-score").innerHTML = \`
    <div class="sidebar-score-row">
      <div style="text-align:center">
        <div class="sidebar-score-num" style="color:\${scoreColor}">\${score.total||0}</div>
        <div class="sidebar-score-label">out of 100</div>
      </div>
      <div>
        <div class="sidebar-score-label">Priority Band</div>
        <div class="sidebar-score-band">
          <span class="badge badge-\${band}">\${score.band||"Low"}</span>
        </div>
      </div>
    </div>
    <div style="padding:10px 0 0;font-size:11px;color:var(--text-muted)">Rubric \${esc(score.rubric_version||"v1.0")}</div>
  \`;

  // ---- BRIEF tab (rendered into chat bubble) ----
  const briefHtml = buildBriefHtml(brief, score, band, snap, contact, cr, companyName, scoreColor);
  document.getElementById("ai-bubble").innerHTML = \`
    <div class="wf-complete-tag">\\u2713 WORKFLOW COMPLETE &nbsp;<span style="color:var(--text-muted);font-weight:400">Prospect Research</span></div>
    <div class="msg-card" id="brief-msg-card">\${briefHtml}</div>
  \`;

  // ---- other tabs ----
  document.getElementById("tab-score").innerHTML    = buildScoreHtml(score, band, scoreColor);
  document.getElementById("tab-crm").innerHTML      = buildCrmHtml(crm);
  document.getElementById("tab-outreach").innerHTML = buildOutreachPlaceholder();
  document.getElementById("tab-proposal").innerHTML = buildProposalPlaceholder();

  // listeners
  document.getElementById("gen-outreach-btn")?.addEventListener("click", generateOutreach);
  document.getElementById("gen-proposal-btn")?.addEventListener("click", generateProposal);
}

function buildBriefHtml(brief, score, band, snap, contact, cr, companyName, scoreColor) {
  const kvSnap    = kvSection(snap);
  const kvContact = kvSection(contact);
  const kvCr      = kvSection(cr);

  return \`
    \${kvSnap ? \`
    <div class="think-step"><span class="chk">\\u2713</span> Search policy documents <span class="dur">&nbsp;</span></div>
    <div class="msg-section">
      <div class="msg-section-title">Company Snapshot</div>
      <div class="msg-kv">\${kvSnap}</div>
    </div>\` : ""}

    \${kvContact ? \`
    <div class="msg-section">
      <div class="msg-section-title">Contact / Decision-Maker</div>
      <div class="msg-kv">\${kvContact}</div>
    </div>\` : ""}

    \${kvCr ? \`
    <div class="msg-section">
      <div class="msg-section-title">Company Research</div>
      <div class="msg-kv">\${kvCr}</div>
    </div>\` : ""}

    \${(brief.projects_signals||[]).length ? \`
    <div class="msg-section">
      <div class="msg-section-title">Projects &amp; Buying Signals</div>
      <table class="msg-table">
        <thead><tr><th>Confidence</th><th>Signal</th><th>Detail</th></tr></thead>
        <tbody>\${findingRows(brief.projects_signals)}</tbody>
      </table>
    </div>\` : ""}

    \${(brief.likely_requirements||[]).length ? \`
    <div class="msg-section">
      <div class="msg-section-title">Likely Requirements <em style="font-weight:normal;font-size:.9em">(hypothesis)</em></div>
      <table class="msg-table">
        <thead><tr><th>Confidence</th><th>Type</th><th>Detail</th></tr></thead>
        <tbody>\${findingRows(brief.likely_requirements)}</tbody>
      </table>
    </div>\` : ""}

    \${(brief.pain_point_hypotheses||[]).length ? \`
    <div class="msg-section">
      <div class="msg-section-title">Pain-Point Hypotheses <em style="font-weight:normal;font-size:.9em">(unconfirmed)</em></div>
      <table class="msg-table">
        <thead><tr><th>Confidence</th><th>Type</th><th>Detail</th></tr></thead>
        <tbody>\${findingRows(brief.pain_point_hypotheses)}</tbody>
      </table>
    </div>\` : ""}

    <div class="msg-section">
      <div class="msg-section-title">Recommended Approach</div>
      <p style="font-size:14px;line-height:1.65;color:var(--text-primary)">\${esc(brief.recommended_approach?.summary||"No recommendation generated.")}</p>
      \${brief.recommended_approach?.angle ? \`<p style="margin-top:8px;font-size:13px;color:var(--text-secondary)"><strong>Angle:</strong> \${esc(brief.recommended_approach.angle)}</p>\` : ""}
      \${(brief.recommended_approach?.key_capabilities_to_lead_with||[]).length ? \`
        <ul style="padding-left:18px;margin-top:8px;font-size:13px;line-height:1.8;color:var(--text-secondary)">
          \${brief.recommended_approach.key_capabilities_to_lead_with.map(c=>\`<li>\${esc(c)}</li>\`).join("")}
        </ul>\` : ""}
    </div>

    \${(brief.risks_unknowns||[]).length ? \`
    <div class="msg-section">
      <div class="msg-section-title">Risks &amp; Unknowns</div>
      <ul style="padding-left:18px;font-size:13px;line-height:1.8;color:var(--text-secondary)">
        \${(brief.risks_unknowns||[]).map(r=>\`<li>\${esc(r)}</li>\`).join("")}
      </ul>
    </div>\` : ""}

    <div class="msg-section">
      <div class="msg-section-title">Next Action</div>
      <p style="font-size:14px;font-weight:600;color:var(--text-primary)">\${esc(brief.next_action?.action||"")}</p>
      \${brief.next_action?.notes ? \`<p style="font-size:13px;color:var(--text-secondary);margin-top:6px">\${esc(brief.next_action.notes)}</p>\` : ""}
    </div>

    \${(brief.sources||[]).length ? \`
    <div class="msg-section">
      <div class="msg-section-title">Reference</div>
      \${(brief.sources||[]).slice(0,4).map(s=>\`
        <span class="ref-chip" style="margin:2px 4px 2px 0;display:inline-flex">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          <a href="\${esc(String(s.url))}" target="_blank" style="color:inherit;text-decoration:none">\${esc((s.title||String(s.url)).slice(0,60))}</a>
        </span>
      \`).join("")}
    </div>\` : ""}

    <div class="msg-section" style="display:flex;gap:10px;flex-wrap:wrap;background:var(--bg-secondary)">
      <a class="btn btn-outline" style="margin-top:0;font-size:13px;padding:8px 14px"
         href="/api/v1/prospects/\${jobId}/brief?format=markdown" download="\${jobId}_brief.md">
        \\u2193 Download Brief
      </a>
    </div>

    <!-- FEEDBACK inside the brief card -->
    <div class="msg-section" style="background:var(--bg-secondary);">
      <div class="msg-section-title" style="margin-bottom:12px">Feedback — Help tune our rubric</div>
      <form id="feedback-form" onsubmit="handleFeedbackSubmit(event)">
        <div style="margin-bottom:12px">
          <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:6px">Was this score accurate?</div>
          <div class="fb-btn-group" id="grp-score">
            <button type="button" class="fb-btn" data-group="score_accuracy" data-val="too_low" onclick="selFb(this)">Too low</button>
            <button type="button" class="fb-btn selected" data-group="score_accuracy" data-val="about_right" onclick="selFb(this)">About right</button>
            <button type="button" class="fb-btn" data-group="score_accuracy" data-val="too_high" onclick="selFb(this)">Too high</button>
          </div>
        </div>
        <div style="margin-bottom:12px">
          <div style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:6px">How was the brief?</div>
          <div class="fb-btn-group" id="grp-brief">
            <button type="button" class="fb-btn" data-group="brief_quality" data-val="poor" onclick="selFb(this)">Poor</button>
            <button type="button" class="fb-btn" data-group="brief_quality" data-val="okay" onclick="selFb(this)">Okay</button>
            <button type="button" class="fb-btn selected" data-group="brief_quality" data-val="good" onclick="selFb(this)">Good</button>
          </div>
        </div>
        <div style="margin-bottom:12px">
          <label style="font-size:12px;color:var(--text-muted);margin-bottom:4px;margin-top:0;display:block">Comments (optional)</label>
          <textarea id="fb-comment" rows="2" placeholder="Any feedback on scoring or brief quality?" style="font-size:13px"></textarea>
        </div>
        <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
          <div style="flex:1;min-width:160px">
            <label style="font-size:12px;color:var(--text-muted);margin-bottom:4px;margin-top:0;display:block">Name / Initials (optional)</label>
            <input type="text" id="fb-name" placeholder="e.g. Sales Rep" style="font-size:13px" />
          </div>
          <button type="submit" class="btn" id="fb-submit" style="margin-top:0;padding:8px 18px;font-size:13px">Submit</button>
        </div>
        <div id="fb-status" style="display:none;margin-top:8px"></div>
      </form>
    </div>
  \`;
}

function buildScoreHtml(score, band, scoreColor) {
  return \`
    <div class="msg" style="padding:20px 24px 0">
      <div class="msg-avatar">C</div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">Lead Score Breakdown</span></div>
        <div class="msg-card">
          <div class="msg-section" style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
            <div style="font-size:40px;font-weight:700;color:\${scoreColor};line-height:1">\${score.total||0}</div>
            <div>
              <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">Priority Band</div>
              <span class="badge badge-\${band}" style="font-size:13px;padding:4px 12px">\${score.band||"Low"}</span>
            </div>
            <div style="margin-left:auto;font-size:12px;color:var(--text-muted)">Rubric \${esc(score.rubric_version||"v1.0")}</div>
          </div>
          <div class="msg-section">
            <div class="msg-section-title">10-Factor Breakdown</div>
            \${(score.breakdown||[]).map(f=>{
              const pct = Math.round((f.points_awarded/f.weight)*100);
              const fc  = f.points_awarded>0?"var(--high)":"var(--border-strong)";
              return \`<div style="margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
                  <span style="color:var(--text-primary)">\${esc(f.factor.replace(/_/g," "))}</span>
                  <span style="color:\${f.points_awarded>0?"var(--high)":"var(--text-muted)"}"><strong>\${f.points_awarded}</strong><span style="color:var(--text-muted)"> / \${f.weight}</span></span>
                </div>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:\${pct}%;background:\${fc}"></div></div>
                \${f.evidence ? \`<div style="font-size:12px;color:var(--text-muted);margin-top:3px">\${esc((f.evidence||"").replace(/[\\[\\]']/g,"").trim())}</div>\` : ""}
              </div>\`;
            }).join("")}
          </div>
        </div>
      </div>
    </div>
  \`;
}

function buildCrmHtml(crm) {
  if (!crm) return \`<div style="padding:20px 24px"><div class="msg"><div class="msg-avatar">C</div><div class="msg-body"><div class="msg-card"><div class="msg-section">CRM export not available.</div></div></div></div></div>\`;
  const kv = obj => Object.entries(obj).filter(([,v])=>v&&v!=="No evidence found")
    .map(([k,v])=>\`<div class="msg-kv-row"><div class="msg-kv-key">\${cap(k.replace(/_/g," "))}</div><div class="msg-kv-val">\${esc(v)}</div></div>\`).join("");
  return \`
    <div class="msg" style="padding:20px 24px 0">
      <div class="msg-avatar">C</div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">CRM Export</span></div>
        <div class="msg-card">
          \${crm.possible_duplicate ? \`<div class="msg-section" style="background:#fffbeb;color:#92400e;font-size:13px">\\u26a0\\ufe0f Possible duplicate — a matching record may already exist.</div>\` : ""}
          <div class="msg-section"><div class="msg-section-title">Company Fields</div><div class="msg-kv">\${kv(crm.company_fields||{})}</div></div>
          <div class="msg-section"><div class="msg-section-title">Contact Fields</div><div class="msg-kv">\${kv(crm.contact_fields||{})}</div></div>
          <div class="msg-section"><div class="msg-section-title">Deal Fields</div><div class="msg-kv">\${kv(crm.deal_fields||{})}</div></div>
          <div class="msg-section" style="display:flex;gap:10px;flex-wrap:wrap;background:var(--bg-secondary)">
            <a class="btn btn-outline" style="margin-top:0;font-size:13px;padding:8px 14px" href="/api/v1/prospects/\${jobId}/crm-export?format=csv" download="\${jobId}_crm.csv">\\u2193 CSV</a>
            <a class="btn btn-outline" style="margin-top:0;font-size:13px;padding:8px 14px" href="/api/v1/prospects/\${jobId}/crm-export" download="\${jobId}_crm.json">\\u2193 JSON</a>
          </div>
        </div>
      </div>
    </div>
  \`;
}

function buildOutreachPlaceholder() {
  return \`
    <div class="msg" style="padding:20px 24px 0">
      <div class="msg-avatar">C</div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">Outreach Drafts</span></div>
        <div class="msg-card">
          <div class="msg-section" style="text-align:center;padding:24px">
            <p style="color:var(--text-muted);font-size:14px;margin-bottom:14px">Generate personalised outreach drafts based on the research findings.</p>
            <button class="btn" id="gen-outreach-btn" style="margin-top:0">Generate Outreach Drafts</button>
          </div>
          <div id="outreach-content"></div>
        </div>
      </div>
    </div>
  \`;
}

function buildProposalPlaceholder() {
  return \`
    <div class="msg" style="padding:20px 24px 0">
      <div class="msg-avatar">C</div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">Proposal Draft</span></div>
        <div class="msg-card">
          <div class="msg-section" style="text-align:center;padding:24px">
            <p style="color:var(--text-muted);font-size:14px;margin-bottom:14px">Generate a tailored Scope of Work proposal grounded in Coextend's proposal template.</p>
            <button class="btn" id="gen-proposal-btn" style="margin-top:0">Generate Proposal Draft</button>
          </div>
          <div id="proposal-content"></div>
        </div>
      </div>
    </div>
  \`;
}

// ---- TAB SWITCHING ----
function switchTab(name, el) {
  activeTab = name;
  document.querySelectorAll(".chat-tab").forEach(t=>t.classList.remove("active"));
  el.classList.add("active");

  const thread = document.getElementById("chat-thread");
  const panels = document.querySelectorAll(".tab-content-panel");

  if (name === "brief") {
    thread.style.display = "flex";
    panels.forEach(p=>p.style.display="none");
  } else {
    thread.style.display = "none";
    panels.forEach(p=>p.style.display="none");
    const panel = document.getElementById("tab-"+name);
    if (panel) {
      panel.style.display = "block";
      // Move panel inside chat-main
      document.querySelector(".chat-thread").parentNode.appendChild(panel);
      panel.style.overflowY = "auto";
      panel.style.flex = "1";
    }
  }
}

// ---- helper: kv rows ----
function kvSection(obj) {
  return Object.entries(obj)
    .filter(([,v])=>v&&v!=="No evidence found"&&v!=="no evidence found")
    .map(([k,v])=>\`<div class="msg-kv-row"><div class="msg-kv-key">\${cap(k.replace(/_/g," "))}</div><div class="msg-kv-val">\${esc(v)}</div></div>\`)
    .join("");
}

function findingRows(items) {
  return (items||[]).filter(f=>f.value).map(f=>\`
    <tr>
      <td><span class="badge badge-\${f.label.toLowerCase()}">\${f.label}</span></td>
      <td style="color:var(--text-muted)">\${esc(f.field.replace(/_/g," "))}</td>
      <td style="font-size:13px">\${esc(f.value)}</td>
    </tr>\`).join("");
}

// ---- outreach / proposal ----
async function generateOutreach() {
  const btn = document.getElementById("gen-outreach-btn");
  btn.disabled = true; btn.textContent = "Generating\\u2026";
  try {
    const res = await fetch(\`/api/v1/prospects/\${jobId}/outreach\`,{method:"POST"});
    const data = await res.json();
    if (!res.ok) { document.getElementById("outreach-content").innerHTML=\`<div class="msg-section" style="color:#dc2626">\${esc(data.detail||"Error")}</div>\`; return; }
    renderOutreach(data);
    btn.style.display = "none";
  } catch(e) { document.getElementById("outreach-content").innerHTML=\`<div class="msg-section" style="color:#dc2626">Network error.</div>\`; }
}

function renderOutreach(d) {
  const t1=d.email_touch_1||d.email_body||"";
  const t2=d.email_touch_2||"";
  const t3=d.email_touch_3||"";
  const liConn=d.linkedin_connection||d.linkedin_message||"";
  const liPitch=d.linkedin_pitch||"";
  document.getElementById("outreach-content").innerHTML=\`
    <div class="msg-section" style="background:var(--accent-lighter);color:var(--accent-primary);font-size:13px">\\u26a0\\ufe0f \${esc(d.review_note||"Draft — review before sending")}</div>
    <div class="msg-section">
      <div class="msg-section-title">Subject Line</div>
      <p style="font-size:14px;font-weight:600;color:var(--accent-primary)">\${esc(d.email_subject||"")}</p>
    </div>
    \${t1?\`<div class="msg-section"><div class="msg-section-title">Touch 1 — Cold Outreach (Day 1)</div><div class="msg-pre">\${esc(t1)}</div></div>\`:""}
    \${t2?\`<div class="msg-section"><div class="msg-section-title">Touch 2 — Soft Bump (+3-4 Days)</div><div class="msg-pre">\${esc(t2)}</div></div>\`:""}
    \${t3?\`<div class="msg-section"><div class="msg-section-title">Touch 3 — Value-Add (+7-8 Days)</div><div class="msg-pre">\${esc(t3)}</div></div>\`:""}
    \${liConn?\`<div class="msg-section"><div class="msg-section-title">LinkedIn Connection Note</div><div class="msg-pre">\${esc(liConn)}</div><div style="font-size:12px;color:var(--text-muted);margin-top:4px">\${liConn.length}/300 chars \${liConn.length<=300?"\\u2713":"\\u26a0"}</div></div>\`:""}
    \${liPitch?\`<div class="msg-section"><div class="msg-section-title">LinkedIn Follow-Up Pitch</div><div class="msg-pre">\${esc(liPitch)}</div></div>\`:""}
  \`;
}

async function generateProposal() {
  const btn = document.getElementById("gen-proposal-btn");
  btn.disabled=true; btn.textContent="Generating\\u2026";
  try {
    const res = await fetch(\`/api/v1/prospects/\${jobId}/proposal\`,{method:"POST"});
    const data = await res.json();
    if (!res.ok) { document.getElementById("proposal-content").innerHTML=\`<div class="msg-section" style="color:#dc2626">\${esc(data.detail||"Error")}</div>\`; return; }
    renderProposal(data);
    btn.style.display="none";
  } catch(e) { document.getElementById("proposal-content").innerHTML=\`<div class="msg-section" style="color:#dc2626">Network error.</div>\`; }
}

function renderProposal(p) {
  const comm=p.commercial_options||{};
  const qa=p.qa_protocol||[];
  const assump=p.assumptions_exclusions||[];
  const deliv=p.deliverables||[];
  document.getElementById("proposal-content").innerHTML=\`
    <div class="msg-section" style="background:var(--accent-lighter);color:var(--accent-primary);font-size:13px">\\u26a0\\ufe0f \${esc(p.review_note||"Draft — review required")}</div>
    <div class="msg-section"><div class="msg-section-title">Client Requirement</div><p style="font-size:13px;line-height:1.6">\${esc(p.client_requirement||"")}</p></div>
    <div class="msg-section"><div class="msg-section-title">Proposed Scope</div><p style="font-size:13px;line-height:1.6">\${esc(p.proposed_scope||"")}</p></div>
    \${deliv.length?\`<div class="msg-section"><div class="msg-section-title">Key Deliverables</div><ul style="padding-left:18px;font-size:13px;line-height:1.8">\${deliv.map(d=>\`<li>\${esc(d)}</li>\`).join("")}</ul></div>\`:""}
    <div class="msg-section"><div class="msg-section-title">Programme &amp; Turnaround</div><p style="font-size:13px;line-height:1.6">\${esc(p.programme_turnaround||"")}</p></div>
    \${Object.values(comm).some(Boolean)?\`<div class="msg-section"><div class="msg-section-title">Commercial Models</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:8px">\${[["Option 1: Package",comm.option_1_package],["Option 2: Hourly",comm.option_2_hourly],["Option 3: Retainer",comm.option_3_retainer]].filter(([,v])=>v).map(([l,v])=>\`<div style="background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;padding:12px"><div style="font-size:11px;font-weight:600;color:var(--accent-primary);text-transform:uppercase;margin-bottom:4px">\${l}</div><div style="font-size:13px;line-height:1.5">\${esc(v)}</div></div>\`).join("")}</div></div>\`:""}
    \${qa.length?\`<div class="msg-section"><div class="msg-section-title">QA Protocol</div><ul style="padding-left:18px;font-size:13px;line-height:1.8">\${qa.map(q=>\`<li>\${esc(q)}</li>\`).join("")}</ul></div>\`:""}
    \${assump.length?\`<div class="msg-section"><div class="msg-section-title">Assumptions &amp; Exclusions</div><ul style="padding-left:18px;font-size:13px;line-height:1.8;color:var(--text-secondary)">\${assump.map(a=>\`<li>\${esc(a)}</li>\`).join("")}</ul></div>\`:""}
    <div class="msg-section" style="background:var(--bg-secondary)"><a class="btn btn-outline" style="margin-top:0;font-size:13px;padding:8px 14px" href="/api/v1/prospects/\${jobId}/proposal?format=markdown" download="\${jobId}_proposal.md">\\u2193 Download Proposal</a></div>
  \`;
}

// ---- feedback ----
function selFb(btn) {
  const g = btn.getAttribute("data-group");
  document.querySelectorAll(\`.fb-btn[data-group="\${g}"]\`).forEach(b=>b.classList.remove("selected"));
  btn.classList.add("selected");
}

async function handleFeedbackSubmit(ev) {
  ev.preventDefault();
  const sb  = document.getElementById("fb-submit");
  const ste = document.getElementById("fb-status");
  sb.disabled=true; sb.textContent="Submitting\\u2026";
  const sel = g => document.querySelector(\`.fb-btn[data-group="\${g}"].selected\`)?.getAttribute("data-val")||"";
  try {
    const res = await fetch(\`/api/v1/prospects/\${jobId}/feedback\`,{
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        score_accuracy: sel("score_accuracy")||"about_right",
        brief_quality:  sel("brief_quality") ||"good",
        outreach_quality: "not_applicable",
        comment: document.getElementById("fb-comment")?.value?.trim()||null,
        submitted_by: document.getElementById("fb-name")?.value?.trim()||null,
      }),
    });
    if (res.ok) {
      ste.innerHTML=\`<div class="alert alert-info" style="margin:0;padding:8px 12px;font-size:13px">\\u2713 Feedback recorded!</div>\`;
      ste.style.display="block"; sb.textContent="Submitted";
      setTimeout(()=>{sb.disabled=false;sb.textContent="Submit again";},2000);
    } else {
      const e=await res.json();
      ste.innerHTML=\`<div class="alert alert-error" style="margin:0;padding:8px 12px;font-size:13px">Failed: \${esc(e.detail||"Error")}</div>\`;
      ste.style.display="block"; sb.disabled=false; sb.textContent="Submit";
    }
  } catch(e) {
    ste.innerHTML=\`<div class="alert alert-error" style="margin:0;padding:8px 12px;font-size:13px">Network error.</div>\`;
    ste.style.display="block"; sb.disabled=false; sb.textContent="Submit";
  }
}

function esc(s) { return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function cap(s) { return s.charAt(0).toUpperCase()+s.slice(1); }

// kick off
renderSidebar("pending");
renderThinking("pending");
poll();
</script>
{% endblock %}
""")
new_results.close()
print("Written results_new.html")
