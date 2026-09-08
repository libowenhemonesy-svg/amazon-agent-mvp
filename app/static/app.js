const endpoints = {
  report: "/reports/daily",
  alerts: "/alerts",
  metrics: "/metrics/daily",
  run: "/jobs/daily-run",
  demo: "/demo/load-sample",
  listingOptimize: "/api/listing/optimize",
  dianxiaomiGenerate: "/api/dianxiaomi/generate-attributes",
  dianxiaomiFill: "/api/dianxiaomi/fill",
  dianxiaomiStatus: "/api/dianxiaomi/fill/status",
  dianxiaomiContinue: "/api/dianxiaomi/fill/continue",
  adOptimize: "/api/ads/optimize",
  supplyChainAnalyze: "/api/supply-chain/analyze",
  profitCalculate: "/api/profit/calculate",
  profitCalculations: "/api/profit/calculations",
  fbaEstimate: "/api/fba/estimate",
  salesMonitorOverview: "/api/sales-monitor/overview",
  salesMonitorMetrics: "/api/sales-monitor/metrics",
  salesDashboard: "/api/sales-monitor/dashboard",
  adsDashboard: "/api/ads-analysis/dashboard",
  inventoryDashboard: "/api/inventory-agent/dashboard",
};

const statusOptions = [
  ["pending", "待处理"],
  ["processing", "处理中"],
  ["done", "已处理"],
  ["reviewed", "已复盘"],
  ["ignored", "忽略"],
];

let currentAlerts = [];
let currentDianxiaomiAttributes = null;
let dianxiaomiStatusTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item[data-page]").forEach((item) => {
    item.addEventListener("click", activateNavItem);
  });
  window.addEventListener("hashchange", initPageFromHash);
  window.addEventListener("popstate", initPageFromHash);
  document.getElementById("run-analysis").addEventListener("click", runAnalysis);
  document.getElementById("load-demo").addEventListener("click", loadDemo);
  document.getElementById("refresh-results").addEventListener("click", refreshResults);
  document.getElementById("reset-day").addEventListener("click", resetDay);
  document.getElementById("sidebar-toggle").addEventListener("click", toggleSidebar);
  document.getElementById("global-search").addEventListener("input", syncGlobalSearch);
  document.getElementById("run-date").addEventListener("change", refreshResults);
  document.getElementById("alert-search").addEventListener("input", renderFilteredAlerts);
  document.getElementById("severity-filter").addEventListener("change", renderFilteredAlerts);
  document.getElementById("status-filter").addEventListener("change", renderFilteredAlerts);
  const initialPageName = initPageFromHash();
  initSidebarUser();
  if (shouldRefreshDashboardOnLoad(initialPageName)) {
    refreshResults();
  }
});

function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("is-open");
}

function initSidebarUser() {
  const trigger = document.getElementById("sidebar-user-menu");
  const popover = document.getElementById("sidebar-user-popover");
  const user = window.currentUser || {};
  if (!trigger || !popover) return;

  const name = user.displayName || user.username || "用户";
  document.getElementById("sidebar-user-name").textContent = name;
  document.getElementById("sidebar-user-avatar").textContent = name.slice(0, 1).toUpperCase();
  document.getElementById("sidebar-user-role").textContent = user.role === "admin" ? "管理员" : "用户";

  trigger.addEventListener("click", () => {
    const isOpen = !popover.hidden;
    popover.hidden = isOpen;
    trigger.setAttribute("aria-expanded", String(!isOpen));
  });

  const adminAction = document.getElementById("sidebar-admin-action");
  if (user.role === "admin") {
    adminAction.hidden = false;
    adminAction.addEventListener("click", () => window.showAdminPanel());
  }
  document.getElementById("sidebar-logout-action").addEventListener("click", () => window.logout());
  document.addEventListener("click", (event) => {
    if (!trigger.contains(event.target) && !popover.contains(event.target)) {
      popover.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }
  });
}

// 页面标题映射
const pageTitles = {
  overview: { title: "运营总览", subtitle: "销售 · 广告 · 库存 · 质量异常监控" },
  analytics: { title: "风险分析", subtitle: "查看风险等级分布和模块统计" },
  tasks: { title: "异常任务", subtitle: "查看每日简报和异常告警" },
  "ai-selection": { title: "AI 选品", subtitle: "关键词调研 · 产品方向 · 成本定价 · 决策报告" },
  "image-studio": { title: "图片制作", subtitle: "云模型 · 工作流 · 任务队列 · 素材库" },
  "listing-optimization": { title: "Listing", subtitle: "标题 · 五点描述 · 产品详情 · Search Terms" },
  "ad-optimization": { title: "广告优化", subtitle: "预算 · ACoS · 出价 · 否定词 · 分时策略" },
  "supply-chain": { title: "供应链分析", subtitle: "采购成本 · 供应商 · 物流 · 备货补货" },
  "profit-calculator": { title: "利润核算", subtitle: "售价 · 成本 · FBA · 广告 · ROI" },
  "fba-estimator": { title: "FBA 成本估算", subtitle: "尺寸 · 重量 · Size Tier · Fulfillment Fee" },
  chat: { title: "AI 助手", subtitle: "智能对话查询运营数据" },
  "sales-monitor": { title: "销售监控", subtitle: "实时监控销售数据，自动识别异常波动" },
  "ads-analysis": { title: "广告分析", subtitle: "深度分析广告投放效果，优化广告策略" },
  "inventory-agent": { title: "库存管家", subtitle: "智能库存管理，避免断货和积压" },
  automation: { title: "自动化任务", subtitle: "定时分析 · 自动同步 · 竞品监控" },
  settings: { title: "MCP 对接", subtitle: "手动配置数据源 MCP 服务" },
};

function activateNavItem(event) {
  event.preventDefault();

  const navItem = event.currentTarget;
  const pageName = navItem.dataset.page;
  const targetHash = navItem.getAttribute("href") || `#${pageName}`;
  if (window.location.hash !== targetHash) {
    window.history.pushState(null, "", targetHash);
  }
  showPage(pageName, navItem);
}

function getCurrentPageName() {
  return window.location.hash.replace("#", "") || "overview";
}

function findNavItem(pageName) {
  return Array.from(document.querySelectorAll(".nav-item[data-page]")).find((item) => item.dataset.page === pageName);
}

function shouldRefreshDashboardOnLoad(pageName = getCurrentPageName()) {
  return ["overview", "analytics", "tasks"].includes(pageName);
}

function isPageVisible(pageName) {
  const page = document.getElementById("page-" + pageName);
  return Boolean(page && page.style.display !== "none");
}

function initPageFromHash() {
  const requestedPageName = getCurrentPageName();
  const pageName = document.getElementById("page-" + requestedPageName)
    ? requestedPageName
    : "overview";
  if (pageName !== requestedPageName) {
    window.history.replaceState(null, "", "#overview");
  }
  const navItem = findNavItem(pageName) || findNavItem("overview");
  if (!navItem) return "overview";
  const resolvedPageName = navItem.dataset.page || "overview";
  showPage(resolvedPageName, navItem);
  return resolvedPageName;
}

