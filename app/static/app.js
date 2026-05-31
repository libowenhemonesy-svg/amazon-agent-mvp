const endpoints = {
  report: "/reports/daily",
  alerts: "/alerts",
  metrics: "/metrics/daily",
  run: "/jobs/daily-run",
  demo: "/demo/load-sample",
  selectionResearch: "/api/selection/research",
};

const statusOptions = [
  ["pending", "待处理"],
  ["processing", "处理中"],
  ["done", "已处理"],
  ["reviewed", "已复盘"],
  ["ignored", "忽略"],
];

let currentAlerts = [];

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".upload-card").forEach((form) => {
    form.addEventListener("submit", uploadFile);
    initDragAndDrop(form);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", activateNavItem);
  });
  document.getElementById("run-analysis").addEventListener("click", runAnalysis);
  document.getElementById("load-demo").addEventListener("click", loadDemo);
  document.getElementById("refresh-results").addEventListener("click", refreshResults);
  document.getElementById("reset-day").addEventListener("click", resetDay);
  document.getElementById("sidebar-toggle").addEventListener("click", toggleSidebar);
  document.getElementById("global-search").addEventListener("input", syncGlobalSearch);
  document.getElementById("sample-date").addEventListener("click", () => {
    document.getElementById("run-date").value = "2026-01-07";
  });
  document.getElementById("run-date").addEventListener("change", refreshResults);
  document.getElementById("alert-search").addEventListener("input", renderFilteredAlerts);
  document.getElementById("severity-filter").addEventListener("change", renderFilteredAlerts);
  document.getElementById("status-filter").addEventListener("change", renderFilteredAlerts);
  refreshResults();
});

function initDragAndDrop(form) {
  const dropZone = form.querySelector(".drop-zone");
  const fileInput = form.querySelector("input[type=file]");
  const fileLabel = form.querySelector(".file-type");

  if (!dropZone) return;

  // 点击 dropZone 触发文件选择
  dropZone.addEventListener("click", (e) => {
    e.preventDefault();
    fileInput.click();
  });

  // 点击标签触发文件选择
  if (fileLabel) {
    fileLabel.addEventListener("click", (e) => {
      e.preventDefault();
      fileInput.click();
    });
  }

  // 文件选择后更新显示
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      const fileName = fileInput.files[0].name;
      dropZone.querySelector("span").textContent = fileName;
      form.classList.add("has-file");
    }
  });

  // 拖拽事件
  form.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    form.classList.add("drag-over");
  });

  form.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    form.classList.remove("drag-over");
  });

  form.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    form.classList.remove("drag-over");

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      const fileName = files[0].name;
      dropZone.querySelector("span").textContent = fileName;
      form.classList.add("has-file");

      // 自动触发上传
      const submitEvent = new Event("submit", { cancelable: true });
      form.dispatchEvent(submitEvent);
    }
  });
}

function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("is-open");
}

// 页面标题映射
const pageTitles = {
  overview: { title: "运营总览", subtitle: "销售 · 广告 · 库存 · 质量异常监控" },
  imports: { title: "数据导入", subtitle: "上传 CSV/Excel 文件导入运营数据" },
  analytics: { title: "风险分析", subtitle: "查看风险等级分布和模块统计" },
  tasks: { title: "异常任务", subtitle: "查看每日简报和异常告警" },
  "ai-selection": { title: "AI 选品", subtitle: "Chrome 插件采集商品 · AI 分析选品" },
  chat: { title: "AI 助手", subtitle: "智能对话查询运营数据" },
  battlefield: { title: "战场地图", subtitle: "竞品分析 · 市场份额 · 关键词洞察" },
  diagnosis: { title: "运营天眼", subtitle: "产品健康度诊断 · 优化建议" },
  "sales-monitor": { title: "销售监控", subtitle: "实时监控销售数据，自动识别异常波动" },
  "ads-analysis": { title: "广告分析", subtitle: "深度分析广告投放效果，优化广告策略" },
  "inventory-agent": { title: "库存管家", subtitle: "智能库存管理，避免断货和积压" },
  automation: { title: "自动化任务", subtitle: "定时分析 · 自动同步 · 竞品监控" },
  settings: { title: "ERP 对接", subtitle: "配置易仓ERP和亚马逊店铺连接" },
};

function activateNavItem(event) {
  event.preventDefault();

  const navItem = event.currentTarget;
  const pageName = navItem.dataset.page;

  // 更新导航状态
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-active"));
  navItem.classList.add("is-active");
  document.getElementById("sidebar").classList.remove("is-open");

  // 隐藏所有页面
  document.querySelectorAll(".page").forEach((page) => {
    page.style.display = "none";
  });

  // 显示目标页面
  const targetPage = document.getElementById("page-" + pageName);
  if (targetPage) {
    targetPage.style.display = "block";
  }

  // 更新顶部标题
  const titleInfo = pageTitles[pageName];
  if (titleInfo) {
    document.getElementById("page-title").textContent = titleInfo.title;
    document.getElementById("page-subtitle").textContent = titleInfo.subtitle;
  }

  // 特殊页面初始化
  if (pageName === "settings") {
    loadSettings();
  }
  if (pageName === "ai-selection") {
    loadChromeProducts();
  }
}

function syncGlobalSearch(event) {
  document.getElementById("alert-search").value = event.currentTarget.value;
  renderFilteredAlerts();
}

async function loadDemo() {
  const jobStatus = document.getElementById("job-status");
  const button = document.getElementById("load-demo");
  button.disabled = true;
  setNotice(jobStatus, "正在载入示例数据并分析…", true);
  try {
    const data = await requestJson(endpoints.demo, { method: "POST" });
    document.getElementById("run-date").value = data.date;
    setNotice(
      jobStatus,
      `示例已就绪：${data.metrics_created} 条指标，${data.alerts_created} 条异常，飞书：${feishuStatus(data)}`,
      true,
    );
    await refreshResults();
  } catch (error) {
    setNotice(jobStatus, error.message, false);
  } finally {
    button.disabled = false;
  }
}

async function uploadFile(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const output = form.querySelector("output");
  const fileInput = form.querySelector("input[type=file]");
  const button = form.querySelector("button");
  if (!fileInput.files.length) {
    setNotice(output, "请选择文件", false);
    return;
  }
  const body = new FormData();
  body.append("file", fileInput.files[0]);
  button.disabled = true;
  setNotice(output, "上传中…", true);
  try {
    const data = await requestJson(form.dataset.endpoint, { method: "POST", body });
    setNotice(output, `已导入 ${data.imported} 行`, true);
  } catch (error) {
    setNotice(output, error.message, false);
  } finally {
    button.disabled = false;
  }
}

