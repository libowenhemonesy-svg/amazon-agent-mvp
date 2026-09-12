# Amazon Agent 商品采集扩展

在 Amazon 美国站商品详情页采集当前页面可见的标题、价格、评分、评论数、五点描述、主图和 ASIN，发送到本地 Amazon Agent。

1. 启动主项目：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`。
2. 打开 Chrome 的 `chrome://extensions`，开启开发者模式。
3. 选择“加载已解压的扩展程序”，选择本目录。
4. 打开 `https://www.amazon.com/` 的商品详情页，点击扩展并选择“采集并发送”。

扩展仅处理 `amazon.com`，后端仅接受 HTTPS Amazon 链接和有效 ASIN。提交的页面内容会写入本地运营数据库，未自动调用模型或抓取评论。