function showPage(pageName, navItem) {
  const targetPage = document.getElementById("page-" + pageName);
  if (!targetPage) return;
  const topbar = document.querySelector(".topbar");
  topbar.classList.toggle("is-selection-page", pageName === "ai-selection");
  const dashboard = document.querySelector(".dashboard");

  dashboard?.classList.toggle("is-selection-page", pageName === "ai-selection");
  // 更新导航状态
  document.querySelectorAll(".nav-item[data-page]").forEach((item) => {
    const isActiveItem = item === navItem;
    item.classList.toggle("is-active", isActiveItem);
    if (isActiveItem) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });
  document.getElementById("sidebar").classList.remove("is-open");

  // 切换页面可见状态
  document.querySelectorAll(".page").forEach((page) => {
    const isTargetPage = page === targetPage;
    page.style.display = isTargetPage ? "block" : "none";
    page.classList.toggle("is-visible", isTargetPage);
    page.setAttribute("aria-hidden", String(!isTargetPage));
  });

  window.scrollTo({ top: 0, left: 0, behavior: "auto" });

  // 更新顶部标题
  const titleInfo = pageTitles[pageName];
  if (titleInfo) {
    document.getElementById("page-title").textContent = titleInfo.title;
    document.getElementById("page-subtitle").textContent = titleInfo.subtitle;
    document.title = `${titleInfo.title} · SellAI Pro`;
  }

  // 特殊页面初始化
  if (pageName === "settings") {
    loadSettings();
  }
  if (pageName === "ai-selection") {
    window.SelectionWorkbench?.activate();
  }
  if (pageName === "image-studio") {
    window.ImageStudio?.activate();
  }
  if (pageName === "profit-calculator") {
    loadProfitHistory();
  }
  if (pageName === "fba-estimator" && isPageVisible("fba-estimator")) {
    runFbaEstimate();
  }
  if (pageName === "sales-monitor") {
    initSalesMonitor();
  }
  if (pageName === "ads-analysis") {
    initAdsAnalysis();
  }
  if (pageName === "inventory-agent") {
    initInventoryAgent();
  }
  if (pageName === "automation") {
    loadAutomationTasks();
  }
  if (pageName === "chat") {
    initChat();
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

// ==================== Listing 优化 ====================

function initListingOptimization() {
  const generateButton = document.getElementById("generate-listing");
  const fillDianxiaomiButton = document.getElementById("fill-dianxiaomi");
  const categoryDoneButton = document.getElementById("dianxiaomi-category-done");
  const productIdDoneButton = document.getElementById("dianxiaomi-product-id-done");
  const descriptionInput = document.getElementById("listing-product-description");
  const keywordInput = document.getElementById("listing-keywords");

  if (generateButton) {
    generateButton.addEventListener("click", runListingOptimization);
  }
  if (fillDianxiaomiButton) {
    fillDianxiaomiButton.addEventListener("click", runDianxiaomiFill);
  }
  if (categoryDoneButton) {
    categoryDoneButton.addEventListener("click", () => continueDianxiaomiFill("category"));
  }
  if (productIdDoneButton) {
    productIdDoneButton.addEventListener("click", () => continueDianxiaomiFill("product_id"));
  }

  [descriptionInput, keywordInput].forEach((input) => {
    if (!input) return;
    input.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        runListingOptimization();
      }
    });
  });

}

async function runDianxiaomiFill() {
  const descriptionInput = document.getElementById("listing-product-description");
  const keywordInput = document.getElementById("listing-keywords");
  const marketplaceSelect = document.getElementById("listing-marketplace");
  const button = document.getElementById("fill-dianxiaomi");
  const productContext = descriptionInput.value.trim();
  const keyword = extractPrimaryKeyword(keywordInput.value);

  if (!productContext) {
    setDianxiaomiStatus("请先输入产品描述", false);
    descriptionInput.focus();
    return;
  }
  if (!keyword) {
    setDianxiaomiStatus("请先输入目标关键词，ProductListingAgent 需要关键词生成 Listing", false);
    keywordInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>生成并启动中...';
  setDianxiaomiStatus("正在调用 ProductListingAgent 生成 Listing，并转换店小秘 JSON", true);
  hideDianxiaomiControls();

  try {
    const generated = await requestJson(endpoints.dianxiaomiGenerate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        keyword,
        product_context: productContext,
        marketplace: marketplaceSelect.value,
      }),
    });
    currentDianxiaomiAttributes = generated.attributes;
    renderDianxiaomiGeneratedListing(generated.listing);
    renderDianxiaomiPreview(generated.attributes);
    setDianxiaomiStatus("店小秘 JSON 已生成，正在启动浏览器填表", true);

    await requestJson(endpoints.dianxiaomiFill, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attributes: currentDianxiaomiAttributes }),
    });
    setDianxiaomiStatus("Playwright 已启动。请在打开的店小秘浏览器中按提示处理分类和产品 ID。", true);
    startDianxiaomiStatusPolling();
  } catch (error) {
    setDianxiaomiStatus(error.message, false);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4"/><path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9c1.62 0 3.14.43 4.45 1.18"/></svg>
      生成并填写店小秘
    `;
  }
}

function extractPrimaryKeyword(value) {
  return String(value || "")
    .split(/[,，;；\n]/)
    .map((item) => item.trim())
    .find(Boolean) || "";
}

function renderDianxiaomiGeneratedListing(listing) {
  if (!listing) return;
  const title = listing.title || "";
  const bullets = listing.bullet_points || listing.bullets || [];
  const description = listing.description || "";
  const searchTerms = listing.search_terms || "";

  document.getElementById("listing-title-output").classList.remove("empty");
  document.getElementById("listing-title-output").textContent = title;
  document.getElementById("listing-title-count").textContent = `${title.length}/200`;
  document.getElementById("listing-bullets-output").innerHTML = bullets
    .map((bullet) => `<li>${escapeHtml(bullet)}</li>`)
    .join("");
  document.getElementById("listing-description-output").classList.remove("empty");
  document.getElementById("listing-description-output").textContent = description;
  document.getElementById("listing-description-count").textContent = `${description.length}/2000`;
  const terms = searchTerms.split(/\s+/).filter(Boolean);
  const searchTermsOutput = document.getElementById("listing-search-terms-output");
  searchTermsOutput.classList.remove("empty");
  searchTermsOutput.innerHTML = terms.map((term) => `<span>${escapeHtml(term)}</span>`).join("");
}

function renderDianxiaomiPreview(attributes) {
  const preview = document.getElementById("dianxiaomi-json-preview");
  if (!preview) return;
  preview.style.display = "block";
  preview.textContent = JSON.stringify(attributes || {}, null, 2);
}

function startDianxiaomiStatusPolling() {
  if (dianxiaomiStatusTimer) {
    window.clearInterval(dianxiaomiStatusTimer);
  }
  pollDianxiaomiStatus();
  dianxiaomiStatusTimer = window.setInterval(pollDianxiaomiStatus, 2500);
}

async function pollDianxiaomiStatus() {
  try {
    const data = await requestJson(endpoints.dianxiaomiStatus);
    setDianxiaomiStatus(data.message || "等待店小秘填表状态", true);
    const controls = document.getElementById("dianxiaomi-controls");
    if (controls) {
      controls.style.display = data.paused ? "flex" : "none";
    }
    const categoryBtn = document.getElementById("dianxiaomi-category-done");
    const productIdBtn = document.getElementById("dianxiaomi-product-id-done");
    if (categoryBtn) categoryBtn.disabled = data.step !== "category";
    if (productIdBtn) productIdBtn.disabled = data.step !== "product_id";
    if (data.done && dianxiaomiStatusTimer) {
      window.clearInterval(dianxiaomiStatusTimer);
      dianxiaomiStatusTimer = null;
    }
  } catch (error) {
    setDianxiaomiStatus(error.message, false);
  }
}

async function continueDianxiaomiFill(step) {
  try {
    await requestJson(endpoints.dianxiaomiContinue, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step }),
    });
    setDianxiaomiStatus("已发送继续信号，请等待脚本执行下一步", true);
    hideDianxiaomiControls();
  } catch (error) {
    setDianxiaomiStatus(error.message, false);
  }
}

function hideDianxiaomiControls() {
  const controls = document.getElementById("dianxiaomi-controls");
  if (controls) controls.style.display = "none";
}

function setDianxiaomiStatus(message, ok) {
  const status = document.getElementById("dianxiaomi-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

async function runListingOptimization() {
  const descriptionInput = document.getElementById("listing-product-description");
  const keywordInput = document.getElementById("listing-keywords");
  const asinInput = document.getElementById("listing-competitor-asin");
  const marketplaceSelect = document.getElementById("listing-marketplace");
  const button = document.getElementById("generate-listing");
  const status = document.getElementById("listing-status");
  const productDescription = descriptionInput.value.trim();

  if (!productDescription) {
    setListingStatus("请先输入产品描述", false);
    descriptionInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>生成中...';
  setListingStatus("正在生成 Listing 内容并计算 8 维质量评分", true);

  try {
    const data = await requestJson(endpoints.listingOptimize, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_description: productDescription,
        keywords: keywordInput.value,
        competitor_asin: asinInput.value,
        marketplace: marketplaceSelect.value,
      }),
    });
    renderListingOptimization(data);
    setListingStatus("Listing 已生成，评分与关键词覆盖地图已更新", true);
  } catch (error) {
    setListingStatus(error.message, false);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      生成 Listing
    `;
  }
}

function renderListingOptimization(data) {
  const listing = data.listing;
  const score = data.quality_score;
  const coverage = data.keyword_coverage;

  document.getElementById("listing-title-output").classList.remove("empty");
  document.getElementById("listing-title-output").textContent = listing.title;
  document.getElementById("listing-title-count").textContent = `${listing.title.length}/200`;

  const bulletsOutput = document.getElementById("listing-bullets-output");
  bulletsOutput.innerHTML = listing.bullets
    .map((bullet) => `<li>${escapeHtml(bullet)}</li>`)
    .join("");

  document.getElementById("listing-description-output").classList.remove("empty");
  document.getElementById("listing-description-output").textContent = listing.description;
  document.getElementById("listing-description-count").textContent = `${listing.description.length}/2000`;

  const searchTermsOutput = document.getElementById("listing-search-terms-output");
  searchTermsOutput.classList.remove("empty");
  searchTermsOutput.innerHTML = (listing.backend_terms || [])
    .map((term) => `<span>${escapeHtml(term)}</span>`)
    .join("");

  document.getElementById("listing-quality-score").textContent = `${score.overall_score}/100`;
  document.getElementById("listing-quality-grade").textContent = score.grade;
  document.getElementById("listing-score-dimensions").innerHTML = score.dimensions
    .map(renderListingScoreDimension)
    .join("");

  document.getElementById("listing-coverage-map").innerHTML = coverage.items.length
    ? coverage.items.map(renderListingCoverageItem).join("")
    : '<p class="empty">未输入目标关键词，无法生成覆盖地图</p>';
}

