from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

DXD_URL = "https://www.dianxiaomi.com/web/amazon/add"
RUNTIME_DIR = Path(os.getenv("DIANXIAOMI_RUNTIME_DIR", ".tmp/dianxiaomi")).resolve()
USER_DATA_DIR = RUNTIME_DIR / "browser-data"
STATE_FILE = RUNTIME_DIR / "filler_state.json"
SIGNAL_FILE = RUNTIME_DIR / "filler_signal.txt"

KNOWN_LABELS = {
    "店铺账号", "站点选择", "产品标题", "产品分类", "售卖形式", "UPC豁免", "小语种翻译", "来源URL",
    "Parent SKU", "产品ID", "品牌", "制造商", "价格", "产品数量", "销售开始时间", "销售结束时间",
    "产品描述", "物品状况", "状况描述", "产品图片", "处理时间", "配送渠道", "运费模板", "Search Terms",
}


def web_pause(step: str, message: str, timeout: int = 600) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"paused": True, "step": step, "message": message}, ensure_ascii=False), encoding="utf-8")
    if SIGNAL_FILE.exists():
        SIGNAL_FILE.unlink()
    elapsed = 0
    while elapsed < timeout:
        time.sleep(1)
        elapsed += 1
        if SIGNAL_FILE.exists() and SIGNAL_FILE.read_text(encoding="utf-8").strip() == step:
            SIGNAL_FILE.unlink()
            break
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def web_done(message: str = "填写完成") -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"paused": False, "done": True, "message": message}, ensure_ascii=False),
        encoding="utf-8",
    )


def cli_pause(message: str) -> None:
    print()
    print("=" * 50)
    print(message)
    print("完成后按 Enter 继续...")
    print("=" * 50)
    input()


def get_form_items(page):
    return page.evaluate(
        """
        () => {
            const items = [];
            document.querySelectorAll('.ant-form-item').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.height < 5) return;
                const labelEl = el.querySelector('.ant-form-item-label label');
                const label = labelEl ? labelEl.innerText.trim().replace(/\\n/g, ' ').replace(/\\s+/g, ' ').substring(0, 80) : '';
                if (!label) return;
                const disabled = el.querySelector('[disabled], .ant-select-disabled, .ant-input-disabled, input[disabled]');
                items.push({ label, disabled: !!disabled });
            });
            return items;
        }
        """
    )


