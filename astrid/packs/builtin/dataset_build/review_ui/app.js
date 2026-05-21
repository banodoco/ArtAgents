const PAGE_LIMIT = 50;
const VISIBLE_WINDOW_SIZE = 8;
const REJECT_REASONS = [
  "watermark",
  "wrong_scene",
  "wrong_character",
  "bad_motion",
  "low_quality",
  "wrong_content",
  "rights_concern",
  "other",
];

const state = {
  token: new URLSearchParams(window.location.search).get("token") || "",
  offset: 0,
  limit: PAGE_LIMIT,
  total: 0,
  status: "",
  items: [],
  activeIndex: 0,
  baseStateVersion: 0,
  revisions: new Map(),
};

const els = {
  summary: document.getElementById("summary"),
  statusFilter: document.getElementById("statusFilter"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  save: document.getElementById("save"),
  submit: document.getElementById("submit"),
  pageMeta: document.getElementById("pageMeta"),
  itemList: document.getElementById("itemList"),
  detail: document.getElementById("detail"),
};

function authHeaders() {
  return state.token ? {"X-Session-Token": state.token} : {};
}

async function loadState() {
  if (!state.token) return;
  const response = await fetch("/state.json", {headers: authHeaders()});
  if (!response.ok) return;
  const payload = await response.json();
  state.baseStateVersion = Number(payload.state_version || 0);
}

async function loadPage(offset = state.offset) {
  state.offset = Math.max(0, offset);
  const params = new URLSearchParams({
    offset: String(state.offset),
    limit: String(state.limit),
  });
  if (state.status) params.set("status", state.status);
  const response = await fetch(`/data.json?${params.toString()}`);
  if (!response.ok) throw new Error(`data load failed: ${response.status}`);
  const payload = await response.json();
  state.items = Array.isArray(payload.items) ? payload.items : [];
  state.total = Number(payload.total || state.items.length);
  state.activeIndex = Math.min(state.activeIndex, Math.max(0, state.items.length - 1));
  render();
}

function render() {
  els.summary.textContent = `${state.total} item${state.total === 1 ? "" : "s"}${state.status ? ` (${state.status})` : ""}`;
  els.pageMeta.textContent = `Showing ${state.offset + 1}-${Math.min(state.offset + state.items.length, state.offset + state.limit)} of ${state.total}`;
  els.prevPage.disabled = state.offset === 0;
  els.nextPage.disabled = state.offset + state.limit >= state.total;
  renderVisibleList();
  renderDetail();
}

function renderVisibleList() {
  const windowStart = Math.max(0, Math.min(state.activeIndex - 3, Math.max(0, state.items.length - VISIBLE_WINDOW_SIZE)));
  const windowEnd = Math.min(state.items.length, windowStart + VISIBLE_WINDOW_SIZE);
  const visibleItems = state.items.slice(windowStart, windowEnd);
  els.itemList.replaceChildren(...visibleItems.map((item, localIndex) => {
    const index = windowStart + localIndex;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "item-button";
    button.setAttribute("aria-current", String(index === state.activeIndex));
    button.addEventListener("click", () => selectIndex(index));
    button.innerHTML = `
      <span>${state.offset + index + 1}</span>
      <span>
        <span class="item-id">${escapeHtml(item.item_id || item.source_id || "item")}</span>
        <span class="item-caption">${escapeHtml(captionText(item))}</span>
      </span>
      <span class="status ${escapeHtml(reviewStatus(item))}">${escapeHtml(reviewStatus(item))}</span>
    `;
    const li = document.createElement("li");
    li.appendChild(button);
    return li;
  }));
}

function renderDetail() {
  const item = state.items[state.activeIndex];
  if (!item) {
    els.detail.textContent = "No items on this page.";
    return;
  }
  const revision = state.revisions.get(item.item_id) || {};
  const caption = revision.edited_caption ?? captionText(item);
  els.detail.innerHTML = `
    <div class="viewer">
      <div>
        <video src="${escapeAttr(item.media_path || "")}" controls preload="metadata"></video>
      </div>
      <div class="panel">
        <h2>${escapeHtml(item.item_id || item.source_id || "Item")}</h2>
        <dl class="meta-grid">
          <dt>Bucket</dt><dd>${escapeHtml(item.bucket || "")}</dd>
          <dt>Status</dt><dd>${escapeHtml(revision.decision || reviewStatus(item))}</dd>
          <dt>Duration</dt><dd>${escapeHtml(String(item.duration_s ?? ""))}</dd>
          <dt>Hash</dt><dd>${escapeHtml(item.content_hash || "")}</dd>
        </dl>
        <h3>Caption</h3>
        <textarea id="captionEdit" class="caption-editor">${escapeHtml(caption)}</textarea>
        <div class="decision-row">
          <button type="button" data-decision="accepted">Accept</button>
          <button type="button" data-decision="rejected">Reject</button>
        </div>
        <div class="reason-grid">
          ${REJECT_REASONS.map((reason, index) => `<button type="button" data-reason="${reason}">${index + 1}. ${reason}</button>`).join("")}
        </div>
        <h3>Metadata</h3>
        <pre>${escapeHtml(JSON.stringify(item.source_metadata || item.judge_result || {}, null, 2))}</pre>
      </div>
    </div>
  `;
  els.detail.querySelector("#captionEdit").addEventListener("input", event => {
    updateRevision(item, {edited_caption: event.target.value});
  });
  els.detail.querySelectorAll("[data-decision]").forEach(button => {
    button.addEventListener("click", () => {
      updateRevision(item, {decision: button.dataset.decision});
      render();
    });
  });
  els.detail.querySelectorAll("[data-reason]").forEach(button => {
    button.addEventListener("click", () => {
      updateRevision(item, {decision: "rejected", reject_reason: button.dataset.reason});
      render();
    });
  });
}

function updateRevision(item, patch) {
  const itemId = item.item_id;
  const existing = state.revisions.get(itemId) || {item_id: itemId};
  state.revisions.set(itemId, {
    ...existing,
    ...patch,
    reviewed_at: new Date().toISOString(),
  });
}

async function saveDiff() {
  const revisions = Array.from(state.revisions.values());
  if (!revisions.length) return;
  const response = await fetch("/save", {
    method: "POST",
    headers: {"Content-Type": "application/json", ...authHeaders()},
    body: JSON.stringify({
      base_state_version: state.baseStateVersion,
      revisions,
    }),
  });
  if (!response.ok) throw new Error(`save failed: ${response.status}`);
  const payload = await response.json();
  state.baseStateVersion = Number(payload.state_version || state.baseStateVersion);
  state.revisions.clear();
  await loadPage(state.offset);
}

async function submitReview() {
  await saveDiff();
  const response = await fetch("/submit", {
    method: "POST",
    headers: {"Content-Type": "application/json", ...authHeaders()},
    body: JSON.stringify({submitted_at: new Date().toISOString()}),
  });
  if (!response.ok) throw new Error(`submit failed: ${response.status}`);
}

function selectIndex(index) {
  state.activeIndex = Math.max(0, Math.min(index, state.items.length - 1));
  render();
}

function captionText(item) {
  return item.caption && item.caption.text ? item.caption.text : "";
}

function reviewStatus(item) {
  return item.review_status || "pending";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function nextItem() {
  if (state.activeIndex + 1 < state.items.length) {
    selectIndex(state.activeIndex + 1);
  } else if (state.offset + state.limit < state.total) {
    loadPage(state.offset + state.limit);
  }
}

function previousItem() {
  if (state.activeIndex > 0) {
    selectIndex(state.activeIndex - 1);
  } else if (state.offset > 0) {
    loadPage(Math.max(0, state.offset - state.limit)).then(() => selectIndex(state.items.length - 1));
  }
}

document.addEventListener("keydown", event => {
  if (event.target && ["TEXTAREA", "INPUT", "SELECT"].includes(event.target.tagName) && event.key !== "Enter") return;
  const item = state.items[state.activeIndex];
  if (!item) return;
  if (event.key === "ArrowRight") nextItem();
  if (event.key === "ArrowLeft") previousItem();
  if (event.key.toLowerCase() === "y") updateRevision(item, {decision: "accepted"});
  if (event.key.toLowerCase() === "n") updateRevision(item, {decision: "rejected"});
  if (/^[1-8]$/.test(event.key)) updateRevision(item, {decision: "rejected", reject_reason: REJECT_REASONS[Number(event.key) - 1]});
  if (event.key.toLowerCase() === "e") {
    const editor = document.getElementById("captionEdit");
    if (editor) editor.focus();
  }
  if (event.key === "Enter") saveDiff();
  render();
});

els.prevPage.addEventListener("click", () => loadPage(Math.max(0, state.offset - state.limit)));
els.nextPage.addEventListener("click", () => loadPage(state.offset + state.limit));
els.save.addEventListener("click", () => saveDiff());
els.submit.addEventListener("click", () => submitReview());
els.statusFilter.addEventListener("change", () => {
  state.status = els.statusFilter.value;
  state.offset = 0;
  state.activeIndex = 0;
  loadPage(0);
});

loadState().then(() => loadPage()).catch(error => {
  els.summary.textContent = error.message;
});
