# Amazon Agent 运营台

> AI 驱动的跨境电商运营分析平台，集成竞品分析、智能诊断、自动化任务等功能

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 功能特性

### 核心功能
- **运营总览** — 一图掌握销售、广告、库存、质量全貌
- **数据导入** — 支持 CSV/Excel 批量导入 SKU、销售、广告、库存、利润、退货数据
- **风险分析** — 自动识别高风险项，按等级和模块分类展示
- **异常任务** — 每日简报 + 告警任务管理，支持状态跟踪

### AI 工具
- **AI 助手** — 智能对话，查询运营数据、分析问题、提供建议
- **战场地图** — 竞品分析，市场份额、价格带、关键词洞察
- **运营天眼** — 产品健康度诊断，六大因子分析 + 优化建议
- **销售监控** — 实时监控销售数据，自动识别异常波动
- **广告分析** — 深度分析广告投放效果，优化广告策略
- **库存管家** — 智能库存管理，避免断货和积压

### 自动化
- **定时分析** — 每天自动执行分析，生成报告
- **数据同步** — 定时同步易仓/亚马逊数据
- **竞品监控** — 定时监控竞品变化

### 系统集成
- **易仓 ERP** — 对接易仓 API，获取订单、库存、物流数据
- **亚马逊 SP-API** — 连接亚马逊店铺，获取销售、广告数据
- **飞书** — 同步数据到飞书多维表格

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| AI | LangGraph, LangChain, DeepSeek |
| 前端 | Vanilla JS, CSS3, HTML5 |
| 数据库 | SQLite (开发), PostgreSQL (生产) |
| 部署 | Render, Vercel, Docker |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/libowenhemonesy-svg/amazon-agent-mvp.git
cd amazon-agent-mvp
```

### 2. 安装依赖

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

```env
# DeepSeek API（AI 功能必需）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 飞书（可选）
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

### 4. 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

访问 http://localhost:8010

## 部署指南

### Render（免费）

1. Fork 本仓库
2. 登录 [Render](https://render.com)
3. 创建 Web Service，连接 GitHub 仓库
4. 配置环境变量
5. 部署完成

详细步骤见 [部署文档](docs/deploy.md)

### 腾讯云轻量服务器

```bash
# SSH 连接服务器后执行
curl -O https://raw.githubusercontent.com/libowenhemonesy-svg/amazon-agent-mvp/codex/langgraph-mvp/deploy.sh
sudo bash deploy.sh
```

## 项目结构

```
amazon-agent-mvp/
├── app/
│   ├── agents/          # AI Agent（LangGraph）
│   ├── analysis/        # 分析模块（战场地图、运营天眼）
│   ├── automation/      # 自动化任务
│   ├── db/              # 数据库模型和操作
│   ├── importers/       # 数据导入
│   ├── integrations/    # 外部集成（飞书、易仓）
│   ├── metrics/         # 指标计算
│   ├── reports/         # 报告生成
│   ├── rules/           # 规则引擎
│   └── static/          # 前端文件
├── sample_data/         # 示例数据
├── tests/               # 测试用例
├── requirements.txt     # Python 依赖
└── render.yaml          # Render 部署配置
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8010/docs
- ReDoc: http://localhost:8010/redoc

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

## 联系方式

- GitHub: [@libowenhemonesy-svg](https://github.com/libowenhemonesy-svg)
- Issues: [提交问题](https://github.com/libowenhemonesy-svg/amazon-agent-mvp/issues)

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [LangGraph](https://langchain-ai.github.io/langgraph/) — AI Agent 编排框架
- [DeepSeek](https://www.deepseek.com/) — AI 大模型服务