function renderListingScoreDimension(item) {
  return `
    <div class="listing-score-row">
      <div>
        <span>${escapeHtml(item.label)}</span>
        <strong>${item.score}%</strong>
      </div>
      <div class="listing-score-bar" aria-hidden="true">
        <i style="width:${Math.max(0, Math.min(100, item.score))}%"></i>
      </div>
    </div>
  `;
}

function renderListingCoverageItem(item) {
  const statusClass = item.status === "已覆盖" ? "covered" : item.status === "部分覆盖" ? "partial" : "missing";
  const locations = item.locations && item.locations.length ? item.locations : ["未覆盖"];
  return `
    <article class="listing-coverage-item ${statusClass}">
      <div>
        <strong>${escapeHtml(item.keyword)}</strong>
        <span>${escapeHtml(item.status)}</span>
      </div>
      <div class="listing-location-tags">
        ${locations.map((location) => `<em>${escapeHtml(location)}</em>`).join("")}
      </div>
    </article>
  `;
}

function setListingStatus(message, ok) {
  const status = document.getElementById("listing-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

// ==================== 广告优化 ====================

function initAdOptimization() {
  const generateButton = document.getElementById("generate-ad-strategy");
  const keywordInput = document.getElementById("ad-product-keyword");

  if (generateButton) {
    generateButton.addEventListener("click", runAdOptimization);
  }

  if (keywordInput) {
    keywordInput.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        runAdOptimization();
      }
    });
  }
}

async function runAdOptimization() {
  const keywordInput = document.getElementById("ad-product-keyword");
  const budgetInput = document.getElementById("ad-daily-budget");
  const acosSelect = document.getElementById("ad-target-acos");
  const adTypeSelect = document.getElementById("ad-type");
  const marketplaceSelect = document.getElementById("ad-marketplace");
  const categorySelect = document.getElementById("ad-category");
  const button = document.getElementById("generate-ad-strategy");
  const productKeyword = keywordInput.value.trim();

  if (!productKeyword) {
    setAdStatus("请先输入产品关键词", false);
    keywordInput.focus();
    return;
  }

  const dailyBudget = Number(budgetInput.value);
  if (!dailyBudget || dailyBudget <= 0) {
    setAdStatus("每日预算必须大于 0", false);
    budgetInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>生成中...';
  setAdStatus("正在生成广告策略、出价建议和预算分配", true);
  setAdProgress(true);

  try {
    const data = await requestJson(endpoints.adOptimize, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_keyword: productKeyword,
        daily_budget: dailyBudget,
        target_acos: Number(acosSelect.value),
        ad_type: adTypeSelect.value,
        marketplace: marketplaceSelect.value,
        category: categorySelect.value,
      }),
    });
    renderAdOptimization(data);
    setAdStatus("广告策略已生成，可按预算与关键词表执行首轮投放", true);
  } catch (error) {
    setAdStatus(error.message, false);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      生成广告策略
    `;
  }
}

function renderAdOptimization(data) {
  renderAdMetrics(data.metrics);
  renderAdKeywordBids(data.keyword_bids || []);
  renderAdNegativeKeywords(data.negative_keywords || []);
  renderAdDayparting(data.dayparting_strategy || []);
  renderAdBudgetAllocation(data.budget_allocation || {});
  renderAdReport(data);
}

function renderAdMetrics(metrics) {
  const grid = document.getElementById("ad-metrics-grid");
  grid.innerHTML = `
    <article><span>建议日预算</span><strong>$${metrics.daily_budget}</strong><em>基准</em></article>
    <article><span>目标 ACoS</span><strong>${metrics.target_acos}%</strong><em>目标</em></article>
    <article><span>预估 ROAS</span><strong>${metrics.estimated_roas}x</strong><em>回报率</em></article>
    <article><span>基准 CPC</span><strong>$${metrics.baseline_cpc}</strong><em>估算</em></article>
  `;
}

function renderAdKeywordBids(rows) {
  document.getElementById("ad-keyword-count").textContent = `${rows.length} 个关键词`;
  const tbody = document.getElementById("ad-keyword-bids");
  tbody.innerHTML = rows.length
    ? rows
        .map((row) => {
          const competitionClass = row.competition === "高" ? "high" : row.competition === "中" ? "mid" : "low";
          return `
            <tr>
              <td>${escapeHtml(row.keyword)}</td>
              <td><span class="ad-match-tag">${escapeHtml(row.match_type)}</span></td>
              <td>$${row.suggested_bid}</td>
              <td>$${row.estimated_cpc}</td>
              <td><span class="ad-competition ${competitionClass}">${escapeHtml(row.competition)}</span></td>
              <td><button type="button" class="copy-btn" data-copy="${escapeHtml(row.keyword)}">复制</button></td>
            </tr>
          `;
        })
        .join("")
    : '<tr><td colspan="6">暂无关键词建议</td></tr>';

  tbody.querySelectorAll(".copy-btn").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.copy || ""));
  });
}

function renderAdNegativeKeywords(rows) {
  document.getElementById("ad-negative-count").textContent = `${rows.length} 个否定词`;
  const container = document.getElementById("ad-negative-keywords");
  container.classList.toggle("empty", rows.length === 0);
  container.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <span title="${escapeHtml(row.reason)}">${escapeHtml(row.keyword)} <button type="button" data-copy="${escapeHtml(row.keyword)}">复制</button></span>
          `,
        )
        .join("")
    : "暂无否定词建议";

  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.copy || ""));
  });
}

function renderAdDayparting(rows) {
  const container = document.getElementById("ad-dayparting-chart");
  container.innerHTML = rows
    .map((row) => {
      const height = Math.round(Number(row.bid_multiplier) * 54);
      const levelClass = row.level === "高峰时段" ? "peak" : row.level === "低谷时段" ? "low" : "normal";
      return `
        <div class="ad-hour-bar ${levelClass}" title="${row.hour}:00 ${escapeHtml(row.level)} ${row.bid_multiplier}x">
          <i style="height:${height}px"></i>
          <span>${row.hour}</span>
        </div>
      `;
    })
    .join("");
}

function renderAdBudgetAllocation(allocation) {
  const container = document.getElementById("ad-budget-allocation");
  const items = allocation.items || [];
  container.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article>
              <div>
                <strong>${escapeHtml(item.channel)}</strong>
                <span>${escapeHtml(item.goal)}</span>
              </div>
              <em>${item.ratio}% · $${item.daily_budget}/天</em>
              <div class="ad-budget-bar"><i style="width:${item.ratio}%"></i></div>
            </article>
          `,
        )
        .join("")
    : '<p class="empty">生成后显示 SP / SB / SD 配比</p>';
}

function renderAdReport(data) {
  document.getElementById("ad-report-text").textContent = data.report;
  document.getElementById("ad-launch-plan").innerHTML = (data.launch_plan || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  document.getElementById("ad-risk-controls").innerHTML = (data.risk_controls || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

function setAdStatus(message, ok) {
  const status = document.getElementById("ad-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

function setAdProgress(done) {
  document.querySelectorAll("#ad-progress-list div").forEach((item) => {
    item.classList.toggle("done", done);
  });
}

function copyText(value) {
  if (!value) return;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(value).catch(() => {});
  }
}

// ==================== 利润核算 ====================

function initProfitCalculator() {
  const form = document.getElementById("profit-form");
  const refreshButton = document.getElementById("refresh-profit-history");

  if (form) {
    form.addEventListener("submit", saveProfitCalculation);
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", loadProfitHistory);
  }
}

async function saveProfitCalculation(event) {
  event.preventDefault();
  const productInput = document.getElementById("profit-product-name");
  const button = document.getElementById("save-profit-calculation");
  const productName = productInput.value.trim();

  if (!productName) {
    setProfitStatus("请输入产品名称", false);
    productInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>保存中...';
  setProfitStatus("正在计算并保存核算快照", true);

  try {
    const data = await requestJson(endpoints.profitCalculate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readProfitPayload()),
    });
    renderProfitCalculation(data);
    await loadProfitHistory();
    setProfitStatus("利润核算已保存", true);
  } catch (error) {
    setProfitStatus(error.message, false);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      保存核算
    `;
  }
}

