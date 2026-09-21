/**
 * Investment Research Swarm — Frontend Controller
 * ChatGPT-Style UI with real-time Server-Sent Events (SSE) streaming,
 * multi-agent checklist animation, Chart.js visualizations, and session history.
 */

// State Management
let currentSessionId = null;
let currentTicker = null;
let currentReportMarkdown = "";
let chartInstance = null;

// DOM Elements
const chatViewport = document.getElementById("chat-viewport");
const welcomeHero = document.getElementById("welcome-hero");
const messagesContainer = document.getElementById("messages-container");
const chatForm = document.getElementById("chat-form");
const queryInput = document.getElementById("user-query-input");
const submitBtn = document.getElementById("submit-query-btn");
const historyList = document.getElementById("history-list");
const btnNewResearch = document.getElementById("btn-new-research");
const themeToggleBtn = document.getElementById("theme-toggle-btn");
const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
const sidebar = document.getElementById("sidebar");
const btnExportMarkdown = document.getElementById("btn-export-markdown");
const quickTickers = document.querySelectorAll(".ticker-chip");
const promptCards = document.querySelectorAll(".prompt-card");

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadHistory();
  setupEventListeners();
  autoResizeTextarea();
});

function setupEventListeners() {
  // Chat submission
  chatForm.addEventListener("submit", handleFormSubmit);

  // New research button
  btnNewResearch.addEventListener("click", resetToNewChat);

  // Theme toggle
  themeToggleBtn.addEventListener("click", toggleTheme);

  // Sidebar toggle
  sidebarToggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });

  // Quick ticker chips
  quickTickers.forEach(chip => {
    chip.addEventListener("click", () => {
      const ticker = chip.getAttribute("data-ticker");
      startResearchQuery(`Analyze ${ticker} for the last 12 months. Include financial performance, market performance, recent developments, quantitative metrics, and risks.`);
    });
  });

  // Prompt suggestion cards
  promptCards.forEach(card => {
    card.addEventListener("click", () => {
      const promptText = card.getAttribute("data-prompt");
      startResearchQuery(promptText);
    });
  });

  // Copy Markdown button
  btnExportMarkdown.addEventListener("click", () => {
    if (!currentReportMarkdown) {
      alert("No research report available to copy yet.");
      return;
    }
    navigator.clipboard.writeText(currentReportMarkdown).then(() => {
      const originalText = btnExportMarkdown.innerHTML;
      btnExportMarkdown.innerHTML = "<span>✓ Copied!</span>";
      setTimeout(() => {
        btnExportMarkdown.innerHTML = originalText;
      }, 2000);
    });
  });

  // Textarea enter-to-submit (Shift+Enter for newline)
  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });
}

function autoResizeTextarea() {
  queryInput.addEventListener("input", () => {
    queryInput.style.height = "auto";
    queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + "px";
  });
}

// Theme Handlers
function initTheme() {
  const saved = localStorage.getItem("irs_theme") || "dark";
  if (saved === "light") {
    document.body.classList.remove("dark-theme");
    document.body.classList.add("light-theme");
  } else {
    document.body.classList.remove("light-theme");
    document.body.classList.add("dark-theme");
  }
}

function toggleTheme() {
  if (document.body.classList.contains("dark-theme")) {
    document.body.classList.remove("dark-theme");
    document.body.classList.add("light-theme");
    localStorage.setItem("irs_theme", "light");
  } else {
    document.body.classList.remove("light-theme");
    document.body.classList.add("dark-theme");
    localStorage.setItem("irs_theme", "dark");
  }
}

function resetToNewChat() {
  currentSessionId = null;
  currentTicker = null;
  currentReportMarkdown = "";
  messagesContainer.innerHTML = "";
  welcomeHero.style.display = "flex";
  queryInput.value = "";
  queryInput.placeholder = "Ask about any company (e.g. 'Analyze NVDA for the last 12 months')...";
  queryInput.focus();
}

// Research Execution and SSE Streaming
async function handleFormSubmit(e) {
  e.preventDefault();
  const text = queryInput.value.trim();
  if (!text) return;

  queryInput.value = "";
  queryInput.style.height = "auto";

  // If a session already exists and has a report, handle as a contextual follow-up
  if (currentSessionId && currentReportMarkdown) {
    appendUserMessage(text);
    await handleFollowupChat(currentSessionId, text);
    return;
  }

  // Otherwise, start fresh research session
  await startResearchQuery(text);
}

