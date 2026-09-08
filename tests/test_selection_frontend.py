from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ai_selection_removes_workspace_copy_and_hides_global_topbar_content():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    styles_css = (PROJECT_ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")

    assert "AI Selection Workspace" not in index_html
    assert "AI 选品工作台" not in index_html
    assert "从关键词调研到决策报告，全流程仅使用已配置的 MCP 数据源。" not in index_html
    assert "先创建或选择一个项目" not in index_html
    assert "项目会保存关键词、产品方向、运费汇率快照和最终报告。" not in index_html
    assert 'topbar.classList.toggle("is-selection-page", pageName === "ai-selection")' in app_js
    assert ".topbar.is-selection-page .title-block" in styles_css
    assert ".topbar.is-selection-page .search-control" in styles_css
    assert ".topbar.is-selection-page #refresh-results" in styles_css


def test_ai_selection_exposes_full_mcp_fields_with_chinese_headers_only():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    selection_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")

    assert 'id="selection-mcp-fields"' in index_html
    assert 'id="selection-mcp-raw"' not in index_html
    assert "renderMcpFields();" in selection_js
    assert "renderMcpRawSnapshots" not in selection_js
    assert "mcpFieldLabel(column)" in selection_js
    assert "MCP_FIELD_CANONICAL" in selection_js
    assert 'search_volume: "searches"' in selection_js
    assert 'keyword_translation: "keywordCn"' in selection_js
    assert "MCP_IGNORED_FIELDS" in selection_js
    assert "hasMcpFieldValue(row, column)" in selection_js
    assert "return MCP_FIELD_LABELS[column] || `其他字段（${column}）`" in selection_js
    assert 'searches: "搜索量"' in selection_js
    assert 'data-selection-snapshot-id' not in selection_js
    assert "Object.keys(row.metrics || {})" in selection_js


def test_ai_selection_uses_the_detailed_mcp_table_for_keyword_research():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    selection_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")

    assert 'id="selection-keyword-body"' not in index_html
    assert 'id="selection-mcp-fields"' in index_html
    assert 'data-selection-action="save-keywords"' in index_html
    assert 'data-selection-keyword-id="${row.id}"' in selection_js
    assert "renderMcpFields();" in selection_js


def test_ai_selection_does_not_show_multi_mcp_label():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")

    assert "多 MCP 数据源" not in index_html


def test_ai_selection_shows_collected_page_count():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    selection_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")

    assert 'id="selection-mcp-page-info"' in index_html
    assert "data.pagination?.collected_pages" in selection_js


def test_ai_selection_displays_llm_product_direction():
    selection_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")

    assert 'item.market_metrics?.llm_research' in selection_js
    assert "LLM 产品方向" in selection_js


def test_ai_selection_does_not_describe_product_direction_as_mcp_calls():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    selection_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")

    assert "调用竞品与趋势能力形成一个可追溯方向" not in index_html
    assert "正在将已选关键词完整数据交给 LLM 研究" in selection_js
    assert "llm_input" in selection_js


def test_battlefield_and_diagnosis_modules_are_not_exposed():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'data-page="battlefield"' not in index_html
    assert 'data-page="diagnosis"' not in index_html
    assert 'id="page-battlefield"' not in index_html
    assert 'id="page-diagnosis"' not in index_html
    assert "initBattlefield" not in app_js
    assert "initDiagnosis" not in app_js


def test_chat_page_initializes_when_opened_and_keeps_welcome_visible_while_loading_history():
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'if (pageName === "chat") {' in app_js
    assert "initChat();" in app_js
    assert "chatInitialized" in app_js
    assert "showChatWelcome();" in app_js
    assert "/static/app.js?v=ai-chat-page-20260716-1" in index_html
    assert "/static/styles.css?v=ai-chat-page-20260716-1" in index_html
