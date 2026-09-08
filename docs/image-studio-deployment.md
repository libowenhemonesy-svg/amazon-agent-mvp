# 图片工作台部署说明

图片工作台使用 Amazon Agent 自身服务器处理用户、工作流、任务和素材，图片生成与编辑由阿里云百炼完成，不需要部署 GPU。

## 必需配置

```env
BAILIAN_API_KEY=你的百炼API密钥
PUBLIC_BASE_URL=https://你的Amazon-Agent域名
IMAGE_STUDIO_OUTPUT_DIR=/var/lib/amazon-agent/image-assets
```

- `BAILIAN_API_KEY` 也可使用现有的 `DASHSCOPE_API_KEY`。
- `PUBLIC_BASE_URL` 只在参考图编辑时必需。千问通过该公网地址读取 `/image-assets/*` 下的参考图。
- `IMAGE_STUDIO_OUTPUT_DIR` 应指向服务器持久磁盘，不要使用容器临时目录。
- 可选的 `BAILIAN_IMAGE_BASE_URL` 用于配置百炼地域或业务空间专属 API 地址。

OpenAI 与 Google 适配器目前只预留提供商状态，不会读取或调用对应模型。

## 数据库迁移

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

生产环境 PostgreSQL 必须执行迁移。开发环境通过 SQLAlchemy 创建缺失表，但仍建议保持迁移版本一致。

## 部署检查

1. 登录运营台并打开“图片制作”。
2. 确认“阿里云百炼 / 千问图片”显示为“可用”。
3. 从“Amazon 白底主图”模板创建工作流并保存。
4. 输入提示词运行，确认任务最终为“已完成”，图片出现在素材库。
5. 重启服务后再次打开素材库，确认持久磁盘中的图片仍能访问。

当前任务执行使用 FastAPI 后台任务，适合单实例部署。多实例或需要任务跨重启恢复时，应在下一阶段替换为 Redis 队列工作进程。