async function startResearchQuery(queryText) {
  welcomeHero.style.display = "none";
  appendUserMessage(queryText);

  // Create Swarm Progress UI Container
  const assistantBubble = createAssistantMessageContainer();
  const checklistId = `checklist-${Date.now()}`;
  assistantBubble.innerHTML = `
    <div class="agent-checklist-card" id="${checklistId}">
      <div class="checklist-header">
        <div class="checklist-title">Agent Execution Swarm</div>
        <div class="spinner"></div>
      </div>
      <div class="checklist-items">
        <div class="checklist-item active" data-step="InputGuardrail">
          <span class="step-icon"><div class="spinner"></div></span>
          <span>Input Guardrails</span>
        </div>
        <div class="checklist-item" data-step="Orchestrator Agent">
          <span class="step-icon">•</span>
          <span>Orchestrator Agent</span>
        </div>
        <div class="checklist-item" data-step="SEC Agent">
          <span class="step-icon">•</span>
          <span>SEC Agent (10-K/Q)</span>
        </div>
        <div class="checklist-item" data-step="Market Agent">
          <span class="step-icon">•</span>
          <span>Market Agent (yfinance)</span>
        </div>
        <div class="checklist-item" data-step="Research Agent">
          <span class="step-icon">•</span>
          <span>Research Agent (Tavily)</span>
        </div>
        <div class="checklist-item" data-step="Quant Agent">
          <span class="step-icon">•</span>
          <span>Quant Agent (Python)</span>
        </div>
        <div class="checklist-item" data-step="Risk Agent">
          <span class="step-icon">•</span>
          <span>Risk Agent</span>
        </div>
        <div class="checklist-item" data-step="Critic Agent">
          <span class="step-icon">•</span>
          <span>Critic Agent (Auditing)</span>
        </div>
        <div class="checklist-item" data-step="Report Agent">
          <span class="step-icon">•</span>
          <span>Report Agent</span>
        </div>
        <div class="checklist-item" data-step="Output Guardrail">
          <span class="step-icon">•</span>
          <span>Output Guardrails</span>
        </div>
      </div>
    </div>
    <div class="report-content-area" style="display:none;"></div>
  `;

  scrollToBottom();
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText }),
    });

    const data = await res.json();
    if (!res.ok || data.status === "BLOCKED") {
      assistantBubble.innerHTML = `
        <div class="agent-checklist-card" style="border-color: var(--danger);">
          <div style="color: var(--danger); font-weight: 600; margin-bottom: 6px;">⚠️ Guardrail Alert</div>
          <div style="font-size: 0.9rem; color: var(--text-secondary);">${data.reason || "Request was blocked by security policies."}</div>
        </div>
      `;
      submitBtn.disabled = false;
      return;
    }

    currentSessionId = data.session_id;
    connectEventStream(currentSessionId, assistantBubble, checklistId);

  } catch (err) {
    assistantBubble.innerHTML = `<div style="color:var(--danger)">Error connecting to research swarm: ${err.message}</div>`;
    submitBtn.disabled = false;
  }
}

function connectEventStream(sessionId, container, checklistId) {
  const eventSource = new EventSource(`/api/research/stream/${sessionId}`);
  const checklistEl = document.getElementById(checklistId);
  const reportArea = container.querySelector(".report-content-area");

  eventSource.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);

      // Handle Step progress
      if (payload.event === "step") {
        updateChecklistStep(checklistEl, payload.agent, payload.status);
      }

      // Handle Final Report delivery
      if (payload.event === "report") {
        currentReportMarkdown = payload.report || "";
        currentTicker = payload.ticker;

        // Render Markdown report
        reportArea.style.display = "block";
        reportArea.innerHTML = renderMarkdownSafely(currentReportMarkdown);

        // Render Interactive Price Chart if historical closes exist
        if (payload.market_data && payload.market_data.historical_closes && payload.market_data.historical_closes.length > 0) {
          renderMarketChart(reportArea, payload.market_data);
        }

        // Render Collapsible Agent Trace
        if (payload.agent_runs) {
          renderAgentTrace(reportArea, payload.agent_runs, payload.critic);
        }

        // Change checklist spinner to green checkmark
        const spinner = checklistEl.querySelector(".checklist-header .spinner");
        if (spinner) {
          spinner.outerHTML = `<span style="color:var(--success); font-weight:600; font-size:0.85rem;">✓ Swarm Complete</span>`;
        }

        loadHistory();
        scrollToBottom();
      }

      // Handle Completion
      if (payload.event === "done") {
        eventSource.close();
        submitBtn.disabled = false;
        queryInput.placeholder = `Ask a follow-up about ${currentTicker || 'the research'}...`;
        queryInput.focus();
      }

      // Handle Error
      if (payload.event === "error") {
        eventSource.close();
        submitBtn.disabled = false;
        reportArea.style.display = "block";
        reportArea.innerHTML = `<div style="color:var(--danger); padding:10px;">Swarm Execution Error: ${payload.error}</div>`;
      }
    } catch (err) {
      console.error("Error parsing SSE frame:", err);
    }
  };

  eventSource.onerror = (err) => {
    console.warn("EventSource encountered an error or closed:", err);
    eventSource.close();
    submitBtn.disabled = false;
  };
}

