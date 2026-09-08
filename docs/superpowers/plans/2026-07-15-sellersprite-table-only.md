# 卖家精灵字段表格 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让卖家精灵完整字段只以中文标题表格展示，并移除原始数据 UI。

**Architecture:** `selection-workbench.js` 通过字段标题映射函数渲染完整字段表格；`index.html` 仅保留该表格；静态测试断言旧原始数据元素与渲染函数不存在。

**Tech Stack:** Vanilla JavaScript、HTML、pytest。

## Global Constraints

- 不改变 MCP 请求、响应存储或关键词数据值。
- 未映射字段必须保留，并以“其他字段（字段名）”标识。
- 不提交、不推送代码。

---

### Task 1: 表格中文标题与原始数据 UI 移除

**Files:**
- Modify: `tests/test_selection_frontend.py`
- Modify: `app/static/selection-workbench.js`
- Modify: `app/static/index.html`

- [ ] **Step 1: Write the failing test**

```python
assert "mcpFieldLabel(column)" in selection_js
assert 'id="selection-mcp-raw"' not in index_html
assert "renderMcpRawSnapshots" not in selection_js
assert 'data-selection-snapshot-id' not in selection_js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_selection_frontend.py -q`

Expected: FAIL because the old raw-response UI is still present.

- [ ] **Step 3: Write minimal implementation**

```javascript
function mcpFieldLabel(column) {
  return MCP_FIELD_LABELS[column] || `其他字段（${column}）`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_selection_frontend.py -q`

Expected: PASS。
