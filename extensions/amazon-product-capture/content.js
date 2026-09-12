function text(selector) {
  return document.querySelector(selector)?.textContent?.trim() || "";
}

function attribute(selector, name) {
  return document.querySelector(selector)?.getAttribute(name) || "";
}

function captureProduct() {
  const asin = attribute("#ASIN", "value") || location.pathname.match(/\/dp\/([A-Z0-9]{10})/i)?.[1] || "";
  return {
    asin,
    title: text("#productTitle"),
    price: text(".a-price .a-offscreen"),
    rating: text("#acrPopover"),
    review_count: text("#acrCustomerReviewText"),
    bullets: [...document.querySelectorAll("#feature-bullets li span.a-list-item")]
      .map((node) => node.textContent.trim()).filter(Boolean),
    image: attribute("#landingImage", "data-old-hires") || attribute("#landingImage", "src"),
    url: location.href.split("?")[0],
    reviews: []
  };
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.type !== "capture-product") return;
  try {
    sendResponse({ok: true, product: captureProduct()});
  } catch (error) {
    sendResponse({ok: false, error: error instanceof Error ? error.message : "无法读取商品页面"});
  }
});