function updateChecklistStep(checklistEl, agentName, status) {
  if (!checklistEl) return;
  const items = checklistEl.querySelectorAll(".checklist-item");

  items.forEach(item => {
    const step = item.getAttribute("data-step");
    if (step && agentName.toLowerCase().includes(step.toLowerCase())) {
      item.classList.remove("active");
      item.classList.add("completed");
      const icon = item.querySelector(".step-icon");
      if (icon) icon.innerHTML = `<span class="check-mark">✓</span>`;
    }
  });

  // Activate next pending item
  const pending = checklistEl.querySelector(".checklist-item:not(.completed)");
  if (pending) {
    pending.classList.add("active");
    const icon = pending.querySelector(".step-icon");
    if (icon && !icon.querySelector(".spinner")) {
      icon.innerHTML = `<div class="spinner"></div>`;
    }
  }
}

// Interactive Chart.js Rendering
function renderMarketChart(reportArea, marketData) {
  const chartCard = document.createElement("div");
  chartCard.className = "chart-card";
  const canvasId = `chart-${Date.now()}`;

  chartCard.innerHTML = `
    <div class="chart-card-header">
      <div class="chart-card-title">Historical Price & Return Performance (${marketData.ticker || ''})</div>
      <div style="font-size:0.75rem; color:var(--text-muted);">Source: Finance MCP (yfinance)</div>
    </div>
    <div class="chart-canvas-wrapper">
      <canvas id="${canvasId}"></canvas>
    </div>
  `;

  // Insert before the Recent Developments (section 6) or after Market Performance (section 4)
  const headings = reportArea.querySelectorAll("h2");
  let targetHeader = null;
  headings.forEach(h => {
    if (h.textContent.includes("Market Performance") || h.textContent.includes("Recent Developments")) {
      targetHeader = h;
    }
  });

  if (targetHeader && targetHeader.parentNode) {
    targetHeader.parentNode.insertBefore(chartCard, targetHeader.nextSibling);
  } else {
    reportArea.appendChild(chartCard);
  }

  // Draw Chart
  const ctx = document.getElementById(canvasId).getContext("2d");
  const dates = marketData.historical_dates || [];
  const closes = marketData.historical_closes || [];

  new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [{
        label: `${marketData.ticker || 'Share'} Price (USD)`,
        data: closes,
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59, 130, 246, 0.08)",
        borderWidth: 2,
        fill: true,
        tension: 0.2,
        pointRadius: closes.length > 30 ? 1 : 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: "index",
          intersect: false,
          backgroundColor: "#1a1e24",
          titleColor: "#f3f4f6",
          bodyColor: "#9ca3af",
          borderColor: "#2b313a",
          borderWidth: 1,
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#6b7280", font: { size: 10 }, maxTicksLimit: 8 }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: {
            color: "#6b7280",
            font: { size: 10 },
            callback: (val) => `$${val}`
          }
        }
      }
    }
  });
}

// Collapsible Agent Trace
function renderAgentTrace(reportArea, agentRuns, critic) {
  const traceCard = document.createElement("details");
  traceCard.className = "agent-trace-accordion";

  let rowsHtml = "";
  let totalLatency = 0;
  agentRuns.forEach(run => {
    totalLatency += (run.latency_ms || 0);
    rowsHtml += `
      <div class="trace-row">
        <span class="trace-agent">✓ ${run.agent_name}</span>
        <span class="trace-metric">${run.latency_ms || 0}ms • Status: ${run.status}</span>
      </div>
    `;
  });

  const criticStatus = critic ? critic.status : "PASS";
  const verified = critic ? critic.verified_claims : 0;

  traceCard.innerHTML = `
    <summary class="trace-summary">
      <span>🔍 Expand Swarm Execution Telemetry (${totalLatency}ms total latency)</span>
      <span>Critic: <b style="color:var(--success)">${criticStatus}</b> (${verified} verified)</span>
    </summary>
    <div class="trace-content">
      ${rowsHtml}
    </div>
  `;

  reportArea.appendChild(traceCard);
}

// Follow-Up Chat Handling
async function handleFollowupChat(sessionId, question) {
  const assistantBubble = createAssistantMessageContainer();
  assistantBubble.innerHTML = `<div class="spinner"></div> Answering from conversational memory...`;
  scrollToBottom();
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: question }),
    });
    const data = await res.json();
    assistantBubble.innerHTML = renderMarkdownSafely(data.answer || "No response received.");
  } catch (err) {
    assistantBubble.innerHTML = `<div style="color:var(--danger)">Error answering follow-up: ${err.message}</div>`;
  } finally {
    submitBtn.disabled = false;
    scrollToBottom();
    queryInput.placeholder = `Ask another follow-up about ${currentTicker || 'the company'}...`;
    queryInput.focus();
  }
}