async function runAnalysis() {
  const runDate = getRunDate();
  const jobStatus = document.getElementById("job-status");
  const button = document.getElementById("run-analysis");
  button.disabled = true;
  setNotice(jobStatus, "分析中…", true);
  try {
    const data = await requestJson(`${endpoints.run}?run_date=${encodeURIComponent(runDate)}`, {
      method: "POST",
    });
    setNotice(
      jobStatus,
      `已生成 ${data.metrics_created} 条指标，${data.alerts_created} 条异常，飞书：${feishuStatus(data)}`,
      true,
    );
    await refreshResults();
  } catch (error) {
    setNotice(jobStatus, error.message, false);
  } finally {
    button.disabled = false;
  }
}

async function resetDay() {
  const runDate = getRunDate();
  const jobStatus = document.getElementById("job-status");
  const button = document.getElementById("reset-day");
  if (!window.confirm(`确定要清空 ${runDate} 的所有分析结果吗？此操作不可撤销。`)) return;
  button.disabled = true;
  setNotice(jobStatus, "清理中…", true);
  try {
    const data = await requestJson(`${endpoints.run}?run_date=${encodeURIComponent(runDate)}`, {
      method: "DELETE",
    });
    setNotice(jobStatus, `已清理 ${data.deleted_alerts} 条异常`, true);
    await refreshResults();
  } catch (error) {
    setNotice(jobStatus, error.message, false);
  } finally {
    button.disabled = false;
  }
}

async function refreshResults() {
  const runDate = getRunDate();
  const refreshButton = document.getElementById("refresh-results");
  refreshButton.disabled = true;
  try {
    const [report, alerts] = await Promise.all([
      fetchOptional(`${endpoints.report}?date=${encodeURIComponent(runDate)}`),
      fetchOptional(`${endpoints.alerts}?date=${encodeURIComponent(runDate)}`),
    ]);
    renderReport(report);
    currentAlerts = alerts || [];
    renderFilteredAlerts();
    document.getElementById("last-updated").textContent = `刚刚刷新 ${new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  } catch (error) {
    setNotice(document.getElementById("job-status"), error.message, false);
  } finally {
    refreshButton.disabled = false;
  }
}

function renderReport(report) {
  const riskCount = document.getElementById("risk-count");
  const pendingCount = document.getElementById("pending-count");
  const highCount = document.getElementById("high-count");
  const inventoryCount = document.getElementById("inventory-count");
  const summary = document.getElementById("report-summary");
  const topRisks = document.getElementById("top-risks");

  if (!report) {
    riskCount.textContent = "-";
    pendingCount.textContent = "-";
    highCount.textContent = "-";
    inventoryCount.textContent = "-";
    summary.textContent = "暂无日报";
    topRisks.innerHTML = "";
    renderBars("risk-bars", {}, severityLabels);
    renderBars("module-bars", {}, moduleLabels);
    return;
  }

  const data = report.report_data || {};
  riskCount.textContent = report.risk_count ?? 0;
  pendingCount.textContent = report.pending_count ?? 0;
  highCount.textContent = data.severity_counts?.high ?? 0;
  inventoryCount.textContent = data.module_counts?.inventory ?? 0;
  summary.textContent = report.summary || "暂无日报";
  topRisks.innerHTML = (data.top_risks || []).map(renderRisk).join("");
  renderBars("risk-bars", data.severity_counts || {}, severityLabels);
  renderBars("module-bars", data.module_counts || {}, moduleLabels);
}

const severityLabels = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const moduleLabels = {
  sales: "销售",
  ads: "广告",
  inventory: "库存",
  profit: "利润",
  quality: "质量",
  other: "其他",
};

function renderBars(containerId, counts, labels) {
  const container = document.getElementById(containerId);
  const entries = Object.entries(labels).map(([key, label]) => [key, label, counts[key] || 0]);
  const maxValue = Math.max(1, ...entries.map((entry) => entry[2]));
  container.innerHTML = entries
    .map(([key, label, value]) => {
      const width = Math.round((value / maxValue) * 100);
      return `
        <div class="bar-row">
          <span>${escapeHtml(label)}</span>
          <div class="bar-track"><div class="bar-fill bar-${escapeHtml(key)}" style="width: ${width}%"></div></div>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
    })
    .join("");
}

function renderRisk(risk) {
  const actions = (risk.recommended_actions || [])
    .map((action) => `<li>${escapeHtml(action)}</li>`)
    .join("");
  const severity = risk.severity || "medium";
  const severityClass = `severity-${severity}`;
  return `
    <div class="risk-item ${severityClass}">
      <div class="risk-title">
        <span class="risk-sku">${escapeHtml(risk.sku || "-")}</span>
        ${renderSeverityBadge(severity)}
      </div>
      <div class="risk-type">${escapeHtml(risk.alert_type || "-")}</div>
      <p class="risk-summary">${escapeHtml(risk.summary || "")}</p>
      ${actions ? `<div class="risk-actions-wrap"><strong>建议操作：</strong><ul class="risk-actions">${actions}</ul></div>` : ""}
    </div>
  `;
}

function renderFilteredAlerts() {
  const search = document.getElementById("alert-search").value.trim().toLowerCase();
  const severity = document.getElementById("severity-filter").value;
  const status = document.getElementById("status-filter").value;
  const filtered = currentAlerts.filter((alert) => {
    const haystack = `${alert.sku || ""} ${alert.alert_type || ""} ${alert.reason || ""}`.toLowerCase();
    const matchesSearch = !search || haystack.includes(search);
    const matchesSeverity = severity === "all" || alert.severity === severity;
    const matchesStatus = status === "all" || alert.status === status;
    return matchesSearch && matchesSeverity && matchesStatus;
  });
  renderAlerts(filtered);
}

function renderAlerts(alerts) {
  const body = document.getElementById("alerts-body");
  if (!alerts.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">暂无匹配异常</td></tr>';
    return;
  }
  body.innerHTML = alerts
    .map((alert) => {
      const result = alert.agent_result || {};
      return `
        <tr>
          <td>${escapeHtml(alert.sku)}</td>
          <td>${escapeHtml(alert.alert_type)}</td>
          <td>${renderSeverityBadge(alert.severity)}</td>
          <td>
            <strong>${escapeHtml(result.summary || alert.reason || "")}</strong>
            ${renderActionList(result.recommended_actions || [])}
          </td>
          <td>${renderStatusSelect(alert)}</td>
        </tr>
      `;
    })
    .join("");
  body.querySelectorAll("select[data-alert-id]").forEach((select) => {
    select.addEventListener("change", updateAlertStatus);
  });
}

