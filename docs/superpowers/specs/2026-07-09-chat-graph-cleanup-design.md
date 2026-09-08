# ChatGraph 职责整理设计

## 目标

降低 `app/agents/chat_graph.py` 的职责密度，使聊天编排流程更容易阅读和测试；不改变现有聊天、MCP、记忆或 SSE 事件行为。

## 范围

仅调整 `app/agents/` 及其对应测试：

- 新增 `app/agents/chat_formatting.py`，承载无状态的文本清理与工具输出格式化逻辑。
- 新增 `app/agents/chat_prompts.py`，承载 MCP 与记忆上下文的提示词拼装逻辑。
- `chat_graph.py` 保留 `ChatState`、本地工具注册、`ChatGraph` 的状态管理、LangGraph 构建和聊天/流式编排。
- 更新现有测试的导入并补充纯函数直接测试。

不修改 `OrchestratorGraph`、MCP 客户端、数据库工具、路由或对外 API。

## 模块边界

`chat_formatting.py` 提供：

- `filter_thinking(text)`：清理聊天回复中的不合规格式。
- `tool_output_to_text(output)`：把工具输出转换为可展示文本。
- `format_sellersprite_raw_data(tool_name, output)`：保留并展示卖家精灵原始数据。
- `is_sellersprite_raw_data_request(message)`：识别用户的原始数据查询。

`chat_prompts.py` 提供：

- `tool_name(tool_item)`：读取工具名。
- `build_contextual_message(tools, local_tool_count, user_message)`：将 MCP 工具能力附加到用户消息。
- `build_memory_contextual_message(memory_context, user_message)`：附加可信记忆上下文。
- `build_mcp_system_addon(tools, local_tool_count)`：构建系统提示词中的 MCP 规则段。

`ChatGraph` 从上述模块导入函数，不修改以下公开行为：

- 构造参数：`llm_client`、`chat_tools`、`mcp_tools_loader`、`memory_service`。
- 方法：`ensure_mcp_tools_loaded()`、`get_mcp_status()`、`chat()`、`chat_stream()`。
- 流式事件：`token`、`tool_start`、`tool_end`、`error`、`done` 及其字段。
- MCP 原始数据的保存、读取和返回格式。

## 数据流

1. `ChatGraph` 读取记忆和已加载工具。
2. `chat_prompts.py` 生成用户消息与系统提示中的上下文。
3. `ChatGraph` 调用 LangGraph 或现有 LLM 回退路径。
4. 流式事件中的工具输出交由 `chat_formatting.py` 转换；卖家精灵原始结果仍按原格式缓存和输出。

## 错误处理

保持现有策略：MCP 加载、记忆读写和流式执行异常继续由 `ChatGraph` 捕获并以既有事件/空上下文处理。新模块仅处理纯值转换，不增加新的兜底或吞错逻辑。

## 验收标准

- `ChatGraph` 的公开构造参数、公开方法和事件结构未变化。
- 卖家精灵原始数据查询及输出格式与重构前一致。
- MCP 提示词、记忆提示词和工具输出仍可由现有调用链使用。
- 通过 `tests/test_chat_memory.py` 与 `tests/test_mcp_tools.py`。
- 新增的纯函数测试覆盖迁出的格式化和提示词逻辑。
