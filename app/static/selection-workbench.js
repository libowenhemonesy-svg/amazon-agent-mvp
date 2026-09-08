(function () {
  "use strict";

  const selectionState = {
    projects: [],
    currentProject: null,
    currentStage: "keywords",
    inputType: "seed",
    keywordRows: [],
    keywordPageCount: 0,
    selectedKeywordIds: new Set(),
    direction: null,
    pricing: null,
    report: null,
    freightTemplates: [],
    initialized: false,
  };

  const MCP_FIELD_LABELS = Object.freeze({
    id: "记录 ID", project_id: "项目 ID", run_id: "调研任务 ID", keyword: "关键词",
    keywordCn: "关键词中文名", keyword_translation: "关键词中文名", searches: "搜索量",
    search_volume: "搜索量", products: "商品数", product_count: "商品数", purchases: "购买量",
    monthly_purchase_volume: "月购买量", purchaseRate: "购买率", bid: "建议竞价",
    bidMin: "最低竞价", bidMax: "最高竞价", badges: "标签", searchesRank: "搜索量排名",
    latest1daysAds: "近 1 日广告商品数", latest7daysAds: "近 7 日广告商品数",
    latest30daysAds: "近 30 日广告商品数", supplyDemandRatio: "供需比",
    trafficPercentage: "流量占比", calculatedWeeklySearches: "预估周搜索量",
    avgPrice: "平均价格", avgReviews: "平均评论数", avgRating: "平均评分",
    titleDensity: "标题密度", spr: "供需比", monopolyClickRate: "垄断点击率",
    top3ClickingRate: "前三点击率", top3ConversionRate: "前三转化率",
    relationVariationsItems: "关联变体", trend_rate: "趋势变化率", trend_period: "趋势周期",
    competition_index: "竞争指数", cpc: "单次点击成本", conversion_rate: "转化率",
    relevance_score: "相关性评分", opportunity_score: "机会评分", source_id: "数据源 ID",
    source_name: "数据源", collected_at: "采集时间", selected: "已选中", created_at: "创建时间",
  });

  const MCP_FIELD_CANONICAL = Object.freeze({
    keyword_translation: "keywordCn",
    search_volume: "searches",
    product_count: "products",
    monthly_purchase_volume: "purchases",
    cpc: "bid",
  });

  const MCP_IGNORED_FIELDS = new Set(["metrics", "field_lineage"]);

  const root = () => document.getElementById("selection-workbench");

  async function api(url, options) {
    const token = localStorage.getItem("access_token");
    const requestOptions = {
      ...(options || {}),
      headers: {
        ...(options?.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };
    if (typeof window.requestJson === "function") {
      return window.requestJson(url, requestOptions);
    }
    const response = await fetch(url, requestOptions);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `请求失败（${response.status}）`);
    }
    return response.json();
  }

  async function optionalApi(url) {
    try {
      return await api(url);
    } catch (error) {
      return null;
    }
  }

  function init() {
    const container = root();
    if (!container || selectionState.initialized) return;
    selectionState.initialized = true;
    container.addEventListener("click", onClick);
    container.addEventListener("change", onChange);
    container.addEventListener("input", onInput);
    container.addEventListener("submit", onSubmit);
    loadProjects();
  }

  function activate() {
    init();
    loadProjects();
  }

  async function loadProjects() {
    try {
      const data = await api("/api/selection/projects");
      selectionState.projects = data.items || [];
      renderProjects();
      if (selectionState.currentProject) {
        const current = selectionState.projects.find(
          (item) => item.id === selectionState.currentProject.id
        );
        if (current) selectionState.currentProject = current;
      }
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  async function chooseProject(projectId) {
    const project = selectionState.projects.find((item) => item.id === projectId);
    if (!project) return;
    selectionState.currentProject = project;
    selectionState.currentStage = "keywords";
    renderProjects();
    renderWorkspace();
    await Promise.all([
      loadKeywords(),
      loadDirection(),
      loadPricing(),
      loadReport(),
      loadFreightTemplates(),
    ]);
  }

  async function loadKeywords() {
    if (!selectionState.currentProject) return;
    try {
      const data = await api(
        `/api/selection/projects/${selectionState.currentProject.id}/keywords`
      );
      selectionState.keywordRows = data.items || [];
      selectionState.keywordPageCount = 0;
      selectionState.selectedKeywordIds = new Set(
        selectionState.keywordRows.filter((item) => item.selected).map((item) => item.id)
      );
      renderKeywords();
      renderMcpFields();
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  async function loadDirection() {
    if (!selectionState.currentProject) return;
    selectionState.direction = await optionalApi(
      `/api/selection/projects/${selectionState.currentProject.id}/product-direction`
    );
    renderDirection();
  }

  async function loadPricing() {
    if (!selectionState.currentProject) return;
    selectionState.pricing = await optionalApi(
      `/api/selection/projects/${selectionState.currentProject.id}/pricing`
    );
    renderPricing();
  }

  async function loadReport() {
    if (!selectionState.currentProject) return;
    selectionState.report = await optionalApi(
      `/api/selection/projects/${selectionState.currentProject.id}/report`
    );
    renderReport();
  }

  async function loadFreightTemplates() {
    try {
      const data = await api("/api/selection/freight-templates");
      selectionState.freightTemplates = (data.items || []).filter((item) => item.enabled);
      renderFreightTemplates();
    } catch (error) {
      selectionState.freightTemplates = [];
      renderFreightTemplates();
    }
  }

  function onClick(event) {
    const projectButton = event.target.closest("[data-selection-project-id]");
    if (projectButton) {
      chooseProject(Number(projectButton.dataset.selectionProjectId));
      return;
    }
    const stageButton = event.target.closest("[data-selection-stage-target]");
    if (stageButton) {
      setStage(stageButton.dataset.selectionStageTarget);
      return;
    }
    const inputButton = event.target.closest("[data-selection-input-type]");
    if (inputButton) {
      setInputType(inputButton.dataset.selectionInputType);
      return;
    }
    const action = event.target.closest("[data-selection-action]")?.dataset.selectionAction;
    if (!action) return;
    if (action === "show-project-form") toggleProjectForm(true);
    if (action === "cancel-project") toggleProjectForm(false);
    if (action === "save-keywords") saveSelectedKeywords(true);
    if (action === "build-direction") buildDirection();
    if (action === "generate-report") generateReport();
    if (action === "close-modal") closeModal();
  }

  function onChange(event) {
    if (!event.target.matches("[data-selection-keyword-id]")) return;
    const id = Number(event.target.dataset.selectionKeywordId);
    if (event.target.checked) selectionState.selectedKeywordIds.add(id);
    else selectionState.selectedKeywordIds.delete(id);
    renderSelectedKeywords();
  }

  function onInput(event) {
    if (event.target.id === "selection-keyword-filter") renderMcpFields();
  }

  function onSubmit(event) {
    if (event.target.id === "selection-project-form") {
      event.preventDefault();
      createProject(event.target);
    }
    if (event.target.id === "selection-keyword-form") {
      event.preventDefault();
      runKeywordResearch(event.target);
    }
    if (event.target.id === "selection-pricing-form") {
      event.preventDefault();
      savePricing(event.target);
    }
  }

  async function createProject(form) {
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const project = await api("/api/selection/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      form.reset();
      toggleProjectForm(false);
      await loadProjects();
      await chooseProject(project.id);
      showNotice("项目已创建", "success");
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  async function runKeywordResearch(form) {
    if (!selectionState.currentProject) return;
    const values = Object.fromEntries(new FormData(form).entries());
    const payload = {
      input_type: selectionState.inputType,
      input_value: values.input_value,
    };
    if (values.category?.trim()) payload.category = values.category.trim();
    setBusy(form, true);
    try {
      const data = await api(
        `/api/selection/projects/${selectionState.currentProject.id}/keyword-research`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": `web-${Date.now()}-${cryptoRandom()}`,
          },
          body: JSON.stringify(payload),
        }
      );
      selectionState.keywordRows = data.keywords || [];
      selectionState.keywordPageCount = data.pagination?.collected_pages || 0;
      selectionState.selectedKeywordIds = new Set();
      selectionState.direction = null;
      selectionState.pricing = null;
      selectionState.report = null;
      renderKeywords();
      renderMcpFields();
      renderDirection();
      renderPricing();
      renderReport();
      const type = data.status === "succeeded" ? "success" : data.status === "partial" ? "warning" : "error";
      const message = data.status === "partial"
        ? "部分 MCP 数据源调用失败，已保留成功来源的数据。"
        : data.status === "failed"
          ? (data.error_summary || "卖家精灵 MCP 未返回关键词。")
          : `关键词调研完成，共 ${selectionState.keywordRows.length} 条。`;
      showNotice(message, type);
    } catch (error) {
      showNotice(error.message, "error");
    } finally {
      setBusy(form, false);
    }
  }

  async function saveSelectedKeywords(advance) {
    if (!selectionState.currentProject) return;
    if (!selectionState.selectedKeywordIds.size) {
      showNotice("请至少选择一个关键词", "error");
      return;
    }
    try {
      await api(
        `/api/selection/projects/${selectionState.currentProject.id}/selected-keywords`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword_ids: [...selectionState.selectedKeywordIds] }),
        }
      );
      selectionState.keywordRows.forEach((row) => {
        row.selected = selectionState.selectedKeywordIds.has(row.id);
      });
      showNotice("研究清单已保存，下游结果需要重新生成。", "success");
      if (advance) {
        setStage("direction");
        await buildDirection();
      }
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  async function buildDirection() {
    if (!selectionState.currentProject) return;
    try {
      showNotice("正在调用竞品与趋势 MCP 能力…", "warning");
      showNotice("正在将已选关键词完整数据交给 LLM 研究…", "warning");
      selectionState.direction = await api(
        `/api/selection/projects/${selectionState.currentProject.id}/product-direction`,
        { method: "POST" }
      );
      selectionState.report = null;
      renderDirection();
      renderReport();
      showNotice("产品方向研究完成", "success");
    } catch (error) {
      showNotice(error.message, "error");
      renderDirection();
    }
  }

  async function savePricing(form) {
    if (!selectionState.currentProject) return;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.freight_template_id = Number(payload.freight_template_id);
    if (!payload.manual_exchange_rate) delete payload.manual_exchange_rate;
    setBusy(form, true);
    try {
      selectionState.pricing = await api(
        `/api/selection/projects/${selectionState.currentProject.id}/pricing`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      selectionState.report = null;
      renderPricing();
      renderReport();
      showNotice("定价快照已保存", "success");
    } catch (error) {
      showNotice(error.message, "error");
    } finally {
      setBusy(form, false);
    }
  }

  async function generateReport() {
    if (!selectionState.currentProject) return;
    try {
      showNotice("正在生成规则评分与真实 LLM 解读…", "warning");
      selectionState.report = await api(
        `/api/selection/projects/${selectionState.currentProject.id}/report`,
        { method: "POST" }
      );
      renderReport();
      showNotice(
        selectionState.report.llm_status === "succeeded"
          ? "决策报告已生成"
          : "规则报告已生成，真实 LLM 当前不可用。",
        selectionState.report.llm_status === "succeeded" ? "success" : "warning"
      );
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  function renderProjects() {
    const list = document.getElementById("selection-project-list");
    if (!list) return;
    if (!selectionState.projects.length) {
      list.innerHTML = '<div class="selection-missing">暂无项目</div>';
      return;
    }
    list.innerHTML = selectionState.projects.map((project) => `
      <button type="button" class="selection-project-item ${selectionState.currentProject?.id === project.id ? "is-active" : ""}" data-selection-project-id="${project.id}">
        <strong>${escape(project.name)}</strong>
        <span>${escape(project.marketplace)} · ${escape(project.target_currency)} · ${escape(project.status)}</span>
      </button>
    `).join("");
  }

  function renderWorkspace() {
    const workspace = document.getElementById("selection-project-workspace");
    if (!workspace) return;
    const hasProject = Boolean(selectionState.currentProject);
    workspace.hidden = !hasProject;
    if (!hasProject) return;
    document.getElementById("selection-current-project").textContent = selectionState.currentProject.name;
    document.getElementById("selection-current-meta").textContent = `${selectionState.currentProject.marketplace} · ${selectionState.currentProject.target_currency}`;
    setStage(selectionState.currentStage);
  }

  function renderKeywords() {
    const body = document.getElementById("selection-keyword-body");
    if (!body) return;
    const query = (document.getElementById("selection-keyword-filter")?.value || "").trim().toLowerCase();
    const rows = selectionState.keywordRows.filter((row) =>
      !query || String(row.keyword || "").toLowerCase().includes(query)
    );
    document.getElementById("selection-keyword-count").textContent = `${rows.length} 条数据`;
    body.innerHTML = rows.length ? rows.map(renderKeywordRow).join("") : `
      <tr><td colspan="10" class="selection-missing">暂无真实关键词数据，请先运行调研。</td></tr>
    `;
    renderSelectedKeywords();
  }

  function renderMcpFields() {
    const container = document.getElementById("selection-mcp-fields");
    const count = document.getElementById("selection-mcp-field-count");
    if (!container) return;
    const query = (document.getElementById("selection-keyword-filter")?.value || "").trim().toLowerCase();
    const rows = (selectionState.keywordRows || []).filter((row) =>
      !query || String(row.keyword || "").toLowerCase().includes(query)
    );
    const keywordCount = document.getElementById("selection-keyword-count");
    const pageInfo = document.getElementById("selection-mcp-page-info");
    if (keywordCount) keywordCount.textContent = `${rows.length} 条数据`;
    if (pageInfo) pageInfo.textContent = selectionState.keywordPageCount
      ? `已返回前 ${selectionState.keywordPageCount} 页`
      : "暂无分页结果";
    const columns = mcpFieldColumns(rows);
    if (count) count.textContent = `${Math.max(columns.length - 1, 0)} 个字段`;
    if (!rows.length || !columns.length) {
      container.innerHTML = '<div class="selection-missing">暂无 MCP 字段数据。</div>';
      return;
    }
    container.innerHTML = `<table><thead><tr><th>选择</th>${columns.map((column) => `<th>${escape(mcpFieldLabel(column))}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `
      <tr><td><input type="checkbox" data-selection-keyword-id="${row.id}" ${selectionState.selectedKeywordIds.has(row.id) ? "checked" : ""} /></td>${columns.map((column) => `<td>${formatMcpValue(mcpFieldValue(row, column))}</td>`).join("")}</tr>
    `).join("")}</tbody></table>`;
  }

  function mcpFieldColumns(rows) {
    const preferred = [
      "keyword",
      "keywordCn",
      "keyword_translation",
      "searches",
      "search_volume",
      "products",
      "product_count",
      "purchases",
      "purchaseRate",
      "bid",
      "bidMin",
      "bidMax",
      "badges",
      "searchesRank",
      "latest7daysAds",
      "supplyDemandRatio",
      "trafficPercentage",
      "calculatedWeeklySearches",
      "avgPrice",
      "avgReviews",
      "avgRating",
      "titleDensity",
      "monopolyClickRate",
      "top3ClickingRate",
      "top3ConversionRate",
      "source_name",
      "collected_at",
    ];
    const seen = new Set();
    const columns = [];
    const add = (column) => {
      if (MCP_IGNORED_FIELDS.has(column)) return;
      const canonical = MCP_FIELD_CANONICAL[column] || column;
      if (canonical && !seen.has(canonical)) {
        seen.add(canonical);
        columns.push(canonical);
      }
    };
    preferred.forEach(add);
    rows.forEach((row) => {
      Object.keys(row || {}).forEach(add);
      Object.keys(row.metrics || {}).forEach(add);
    });
    return columns.filter((column) =>
      rows.some((row) => hasMcpFieldValue(row, column))
    );
  }

  function mcpFieldValue(row, column) {
    const candidates = [
      column,
      ...Object.keys(MCP_FIELD_CANONICAL).filter(
        (alias) => MCP_FIELD_CANONICAL[alias] === column
      ),
    ];
    let fallback;
    for (const field of candidates) {
      const values = [
        row && Object.prototype.hasOwnProperty.call(row, field) ? row[field] : undefined,
        row?.metrics && Object.prototype.hasOwnProperty.call(row.metrics, field)
          ? row.metrics[field]
          : undefined,
      ];
      for (const value of values) {
        if (value !== undefined && value !== null && value !== "") return value;
        if (fallback === undefined && value !== undefined) fallback = value;
      }
    }
    return fallback;
  }

  function mcpFieldLabel(column) {
    return MCP_FIELD_LABELS[column] || `其他字段（${column}）`;
  }

  function hasMcpFieldValue(row, column) {
    const value = mcpFieldValue(row, column);
    if (value === undefined || value === null || value === "") return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    return true;
  }

  function formatMcpValue(item) {
    if (item === null || item === undefined || item === "") {
      return '<span class="selection-missing">未提供</span>';
    }
    if (typeof item === "object") {
      return `<code>${escape(JSON.stringify(item))}</code>`;
    }
    return escape(item);
  }

  function renderKeywordRow(row) {
    return `<tr>
      <td><input type="checkbox" data-selection-keyword-id="${row.id}" ${selectionState.selectedKeywordIds.has(row.id) ? "checked" : ""} /></td>
      <td><strong>${escape(row.keyword)}</strong></td>
      <td>${value(row.search_volume)}</td>
      <td>${value(row.trend_rate)}</td>
      <td>${value(row.product_count)}</td>
      <td>${value(row.competition_index)}</td>
      <td>${value(row.cpc)}</td>
      <td>${value(row.conversion_rate)}</td>
      <td><span class="selection-source-meta"><strong>${escape(row.source_name || "数据源未提供")}</strong><span>${formatTime(row.collected_at)}</span></span></td>
    </tr>`;
  }

  function renderSelectedKeywords() {
    const container = document.getElementById("selection-selected-keywords");
    const count = document.getElementById("selection-selected-count");
    const selected = selectionState.keywordRows.filter((row) => selectionState.selectedKeywordIds.has(row.id));
    if (count) count.textContent = String(selected.length);
    if (!container) return;
    container.innerHTML = selected.length
      ? selected.map((row) => `<span class="selection-keyword-chip" title="${escape(row.keyword)}">${escape(row.keyword)}</span>`).join("")
      : '<span class="selection-missing">尚未选择关键词</span>';
  }

  function renderDirection() {
    const container = document.getElementById("selection-direction-result");
    if (!container) return;
    const item = selectionState.direction;
    if (!item) {
      container.innerHTML = '<span class="selection-missing">保存关键词研究清单后生成产品方向。</span>';
      return;
    }
    const cluster = item.keyword_cluster || {};
    const llmResearch = item.market_metrics?.llm_research || {};
    const llmInput = item.market_metrics?.llm_input || {};
    container.innerHTML = `
      <div class="selection-result-grid">
        <article class="selection-result-metric"><span>方向名称</span><strong>${escape(item.name)}</strong></article>
        <article class="selection-result-metric"><span>数据完整度</span><strong>${formatPercent(item.data_completeness)}</strong></article>
        <article class="selection-result-metric"><span>关键词数量</span><strong>${(cluster.all || []).length}</strong></article>
        <article class="selection-result-metric"><span>已交给 LLM</span><strong>${(llmInput.selected_keywords || []).length} 条完整关键词数据</strong></article>
      </div>
      ${renderCluster(cluster)}
      ${llmResearch.product_direction ? `<article class="selection-result-metric" style="margin-top:12px"><span>LLM 产品方向</span><div>${escape(llmResearch.product_direction)}</div></article>` : ""}
      ${renderWarnings(item.warnings)}
    `;
  }

  function renderCluster(cluster) {
    const groups = [
      ["主词", cluster.primary], ["相关词", cluster.related],
      ["长尾词", cluster.long_tail], ["场景词", cluster.scenario],
    ];
    return `<div class="selection-result-grid" style="margin-top:12px">${groups.map(([label, words]) => `
      <article class="selection-result-metric"><span>${label}</span><strong>${(words || []).length}</strong><div>${(words || []).map((word) => `<span class="selection-keyword-chip">${escape(word)}</span>`).join(" ") || '<span class="selection-missing">数据源未提供</span>'}</div></article>
    `).join("")}</div>`;
  }

  function renderFreightTemplates() {
    const select = document.getElementById("selection-freight-template");
    if (!select) return;
    select.innerHTML = selectionState.freightTemplates.length
      ? '<option value="">请选择模板</option>' + selectionState.freightTemplates.map((item) => `<option value="${item.id}">${escape(item.name)} · ${escape(item.currency)} · ${escape(item.channel)}</option>`).join("")
      : '<option value="">暂无可用模板，请管理员先配置</option>';
  }

  function renderPricing() {
    const container = document.getElementById("selection-pricing-result");
    if (!container) return;
    const item = selectionState.pricing;
    if (!item) {
      container.innerHTML = '<span class="selection-missing">尚未保存定价快照。</span>';
      return;
    }
    container.innerHTML = `
      <div class="selection-result-grid">
        ${metric("计费重量", `${item.billable_weight_kg} kg`)}
        ${metric("国际运费", item.international_shipping)}
        ${metric("建议最低售价", item.target_price)}
        ${metric("平台佣金", item.commission_amount)}
        ${metric("最终净利润", item.net_profit_amount)}
        ${metric("汇率来源", item.exchange_rate_snapshot?.source_name || "数据源未提供")}
      </div>
      <div class="selection-formula">售价 =（商品价格 + 国内运费 + 国际运费）÷（1 - 15% - 40%）</div>
    `;
  }

  function renderReport() {
    const container = document.getElementById("selection-report-result");
    if (!container) return;
    const item = selectionState.report;
    if (!item) {
      container.innerHTML = '<span class="selection-missing">完成产品方向和定价后生成决策报告。</span>';
      return;
    }
    const llm = item.llm_report;
    const statusClass = item.llm_status === "succeeded" ? "is-success" : "is-warning";
    container.innerHTML = `
      <div class="selection-result-grid">
        ${metric("综合评分", item.score_total ?? "需要补充数据")}
        ${metric("固定结论", decisionLabel(item.decision))}
        ${metric("数据覆盖率", formatPercent(item.score_dimensions?.coverage))}
      </div>
      <p><span class="selection-report-status ${statusClass}">LLM：${escape(item.llm_status)}</span></p>
      ${llm ? `
        <h4>${escape(llm.summary)}</h4>
        ${renderTextList("主要发现", llm.findings)}
        ${renderTextList("风险", llm.risks)}
        ${renderTextList("行动建议", llm.actions)}
      ` : '<p class="selection-missing">真实 LLM 未配置或调用失败；规则评分和证据仍然保留。</p>'}
      ${renderWarnings(item.risks?.warnings)}
    `;
  }

  function setStage(stage) {
    if (!["keywords", "direction", "pricing", "report"].includes(stage)) return;
    selectionState.currentStage = stage;
    document.querySelectorAll("[data-selection-stage]").forEach((section) => {
      const active = section.dataset.selectionStage === stage;
      section.hidden = !active;
      section.classList.toggle("is-active", active);
    });
    document.querySelectorAll("[data-selection-stage-target]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.selectionStageTarget === stage);
    });
  }

  function setInputType(type) {
    selectionState.inputType = type;
    document.querySelectorAll("[data-selection-input-type]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.selectionInputType === type);
    });
    const input = document.getElementById("selection-research-input");
    const placeholders = {
      seed: "输入种子关键词",
      asin: "输入 10 位 ASIN",
      category: "输入类目名称或 NodeId",
    };
    if (input) input.placeholder = placeholders[type];
  }

  function toggleProjectForm(show) {
    const form = document.getElementById("selection-project-form");
    if (form) form.hidden = !show;
  }

  function setBusy(form, busy) {
    form.querySelectorAll("button, input, select").forEach((element) => {
      element.disabled = busy;
    });
  }

  function showNotice(message, type) {
    const notice = document.getElementById("selection-notice");
    if (!notice) return;
    notice.hidden = !message;
    notice.textContent = message || "";
    notice.className = `selection-notice ${type ? `is-${type}` : ""}`;
  }

  function metric(label, content) {
    return `<article class="selection-result-metric"><span>${escape(label)}</span><strong>${escape(content)}</strong></article>`;
  }

  function renderWarnings(items) {
    return items?.length
      ? `<ul class="selection-warning-list">${items.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>`
      : "";
  }

  function renderTextList(title, items) {
    return `<section><h4>${escape(title)}</h4>${items?.length ? `<ul>${items.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>` : '<p class="selection-missing">数据源未提供</p>'}</section>`;
  }

  function value(item) {
    return item === null || item === undefined
      ? '<span class="selection-missing">数据源未提供</span>'
      : escape(item);
  }

  function formatTime(item) {
    if (!item) return "时间未提供";
    const date = new Date(item);
    return Number.isNaN(date.getTime()) ? String(item) : date.toLocaleString("zh-CN");
  }

  function formatPercent(item) {
    const number = Number(item);
    return Number.isFinite(number) ? `${(number * 100).toFixed(0)}%` : "数据源未提供";
  }

  function decisionLabel(decision) {
    return {
      recommended: "推荐开发",
      cautious: "谨慎测试",
      not_recommended: "暂不建议",
      needs_data: "需要补充数据",
    }[decision] || "需要补充数据";
  }

  function cryptoRandom() {
    if (window.crypto?.getRandomValues) {
      const value = new Uint32Array(1);
      window.crypto.getRandomValues(value);
      return value[0].toString(16);
    }
    return Math.random().toString(16).slice(2);
  }

  function escape(input) {
    return String(input ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  window.SelectionWorkbench = { init, activate, state: selectionState };
  document.addEventListener("DOMContentLoaded", init);
})();