function renderActionList(actions) {
  if (!actions.length) return "";
  return `<ul class="risk-actions">${actions.slice(0, 3).map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ul>`;
}

function renderStatusSelect(alert) {
  const options = statusOptions
    .map(([value, label]) => {
      const selected = alert.status === value ? "selected" : "";
      return `<option value="${value}" ${selected}>${label}</option>`;
    })
    .join("");
  return `<select class="status-select" data-alert-id="${alert.id}" aria-label="${escapeHtml(alert.sku)} 状态">${options}</select>`;
}

function renderSeverityBadge(severity) {
  const normalized = severity || "medium";
  const icons = {
    high: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    medium: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    low: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };
  const icon = icons[normalized] || icons.medium;
  return `<span class="severity-badge severity-${escapeHtml(normalized)}">${icon} ${escapeHtml(severityLabels[normalized] || normalized)}</span>`;
}

async function updateAlertStatus(event) {
  const select = event.currentTarget;
  const alertId = select.dataset.alertId;
  const row = select.closest("tr");
  select.disabled = true;
  try {
    await requestJson(`/alerts/${alertId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: select.value }),
    });
    await refreshResults();
  } catch (error) {
    setNotice(select, error.message, false);
    if (row) {
      const statusCell = row.querySelector("td:last-child");
      if (statusCell) {
        const existingError = statusCell.querySelector(".notice-error");
        if (existingError) existingError.remove();
        const errorEl = document.createElement("span");
        errorEl.className = "notice-error";
        errorEl.textContent = error.message;
        errorEl.setAttribute("role", "alert");
        statusCell.appendChild(errorEl);
        setTimeout(() => errorEl.remove(), 5000);
      }
    }
  } finally {
    select.disabled = false;
  }
}

async function fetchOptional(url) {
  const response = await fetch(url);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = await response.text();
    try {
      const parsed = JSON.parse(message);
      message = parsed.detail || message;
    } catch {
      // Keep raw response text.
    }
    throw new Error(message);
  }
  return response.json();
}

function getRunDate() {
  return document.getElementById("run-date").value;
}

function setNotice(element, message, ok) {
  element.textContent = message;
  element.className = ok ? "notice-ok" : "notice-error";
}

function feishuStatus(data) {
  return data.feishu_sync?.status || "unknown";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ==================== 聊天功能 ====================

let chatConversationId = "default";
let chatIsStreaming = false;

// 初始化聊天
function initChat() {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const quickBtns = document.querySelectorAll(".quick-btn");

  if (chatForm) {
    chatForm.addEventListener("submit", handleChatSubmit);
  }

  quickBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const question = btn.dataset.question;
      if (question) {
        chatInput.value = question;
        chatForm.dispatchEvent(new Event("submit"));
      }
    });
  });
}

// 处理聊天提交
async function handleChatSubmit(event) {
  event.preventDefault();

  const chatInput = document.getElementById("chat-input");
  const message = chatInput.value.trim();

  if (!message || chatIsStreaming) return;

  // 清空输入
  chatInput.value = "";

  // 隐藏欢迎界面
  const welcome = document.querySelector(".chat-welcome");
  if (welcome) {
    welcome.style.display = "none";
  }

  // 添加用户消息
  addChatMessage("user", message);

  // 开始流式响应
  chatIsStreaming = true;
  updateChatStatus("正在思考...");

  // 添加打字指示器
  const typingId = addTypingIndicator();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        conversation_id: chatConversationId,
      }),
    });

    if (!response.ok) {
      throw new Error("请求失败");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let assistantContent = "";
    let messageElement = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split("\n");

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;

        try {
          const event = JSON.parse(line.slice(6));

          switch (event.type) {
            case "token":
              if (!messageElement) {
                // 移除打字指示器，创建消息元素
                removeTypingIndicator(typingId);
                messageElement = addChatMessage("assistant", "");
              }
              assistantContent += event.content;
              updateMessageContent(messageElement, assistantContent);
              break;

            case "tool_start":
              if (!messageElement) {
                removeTypingIndicator(typingId);
                messageElement = addChatMessage("assistant", "");
              }
              addToolCallIndicator(messageElement, event.tool, "执行中...");
              updateChatStatus(`正在查询 ${event.tool}...`);
              break;

            case "tool_end":
              updateToolCallStatus(messageElement, event.tool, "完成");
              break;

            case "done":
              chatConversationId = event.conversation_id || chatConversationId;
              break;

            case "error":
              throw new Error(event.content);
          }
        } catch (e) {
          if (e.message !== "请求失败") {
            console.error("解析事件失败:", e);
          }
        }
      }
    }

    // 如果没有收到内容，显示默认消息
    if (!assistantContent && !messageElement) {
      removeTypingIndicator(typingId);
      addChatMessage("assistant", "抱歉，我无法处理您的请求。请稍后再试。");
    }
  } catch (error) {
    removeTypingIndicator(typingId);
    addChatMessage("assistant", `错误: ${error.message}`);
  } finally {
    chatIsStreaming = false;
    updateChatStatus("在线");
    scrollToBottom();
  }
}

// 添加聊天消息
function addChatMessage(role, content) {
  const messagesContainer = document.getElementById("chat-messages");

  const messageDiv = document.createElement("div");
  messageDiv.className = `chat-message ${role}`;

  const avatarDiv = document.createElement("div");
  avatarDiv.className = "message-avatar";
  avatarDiv.innerHTML =
    role === "user"
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 01 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 01 7 7h1a1 1 0 01 1 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 01 1-1h1a7 7 0 01 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 01 2-2z"/></svg>';

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.textContent = content;

  messageDiv.appendChild(avatarDiv);
  messageDiv.appendChild(contentDiv);

  messagesContainer.appendChild(messageDiv);
  scrollToBottom();

  return messageDiv;
}

// 更新消息内容
function updateMessageContent(messageElement, content) {
  const contentDiv = messageElement.querySelector(".message-content");
  if (contentDiv) {
    // 将换行符转换为 <br> 标签
    const html = escapeHtml(content).replace(/\n/g, '<br>');
    contentDiv.innerHTML = html;
    scrollToBottom();
  }
}

// 添加工具调用指示器
function addToolCallIndicator(messageElement, toolName, status) {
  const contentDiv = messageElement.querySelector(".message-content");
  if (!contentDiv) return;

  const toolDiv = document.createElement("div");
  toolDiv.className = "tool-call";
  toolDiv.dataset.tool = toolName;
  toolDiv.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
    <span class="tool-name">${escapeHtml(toolName)}</span>
    <span class="tool-status">${escapeHtml(status)}</span>
  `;

  contentDiv.appendChild(toolDiv);
  scrollToBottom();
}

// 更新工具调用状态
function updateToolCallStatus(messageElement, toolName, status) {
  const toolDiv = messageElement.querySelector(`.tool-call[data-tool="${toolName}"]`);
  if (toolDiv) {
    const statusSpan = toolDiv.querySelector(".tool-status");
    if (statusSpan) {
      statusSpan.textContent = status;
    }
  }
}

// 添加打字指示器
function addTypingIndicator() {
  const messagesContainer = document.getElementById("chat-messages");
  const typingDiv = document.createElement("div");
  typingDiv.className = "typing-indicator";
  typingDiv.id = "typing-" + Date.now();
  typingDiv.innerHTML = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;
  messagesContainer.appendChild(typingDiv);
  scrollToBottom();
  return typingDiv.id;
}

// 移除打字指示器
function removeTypingIndicator(id) {
  const typingDiv = document.getElementById(id);
  if (typingDiv) {
    typingDiv.remove();
  }
}

// 更新聊天状态
function updateChatStatus(status) {
  const statusElement = document.getElementById("chat-status");
  if (statusElement) {
    statusElement.textContent = status;
  }
}

// 滚动到底部
function scrollToBottom() {
  const messagesContainer = document.getElementById("chat-messages");
  if (messagesContainer) {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

// 在 DOMContentLoaded 中初始化聊天
document.addEventListener("DOMContentLoaded", initChat);

// ==================== 设置功能 ====================

// 加载设置
async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    const settings = await response.json();

    // 易仓设置
    if (settings.eccang) {
      document.getElementById("eccang-app-key").value = settings.eccang.app_key || "";
      document.getElementById("eccang-base-url").value = settings.eccang.base_url || "https://open.eccang.com";
      const eccangStatus = document.getElementById("eccang-status");
      if (settings.eccang.connected) {
        eccangStatus.textContent = "已连接";
        eccangStatus.classList.add("connected");
      } else {
        eccangStatus.textContent = "未连接";
        eccangStatus.classList.remove("connected");
      }
    }

    // 亚马逊设置
    if (settings.amazon) {
      document.getElementById("amazon-seller-id").value = settings.amazon.seller_id || "";
      document.getElementById("amazon-marketplace").value = settings.amazon.marketplace || "US";
      const amazonStatus = document.getElementById("amazon-status");
      if (settings.amazon.connected) {
        amazonStatus.textContent = "已连接";
        amazonStatus.classList.add("connected");
      } else {
        amazonStatus.textContent = "未连接";
        amazonStatus.classList.remove("connected");
      }
    }
  } catch (error) {
    console.error("加载设置失败:", error);
  }
}

// 初始化设置表单
function initSettings() {
  const eccangForm = document.getElementById("eccang-form");
  const amazonForm = document.getElementById("amazon-form");

  if (eccangForm) {
    eccangForm.addEventListener("submit", saveEccangSettings);
  }

  if (amazonForm) {
    amazonForm.addEventListener("submit", saveAmazonSettings);
  }
}

// 保存易仓设置
async function saveEccangSettings(event) {
  event.preventDefault();

  const appKey = document.getElementById("eccang-app-key").value.trim();
  const appSecret = document.getElementById("eccang-app-secret").value.trim();
  const baseUrl = document.getElementById("eccang-base-url").value.trim();
  const messageEl = document.getElementById("eccang-message");

  if (!appKey || !appSecret) {
    showMessage(messageEl, "请填写 App Key 和 App Secret", "error");
    return;
  }

  try {
    const response = await fetch("/api/settings/eccang", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        app_key: appKey,
        app_secret: appSecret,
        base_url: baseUrl,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showMessage(messageEl, "易仓设置已保存", "success");
      loadSettings();
    } else {
      showMessage(messageEl, result.message || "保存失败", "error");
    }
  } catch (error) {
    showMessage(messageEl, "保存失败: " + error.message, "error");
  }
}

// 保存亚马逊设置
async function saveAmazonSettings(event) {
  event.preventDefault();

  const sellerId = document.getElementById("amazon-seller-id").value.trim();
  const marketplace = document.getElementById("amazon-marketplace").value;
  const refreshToken = document.getElementById("amazon-refresh-token").value.trim();
  const clientId = document.getElementById("amazon-client-id").value.trim();
  const clientSecret = document.getElementById("amazon-client-secret").value.trim();
  const messageEl = document.getElementById("amazon-message");

  if (!sellerId || !refreshToken) {
    showMessage(messageEl, "请填写 Seller ID 和 Refresh Token", "error");
    return;
  }

  try {
    const response = await fetch("/api/settings/amazon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seller_id: sellerId,
        marketplace: marketplace,
        refresh_token: refreshToken,
        client_id: clientId,
        client_secret: clientSecret,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showMessage(messageEl, "亚马逊设置已保存", "success");
      loadSettings();
    } else {
      showMessage(messageEl, result.message || "保存失败", "error");
    }
  } catch (error) {
    showMessage(messageEl, "保存失败: " + error.message, "error");
  }
}

// 测试易仓连接
async function testEccangConnection() {
  const messageEl = document.getElementById("eccang-message");
  showMessage(messageEl, "正在测试连接...", "info");

  try {
    const response = await fetch("/api/settings/eccang/test", {
      method: "POST",
    });

    const result = await response.json();
    if (result.success) {
      showMessage(messageEl, "连接成功！" + (result.message || ""), "success");
    } else {
      showMessage(messageEl, "连接失败: " + (result.message || ""), "error");
    }
  } catch (error) {
    showMessage(messageEl, "测试失败: " + error.message, "error");
  }
}

// 显示消息
function showMessage(element, message, type) {
  if (!element) return;
  element.textContent = message;
  element.className = "form-message " + type;
  element.style.display = "block";

  // 5秒后自动隐藏
  setTimeout(() => {
    element.style.display = "none";
  }, 5000);
}

// 在 DOMContentLoaded 中初始化设置
document.addEventListener("DOMContentLoaded", initSettings);

// ==================== 战场地图 ====================

function initBattlefield() {
  const analyzeBtn = document.getElementById("battlefield-analyze");
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeBattlefield);
  }

  // 初始化 Tab 切换
  document.querySelectorAll(".battlefield-tabs .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabName = btn.dataset.tab;
      // 更新按钮状态
      document.querySelectorAll(".battlefield-tabs .tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      // 更新内容显示
      document.querySelectorAll(".tab-content").forEach((content) => content.classList.remove("active"));
      const targetContent = document.getElementById("tab-" + tabName);
      if (targetContent) {
        targetContent.classList.add("active");
      }
    });
  });
}