// Sidebar History Loading
async function loadHistory() {
  try {
    const res = await fetch("/api/history?limit=15");
    if (!res.ok) return;
    const history = await res.json();

    if (!history || history.length === 0) {
      historyList.innerHTML = `<div class="history-empty">No previous research yet.</div>`;
      return;
    }

    historyList.innerHTML = "";
    history.forEach(item => {
      const el = document.createElement("div");
      el.className = "history-item";
      if (currentSessionId === item.session_id) el.classList.add("active");

      el.innerHTML = `
        <div class="history-item-ticker">${item.ticker} <span style="font-size:0.75rem; color:var(--text-muted)">• ${item.period || '12M'}</span></div>
        <div class="history-item-query" title="${item.query}">${item.company_name || item.query}</div>
      `;

      el.addEventListener("click", () => loadSavedSession(item.session_id));
      historyList.appendChild(el);
    });
  } catch (err) {
    console.warn("Could not load research history:", err);
  }
}

async function loadSavedSession(sessionId) {
  try {
    const res = await fetch(`/api/research/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();

    currentSessionId = data.session_id;
    currentTicker = data.ticker;
    currentReportMarkdown = data.report;

    welcomeHero.style.display = "none";
    messagesContainer.innerHTML = "";

    const messages = data.chat_messages || [];

    if (messages.length > 0) {
      // Reconstruct entire multi-turn conversation memory
      messages.forEach((msg, idx) => {
        if (msg.role === "user") {
          appendUserMessage(msg.content);
        } else if (msg.role === "assistant") {
          const assistantBubble = createAssistantMessageContainer();

          if (idx === 1) {
            // Initial research dossier report turn
            const reportArea = document.createElement("div");
            reportArea.className = "report-content-area";
            reportArea.innerHTML = renderMarkdownSafely(msg.content || currentReportMarkdown);
            assistantBubble.appendChild(reportArea);

            if (data.market_data && data.market_data.historical_closes && data.market_data.historical_closes.length > 0) {
              renderMarketChart(reportArea, data.market_data);
            }
            if (data.agent_runs) {
              renderAgentTrace(reportArea, data.agent_runs, data.critic);
            }
          } else {
            // Subsequent follow-up conversational answers
            assistantBubble.innerHTML = renderMarkdownSafely(msg.content);
          }
        }
      });
    } else {
      // Fallback if no chat_messages records exist
      appendUserMessage(data.query);

      const assistantBubble = createAssistantMessageContainer();
      const reportArea = document.createElement("div");
      reportArea.className = "report-content-area";
      reportArea.innerHTML = renderMarkdownSafely(currentReportMarkdown);
      assistantBubble.appendChild(reportArea);

      if (data.market_data && data.market_data.historical_closes && data.market_data.historical_closes.length > 0) {
        renderMarketChart(reportArea, data.market_data);
      }
      if (data.agent_runs) {
        renderAgentTrace(reportArea, data.agent_runs, data.critic);
      }
    }

    loadHistory();
    queryInput.placeholder = `Ask a follow-up about ${currentTicker}...`;
    scrollToBottom();
  } catch (err) {
    console.error("Failed loading saved session:", err);
  }
}

// Markdown Rendering with Clickable URL Enrichment
function renderMarkdownSafely(markdownText) {
  if (!markdownText) return "";
  try {
    const rawHtml = marked.parse(markdownText);
    const container = document.createElement("div");
    container.innerHTML = rawHtml;

    // Direct clickable link enhancement
    const links = container.querySelectorAll("a");
    links.forEach(a => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
      if (!a.querySelector(".ext-icon") && !a.textContent.includes("↗")) {
        const icon = document.createElement("span");
        icon.className = "ext-icon";
        icon.innerHTML = " ↗";
        icon.style.fontSize = "0.8em";
        icon.style.opacity = "0.8";
        a.appendChild(icon);
      }
    });

    return container.innerHTML;
  } catch (e) {
    console.error("Markdown rendering error:", e);
    return escapeHtml(markdownText);
  }
}

// UI Helpers
function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="message-bubble">${escapeHtml(text)}</div>
    <div class="message-avatar">You</div>
  `;
  messagesContainer.appendChild(row);
  scrollToBottom();
}

function createAssistantMessageContainer() {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="message-avatar">IRS</div>
    <div class="message-bubble report-markdown"></div>
  `;
  messagesContainer.appendChild(row);
  return row.querySelector(".message-bubble");
}

function scrollToBottom() {
  chatViewport.scrollTop = chatViewport.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
