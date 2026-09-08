from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.product_listing_agent import ProductListingAgent
from app.integrations.dianxiaomi.attributes import generate_dianxiaomi_attributes
from app.integrations.dianxiaomi.filler import RUNTIME_DIR, SIGNAL_FILE, STATE_FILE

router = APIRouter(prefix="/api/dianxiaomi", tags=["店小秘"])

_listing_agent: ProductListingAgent | None = None
_llm_client = None


class DianxiaomiGenerateRequest(BaseModel):
    keyword: str
    product_context: str = ""
    marketplace: str = "US"


class DianxiaomiFillRequest(BaseModel):
    attributes: dict[str, Any]


class DianxiaomiContinueRequest(BaseModel):
    step: str = "category"


def init_dianxiaomi_agent(*, llm_client) -> None:
    global _listing_agent, _llm_client
    _llm_client = llm_client
    _listing_agent = ProductListingAgent(llm_client=llm_client)


@router.post("/generate-attributes")
def generate_attributes(payload: DianxiaomiGenerateRequest) -> dict[str, Any]:
    keyword = payload.keyword.strip()
    product_context = payload.product_context.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    if not product_context:
        raise HTTPException(status_code=400, detail="产品描述不能为空")
    if _listing_agent is None or _llm_client is None:
        raise HTTPException(status_code=503, detail="未初始化店小秘 Agent")

    try:
        listing_result = _listing_agent.run(
            {
                "entities": {"keyword": keyword},
                "user_message": f"关键词：{keyword}，产品信息：{product_context}，生成Listing",
            },
            research_context={"keyword": keyword, "product_context": product_context},
        )
    except Exception as exc:
        message = str(exc)
        status = 503 if "未配置真实 LLM" in message else 502
        raise HTTPException(status_code=status, detail=f"ProductListingAgent 调用失败: {message}") from exc

    listing = listing_result.get("listing") or {}
    if not listing:
        summary = listing_result.get("summary") or "ProductListingAgent 未生成 Listing"
        status = 503 if "未配置真实 LLM" in summary else 502
        raise HTTPException(status_code=status, detail=summary)

    try:
        attributes = generate_dianxiaomi_attributes(
            llm_client=_llm_client,
            listing=listing,
            product_context=product_context,
            marketplace=payload.marketplace,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "ok": True,
        "keyword": keyword,
        "marketplace": (payload.marketplace or "US").upper(),
        "listing": listing,
        "attributes": attributes,
    }


@router.post("/fill")
def fill(payload: DianxiaomiFillRequest) -> dict[str, Any]:
    if not payload.attributes:
        raise HTTPException(status_code=400, detail="没有可填入的数据")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _clear_runtime_state()
    _stop_old_process()

    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.integrations.dianxiaomi.filler",
                json.dumps(payload.attributes, ensure_ascii=False),
                "--web-mode",
            ],
            cwd=str(Path(__file__).resolve().parents[2]),
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="无法启动 Python 解释器") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动店小秘填表失败: {exc}") from exc

    (RUNTIME_DIR / "filler_pid.txt").write_text(str(proc.pid), encoding="utf-8")
    return {"ok": True, "message": "Playwright 已启动，请在浏览器中检查并按提示继续", "pid": proc.pid}


@router.get("/fill/status")
def fill_status() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return {"ok": True, **state}
        except json.JSONDecodeError:
            pass
    return {"ok": True, "paused": False, "done": False, "message": "等待启动..."}


@router.post("/fill/continue")
def fill_continue(payload: DianxiaomiContinueRequest) -> dict[str, Any]:
    if payload.step not in {"category", "product_id"}:
        raise HTTPException(status_code=400, detail="step 只能是 category 或 product_id")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SIGNAL_FILE.write_text(payload.step, encoding="utf-8")
    return {"ok": True, "signal": payload.step}


def _clear_runtime_state() -> None:
    for file_path in (STATE_FILE, SIGNAL_FILE):
        if file_path.exists():
            file_path.unlink()


def _stop_old_process() -> None:
    pid_file = RUNTIME_DIR / "filler_pid.txt"
    if not pid_file.exists():
        return
    try:
        old_pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(old_pid, signal.SIGTERM)
    except Exception:
        pass