async function analyzeBattlefield() {
  const asin = document.getElementById("battlefield-asin").value.trim();
  const marketplace = document.getElementById("battlefield-marketplace").value;

  if (!asin) {
    alert("请输入目标 ASIN");
    return;
  }

  const content = document.getElementById("battlefield-content");
  content.style.display = "block";

  try {
    const response = await fetch(`/api/battlefield/analyze?asin=${asin}&marketplace=${marketplace}`);
    const data = await response.json();

    if (data.error) {
      alert(data.error);
      return;
    }

    // 渲染市场份额
    renderMarketShare(data.market_share);

    // 渲染价格带
    renderPriceBand(data.price_band);

    // 渲染竞品表格
    renderCompetitorTable(data.competitors, data.market_share);

    // 渲染关键词
    renderKeywords(data.keyword_analysis);
  } catch (error) {
    alert("分析失败: " + error.message);
  }
}

function renderMarketShare(marketShare) {
  const container = document.getElementById("market-share-chart");
  if (!marketShare || !marketShare.shares) {
    container.innerHTML = "<p>暂无数据</p>";
    return;
  }

  let html = '<div class="bar-list">';
  marketShare.shares.forEach((share) => {
    html += `
      <div class="bar-row">
        <span>${escapeHtml(share.title || share.asin)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${share.share}%"></div></div>
        <strong>${share.share}%</strong>
      </div>
    `;
  });
  html += "</div>";
  container.innerHTML = html;
}

