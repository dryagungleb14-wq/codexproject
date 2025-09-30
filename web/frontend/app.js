const form = document.getElementById("analyze-form");
const audioInput = document.getElementById("audio-input");
const consentInput = document.getElementById("consent-input");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const resultsSection = document.getElementById("results");
const summaryEl = document.getElementById("summary");
const scoreCardEl = document.getElementById("score-card");
const operationalEl = document.getElementById("operational");
const checklistEl = document.getElementById("checklist");
const highlightsEl = document.getElementById("highlights");
const transcriptEl = document.getElementById("transcript");
const downloadJsonBtn = document.getElementById("download-json");
const openHtmlBtn = document.getElementById("open-html");

let lastPayload = null;

const fmtPercent = (value) => `${Number(value || 0).toFixed(1)}%`;

function setStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.dataset.type = type;
}

function clearContainer(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function renderSummary(payload) {
  clearContainer(summaryEl);
  const items = [
    { label: "Call ID", value: payload.callId },
    { label: "Язык", value: payload.lang?.toUpperCase?.() || "–" },
    {
      label: "Длительность",
      value: `${(payload.durationSec ?? 0).toFixed(1)} сек`,
    },
    { label: "Согласие", value: payload.consent ? "Получено" : "Не указано" },
  ];

  if (payload.partial) {
    items.push({ label: "LLM", value: "Частичный ответ" });
  }

  for (const item of items) {
    const wrapper = document.createElement("div");
    wrapper.className = "summary-item";

    const label = document.createElement("span");
    label.className = "summary-item__label";
    label.textContent = item.label;

    const value = document.createElement("span");
    value.className = "summary-item__value";
    value.textContent = item.value ?? "–";

    wrapper.append(label, value);
    summaryEl.appendChild(wrapper);
  }
}

function renderScores(scores = {}) {
  clearContainer(scoreCardEl);
  const map = [
    ["Эмпатия", scores.empathy],
    ["Комплаенс", scores.compliance],
    ["Структура", scores.structure],
  ];

  for (const [label, rawValue] of map) {
    const row = document.createElement("div");
    row.className = "score-row";

    const labelEl = document.createElement("span");
    labelEl.className = "score-label";
    labelEl.textContent = label;

    const progress = document.createElement("div");
    progress.className = "score-bar";

    const fill = document.createElement("div");
    fill.className = "score-bar__fill";
    const value = typeof rawValue === "number" ? Math.max(0, Math.min(1, rawValue)) : 0;
    fill.style.transform = `scaleX(${value})`;
    fill.style.transformOrigin = "left";

    const valueLabel = document.createElement("span");
    valueLabel.className = "score-value";
    valueLabel.textContent = (rawValue ?? 0).toFixed(2);

    progress.appendChild(fill);
    row.append(labelEl, progress, valueLabel);
    scoreCardEl.appendChild(row);
  }
}

function renderOperational(operational = {}) {
  clearContainer(operationalEl);
  const speech = operational.speechRateWpm || {};
  const interruptions = operational.interruptions || {};
  const items = [
    ["Тишина", fmtPercent(operational.silencePct)],
    ["Перекрытия", fmtPercent(operational.overlapPct)],
    ["Темп речи (менеджер)", `${speech.manager ?? 0} wpm`],
    ["Темп речи (клиент)", `${speech.client ?? 0} wpm`],
    ["Перебивания менеджера", interruptions.byManager ?? 0],
    ["Перебивания клиента", interruptions.byClient ?? 0],
  ];

  for (const [label, value] of items) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    operationalEl.append(dt, dd);
  }
}

function renderChecklist(list = []) {
  clearContainer(checklistEl);
  if (!list.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Чек-лист пуст";
    checklistEl.appendChild(empty);
    return;
  }

  for (const item of list) {
    const card = document.createElement("article");
    card.className = "card";

    const title = document.createElement("div");
    title.className = "card__title";
    title.textContent = `${item.id || "Пункт"} · ${(item.score ?? 0)}/${item.max ?? 0}`;

    const status = document.createElement("div");
    status.className = "card__meta";
    status.textContent = item.passed ? "Выполнено" : "Нужно внимание";

    const reason = document.createElement("p");
    reason.textContent = item.reason || "—";

    const evidence = document.createElement("p");
    evidence.className = "card__meta";
    evidence.textContent = item.evidence ? `${item.ts || ""} · ${item.evidence}` : "";

    card.append(title, status, reason);
    if (evidence.textContent) {
      card.appendChild(evidence);
    }

    checklistEl.appendChild(card);
  }
}

function renderHighlights(items = []) {
  clearContainer(highlightsEl);
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Нет выделенных моментов";
    highlightsEl.appendChild(empty);
    return;
  }

  for (const item of items) {
    const card = document.createElement("article");
    card.className = "card card--highlight";

    const title = document.createElement("div");
    title.className = "card__title";
    title.textContent = item.type || "Событие";

    const quote = document.createElement("p");
    quote.textContent = item.quote || "—";

    const meta = document.createElement("div");
    meta.className = "card__meta";
    meta.textContent = item.ts || "";

    card.append(title, quote);
    if (meta.textContent) {
      card.appendChild(meta);
    }

    highlightsEl.appendChild(card);
  }
}

function renderTranscript(transcript = []) {
  clearContainer(transcriptEl);
  if (!transcript.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Нет сегментов";
    transcriptEl.appendChild(empty);
    return;
  }

  for (const seg of transcript) {
    const row = document.createElement("div");
    row.className = "transcript-row";

    const meta = document.createElement("div");
    meta.className = "transcript-meta";
    meta.textContent = `${seg.speaker || "?"} · ${seg.start.toFixed(2)}–${seg.end.toFixed(2)} c`;

    const text = document.createElement("div");
    text.className = "transcript-text";
    text.textContent = seg.text || "";

    row.append(meta, text);
    transcriptEl.appendChild(row);
  }
}

function render(payload) {
  renderSummary(payload);
  renderScores(payload.scores);
  renderOperational(payload.operational);
  renderChecklist(payload.checklist);
  renderHighlights(payload.highlights);
  renderTranscript(payload.transcript);
  resultsSection.hidden = false;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = audioInput.files?.[0];
  if (!file) {
    setStatus("Выберите аудиофайл", "error");
    return;
  }
  if (file.size > 100 * 1024 * 1024) {
    setStatus("Файл больше 100 МБ", "error");
    return;
  }

  const formData = new FormData();
  formData.append("audio", file);
  if (consentInput.checked) {
    formData.append("consent", "true");
  }

  submitBtn.disabled = true;
  setStatus("Файл загружен, запускаем анализ...");

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Не удалось выполнить анализ");
    }

    lastPayload = payload;
    render(payload);
    setStatus("Готово! Отчёт сохранён в артефактах.", "success");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Ошибка при анализе", "error");
  } finally {
    submitBtn.disabled = false;
  }
});

function downloadJson() {
  if (!lastPayload) {
    setStatus("Сначала выполните анализ", "error");
    return;
  }
  const blob = new Blob([JSON.stringify(lastPayload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${lastPayload.callId || "report"}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

downloadJsonBtn?.addEventListener("click", downloadJson);

openHtmlBtn?.addEventListener("click", () => {
  if (!lastPayload?.reportHtml) {
    setStatus("Нет HTML отчёта", "error");
    return;
  }
  const blob = new Blob([lastPayload.reportHtml], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function pingHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) {
      throw new Error("health check failed");
    }
  } catch (error) {
    console.warn("API health check failed", error);
  }
}

pingHealth();
