# 移除 AI 选品多 MCP 数据源标签 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 AI 选品页面移除“多 MCP 数据源”标签，并防止该文案回归。

**Architecture:** 只改动静态 HTML 中的标签节点；前端静态测试直接读取页面源码并断言该文案不存在。无需改动 JavaScript、API 或 MCP 调用层。

**Tech Stack:** Vanilla HTML、Python pytest。

## Global Constraints

- 不改变 MCP 配置、调用、错误提示或数据展示逻辑。
- 不提交、不推送代码。
- 所有可见界面文案保持中文。

---

### Task 1: 移除标签并添加回归测试

**Files:**
- Modify: `tests/test_selection_frontend.py`
- Modify: `app/static/index.html`

**Interfaces:**
- Consumes: `Path("app/static/index.html").read_text(encoding="utf-8")`
- Produces: 页面源码不含“多 MCP 数据源”。

- [ ] **Step 1: Write the failing test**

```python
def test_selection_page_does_not_show_multi_mcp_label():
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")

    assert "多 MCP 数据源" not in index_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_selection_frontend.py -q`

Expected: FAIL because `app/static/index.html` still contains “多 MCP 数据源”。

- [ ] **Step 3: Write minimal implementation**

```html
<!-- 删除包含“多 MCP 数据源”的 span 标签；保留相邻导航与功能节点。 -->
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_selection_frontend.py -q`

Expected: PASS。