function renderPriceBand(priceBand) {
  const container = document.getElementById("price-band-chart");
  if (!priceBand || !priceBand.bands) {
    container.innerHTML = "<p>暂无数据</p>";
    return;
  }

  let html = '<div class="bar-list">';
  priceBand.bands.forEach((band) => {
    html += `
      <div class="bar-row">
        <span>${escapeHtml(band.range)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${band.percentage}%"></div></div>
        <strong>${band.count}个</strong>
      </div>
    `;
  });
  html += "</div>";
  html += `<p style="margin-top:12px;color:var(--muted)">均价: $${priceBand.avg_price}</p>`;
  container.innerHTML = html;
}

function renderCompetitorTable(competitors, marketShare) {
  const tbody = document.querySelector("#competitor-table tbody");
  if (!competitors || competitors.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">暂无竞品数据</td></tr>';
    return;
  }

  // 合并份额数据
  const shareMap = {};
  if (marketShare && marketShare.shares) {
    marketShare.shares.forEach((s) => {
      shareMap[s.asin] = s.share;
    });
  }

  tbody.innerHTML = competitors
    .map(
      (c) => `
    <tr>
      <td>${escapeHtml(c.competitor_asin || c.asin || "-")}</td>
      <td>${escapeHtml((c.title || "-").substring(0, 50))}</td>
      <td>$${c.price || 0}</td>
      <td>${c.rating || 0}</td>
      <td>${c.review_count || 0}</td>
      <td>${c.bsr_rank || 0}</td>
      <td>${shareMap[c.competitor_asin] || 0}%</td>
    </tr>
  `
    )
    .join("");
}

function renderKeywords(keywordAnalysis) {
  const container = document.getElementById("keyword-competition-chart");
  if (!keywordAnalysis || !keywordAnalysis.top_keywords) {
    container.innerHTML = "<p>暂无关键词数据</p>";
    return;
  }

  let html = '<div class="keyword-list">';
  keywordAnalysis.top_keywords.slice(0, 10).forEach((kw) => {
    html += `
      <div class="keyword-item">
        <span class="keyword-word">${escapeHtml(kw.keyword)}</span>
        <span class="keyword-count">${kw.count}次</span>
      </div>
    `;
  });
  html += "</div>";
  container.innerHTML = html;
}

// ==================== 运营天眼 ====================

function initDiagnosis() {
  const runBtn = document.getElementById("diagnosis-run");
  if (runBtn) {
    runBtn.addEventListener("click", runDiagnosis);
  }
}

async function runDiagnosis() {
  const asin = document.getElementById("diagnosis-asin").value.trim();

  if (!asin) {
    alert("请输入目标 ASIN");
    return;
  }

  const content = document.getElementById("diagnosis-content");
  content.style.display = "block";

  try {
    const response = await fetch(`/api/diagnosis/run?asin=${asin}`);
    const data = await response.json();

    if (data.error) {
      alert(data.error);
      return;
    }

    // 渲染健康评分颜色条
    renderHealthBar(data.health_score, data.health_level);

    // 渲染六大分析因子
    renderSixFactors(data.six_factors);

    // 渲染出单词 TOP 分析
    renderTopKeywords(data.top_keywords);

    // 渲染销量趋势图
    renderSalesTrend(data.sales_trend);

    // 渲染优化建议
    renderRecommendations(data.recommendations);
  } catch (error) {
    alert("诊断失败: " + error.message);
  }
}

function renderHealthBar(score, level) {
  const valueEl = document.getElementById("health-score-value");
  const barFill = document.getElementById("health-bar-fill");

  if (valueEl) {
    valueEl.textContent = Math.round(score);
    // 根据等级设置颜色
    if (level === "green") {
      valueEl.style.color = "#10b981";
    } else if (level === "yellow") {
      valueEl.style.color = "#f59e0b";
    } else {
      valueEl.style.color = "#ef4444";
    }
  }

  if (barFill) {
    barFill.style.width = score + "%";
  }
}

function renderSixFactors(factors) {
  if (!factors) return;

  const factorMap = {
    "sales_trend": "sales",
    "traffic_health": "traffic",
    "conversion_efficiency": "conversion",
    "competitive_landscape": "competitive",
    "review_risk": "review",
    "ad_performance": "ad",
  };

  for (const [key, prefix] of Object.entries(factorMap)) {
    const factor = factors[key];
    if (!factor) continue;

    const valueEl = document.getElementById(`factor-${prefix}-value`);
    const statusEl = document.getElementById(`factor-${prefix}-status`);

    if (valueEl) {
      valueEl.textContent = factor.score + "分";
    }

    if (statusEl) {
      statusEl.textContent = factor.status;
      statusEl.className = "factor-status";
      if (factor.status === "良好") {
        statusEl.classList.add("good");
      } else if (factor.status === "警告") {
        statusEl.classList.add("warning");
      } else {
        statusEl.classList.add("bad");
      }
    }
  }
}