function readProfitPayload() {
  return {
    product_name: document.getElementById("profit-product-name").value.trim(),
    sku: document.getElementById("profit-sku").value.trim(),
    marketplace: document.getElementById("profit-marketplace").value,
    sale_price: readNumber("profit-sale-price"),
    landed_cost: readNumber("profit-landed-cost"),
    first_leg_freight: readNumber("profit-first-leg"),
    referral_rate: readNumber("profit-referral-rate") / 100,
    weight_oz: readNumber("profit-weight"),
    length_in: readNumber("profit-length"),
    width_in: readNumber("profit-width"),
    height_in: readNumber("profit-height"),
    ad_acos: readNumber("profit-ad-acos") / 100,
    return_rate: readNumber("profit-return-rate") / 100,
    monthly_units: Math.round(readNumber("profit-monthly-units")),
    monthly_fixed_cost: readNumber("profit-fixed-cost"),
    q4_peak: document.getElementById("profit-q4-peak").checked,
  };
}

function readNumber(id) {
  return Number(document.getElementById(id).value || 0);
}

function renderProfitCalculation(data) {
  const result = data.result || {};
  const health = result.health || {};
  document.getElementById("profit-monthly-profit").textContent = formatMoney(result.monthly_profit);
  document.getElementById("profit-health").textContent = `${health.label || "未评估"} · 毛利率 ${result.margin_percent || 0}%`;
  document.getElementById("profit-unit-profit").textContent = formatMoney(result.unit_profit);
  document.getElementById("profit-roi").textContent = `${result.roi_percent || 0}%`;
  document.getElementById("profit-break-even").textContent = `${result.break_even_units || 0} 单`;
  document.getElementById("profit-fba-tier").textContent = result.fba_tier || "--";
  renderProfitBreakdown(result.breakdown || []);
  renderProfitAdvice(result.advice || []);
}

function renderProfitBreakdown(items) {
  const container = document.getElementById("profit-breakdown");
  if (!items.length) {
    container.innerHTML = '<p class="empty">暂无成本明细</p>';
    return;
  }
  container.innerHTML = items
    .map((item) => {
      const sign = item.type === "income" ? "+" : "-";
      return `
        <div class="${item.type === "income" ? "income" : ""}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${sign}${formatMoney(item.amount)}</strong>
        </div>
      `;
    })
    .join("");
}

function renderProfitAdvice(advice) {
  const list = document.getElementById("profit-advice");
  list.innerHTML = advice.length
    ? advice.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>暂无建议</li>";
}

async function loadProfitHistory() {
  const container = document.getElementById("profit-history");
  if (!container) return;
  try {
    const data = await requestJson(`${endpoints.profitCalculations}?limit=6`, { method: "GET" });
    renderProfitHistory(data.items || []);
  } catch (error) {
    container.innerHTML = `<p class="notice-error">${escapeHtml(error.message)}</p>`;
  }
}

function renderProfitHistory(items) {
  const container = document.getElementById("profit-history");
  if (!items.length) {
    container.innerHTML = '<p class="empty">暂无保存记录</p>';
    return;
  }
  container.innerHTML = items
    .map((item) => {
      const result = item.result || {};
      const createdAt = item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "";
      return `
        <button class="profit-history-item" type="button" data-profit-id="${item.id}">
          <span>
            <strong>${escapeHtml(item.product_name)}</strong>
            <small>${escapeHtml(item.sku || item.marketplace)} · ${escapeHtml(createdAt)}</small>
          </span>
          <em>${formatMoney(result.unit_profit)} / 件</em>
        </button>
      `;
    })
    .join("");
}

