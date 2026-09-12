const backend = "http://localhost:8010";
const button = document.querySelector("#capture");
const status = document.querySelector("#status");

function show(message) { status.textContent = message; }

button.addEventListener("click", async () => {
  button.disabled = true;
  show("正在读取页面…");
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !tab.url?.startsWith("https://www.amazon.com/")) throw new Error("请先打开 Amazon 美国站商品详情页");
    const result = await chrome.tabs.sendMessage(tab.id, {type: "capture-product"});
    if (!result?.ok) throw new Error(result?.error || "无法读取商品页面");
    if (!/^[A-Z0-9]{10}$/i.test(result.product.asin)) throw new Error("没有识别到有效 ASIN");
    show("正在发送到 Amazon Agent…");
    const response = await fetch(`${backend}/api/chrome/submit`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(result.product)
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.detail || "后端拒绝保存");
    show(`已保存：${data.product.asin}`);
  } catch (error) {
    show(error instanceof Error ? error.message : "采集失败");
  } finally {
    button.disabled = false;
  }
});