function renderTopKeywords(keywords) {
  const tbody = document.querySelector("#top-keywords-table tbody");
  if (!tbody || !keywords || keywords.length === 0) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="empty-state">暂无数据</td></tr>';
    return;
  }

  tbody.innerHTML = keywords
    .map(
      (kw) => `
    <tr>
      <td><strong>${escapeHtml(kw.keyword)}</strong></td>
      <td>${kw.aba_rank.toLocaleString()}</td>
      <td>${(kw.click_share * 100).toFixed(1)}%</td>
      <td>${(kw.conversion_share * 100).toFixed(1)}%</td>
      <td>${(kw.top3_click_share * 100).toFixed(1)}%</td>
    </tr>
  `
    )
    .join("");
}

function renderSalesTrend(trendData) {
  const container = document.getElementById("sales-trend-chart");
  if (!container || !trendData || !trendData.sales) {
    if (container) container.innerHTML = "<p>暂无数据</p>";
    return;
  }

  const maxSales = Math.max(...trendData.sales, 1);
  let html = "";

  trendData.sales.forEach((sales, index) => {
    const height = Math.max(4, (sales / maxSales) * 160);
    const date = trendData.dates[index];
    html += `<div class="trend-bar" style="height:${height}px" data-value="${sales} (${date})"></div>`;
  });

  container.innerHTML = html;
}

function renderRecommendations(recommendations) {
  const container = document.getElementById("recommendations-content");
  if (!container || !recommendations) {
    container.innerHTML = "<p>暂无建议</p>";
    return;
  }

  let html = "";
  recommendations.forEach((rec) => {
    const priorityClass = rec.priority === "紧急" ? "bad" : rec.priority === "重要" ? "warning" : "good";
    html += `
      <div class="recommendation-item">
        <span class="metric-status ${priorityClass}">${escapeHtml(rec.priority)}</span>
        <span class="rec-category">[${escapeHtml(rec.category)}]</span>
        <span class="rec-issue">${escapeHtml(rec.issue)}</span>
        <p class="rec-suggestion">${escapeHtml(rec.suggestion)}</p>
      </div>
    `;
  });

  container.innerHTML = html || "<p>暂无建议</p>";
}

// 在 DOMContentLoaded 中初始化战场地图和运营天眼
document.addEventListener("DOMContentLoaded", initBattlefield);
document.addEventListener("DOMContentLoaded", initDiagnosis);

// ==================== 侧边栏折叠 ====================

function initSidebarSections() {
  document.querySelectorAll(".nav-section-header").forEach((header) => {
    header.addEventListener("click", () => {
      const section = header.closest(".nav-section");
      if (section) {
        section.classList.toggle("collapsed");
      }
    });
  });
}

// 在 DOMContentLoaded 中初始化侧边栏折叠
document.addEventListener("DOMContentLoaded", initSidebarSections);

// ==================== 自动化任务 ====================

function initAutomation() {
  const refreshBtn = document.getElementById("refresh-tasks");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadAutomationTasks);
  }
}

async function loadAutomationTasks() {
  const grid = document.getElementById("tasks-grid");
  if (!grid) return;

  try {
    const response = await fetch("/api/automation/tasks");
    const tasks = await response.json();
    renderAutomationTasks(tasks);
  } catch (error) {
    grid.innerHTML = `<p class="empty-state">加载失败: ${error.message}</p>`;
  }
}

function renderAutomationTasks(tasks) {
  const grid = document.getElementById("tasks-grid");
  if (!grid) return;

  if (!tasks || tasks.length === 0) {
    grid.innerHTML = '<p class="empty-state">暂无自动化任务</p>';
    return;
  }

  const typeIcons = {
    daily_analysis: "daily",
    data_sync: "sync",
    competitor_monitor: "monitor",
  };

  const typeNames = {
    daily_analysis: "定时分析",
    data_sync: "数据同步",
    competitor_monitor: "竞品监控",
  };

  grid.innerHTML = tasks
    .map(
      (task) => `
    <div class="task-card">
      <div class="task-header">
        <div class="task-icon ${typeIcons[task.task_type] || "daily"}">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${getTaskIcon(task.task_type)}
          </svg>
        </div>
        <div class="task-info">
          <div class="task-name">${escapeHtml(task.name)}</div>
          <div class="task-type">${typeNames[task.task_type] || task.task_type}</div>
        </div>
        <div class="task-toggle ${task.enabled ? "active" : ""}" onclick="toggleTask('${task.task_id}', ${!task.enabled})"></div>
      </div>
      <div class="task-details">
        <div class="task-detail">
          <span class="task-detail-label">执行时间</span>
          <span class="task-detail-value">${task.schedule_time}</span>
        </div>
        <div class="task-detail">
          <span class="task-detail-label">状态</span>
          <span class="task-status ${task.status}">${getStatusText(task.status)}</span>
        </div>
        <div class="task-detail">
          <span class="task-detail-label">执行次数</span>
          <span class="task-detail-value">${task.run_count}</span>
        </div>
        <div class="task-detail">
          <span class="task-detail-label">错误次数</span>
          <span class="task-detail-value">${task.error_count}</span>
        </div>
      </div>
      <div class="task-actions">
        <button class="task-btn primary" onclick="runTask('${task.task_id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          立即执行
        </button>
        <button class="task-btn" onclick="editTask('${task.task_id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          编辑
        </button>
      </div>
    </div>
  `
    )
    .join("");
}

function getTaskIcon(type) {
  switch (type) {
    case "daily_analysis":
      return '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>';
    case "data_sync":
      return '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>';
    case "competitor_monitor":
      return '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 000 20 14.5 14.5 0 000-20"/><path d="M2 12h20"/>';
    default:
      return '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>';
  }
}

function getStatusText(status) {
  switch (status) {
    case "pending":
      return "等待中";
    case "running":
      return "运行中";
    case "success":
      return "成功";
    case "failed":
      return "失败";
    case "disabled":
      return "已禁用";
    default:
      return status;
  }
}

async function toggleTask(taskId, enable) {
  const endpoint = enable ? "enable" : "disable";
  try {
    await fetch(`/api/automation/tasks/${taskId}/${endpoint}`, { method: "POST" });
    loadAutomationTasks();
  } catch (error) {
    alert("操作失败: " + error.message);
  }
}

async function runTask(taskId) {
  try {
    const response = await fetch(`/api/automation/tasks/${taskId}/run`, { method: "POST" });
    const result = await response.json();
    if (result.success) {
      alert("任务执行成功");
      loadAutomationTasks();
    } else {
      alert("任务执行失败: " + (result.error || "未知错误"));
    }
  } catch (error) {
    alert("执行失败: " + error.message);
  }
}

function editTask(taskId) {
  // TODO: 实现任务编辑对话框
  alert("编辑功能开发中");
}

// 在 DOMContentLoaded 中初始化自动化任务
document.addEventListener("DOMContentLoaded", initAutomation);

// ==================== AI 选品功能 ====================

let selectedProducts = new Set();