function setProfitStatus(message, ok) {
  const status = document.getElementById("profit-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

// ==================== 销量监控 ====================

let smOverviewData = null;

async function initSalesMonitor() {
  const btn = document.getElementById("sm-refresh");
  if (btn && !btn._bound) {
    btn.addEventListener("click", loadSalesMonitorOverview);
    btn._bound = true;
  }
  await loadSalesMonitorOverview();
}

async function loadSalesMonitorOverview() {
  const listEl = document.getElementById("sm-alerts-list");
  if (listEl) listEl.innerHTML = '<p class="sm-empty">加载中…</p>';

  try {
    const data = await requestJson(`${endpoints.salesDashboard}?days=30`);
    smOverviewData = data;
    renderOpsSourceStatus("sales-source-status", data.source);
    const summaryRows = data.summary?.records || [];
    setText("sm-alert-count", formatOpsNumber(sumOpsField(summaryRows, "sales_amount")));
    setText("sm-affected-skus", formatOpsNumber(sumOpsField(summaryRows, "units_sold")));
    setText("sm-high-count", formatOpsNumber(sumOpsField(summaryRows, "order_count")));
    renderOpsTable("sm-alerts-list", data.trend?.records || [], [
      ["date", "日期"], ["sku", "SKU"], ["marketplace", "站点"],
      ["units_sold", "销量"], ["sales_amount", "销售额"],
      ["refund_amount", "退款额"], ["gross_profit", "毛利"],
    ]);
  } catch (e) {
    if (listEl) listEl.innerHTML = `<p class="sm-empty">加载失败：${escapeHtml(String(e))}</p>`;
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function renderSalesAlerts(alerts) {
  const listEl = document.getElementById("sm-alerts-list");
  if (!listEl) return;

  if (!alerts.length) {
    listEl.innerHTML = '<p class="sm-empty">暂无销量告警，一切正常 🎉</p>';
    return;
  }

  const typeLabels = { sales_drop: "销量骤降", sales_declining_3d: "连续下跌" };
  const sevLabels = { high: "高", medium: "中", low: "低" };
  const sevClass = { high: "sm-sev--high", medium: "sm-sev--medium", low: "sm-sev--low" };

  listEl.innerHTML = alerts.map((a) => {
    const summary = (a.agent_result && a.agent_result.summary) || a.reason || "暂无分析";
    return `
      <article class="sm-alert-card ${sevClass[a.severity] || ""}">
        <div class="sm-alert-head">
          <span class="sm-alert-type">${typeLabels[a.alert_type] || a.alert_type}</span>
          <span class="sm-alert-sku">${escapeHtml(a.sku)}</span>
          <span class="sm-alert-sev">${sevLabels[a.severity] || a.severity}</span>
          <span class="sm-alert-date">${a.date}</span>
        </div>
        <p class="sm-alert-summary">${escapeHtml(summary)}</p>
        ${a.status !== "pending" ? `<span class="sm-alert-status">${a.status}</span>` : ""}
      </article>
    `;
  }).join("");
}

function populateSkuSelect(alerts) {
  const sel = document.getElementById("sm-sku-select");
  if (!sel) return;

  const skus = [...new Set(alerts.map((a) => a.sku))].sort();
  sel.innerHTML = '<option value="">选择 SKU 查看详情</option>';
  skus.forEach((sku) => {
    sel.appendChild(new Option(sku, sku));
  });

  if (!sel._bound) {
    sel.addEventListener("change", () => {
      const sku = sel.value;
      if (sku) {
        loadSalesMonitorSkuMetrics(sku);
      } else {
        const detail = document.getElementById("sm-sku-detail");
        if (detail) detail.style.display = "none";
      }
    });
    sel._bound = true;
  }
}

async function loadSalesMonitorSkuMetrics(sku) {
  const detailEl = document.getElementById("sm-sku-detail");
  const chartEl = document.getElementById("sm-trend-chart");
  const alertsEl = document.getElementById("sm-sku-alerts");
  if (!detailEl) return;

  detailEl.style.display = "block";
  if (chartEl) chartEl.innerHTML = '<p class="sm-empty">加载中…</p>';

  try {
    const data = await requestJson(`/api/sales-monitor/metrics/${encodeURIComponent(sku)}?days=30`);
    renderSalesTrend(data.sales || [], chartEl);
    renderSkuAlerts(data.alerts || [], alertsEl);
  } catch (e) {
    if (chartEl) chartEl.innerHTML = `<p class="sm-empty">加载失败：${escapeHtml(String(e))}</p>`;
  }
}

function renderSalesTrend(sales, container) {
  if (!container) return;
  if (!sales.length) {
    container.innerHTML = '<p class="sm-empty">暂无销量数据</p>';
    return;
  }

  const maxUnits = Math.max(...sales.map((s) => s.units_sold), 1);

  container.innerHTML = `
    <div class="sm-bars">
      ${sales.map((s) => {
        const pct = Math.round((s.units_sold / maxUnits) * 100);
        return `
          <div class="sm-bar-col">
            <div class="sm-bar" style="height:${pct}%" title="${s.date}: ${s.units_sold} 单 / $${s.sales_amount}">
              <span class="sm-bar-val">${s.units_sold}</span>
            </div>
            <span class="sm-bar-label">${s.date.slice(5)}</span>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderSkuAlerts(alerts, container) {
  if (!container) return;
  if (!alerts.length) {
    container.innerHTML = '<p class="sm-empty">该 SKU 无近期告警</p>';
    return;
  }

  const typeLabels = { sales_drop: "销量骤降", sales_declining_3d: "连续下跌" };
  container.innerHTML = alerts.map((a) => {
    const summary = (a.agent_result && a.agent_result.summary) || a.reason || "";
    return `
      <article class="sm-sku-alert-item">
        <strong>${typeLabels[a.alert_type] || a.alert_type}</strong>
        <span>${a.date}</span>
        ${summary ? `<p>${escapeHtml(summary)}</p>` : ""}
      </article>
    `;
  }).join("");
}

// ==================== 领星运营数据模块 ====================

function renderOpsSourceStatus(id, source = {}) {
  const container = document.getElementById(id);
  if (!container) return;
  const ready = source.status === "configured";
  const partial = source.status === "partial";
  const updatedAt = source.source_updated_at
    ? new Date(source.source_updated_at).toLocaleString("zh-CN")
    : "尚未同步";
  container.className = `ops-source-card ${ready ? "is-ready" : partial ? "is-partial" : "is-missing"}`;
  container.innerHTML = `
    <div>
      <strong>数据来源：领星 MCP</strong>
      <p>${escapeHtml(source.message || "未配置领星 MCP")}</p>
    </div>
    <div class="ops-source-meta">
      <span>更新时间：${escapeHtml(updatedAt)}</span>
      ${ready ? "" : '<a class="secondary-button" href="#settings">前往 MCP 对接</a>'}
    </div>
  `;
}

function sumOpsField(records, field) {
  return records.reduce((total, record) => total + (Number(record[field]) || 0), 0);
}

function formatOpsNumber(value) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
    : String(value);
}

function formatOpsRate(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${(Math.abs(number) <= 1 ? number * 100 : number).toFixed(2)}%`;
}

function renderOpsKpis(id, records, definitions) {
  const container = document.getElementById(id);
  if (!container) return;
  container.innerHTML = definitions.map(([field, label, type = "number"]) => {
    const value = sumOpsField(records, field);
    const formatted = type === "rate" ? formatOpsRate(value) : formatOpsNumber(value);
    return `<article class="ops-kpi-card"><span>${escapeHtml(label)}</span><strong>${formatted}</strong></article>`;
  }).join("");
}

function renderOpsTable(id, records, columns) {
  const container = document.getElementById(id);
  if (!container) return;
  if (!records.length) {
    container.innerHTML = '<p class="sm-empty">暂无真实数据，请先配置并同步领星 MCP</p>';
    return;
  }
  container.innerHTML = `
    <table class="data-table ops-data-table">
      <thead><tr>${columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead>
      <tbody>${records.map((record) => `
        <tr>${columns.map(([field]) => `<td>${escapeHtml(formatOpsNumber(record[field]))}</td>`).join("")}</tr>
      `).join("")}</tbody>
    </table>
  `;
}

async function initAdsAnalysis() {
  const level = document.getElementById("ads-entity-level");
  if (level && !level._bound) {
    level.addEventListener("change", loadAdsAnalysis);
    level._bound = true;
  }
  await loadAdsAnalysis();
}

async function loadAdsAnalysis() {
  const level = document.getElementById("ads-entity-level")?.value || "campaign";
  try {
    const data = await requestJson(`${endpoints.adsDashboard}?days=30&level=${encodeURIComponent(level)}`);
    renderOpsSourceStatus("ads-source-status", data.source);
    const performance = data.performance?.records || [];
    renderOpsKpis("ads-kpis", performance, [
      ["spend", "广告花费"], ["ad_sales", "广告销售额"],
      ["ad_orders", "广告订单"], ["acos", "ACOS", "rate"],
      ["roas", "ROAS"], ["tacos", "TACOS", "rate"],
    ]);
    renderOpsTable("ads-entities-table", data.entities?.records || [], [
      ["entity_name", "投放实体"], ["campaign_name", "Campaign"],
      ["impressions", "曝光"], ["clicks", "点击"], ["spend", "花费"],
      ["ad_orders", "订单"], ["ad_sales", "销售额"], ["acos", "ACOS"],
    ]);
  } catch (error) {
    renderOpsLoadError("ads-entities-table", error);
  }
}

async function initInventoryAgent() {
  try {
    const data = await requestJson(`${endpoints.inventoryDashboard}?days=30`);
    renderOpsSourceStatus("inventory-source-status", data.source);
    const snapshot = data.snapshot?.records || [];
    renderOpsKpis("inventory-kpis", snapshot, [
      ["available_inventory", "可售库存"], ["reserved_inventory", "预留库存"],
      ["inbound_inventory", "在途库存"], ["inventory_value", "库存金额"],
    ]);
    renderOpsTable("inventory-table", data.replenishment?.records || [], [
      ["sku", "SKU"], ["daily_sales", "日均销量"], ["available_days", "可售天数"],
      ["coverage_days", "覆盖天数"], ["expected_stockout_date", "预计断货日"],
      ["recommended_replenishment", "建议补货量"],
      ["expected_arrival_date", "预计到货日"], ["purchase_order_status", "采购状态"],
    ]);
  } catch (error) {
    renderOpsLoadError("inventory-table", error);
  }
}

function renderOpsLoadError(id, error) {
  const container = document.getElementById(id);
  if (container) {
    container.innerHTML = `<p class="sm-empty">加载失败：${escapeHtml(String(error))}</p>`;
  }
}

// ==================== FBA 成本估算 ====================

function initFbaEstimator() {
  const form = document.getElementById("fba-form");
  if (!form) return;
  form.addEventListener("input", debounceFbaEstimate);
  form.addEventListener("change", runFbaEstimate);
}

let fbaEstimateTimer = null;

function debounceFbaEstimate() {
  window.clearTimeout(fbaEstimateTimer);
  fbaEstimateTimer = window.setTimeout(runFbaEstimate, 180);
}

async function runFbaEstimate() {
  const form = document.getElementById("fba-form");
  if (!form) return;
  setFbaStatus("正在估算...", true);
  try {
    const data = await requestJson(endpoints.fbaEstimate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readFbaPayload()),
    });
    renderFbaEstimate(data);
    setFbaStatus("", true);
  } catch (error) {
    setFbaStatus(error.message, false);
  }
}

function readFbaPayload() {
  const season = document.querySelector('input[name="fba-season"]:checked')?.value || "normal";
  return {
    weight_oz: readNumber("fba-weight"),
    length_in: readNumber("fba-length"),
    width_in: readNumber("fba-width"),
    height_in: readNumber("fba-height"),
    category: document.getElementById("fba-category").value,
    season,
    sale_price: readNumber("fba-sale-price"),
    landed_cost: readNumber("fba-landed-cost"),
    monthly_units: Math.max(1, Math.round(readNumber("fba-monthly-units"))),
  };
}

function renderFbaEstimate(data) {
  document.getElementById("fba-tier-badge").textContent = data.size_tier;
  document.getElementById("fba-total-cost").textContent = formatMoney(data.total_fba_cost);
  document.getElementById("fba-formula").textContent = `= ${data.formula} / 单`;
  document.getElementById("fba-fulfillment").textContent = formatMoney(data.fulfillment_fee);
  document.getElementById("fba-storage").textContent = formatMoney(data.storage_fee);
  document.getElementById("fba-referral").textContent = data.referral_fee > 0 ? formatMoney(data.referral_fee) : "--";
  document.getElementById("fba-referral-note").textContent = data.referral_fee > 0
    ? `Referral ${data.referral_rate_percent}%`
    : "需填写售价";
  document.getElementById("fba-profit-note").textContent = renderFbaProfitText(data);
  renderFbaTierTable(data.tier_table || [], data.size_tier);
}

function renderFbaProfitText(data) {
  const profit = data.profit || {};
  if (!profit.unit_profit) {
    return "填写售价 + 进货成本可显示净利、毛利率与保本售价。";
  }
  return `净利 ${formatMoney(profit.unit_profit)} / 单 · 毛利率 ${profit.margin_percent}% · Billable weight ${data.billable_weight_lb} lb`;
}

function renderFbaTierTable(rows, activeTier) {
  const tbody = document.getElementById("fba-tier-table");
  tbody.innerHTML = rows
    .map((row) => `
      <tr class="${row.tier === activeTier ? "active" : ""}">
        <td><strong>${escapeHtml(row.tier)}</strong></td>
        <td>${escapeHtml(row.weight_range)}</td>
        <td>${escapeHtml(row.size_limit)}</td>
        <td><strong>${escapeHtml(row.fee_range)}</strong></td>
      </tr>
    `)
    .join("");
}

function setFbaStatus(message, ok) {
  const status = document.getElementById("fba-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

// ==================== 供应链分析 ====================

function initSupplyChainAnalysis() {
  const button = document.getElementById("run-supply-chain");
  const productInput = document.getElementById("supply-product");

  if (button) {
    button.addEventListener("click", runSupplyChainAnalysis);
  }

  if (productInput) {
    productInput.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        runSupplyChainAnalysis();
      }
    });
  }
}

async function runSupplyChainAnalysis() {
  const productInput = document.getElementById("supply-product");
  const quantitySelect = document.getElementById("supply-quantity");
  const marketplaceSelect = document.getElementById("supply-marketplace");
  const logisticsSelect = document.getElementById("supply-logistics");
  const budgetSelect = document.getElementById("supply-budget");
  const categorySelect = document.getElementById("supply-category");
  const button = document.getElementById("run-supply-chain");
  const product = productInput.value.trim();

  if (!product) {
    setSupplyStatus("请先输入产品", false);
    productInput.focus();
    return;
  }

  button.disabled = true;
  button.innerHTML = '<span class="loading"></span>分析中...';
  setSupplyStatus("正在估算成本、供应商、物流和备货补货方案", true);

  try {
    const data = await requestJson(endpoints.supplyChainAnalyze, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product,
        purchase_quantity: Number(quantitySelect.value),
        marketplace: marketplaceSelect.value,
        logistics_method: logisticsSelect.value,
        budget: Number(budgetSelect.value),
        category: categorySelect.value,
      }),
    });
    renderSupplyChainAnalysis(data);
    setSupplyStatus("供应链方案已生成，建议用真实供应商和物流报价复核后执行", true);
  } catch (error) {
    setSupplyStatus(error.message, false);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      分析供应链
    `;
  }
}

function renderSupplyChainAnalysis(data) {
  document.getElementById("supply-empty-state").style.display = "none";
  document.getElementById("supply-results").style.display = "block";

  renderSupplyCosts(data.cost_analysis);
  renderSupplySupplier(data.supplier_evaluation);
  renderSupplyLogistics(data.logistics_plan);
  renderSupplyInventory(data.inventory_plan);
  renderSupplyCashFlow(data.cash_flow);
  renderSupplyRisks(data.risk_controls || []);
  document.getElementById("supply-report-text").textContent = data.report;
}

function renderSupplyCosts(cost) {
  document.getElementById("supply-cost-per-unit").textContent = `$${cost.cost_per_unit}/件`;
  document.getElementById("supply-cost-breakdown").innerHTML = [
    ["货品成本", cost.goods_cost],
    ["头程物流", cost.logistics_cost],
    ["包装成本", cost.packaging_cost],
    ["质检成本", cost.inspection_cost],
    ["关税预留", cost.duty_cost],
    ["总成本", cost.total_cost],
  ]
    .map(
      ([label, value]) => `
        <div>
          <span>${label}</span>
          <strong>$${value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderSupplySupplier(supplier) {
  document.getElementById("supply-supplier-grade").textContent = supplier.grade;
  document.getElementById("supply-supplier-score").innerHTML = `
    <span>综合评分</span>
    <strong>${supplier.overall_score}/100</strong>
  `;
  document.getElementById("supply-supplier-dimensions").innerHTML = supplier.dimensions
    .map(
      (item) => `
        <div>
          <span>${escapeHtml(item.label)}</span>
          <strong>${item.score}%</strong>
          <i><em style="width:${Math.max(0, Math.min(100, item.score))}%"></em></i>
        </div>
      `,
    )
    .join("");
}

function renderSupplyLogistics(plan) {
  document.getElementById("supply-logistics-label").textContent = plan.label;
  document.getElementById("supply-logistics-plan").innerHTML = `
    <div><span>预计头程</span><strong>${plan.lead_time_days} 天</strong></div>
    <div><span>安全缓冲</span><strong>${plan.buffer_days} 天</strong></div>
    <div><span>建议批次</span><strong>${plan.batch_count} 批</strong></div>
    <div><span>单件物流</span><strong>$${plan.cost_per_unit}</strong></div>
    <p>${escapeHtml(plan.recommendation)}</p>
  `;
}

function renderSupplyInventory(plan) {
  document.getElementById("supply-inventory-plan").innerHTML = `
    ${renderSupplyMetric("首批备货", `${plan.first_stock_units} 件`)}
    ${renderSupplyMetric("建议补货批量", `${plan.replenish_units} 件`)}
    ${renderSupplyMetric("补货点", `${plan.reorder_point_units} 件`)}
    ${renderSupplyMetric("安全库存", `${plan.safety_stock_days} 天`)}
    ${renderSupplyMetric("周转周期", `${plan.turnover_days} 天`)}
    <p>${escapeHtml(plan.logic)}</p>
  `;
}

function renderSupplyCashFlow(cash) {
  document.getElementById("supply-cash-flow").innerHTML = `
    ${renderSupplyMetric("预算", `$${cash.budget}`)}
    ${renderSupplyMetric("预算使用率", `${cash.budget_usage_rate}%`)}
    ${renderSupplyMetric("首批现金占用", `$${cash.first_batch_cash}`)}
    ${renderSupplyMetric("预留现金", `$${cash.reserved_cash}`)}
    ${renderSupplyMetric("资金压力", cash.capital_pressure)}
  `;
}

function renderSupplyMetric(label, value) {
  return `
    <div>
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderSupplyRisks(risks) {
  document.getElementById("supply-risk-controls").innerHTML = risks
    .map((risk) => `<li>${escapeHtml(risk)}</li>`)
    .join("");
}

function setSupplyStatus(message, ok) {
  const status = document.getElementById("supply-status");
  if (!status) return;
  status.textContent = message;
  status.className = message ? `listing-status ${ok ? "ok" : "error"}` : "listing-status";
}

// ==================== 聊天功能 ====================

const CHAT_CONVERSATION_STORAGE_KEY = "amazon_agent_chat_conversation_id";
let chatConversationId = localStorage.getItem(CHAT_CONVERSATION_STORAGE_KEY) || "default";
let chatIsStreaming = false;
let chatInitialized = false;

// 初始化聊天
function initChat() {
  if (chatInitialized) return;
  chatInitialized = true;

  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const quickBtns = document.querySelectorAll(".quick-btn");
  const refreshHistoryBtn = document.getElementById("chat-history-refresh");
  const newSessionBtn = document.getElementById("chat-new-session");

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

  if (refreshHistoryBtn) {
    refreshHistoryBtn.addEventListener("click", loadChatSessions);
  }
  if (newSessionBtn) {
    newSessionBtn.addEventListener("click", startNewChatSession);
  }
  showChatWelcome();
  loadChatSessions({ restoreLatest: true });
}

function startNewChatSession() {
  chatConversationId = `chat-${Date.now()}`;
  persistChatConversationId();
  const messagesContainer = document.getElementById("chat-messages");
  if (messagesContainer) {
    messagesContainer.innerHTML = "";
  }
  showChatWelcome();
  loadChatSessions();
  updateChatStatus("新会话");
}

function persistChatConversationId() {
  localStorage.setItem(CHAT_CONVERSATION_STORAGE_KEY, chatConversationId);
}

async function loadChatSessions(options = {}) {
  try {
    const data = await requestJson("/chat/sessions");
    const sessions = data.sessions || [];
    if (options.restoreLatest && chatConversationId === "default" && sessions.length) {
      chatConversationId = sessions[0].id;
      persistChatConversationId();
      renderChatSessions(sessions);
      await loadChatHistory();
      return;
    }
    renderChatSessions(sessions);
    if (options.restoreLatest) {
      await loadChatHistory();
    }
  } catch (error) {
    console.error("加载会话列表失败:", error);
    if (options.restoreLatest) {
      loadChatHistory();
    }
  }
}

function renderChatSessions(sessions) {
  const list = document.getElementById("chat-session-list");
  if (!list) return;
  const knownSessions = Array.isArray(sessions) ? sessions : [];
  const hasCurrent = knownSessions.some((session) => session.id === chatConversationId);
  const visibleSessions = hasCurrent || chatConversationId === "default"
    ? knownSessions
    : [
        {
          id: chatConversationId,
          title: "新会话",
          message_count: 0,
          updated_at: "",
        },
        ...knownSessions,
      ];
  if (!visibleSessions.length) {
    list.innerHTML = '<p class="chat-history-empty">暂无会话记录</p>';
    return;
  }
  list.innerHTML = visibleSessions
    .map((session) => {
      const active = session.id === chatConversationId ? " is-active" : "";
      const title = escapeHtml(session.title || "未命名会话");
      const meta = session.message_count ? `${session.message_count} 条消息` : "新会话";
      return `
        <button class="chat-session-item${active}" type="button" data-session-id="${escapeHtml(session.id)}">
          <span>${title}</span>
          <small>${escapeHtml(meta)}</small>
        </button>
      `;
    })
    .join("");
  list.querySelectorAll(".chat-session-item").forEach((item) => {
    item.addEventListener("click", () => {
      const nextId = item.dataset.sessionId;
      if (!nextId || nextId === chatConversationId || chatIsStreaming) return;
      chatConversationId = nextId;
      persistChatConversationId();
      loadChatHistory();
      renderChatSessions(visibleSessions);
    });
  });
}

async function loadChatHistory() {
  const messagesContainer = document.getElementById("chat-messages");
  if (!messagesContainer) return;

  try {
    const data = await requestJson(`/chat/history?conversation_id=${encodeURIComponent(chatConversationId)}`);
    messagesContainer.innerHTML = "";
    const messages = data.messages || [];
    if (!messages.length) {
      showChatWelcome();
      return;
    }
    messages
      .filter((message) => message.role === "user" || message.role === "assistant")
      .forEach((message) => addChatMessage(message.role, message.content || ""));
  } catch (error) {
    console.error("加载聊天历史失败:", error);
  }
}

function showChatWelcome() {
  const messagesContainer = document.getElementById("chat-messages");
  if (!messagesContainer) return;
  messagesContainer.innerHTML = `
    <div class="chat-welcome">
      <div class="welcome-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
      </div>
      <h3>欢迎使用 AI 运营助手</h3>
      <p>我可以帮你查询运营数据、分析问题、提供建议</p>
      <div class="quick-questions">
        <button class="quick-btn" data-question="查询最近7天销售最好的SKU">查询热销 SKU</button>
        <button class="quick-btn" data-question="查看库存告警">库存告警</button>
        <button class="quick-btn" data-question="分析广告ACOS表现">广告分析</button>
        <button class="quick-btn" data-question="查看今日待处理任务">待处理任务</button>
      </div>
    </div>
  `;
  messagesContainer.querySelectorAll(".quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const chatForm = document.getElementById("chat-form");
      const chatInput = document.getElementById("chat-input");
      const question = btn.dataset.question;
      if (question && chatForm && chatInput) {
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
    let sseBuffer = "";
    let streamHadError = false;

    const processSseBlock = (block) => {
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n")
        .trim();
      if (!data) return;

      try {
        const event = JSON.parse(data);

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
            // 把 MCP 工具的返回结果也显示出来
            if (event.tool && event.tool.startsWith("sellersprite_") && event.result) {
              const resultBlock = document.createElement("div");
              resultBlock.className = "tool-result";
              resultBlock.style.cssText = "margin:8px 0; padding:10px 12px; background:#f8fafc; border-left:3px solid #2563EB; border-radius:4px; font-size:13px; white-space:pre-wrap; max-height:400px; overflow-y:auto;";
              resultBlock.textContent = event.result;
              messageElement.appendChild(resultBlock);
              scrollChatToBottom();
            }
            break;

          case "image":
            if (!messageElement) {
              removeTypingIndicator(typingId);
              messageElement = addChatMessage("assistant", "");
            }
            addImageMessage(messageElement, event);
            break;

          case "done":
            chatConversationId = event.conversation_id || chatConversationId;
            persistChatConversationId();
            loadChatSessions();
            break;

          case "error":
            streamHadError = true;
            removeTypingIndicator(typingId);
            if (!messageElement) {
              messageElement = addChatMessage("assistant", "");
            }
            assistantContent += `错误: ${event.content}`;
            updateMessageContent(messageElement, assistantContent);
            break;
          }
      } catch (e) {
        if (e.message !== "请求失败") {
          console.error("解析事件失败:", e);
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const blocks = sseBuffer.split("\n\n");
      sseBuffer = blocks.pop() || "";
      for (const block of blocks) {
        processSseBlock(block);
      }
    }

    sseBuffer += decoder.decode();
    if (sseBuffer.trim()) {
      processSseBlock(sseBuffer);
    }

    // 如果没有收到内容，显示默认消息
    if (!assistantContent && !messageElement && !streamHadError) {
      removeTypingIndicator(typingId);
      addChatMessage("assistant", "抱歉，我无法处理您的请求。请稍后再试。");
    }
  } catch (error) {
    removeTypingIndicator(typingId);
    addChatMessage("assistant", `错误: ${error.message}`);
  } finally {
    chatIsStreaming = false;
    updateChatStatus("在线");
    loadChatSessions();
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
    renderGeneratedImageLinks(contentDiv, content);
    scrollToBottom();
  }
}

function addImageMessage(messageElement, event) {
  const contentDiv = messageElement.querySelector(".message-content");
  if (!contentDiv || !event.url) return;

  const card = document.createElement("div");
  card.className = "generated-image-card";
  card.dataset.url = event.url;

  const title = event.title || "产品图";
  const prompt = event.prompt || "";
  card.innerHTML = `
    <img src="${escapeHtml(event.url)}" alt="${escapeHtml(title)}" />
    <div class="generated-image-meta">
      <strong>${escapeHtml(title)}</strong>
      ${prompt ? `<p>${escapeHtml(prompt)}</p>` : ""}
    </div>
  `;
  contentDiv.appendChild(card);
  scrollToBottom();
}

function renderGeneratedImageLinks(contentDiv, content) {
  const matches = content.match(/\/static\/generated\/[A-Za-z0-9_-]+\.png/g) || [];
  const uniqueUrls = [...new Set(matches)];
  for (const url of uniqueUrls) {
    if (contentDiv.querySelector(`.generated-image-card[data-url="${cssEscape(url)}"]`)) {
      continue;
    }
    addImageMessage(
      { querySelector: () => contentDiv },
      {
        url,
        title: "产品图",
        prompt: "",
      },
    );
  }
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === "function") {
    return window.CSS.escape(value);
  }
  return value.replace(/"/g, '\\"');
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

const mcpSettingsState = { sources: [], editingId: null, query: "" };

function mcpAuthHeaders(headers = {}) {
  const token = localStorage.getItem("access_token");
  return { ...headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function requestMcpJson(url, options = {}) {
  return requestJson(url, { ...options, headers: mcpAuthHeaders(options.headers || {}) });
}

async function loadSettings() {
  try {
    const result = await requestMcpJson("/api/settings/mcp-sources");
    mcpSettingsState.sources = result.items || [];
    renderMcpSources();
  } catch (error) {
    showMessage(document.getElementById("mcp-message"), `加载数据源失败：${error.message}`, "error");
  }
}

function initSettings() {
  const form = document.getElementById("mcp-form");
  const search = document.getElementById("mcp-search");
  form?.addEventListener("submit", saveMcpSettings);
  document.getElementById("test-mcp-connection")?.addEventListener("click", testMcpConnection);
  document.getElementById("mcp-add-server")?.addEventListener("click", () => openMcpEditor());
  document.getElementById("mcp-close-editor")?.addEventListener("click", closeMcpEditor);
  document.getElementById("mcp-server-list")?.addEventListener("click", handleMcpListClick);
  document.getElementById("mcp-server-list")?.addEventListener("change", handleMcpListChange);
  search?.addEventListener("input", () => {
    mcpSettingsState.query = search.value.trim().toLowerCase();
    renderMcpSources();
  });
}

function renderMcpSources() {
  const list = document.getElementById("mcp-server-list");
  if (!list) return;
  const rows = mcpSettingsState.sources.filter((source) =>
    source.name.toLowerCase().includes(mcpSettingsState.query)
  );
  document.getElementById("mcp-server-count").textContent = String(mcpSettingsState.sources.length);
  if (!rows.length) {
    list.innerHTML = '<p class="empty-state">暂无匹配的数据源</p>';
    return;
  }
  list.innerHTML = rows.map((source) => {
    const capabilityCount = Object.keys(source.capabilities || {}).length;
    const statusLabel = source.connectionStatus || "待测试";
    return `
      <article class="mcp-server-card" data-source-id="${source.id}">
        <div class="mcp-server-identity">
          <strong>${escapeHtml(source.name)}</strong>
          <small>${capabilityCount} 项能力 · 优先级 ${source.priority} · ${escapeHtml(statusLabel)}</small>
        </div>
        <div class="mcp-server-actions">
          <button class="mcp-icon-button" type="button" data-mcp-action="edit" aria-label="编辑 ${escapeHtml(source.name)}">编辑</button>
          <label class="mcp-toggle" title="启用或停用 MCP 服务">
            <input type="checkbox" data-mcp-action="toggle" ${source.enabled ? "checked" : ""} />
            <span></span>
          </label>
        </div>
      </article>`;
  }).join("");
}

function handleMcpListClick(event) {
  const button = event.target.closest('[data-mcp-action="edit"]');
  if (!button) return;
  const id = Number(button.closest("[data-source-id]").dataset.sourceId);
  openMcpEditor(mcpSettingsState.sources.find((source) => source.id === id));
}

async function handleMcpListChange(event) {
  if (event.target.dataset.mcpAction !== "toggle") return;
  const id = Number(event.target.closest("[data-source-id]").dataset.sourceId);
  const previous = !event.target.checked;
  try {
    const updated = await requestMcpJson(`/api/settings/mcp-sources/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: event.target.checked }),
    });
    replaceMcpSource(updated);
  } catch (error) {
    event.target.checked = previous;
    showMessage(document.getElementById("mcp-message"), `状态更新失败：${error.message}`, "error");
  }
}

function openMcpEditor(source = null) {
  mcpSettingsState.editingId = source?.id || null;
  document.getElementById("mcp-editor-title").textContent = source ? "编辑服务器" : "添加服务器";
  document.getElementById("mcp-name").value = source?.name || "";
  document.getElementById("mcp-url").value = source?.url || "";
  document.getElementById("mcp-transport").value = source?.transport || "streamable_http";
  document.getElementById("mcp-priority").value = source?.priority || 10;
  document.getElementById("mcp-capabilities").value = source
    ? JSON.stringify(source.capabilities || {}, null, 2)
    : "";
  document.getElementById("mcp-enabled-editor").checked = source?.enabled ?? true;
  document.getElementById("mcp-api-key").value = "";
  document.getElementById("mcp-headers").value = "";
  document.getElementById("test-mcp-connection").disabled = !source;
  document.getElementById("mcp-form").hidden = false;
  document.getElementById("mcp-name").focus();
}

function closeMcpEditor() {
  mcpSettingsState.editingId = null;
  document.getElementById("mcp-form").hidden = true;
}

async function saveMcpSettings(event) {
  event.preventDefault();
  const messageEl = document.getElementById("mcp-message");
  let capabilities;
  let headers;
  try {
    capabilities = JSON.parse(document.getElementById("mcp-capabilities").value);
    const rawHeaders = document.getElementById("mcp-headers").value.trim();
    headers = rawHeaders ? JSON.parse(rawHeaders) : {};
    if (!capabilities || Array.isArray(capabilities) || typeof capabilities !== "object") throw new Error("能力映射必须是 JSON 对象");
    if (!headers || Array.isArray(headers) || typeof headers !== "object") throw new Error("请求头必须是 JSON 对象");
  } catch (error) {
    showMessage(messageEl, error.message || "JSON 格式无效", "error");
    return;
  }

  const payload = {
    name: document.getElementById("mcp-name").value.trim(),
    url: document.getElementById("mcp-url").value.trim(),
    transport: document.getElementById("mcp-transport").value,
    priority: Number(document.getElementById("mcp-priority").value),
    enabled: document.getElementById("mcp-enabled-editor").checked,
    capabilities,
    api_key: document.getElementById("mcp-api-key").value.trim(),
    headers,
  };

  try {
    const id = mcpSettingsState.editingId;
    const saved = await requestMcpJson(id ? `/api/settings/mcp-sources/${id}` : "/api/settings/mcp-sources", {
      method: id ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    replaceMcpSource(saved);
    showMessage(messageEl, "MCP 数据源已保存", "success");
    closeMcpEditor();
  } catch (error) {
    showMessage(messageEl, `保存失败：${error.message}`, "error");
  }
}

function replaceMcpSource(source) {
  const index = mcpSettingsState.sources.findIndex((item) => item.id === source.id);
  if (index >= 0) mcpSettingsState.sources[index] = source;
  else mcpSettingsState.sources.push(source);
  renderMcpSources();
}

async function testMcpConnection() {
  const messageEl = document.getElementById("mcp-message");
  const id = mcpSettingsState.editingId;
  if (!id) return;
  showMessage(messageEl, "正在测试连接...", "info");

  try {
    const result = await requestMcpJson(`/api/settings/mcp-sources/${id}/test`, { method: "POST" });
    const source = mcpSettingsState.sources.find((item) => item.id === id);
    if (source) source.connectionStatus = result.success ? "已连接" : "连接异常";
    renderMcpSources();
    if (result.success) {
      showMessage(messageEl, result.message || "连接成功", "success");
    } else {
      const missing = Object.keys(result.missing_mappings || {});
      const suffix = missing.length ? `：${missing.join("、")}` : "";
      showMessage(messageEl, `${result.message || "连接失败"}${suffix}`, "error");
    }
  } catch (error) {
    const source = mcpSettingsState.sources.find((item) => item.id === id);
    if (source) {
      source.connectionStatus = "连接异常";
      renderMcpSources();
    }
    showMessage(messageEl, `测试失败：${error.message}`, "error");
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

function removedBattlefieldView() {
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

function removedDiagnosisView() {
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
        <div class="task-detail">
          <span class="task-detail-label">上次执行</span>
          <span class="task-detail-value">${task.last_run ? task.last_run.replace("T", " ").slice(0, 16) : "从未执行"}</span>
        </div>
        ${task.last_result ? `
        <div class="task-detail task-result">
          <span class="task-detail-label">执行结果</span>
          <span class="task-detail-value ${task.last_result.success === false ? "task-result-fail" : ""}">${escapeHtml(String(task.last_result.message || task.last_result.error || JSON.stringify(task.last_result)).slice(0, 80))}</span>
        </div>` : ""}
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

async function editTask(taskId) {
  try {
    const resp = await fetch(`/api/automation/tasks/${taskId}`);
    if (!resp.ok) throw new Error("获取任务详情失败");
    const task = await resp.json();
    showEditTaskModal(task);
  } catch (e) {
    alert("加载任务详情失败: " + e.message);
  }
}

function showEditTaskModal(task) {
  // 移除已有弹窗
  const existing = document.getElementById("edit-task-modal");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "edit-task-modal";
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h3>编辑任务：${escapeHtml(task.name)}</h3>
        <button class="modal-close" onclick="closeEditTaskModal()">&times;</button>
      </div>
      <div class="modal-body">
        <label class="modal-label">
          执行时间
          <input type="time" id="edit-schedule-time" value="${task.schedule_time || "08:00"}" class="modal-input" />
        </label>
        <label class="modal-label">
          启用状态
          <label class="modal-toggle-label">
            <input type="checkbox" id="edit-enabled" ${task.enabled ? "checked" : ""} />
            <span>${task.enabled ? "已启用" : "已禁用"}</span>
          </label>
        </label>
        <label class="modal-label">
          配置参数（JSON）
          <textarea id="edit-config" class="modal-textarea" rows="4">${JSON.stringify(task.config || {}, null, 2)}</textarea>
        </label>
      </div>
      <div class="modal-footer">
        <button class="task-btn" onclick="closeEditTaskModal()">取消</button>
        <button class="task-btn primary" onclick="saveEditTask('${task.task_id}')">保存</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeEditTaskModal();
  });
}

function closeEditTaskModal() {
  const modal = document.getElementById("edit-task-modal");
  if (modal) modal.remove();
}

async function saveEditTask(taskId) {
  const scheduleTime = document.getElementById("edit-schedule-time")?.value;
  const enabled = document.getElementById("edit-enabled")?.checked;
  const configText = document.getElementById("edit-config")?.value;

  let config;
  try {
    config = configText ? JSON.parse(configText) : undefined;
  } catch {
    alert("配置参数 JSON 格式错误");
    return;
  }

  const body = {};
  if (scheduleTime) body.schedule_time = scheduleTime;
  if (typeof enabled === "boolean") body.enabled = enabled;
  if (config !== undefined) body.config = config;

  try {
    const resp = await fetch(`/api/automation/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error((await resp.json()).detail || "保存失败");
    closeEditTaskModal();
    loadAutomationTasks();
  } catch (e) {
    alert("保存失败: " + e.message);
  }
}

// 在 DOMContentLoaded 中初始化自动化任务
document.addEventListener("DOMContentLoaded", initAutomation);

document.addEventListener("DOMContentLoaded", initListingOptimization);
document.addEventListener("DOMContentLoaded", initAdOptimization);
document.addEventListener("DOMContentLoaded", initSupplyChainAnalysis);
document.addEventListener("DOMContentLoaded", initProfitCalculator);
document.addEventListener("DOMContentLoaded", initFbaEstimator);
