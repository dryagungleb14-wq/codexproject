const form = document.getElementById("upload-form");
const fileInput = document.getElementById("audio");
const consentInput = document.getElementById("consent");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) {
    statusEl.textContent = "Выберите аудиофайл";
    return;
  }

  statusEl.textContent = "Анализируем звонок...";
  resultEl.classList.add("hidden");
  resultEl.innerHTML = "";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("consent", consentInput.checked ? "true" : "false");

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Ошибка анализа");
    }

    const { data } = await response.json();
    renderResult(data);
    statusEl.textContent = "Готово";
  } catch (error) {
    console.error(error);
    statusEl.textContent = error.message;
  }
});

function renderResult(data) {
  resultEl.innerHTML = `
    <div class="result-header">
      <div>
        <h2>Отчёт по звонку ${escapeHtml(data.callId)}</h2>
        <p class="meta">Язык: ${escapeHtml(data.language || "-")} · Длительность: ${
    data.durationSec?.toFixed ? data.durationSec.toFixed(2) : data.durationSec
  } c</p>
      </div>
      <div class="badge">${data.consent ? "С согласия" : "Без подтверждения"}</div>
    </div>
    <div class="result-grid">
      ${renderScoreCard("Эмпатия", data.scores?.empathy ?? 0)}
      ${renderScoreCard("Комплаенс", data.scores?.compliance ?? 0)}
      ${renderScoreCard("Структура", data.scores?.structure ?? 0)}
    </div>
    <div class="artifacts">
      ${renderArtifactLink("JSON", data.artifacts?.json)}
      ${renderArtifactLink("HTML", data.artifacts?.html)}
      ${renderArtifactLink("Транскрипт", data.artifacts?.transcript)}
    </div>
    <h3 class="section-title">Операционные метрики</h3>
    ${renderOperational(data.operational)}
    <h3 class="section-title">Чек-лист</h3>
    ${renderChecklist(data.scores?.checklist || [])}
    <h3 class="section-title">Хайлайты</h3>
    ${renderHighlights(data.scores?.highlights || [])}
    <h3 class="section-title">Стенограмма</h3>
    ${renderTranscript(data.segments || [])}
  `;

  resultEl.classList.remove("hidden");
}

function renderScoreCard(title, value) {
  const displayValue = typeof value === "number" ? value.toFixed(2) : "-";
  return `
    <div class="score-card">
      <h3>${escapeHtml(title)}</h3>
      <div class="value">${displayValue}</div>
    </div>
  `;
}

function renderOperational(operational = {}) {
  return `
    <div class="score-card">
      <p>Тишина: ${(operational.silencePct ?? 0).toFixed(2)}%</p>
      <p>Пересечения: ${(operational.overlapPct ?? 0).toFixed(2)}%</p>
      <p>Темп речи: ${escapeHtml(JSON.stringify(operational.speechRateWpm || {}))}</p>
      <p>Перебивания: ${escapeHtml(JSON.stringify(operational.interruptions || {}))}</p>
    </div>
  `;
}

function renderChecklist(items) {
  if (!items.length) {
    return '<p class="muted">Нет пунктов чек-листа</p>';
  }

  const rows = items
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(String(item.id ?? ""))}</td>
          <td>${item.passed ? "✅" : "⚠️"}</td>
          <td>${escapeHtml(String(item.reason ?? ""))}</td>
          <td>${escapeHtml(String(item.evidence ?? ""))}</td>
          <td>${escapeHtml(String(item.ts ?? ""))}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <div class="table-wrapper">
      <table class="table">
        <thead><tr><th>ID</th><th>Статус</th><th>Комментарий</th><th>Цитата</th><th>TS</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderHighlights(items) {
  if (!items.length) {
    return '<p class="muted">Нет хайлайтов</p>';
  }

  return `
    <ul class="list">
      ${items
        .map(
          (item) => `
            <li>
              <strong>${escapeHtml(String(item.type ?? ""))}</strong>
              <div>${escapeHtml(String(item.quote ?? ""))}</div>
              <span class="badge">${escapeHtml(String(item.ts ?? ""))}</span>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderTranscript(segments) {
  if (!segments.length) {
    return '<p class="muted">Нет расшифровки</p>';
  }

  const rows = segments
    .map(
      (segment) => `
        <tr>
          <td>${escapeHtml(String(segment.ts ?? ""))}</td>
          <td>${escapeHtml(String(segment.speaker ?? ""))}</td>
          <td>${escapeHtml(String(segment.text ?? ""))}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <div class="table-wrapper">
      <table class="table">
        <thead><tr><th>Таймкод</th><th>Роль</th><th>Текст</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderArtifactLink(label, info) {
  if (!info) {
    return "";
  }

  const url = info.url || info.path;
  if (!url) {
    return "";
  }

  return `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/"/g, "&quot;");
}