function initAISelection() {
  const refreshBtn = document.getElementById("refresh-products");
  const analyzeBtn = document.getElementById("analyze-selected");
  const selectAll = document.getElementById("select-all");
  const researchBtn = document.getElementById("run-selection-research");
  const keywordInput = document.getElementById("selection-keyword");

  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadChromeProducts);
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeSelectedProducts);
  }

  if (selectAll) {
    selectAll.addEventListener("change", toggleSelectAll);
  }

  if (researchBtn) {
    researchBtn.addEventListener("click", runProductResearch);
  }

  if (keywordInput) {
    keywordInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runProductResearch();
      }
    });
  }
}

async function runProductResearch() {
  const keywordInput = document.getElementById("selection-keyword");
  const marketplaceSelect = document.getElementById("selection-marketplace");
  const categorySelect = document.getElementById("selection-category");
  const button = document.getElementById("run-selection-research");
  const progress = document.getElementById("research-progress");
  const result = document.getElementById("product-research-result");
  const keyword = keywordInput.value.trim();

  if (!keyword) {
    alert("请输入关键词");
    keywordInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>研究中...';
  progress.style.display = "block";
  result.style.display = "none";
  result.innerHTML = "";

  try {
    const data = await requestJson(endpoints.selectionResearch, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        keyword,
        marketplace: marketplaceSelect.value,
        category: categorySelect.value,
      }),
    });
    renderProductResearch(data);
    document.getElementById("analyzed-count").textContent = data.market_overview.sample_size;
    document.getElementById("recommended-count").textContent = data.decision.status === "no_go" ? "0" : "1";
  } catch (error) {
    result.style.display = "block";
    result.innerHTML = `<div class="research-error">${escapeHtml(error.message)}</div>`;
  } finally {
    progress.style.display = "none";
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      开始研究
    `;
  }
}

function renderProductResearch(data) {
  const result = document.getElementById("product-research-result");
  const overview = data.market_overview;
  const pricing = data.pricing_advice;
  const decision = data.decision;
  const decisionClass = decision.status === "go" ? "good" : decision.status === "cautious" ? "warning" : "bad";

  result.style.display = "grid";
  result.innerHTML = `
    ${overview.sample_note ? `<div class="research-sample-note">${escapeHtml(overview.sample_note)}</div>` : ""}
    <section class="research-section">
      <div class="research-section-title">
        <h3>市场概览</h3>
        <span>基于 “${escapeHtml(data.keyword)}” 分析</span>
      </div>
      <div class="research-overview-grid">
        ${renderOverviewCard("月销量估算", formatNumber(overview.monthly_sales_estimate), "件/月", "sales")}
        ${renderOverviewCard("平均售价", formatMoney(overview.avg_price), "采集均价", "price")}
        ${renderOverviewCard("机会评分", `${overview.opportunity_score}/10`, `竞争度：${overview.competition}`, "score")}
        ${renderOverviewCard("竞品样本", `${overview.sample_size}`, `匹配 ${overview.matched_count} / 池 ${overview.total_competitor_pool}`, "sample")}
      </div>
    </section>

    <section class="research-section">
      <div class="research-section-title">
        <h3>蓝海关键词库</h3>
        <span>${data.keywords.length} 个关键词</span>
      </div>
      <div class="table-wrap research-keyword-table">
        <table>
          <thead>
            <tr>
              <th>关键词</th>
              <th>搜索量估算</th>
              <th>竞争度</th>
              <th>机会评分</th>
              <th>趋势</th>
            </tr>
          </thead>
          <tbody>
            ${data.keywords.map(renderResearchKeywordRow).join("")}
          </tbody>
        </table>
      </div>
    </section>

    <section class="research-section">
      <div class="research-section-title">
        <h3>TOP 竞品分析</h3>
        <span>${data.competitors.length} 款竞品</span>
      </div>
      <div class="research-competitor-grid">
        ${data.competitors.length ? data.competitors.map(renderResearchCompetitorCard).join("") : '<p class="empty-state">暂无采集竞品，请先用 Chrome 插件采集 Amazon 商品。</p>'}
      </div>
    </section>

    <section class="research-section pricing-advice">
      <div class="research-section-title">
        <h3>成本、定价、利润区间</h3>
      </div>
      <div class="pricing-grid">
        <div><span>目标售价</span><strong>${formatMoney(pricing.target_price_min)} - ${formatMoney(pricing.target_price_max)}</strong></div>
        <div><span>成本上限</span><strong>${formatMoney(pricing.cost_min)} - ${formatMoney(pricing.cost_max)}</strong></div>
        <div><span>利润区间</span><strong>${formatMoney(pricing.profit_min)} - ${formatMoney(pricing.profit_max)}</strong></div>
        <div><span>毛利率</span><strong>${pricing.margin_min}% - ${pricing.margin_max}%</strong></div>
      </div>
      <ul class="pricing-notes">${pricing.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </section>

    <section class="research-report ${decisionClass}">
      <div class="research-report-header">
        <div>
          <h3>AI 选品决策报告</h3>
          <span>${data.generated_by_ai ? "DeepSeek 润色生成" : "规则模型生成"}</span>
        </div>
        <strong>${escapeHtml(decision.label)}</strong>
      </div>
      <p>${escapeHtml(data.report)}</p>
      <div class="decision-lists">
        <div>
          <h4>判断依据</h4>
          <ul>${decision.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
        </div>
        <div>
          <h4>下一步</h4>
          <ul>${decision.next_steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul>
        </div>
      </div>
    </section>
  `;
}

function renderOverviewCard(label, value, meta, type) {
  return `
    <article class="research-overview-card ${type}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(meta)}</small>
    </article>
  `;
}

function renderResearchKeywordRow(keyword) {
  return `
    <tr>
      <td><strong>${escapeHtml(keyword.keyword)}</strong></td>
      <td>${formatNumber(keyword.search_volume)}</td>
      <td><span class="competition-pill ${competitionClass(keyword.competition)}">${escapeHtml(keyword.competition)}</span></td>
      <td>${keyword.opportunity_score}/10</td>
      <td>${escapeHtml(keyword.trend)}</td>
    </tr>
  `;
}

function renderResearchCompetitorCard(competitor) {
  return `
    <article class="research-competitor-card">
      <div class="competitor-card-body">
        <div class="competitor-thumb">${escapeHtml((competitor.title || competitor.asin || "-").slice(0, 1).toUpperCase())}</div>
        <div>
          <h4>${escapeHtml(competitor.title)}</h4>
          <div class="competitor-meta">
            <strong>${formatMoney(competitor.price)}</strong>
            <span>${competitor.rating ? competitor.rating.toFixed(1) : "0.0"} ★</span>
            <span>${formatNumber(competitor.review_count)} 评论</span>
          </div>
        </div>
      </div>
      <div class="competitor-card-footer">
        <span>月销估算 ${formatNumber(competitor.estimated_monthly_sales)}</span>
        ${competitor.badge ? `<em>${escapeHtml(competitor.badge)}</em>` : ""}
        ${competitor.url ? `<a href="${escapeHtml(competitor.url)}" target="_blank" rel="noopener">查看</a>` : ""}
      </div>
    </article>
  `;
}

function competitionClass(value) {
  if (value === "低") return "low";
  if (value === "中") return "medium";
  return "high";
}

function formatMoney(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

async function loadChromeProducts() {
  const tbody = document.getElementById("products-body");
  const totalProducts = document.getElementById("total-products");

  try {
    const response = await fetch("/api/chrome/products");
    const data = await response.json();

    if (data.products && data.products.length > 0) {
      renderProducts(data.products);
      totalProducts.textContent = data.products.length;
    } else {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">
            <div class="empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
            </div>
            <p>暂无采集数据</p>
            <p class="empty-hint">请使用 Chrome 插件在 Amazon 商品页面采集数据</p>
          </td>
        </tr>
      `;
      totalProducts.textContent = "0";
    }
  } catch (error) {
    console.error("加载商品失败:", error);
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-state">
          <p>加载失败: ${error.message}</p>
          <p class="empty-hint">请确保后端服务已启动</p>
        </td>
      </tr>
    `;
  }
}

function renderProducts(products) {
  const tbody = document.getElementById("products-body");

  tbody.innerHTML = products
    .map(
      (product) => `
    <tr>
      <td>
        <input type="checkbox" class="product-checkbox" data-asin="${escapeHtml(product.asin || '')}" />
      </td>
      <td>
        ${product.main_image ? `<img src="${escapeHtml(product.main_image)}" class="product-thumb" />` : '<span class="no-image">无图片</span>'}
      </td>
      <td>
        <span class="asin-text">${escapeHtml(product.asin || "-")}</span>
      </td>
      <td class="product-title-cell">
        ${escapeHtml(product.title || product.asin || "-")}
      </td>
      <td>${product.price ? "$" + product.price.toFixed(2) : "-"}</td>
      <td>${product.rating ? product.rating.toFixed(1) + " ★" : "-"}</td>
      <td>${product.review_count ? product.review_count.toLocaleString() : "-"}</td>
      <td>
        <a href="${escapeHtml(product.url || "#")}" target="_blank" class="product-link">
          查看商品
        </a>
        <button class="action-btn danger" onclick="deleteProduct('${escapeHtml(product.asin || "")}')">
          删除
        </button>
      </td>
    </tr>
  `
    )
    .join("");

  // 绑定复选框事件
  document.querySelectorAll(".product-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectedCount);
  });
}

function toggleSelectAll(event) {
  const checked = event.currentTarget.checked;
  document.querySelectorAll(".product-checkbox").forEach((checkbox) => {
    checkbox.checked = checked;
  });
  updateSelectedCount();
}

function updateSelectedCount() {
  const checkboxes = document.querySelectorAll(".product-checkbox:checked");
  const analyzeBtn = document.getElementById("analyze-selected");

  selectedProducts.clear();
  checkboxes.forEach((cb) => {
    selectedProducts.add(cb.dataset.asin);
  });

  if (analyzeBtn) {
    analyzeBtn.disabled = selectedProducts.size === 0;
    analyzeBtn.textContent = selectedProducts.size > 0 ? `AI 分析选中商品 (${selectedProducts.size})` : "AI 分析选中商品";
  }
}

async function deleteProduct(asin) {
  if (!asin) return;
  if (!confirm(`确定要删除 ASIN: ${asin} 吗？`)) return;

  // TODO: 实现删除功能
  alert("删除功能开发中");
}

async function analyzeSelectedProducts() {
  if (selectedProducts.size === 0) {
    alert("请先选择要分析的商品");
    return;
  }

  const analyzeBtn = document.getElementById("analyze-selected");
  const analysisResult = document.getElementById("analysis-result");
  const analysisContent = document.getElementById("analysis-content");

  try {
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<span class="loading"></span>分析中...';

    // 调用后端 AI 分析接口
    const response = await fetch("/api/chrome/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asins: Array.from(selectedProducts) })
    });

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || "分析失败");
    }

    const a = data.analysis;
    const scoreClass = a.score >= 80 ? "good" : a.score >= 60 ? "warning" : "bad";

    analysisResult.style.display = "block";
    analysisContent.innerHTML = `
      <div class="analysis-card">
        <h4>AI 选品分析报告</h4>
        <p>已分析 ${data.product_count} 个商品</p>
        <div style="margin-top: 16px;">
          <div class="analysis-score ${scoreClass}">推荐指数: ${a.score}/100</div>
        </div>
        <div style="margin-top: 16px;">
          <strong>总结：</strong>
          <p style="margin-top: 8px;">${escapeHtml(a.summary || "")}</p>
        </div>
        <div style="margin-top: 12px;">
          <strong>市场潜力：</strong>
          <p style="margin-top: 4px;">${escapeHtml(a.market_potential || "")}</p>
        </div>
        <div style="margin-top: 12px;">
          <strong>竞争分析：</strong>
          <p style="margin-top: 4px;">${escapeHtml(a.competition || "")}</p>
        </div>
        <div style="margin-top: 12px;">
          <strong>利润建议：</strong>
          <p style="margin-top: 4px;">${escapeHtml(a.profit_advice || "")}</p>
        </div>
        ${a.risks && a.risks.length > 0 ? `
        <div style="margin-top: 12px;">
          <strong>风险提示：</strong>
          <ul style="margin-top: 4px; padding-left: 20px;">
            ${a.risks.map(r => `<li>${escapeHtml(r)}</li>`).join("")}
          </ul>
        </div>
        ` : ""}
        ${a.suggestions && a.suggestions.length > 0 ? `
        <div style="margin-top: 12px;">
          <strong>操作建议：</strong>
          <ul style="margin-top: 4px; padding-left: 20px;">
            ${a.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
          </ul>
        </div>
        ` : ""}
      </div>
    `;

    // 更新统计
    document.getElementById("analyzed-count").textContent = data.product_count;
    document.getElementById("recommended-count").textContent = a.score >= 70 ? data.product_count : 0;

  } catch (error) {
    alert("分析失败: " + error.message);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
      AI 分析选中商品
    `;
  }
}

// 在 DOMContentLoaded 中初始化 AI 选品
document.addEventListener("DOMContentLoaded", initAISelection);