def fill_form(attrs: dict, *, no_pause: bool = False, web_mode: bool = False) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("未安装 Playwright，请先运行 pip install playwright 和 playwright install chromium") from exc

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page()
        page.goto(DXD_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        if "login" in page.url.lower() or "passport" in page.url.lower():
            page.wait_for_url("**/web/amazon/**", timeout=300000)
            page.goto(DXD_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)

        time.sleep(5)
        try:
            page.wait_for_selector("input:visible, textarea:visible", timeout=15000)
        except Exception:
            pass

        _fill_basic(page, attrs)
        if not no_pause:
            if web_mode:
                web_pause("category", "请手动选择「产品分类」")
            else:
                cli_pause("请手动选择「产品分类」")
        time.sleep(2)
        _fill_product_info(page, attrs)
        if not no_pause:
            if web_mode:
                web_pause("product_id", "请手动填写「产品ID」")
            else:
                cli_pause("请手动填写「产品ID」")
        time.sleep(2)
        _fill_rest(page, attrs)
        if web_mode:
            web_done()
        page.wait_for_event("close", timeout=0)


def _fill_basic(page, attrs: dict) -> None:
    store = page.locator(".ant-select").first
    if store.count() > 0:
        try:
            store.click()
            time.sleep(0.8)
            page.locator(".ant-select-dropdown:visible .ant-select-item").first.click()
        except Exception:
            pass
    title = attrs.get("title", "")
    if title:
        title_input = page.locator('input[placeholder="请输入"]').first
        if title_input.count() > 0:
            title_input.click()
            title_input.fill("")
            title_input.fill(str(title)[:200])
    target = page.locator('label:has-text("单品")').first
    if target.count() > 0:
        try:
            target.click()
        except Exception:
            pass
    upc_no = page.locator('label:has-text("否")').first
    if upc_no.count() > 0:
        try:
            upc_no.click()
        except Exception:
            pass


def _fill_product_info(page, attrs: dict) -> None:
    title = attrs.get("title", "")
    identifier = attrs.get("product_identifier", "") or (str(title)[:50] if title else "")
    pid_input = page.locator('input[placeholder*="Parent SKU"]')
    if pid_input.count() > 0 and not pid_input.is_disabled():
        pid_input.click()
        pid_input.fill("")
        pid_input.fill(identifier)
    _fill_label_input(page, "品牌", attrs.get("brand", ""))


def _fill_rest(page, attrs: dict) -> None:
    more_btn = page.locator('.ant-collapse-header:visible, [class*="collapse"]:visible:has-text("更多属性")').first
    if more_btn.count() > 0:
        try:
            more_btn.click()
            time.sleep(1.5)
        except Exception:
            pass
    price = attrs.get("standard_price")
    price_input = page.locator('input[name="price"]')
    if price is not None and price_input.count() > 0:
        price_input.click()
        price_input.fill("")
        price_input.fill(str(price))
    qty_input = page.locator('input[placeholder*="产品数量"]')
    if qty_input.count() > 0:
        qty_input.click()
        qty_input.fill("")
        qty_input.fill(str(int(attrs.get("quantity", 100))))
    _fill_dynamic_attrs(page, attrs)
    _fill_label_input(page, "制造商", attrs.get("manufacturer") or attrs.get("brand", ""))
    _fill_label_input(page, "颜色", attrs.get("color", ""))
    _select_condition(page)
    _fill_description(page, attrs)
    _fill_bullets(page, attrs)
    _fill_label_textarea(page, "Search Terms", attrs.get("search_terms", ""))
    _select_shipping(page)


def _fill_dynamic_attrs(page, attrs: dict) -> None:
    for item in get_form_items(page):
        label = item["label"]
        if label in KNOWN_LABELS or label.startswith("* Bullet Point") or item["disabled"]:
            continue
        label_lower = label.lower().replace("：", "").replace(":", "").strip()
        match = None
        for key, val in attrs.items():
            if not val:
                continue
            key_lower = key.lower().replace("_", " ").replace("-", " ")
            if label_lower == key_lower or label_lower in key_lower or key_lower in label_lower:
                match = str(val)
                break
        if match:
            _fill_label_input(page, label, match)


def _fill_label_input(page, label: str, value) -> None:
    if not value:
        return
    label_el = page.locator(f'label:has-text("{label}")').first
    if label_el.count() == 0:
        return
    row = label_el.locator('xpath=ancestor::div[contains(@class,"ant-row")]').first
    if row.count() == 0:
        return
    inp = row.locator('input:not([type="hidden"]):not([readonly]):visible').first
    if inp.count() > 0:
        try:
            inp.click()
            inp.fill("")
            inp.fill(str(value)[:200])
        except Exception:
            pass


def _fill_label_textarea(page, label: str, value) -> None:
    if not value:
        return
    label_el = page.locator(f'label:has-text("{label}")').first
    if label_el.count() == 0:
        return
    row = label_el.locator('xpath=ancestor::div[contains(@class,"ant-row")]').first
    ta = row.locator("textarea").first
    if ta.count() > 0:
        ta.click()
        ta.fill("")
        ta.fill(str(value)[:250])


def _select_condition(page) -> None:
    label = page.locator('label:has-text("物品状况")').first
    if label.count() == 0:
        return
    row = label.locator('xpath=ancestor::div[contains(@class,"ant-row")]').first
    sel = row.locator(".ant-select-selector").first
    if sel.count() > 0:
        try:
            sel.click()
            time.sleep(0.8)
            item = page.locator('.ant-select-dropdown:visible .ant-select-item:has-text("New(新的)")').first
            if item.count() == 0:
                item = page.locator('.ant-select-dropdown:visible .ant-select-item:has-text("New"):not(:has-text("Like"))').first
            if item.count() > 0:
                item.click()
        except Exception:
            pass


def _fill_description(page, attrs: dict) -> None:
    desc = attrs.get("description", "")
    if not desc:
        return
    try:
        editor_id = page.evaluate(
            """
            () => {
                for (const id in CKEDITOR.instances) {
                    const editor = CKEDITOR.instances[id];
                    if (editor && editor.container && editor.container.isVisible()) return id;
                }
                return null;
            }
            """
        )
        if editor_id:
            page.evaluate(
                """([id, value]) => {
                    const editor = CKEDITOR.instances[id];
                    if (editor) editor.setData(value);
                }""",
                [editor_id, str(desc)[:1990]],
            )
            return
    except Exception:
        pass
    ta = page.locator("textarea.ant-input:visible").first
    if ta.count() > 0:
        ta.click()
        ta.fill("")
        ta.fill(str(desc)[:1990])


def _fill_bullets(page, attrs: dict) -> None:
    bullets = attrs.get("bullet_points", [])
    if not isinstance(bullets, list):
        return
    for idx in range(5):
        bp = page.locator(f"#form_item_bulletPoints_{idx}")
        if bp.count() > 0:
            bp.click()
            bp.fill("")
            bp.fill(str(bullets[idx] if idx < len(bullets) else ""))


def _select_shipping(page) -> None:
    label = page.locator('label:has-text("配送渠道")').first
    if label.count() == 0:
        return
    row = label.locator('xpath=ancestor::div[contains(@class,"ant-row")]').first
    sel = row.locator(".ant-select-selector").first
    if sel.count() > 0:
        try:
            sel.click()
            time.sleep(0.5)
            item = page.locator('.ant-select-dropdown:visible .ant-select-item:has-text("FBM")').first
            if item.count() > 0:
                item.click()
        except Exception:
            pass


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if not args:
        print("用法: python -m app.integrations.dianxiaomi.filler '<json_attributes>' [--no-pause] [--web-mode]")
        sys.exit(1)
    fill_form(json.loads(args[0]), no_pause="--no-pause" in sys.argv, web_mode="--web-mode" in sys.argv)
