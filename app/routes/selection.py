"""AI 选品项目与关键词调研 API。"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user
from app.auth.schemas import UserInfo
from app.db.models import (
    FreightTemplate,
    KeywordResearchRun,
    McpDataSource,
    ProductDirection,
    PricingSnapshot,
    ResearchKeyword,
    SelectionReport,
    SourceSnapshot,
)
from app.deps import get_session
from app.selection.credentials import EnvCredentialStore
from app.selection.direction_service import ProductDirectionService
from app.selection.keyword_service import IdempotencyConflictError, KeywordResearchService
from app.selection.mcp_registry import McpRegistry
from app.selection.contracts import McpCapability
from app.selection.pricing import (
    FreightRule,
    PricingInput,
    calculate_billable_weight,
    calculate_freight,
    calculate_target_price,
)
from app.selection.repository import SelectionRepository
from app.selection.report_service import ReportService


router = APIRouter(prefix="/api/selection", tags=["AI 选品"])
_report_llm_client = None


def init_selection_llm_client(client: Any) -> None:
    """由应用启动时注入真实 LLM；测试可覆盖依赖。"""
    global _report_llm_client
    _report_llm_client = client


def get_report_llm_client() -> Any | None:
    return _report_llm_client


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    marketplace: str = Field(min_length=1, max_length=32)
    target_currency: str = Field(min_length=1, max_length=8)

    @field_validator("name", "marketplace", "target_currency")
    @classmethod
    def non_empty(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("字段不能为空")
        return cleaned


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=256)
    marketplace: str | None = Field(default=None, min_length=1, max_length=32)
    target_currency: str | None = Field(default=None, min_length=1, max_length=8)
    status: Literal["active", "archived"] | None = None


class KeywordResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_type: Literal["seed", "asin", "category"]
    input_value: str
    category: str | None = None


class SelectedKeywordsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword_ids: list[int]


class FreightTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    marketplace: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=1, max_length=64)
    channel: str = Field(min_length=1, max_length=64)
    currency: str = Field(min_length=1, max_length=8)
    pricing_mode: Literal["per_kg", "first_additional"]
    minimum_billable_weight_kg: Decimal = Decimal("0")
    first_weight_kg: Decimal | None = None
    first_weight_fee: Decimal | None = None
    additional_weight_unit_kg: Decimal | None = None
    additional_weight_fee: Decimal | None = None
    per_kg_rate: Decimal | None = None
    volume_divisor: Decimal = Decimal("6000")
    effective_from: date
    enabled: bool = True
    notes: str | None = None

    @field_validator("name", "marketplace", "country", "channel", "currency")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("字段不能为空")
        return cleaned

    @model_validator(mode="after")
    def validate_rule(self):
        values = {
            "最低计费重量": self.minimum_billable_weight_kg,
            "体积重除数": self.volume_divisor,
            "首重": self.first_weight_kg,
            "首重价格": self.first_weight_fee,
            "续重单位": self.additional_weight_unit_kg,
            "续重价格": self.additional_weight_fee,
            "每公斤价格": self.per_kg_rate,
        }
        for name, value in values.items():
            if value is not None and (not value.is_finite() or value < 0):
                raise ValueError(f"{name}必须是非负有限数值")
        if self.volume_divisor <= 0:
            raise ValueError("体积重除数必须大于 0")
        if self.pricing_mode == "per_kg" and self.per_kg_rate is None:
            raise ValueError("每公斤计价模式必须填写每公斤价格")
        if self.pricing_mode == "first_additional":
            required = (
                self.first_weight_kg,
                self.first_weight_fee,
                self.additional_weight_unit_kg,
                self.additional_weight_fee,
            )
            if any(value is None for value in required):
                raise ValueError("首重续重模式必须填写首重、首重价格、续重单位和续重价格")
            if self.first_weight_kg <= 0:
                raise ValueError("首重必须大于 0")
            if self.additional_weight_unit_kg <= 0:
                raise ValueError("续重单位必须大于 0")
        return self


class FreightTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    marketplace: str | None = None
    country: str | None = None
    channel: str | None = None
    currency: str | None = None
    pricing_mode: Literal["per_kg", "first_additional"] | None = None
    minimum_billable_weight_kg: Decimal | None = None
    first_weight_kg: Decimal | None = None
    first_weight_fee: Decimal | None = None
    additional_weight_unit_kg: Decimal | None = None
    additional_weight_fee: Decimal | None = None
    per_kg_rate: Decimal | None = None
    volume_divisor: Decimal | None = None
    effective_from: date | None = None
    enabled: bool | None = None
    notes: str | None = None


class ExchangeRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_currency: str = Field(min_length=1, max_length=8)
    quote_currency: str = Field(min_length=1, max_length=8)


class PricingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_price: Decimal
    domestic_shipping: Decimal = Decimal("0")
    source_currency: str = Field(min_length=1, max_length=8)
    actual_weight_kg: Decimal
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal
    freight_template_id: int
    commission_rate: Decimal = Decimal("0.15")
    target_net_margin: Decimal = Decimal("0.40")
    manual_exchange_rate: Decimal | None = None

    @model_validator(mode="after")
    def fixed_margin_and_finite_values(self):
        for value in (
            self.product_price, self.domestic_shipping, self.actual_weight_kg,
            self.length_cm, self.width_cm, self.height_cm, self.commission_rate,
            self.target_net_margin,
        ):
            if not value.is_finite():
                raise ValueError("定价数值必须是有限数值")
        if self.manual_exchange_rate is not None and (
            not self.manual_exchange_rate.is_finite() or self.manual_exchange_rate <= 0
        ):
            raise ValueError("手动汇率必须大于 0")
        if self.target_net_margin != Decimal("0.40"):
            raise ValueError("目标净利润率固定为 40%")
        return self


def get_mcp_registry(db: Session = Depends(get_session)) -> McpRegistry:
    store = EnvCredentialStore(__import__("os").environ, lambda _: None)
    sources = []
    for source in db.scalars(
        select(McpDataSource)
        .where(McpDataSource.enabled.is_(True))
        .order_by(McpDataSource.priority, McpDataSource.id)
    ):
        sources.append({
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "transport": source.transport,
            "enabled": source.enabled,
            "priority": source.priority,
            "capability_config_json": source.capability_config_json,
            "headers": store.load_headers(source.credential_reference or ""),
        })
    return McpRegistry(sources=sources)


@router.post("/freight-templates", status_code=status.HTTP_201_CREATED)
def create_freight_template(
    payload: FreightTemplateCreate,
    _: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    template = FreightTemplate(**_template_values(payload))
    db.add(template)
    db.flush()
    db.commit()
    return _freight_template(template)


@router.get("/freight-templates")
def list_freight_templates(
    _: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    return {
        "items": [
            _freight_template(item)
            for item in SelectionRepository(db).list_freight_templates()
        ]
    }


@router.put("/freight-templates/{template_id}")
def update_freight_template(
    template_id: int,
    payload: FreightTemplateUpdate,
    _: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    repository = SelectionRepository(db)
    try:
        template = repository.get_freight_template(template_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    current = {
        name: getattr(template, name)
        for name in FreightTemplateCreate.model_fields
    }
    current.update(payload.model_dump(exclude_unset=True))
    try:
        validated = FreightTemplateCreate.model_validate(current)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for name, value in _template_values(validated).items():
        setattr(template, name, value)
    db.commit()
    return _freight_template(template)


@router.delete("/freight-templates/{template_id}")
def delete_freight_template(
    template_id: int,
    _: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        template = SelectionRepository(db).get_freight_template(template_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.delete(template)
    db.commit()
    return {"id": template_id, "deleted": True}


@router.post("/exchange-rates/refresh")
async def refresh_exchange_rate(
    payload: ExchangeRefreshRequest,
    _: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
    registry: McpRegistry = Depends(get_mcp_registry),
) -> dict[str, Any]:
    base = payload.base_currency.strip().upper()
    quote = payload.quote_currency.strip().upper()
    if base == quote:
        return _same_currency_rate(base, quote)
    rate = await _fetch_exchange_rate(registry, base, quote)
    saved = SelectionRepository(db).save_exchange_rate(
        base_currency=base,
        quote_currency=quote,
        rate=rate["rate_decimal"],
        source_name=rate["source_name"],
        source_type="mcp",
        collected_at=rate["collected_at"],
    )
    return _exchange_rate(saved, manual_override=False)


@router.put("/projects/{project_id}/pricing")
async def put_project_pricing(
    project_id: int,
    payload: PricingRequest,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
    registry: McpRegistry = Depends(get_mcp_registry),
) -> dict[str, Any]:
    repository = SelectionRepository(db)
    project = _owned(repository, project_id, user.username)
    try:
        template = repository.get_freight_template(payload.freight_template_id)
        source_currency = payload.source_currency.strip().upper()
        if template.currency.upper() != source_currency:
            raise ValueError("运费模板币种必须与商品源币种一致")
        rule = FreightRule(
            pricing_mode=template.pricing_mode,
            per_kg_rate=template.per_kg_rate,
            first_weight_kg=template.first_weight_kg,
            first_weight_fee=template.first_weight_fee,
            additional_weight_unit_kg=template.additional_weight_unit_kg,
            additional_weight_fee=template.additional_weight_fee,
        )
        billable_weight = calculate_billable_weight(
            payload.actual_weight_kg, payload.length_cm, payload.width_cm,
            payload.height_cm, template.volume_divisor,
            template.minimum_billable_weight_kg,
        )
        volumetric_weight = (
            payload.length_cm * payload.width_cm * payload.height_cm
            / template.volume_divisor
        )
        international_shipping = calculate_freight(billable_weight, rule)
        exchange_snapshot = await _pricing_exchange_snapshot(
            registry, source_currency, project.target_currency.upper(),
            payload.manual_exchange_rate,
        )
        result = calculate_target_price(PricingInput(
            product_cost=payload.product_price,
            domestic_shipping=payload.domestic_shipping,
            international_shipping=international_shipping,
            exchange_rate=Decimal(exchange_snapshot["rate"]),
            commission_rate=payload.commission_rate,
            target_net_margin=payload.target_net_margin,
        ))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    snapshot = repository.save_pricing_snapshot(
        project_id=project.id,
        product_price=payload.product_price,
        domestic_shipping=payload.domestic_shipping,
        source_currency=source_currency,
        actual_weight_kg=payload.actual_weight_kg,
        length_cm=payload.length_cm,
        width_cm=payload.width_cm,
        height_cm=payload.height_cm,
        commission_rate=payload.commission_rate,
        target_net_margin=payload.target_net_margin,
        freight_template_snapshot_json=_freight_template(template),
        exchange_rate_snapshot_json=exchange_snapshot,
        volumetric_weight_kg=volumetric_weight,
        billable_weight_kg=billable_weight,
        international_shipping=international_shipping,
        target_price=result.target_price,
        commission_amount=result.commission_amount,
        net_profit_amount=result.net_profit_amount,
    )
    return _pricing_snapshot(snapshot)


@router.get("/projects/{project_id}/pricing")
def get_project_pricing(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        snapshot = SelectionRepository(db).latest_pricing_snapshot(project_id, user.username)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _pricing_snapshot(snapshot)


@router.post("/projects/{project_id}/report")
def generate_project_report(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
    llm_client: Any | None = Depends(get_report_llm_client),
) -> dict[str, Any]:
    try:
        report = ReportService(session=db, llm_client=llm_client).generate(
            project_id, user.username
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="选品项目不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _selection_report(report)


@router.get("/projects/{project_id}/report")
def get_project_report(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned(SelectionRepository(db), project_id, user.username)
    report = db.scalar(
        select(SelectionReport)
        .where(SelectionReport.project_id == project_id)
        .order_by(SelectionReport.generated_at.desc(), SelectionReport.id.desc())
    )
    if report is None:
        raise HTTPException(status_code=404, detail="决策报告不存在")
    return _selection_report(report)


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = SelectionRepository(db).create_project(
        user.username, payload.name, payload.marketplace.upper(), payload.target_currency.upper()
    )
    return _project(project)


@router.get("/projects")
def list_projects(
    user: UserInfo = Depends(get_current_user), db: Session = Depends(get_session)
) -> dict[str, Any]:
    return {"items": [_project(item) for item in SelectionRepository(db).list_projects(user.username)]}


@router.get("/projects/{project_id}")
def get_project(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    return _project(_owned(SelectionRepository(db), project_id, user.username))


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = _owned(SelectionRepository(db), project_id, user.username)
    for name, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        cleaned = " ".join(value.split()) if isinstance(value, str) else value
        if name in {"marketplace", "target_currency"}:
            cleaned = cleaned.upper()
        setattr(project, name, cleaned)
    db.commit()
    return _project(project)


@router.post("/projects/{project_id}/keyword-research")
async def research_keywords(
    project_id: int,
    payload: KeywordResearchRequest,
    request_id: str = Header(min_length=1, max_length=128, alias="Idempotency-Key"),
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
    registry: McpRegistry = Depends(get_mcp_registry),
) -> dict[str, Any]:
    repository = SelectionRepository(db)
    project = _owned(repository, project_id, user.username)
    try:
        run = await KeywordResearchService(db, registry).run(
            project.id, user.username, payload.input_type, payload.input_value,
            project.marketplace, payload.category, request_id.strip(),
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _run_detail(db, run)


@router.get("/projects/{project_id}/keyword-runs")
def list_keyword_runs(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned(SelectionRepository(db), project_id, user.username)
    runs = db.scalars(
        select(KeywordResearchRun).where(KeywordResearchRun.project_id == project_id).order_by(KeywordResearchRun.id.desc())
    )
    return {"items": [_run(item) for item in runs]}


@router.get("/projects/{project_id}/keywords")
def list_keywords(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned(SelectionRepository(db), project_id, user.username)
    rows = db.scalars(
        select(ResearchKeyword).where(ResearchKeyword.project_id == project_id).order_by(ResearchKeyword.id)
    )
    return {"items": [_keyword(item) for item in rows]}


@router.put("/projects/{project_id}/selected-keywords")
def select_keywords(
    project_id: int,
    payload: SelectedKeywordsRequest,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        rows = SelectionRepository(db).replace_selected_keywords(project_id, user.username, payload.keyword_ids)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="选品项目不存在") from exc
    return {"items": [_keyword(item) for item in rows]}


@router.post("/projects/{project_id}/product-direction")
async def build_product_direction(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
    llm_client: Any | None = Depends(get_report_llm_client),
) -> dict[str, Any]:
    try:
        direction = await ProductDirectionService(db, llm_client).build(project_id, user.username)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="选品项目不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _direction(direction)


@router.get("/projects/{project_id}/product-direction")
def get_product_direction(
    project_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned(SelectionRepository(db), project_id, user.username)
    direction = db.scalar(
        select(ProductDirection)
        .where(ProductDirection.project_id == project_id)
        .order_by(ProductDirection.created_at.desc(), ProductDirection.id.desc())
    )
    if direction is None:
        raise HTTPException(status_code=404, detail="产品方向不存在")
    return _direction(direction)


@router.get("/source-snapshots/{snapshot_id}")
def get_source_snapshot(
    snapshot_id: int,
    user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="原始数据快照不存在")
    _owned(SelectionRepository(db), snapshot.project_id, user.username)
    return _snapshot(snapshot, full=True)


def _template_values(payload: FreightTemplateCreate) -> dict[str, Any]:
    values = payload.model_dump()
    for name in ("marketplace", "country", "currency"):
        values[name] = values[name].upper()
    return values


def _freight_template(item: FreightTemplate) -> dict[str, Any]:
    data = {
        name: getattr(item, name)
        for name in (
            "id", "name", "marketplace", "country", "channel", "currency",
            "pricing_mode", "effective_from", "enabled", "notes",
        )
    }
    for name in (
        "minimum_billable_weight_kg", "first_weight_kg", "first_weight_fee",
        "additional_weight_unit_kg", "additional_weight_fee", "per_kg_rate",
        "volume_divisor",
    ):
        value = getattr(item, name)
        data[name] = _decimal_text(value) if value is not None else None
    data["effective_from"] = item.effective_from.isoformat()
    return data


async def _fetch_exchange_rate(
    registry: McpRegistry, base: str, quote: str
) -> dict[str, Any]:
    results = await registry.call(
        McpCapability.EXCHANGE_RATE,
        {"base_currency": base, "quote_currency": quote},
    )
    for result in results:
        if result.status != "succeeded":
            continue
        for record in result.records:
            if str(record.get("base_currency") or "").upper() != base:
                continue
            if str(record.get("quote_currency") or "").upper() != quote:
                continue
            try:
                rate = Decimal(str(record.get("rate")))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not rate.is_finite() or rate <= 0:
                continue
            return {
                "base_currency": base,
                "quote_currency": quote,
                "rate_decimal": rate,
                "source_name": result.source_name,
                "source_type": "mcp",
                "collected_at": result.collected_at,
                "manual_override": False,
            }
    raise HTTPException(status_code=502, detail="真实汇率来源未返回有效汇率")


async def _pricing_exchange_snapshot(
    registry: McpRegistry,
    base: str,
    quote: str,
    manual_rate: Decimal | None,
) -> dict[str, Any]:
    if base == quote:
        return _same_currency_rate(base, quote)
    if manual_rate is not None:
        return {
            "base_currency": base,
            "quote_currency": quote,
            "rate": _decimal_text(manual_rate),
            "source_name": "manual_override",
            "source_type": "manual",
            "collected_at": datetime.now(UTC).isoformat(),
            "manual_override": True,
        }
    fetched = await _fetch_exchange_rate(registry, base, quote)
    return {
        "base_currency": base,
        "quote_currency": quote,
        "rate": _decimal_text(fetched["rate_decimal"]),
        "source_name": fetched["source_name"],
        "source_type": fetched["source_type"],
        "collected_at": fetched["collected_at"].isoformat(),
        "manual_override": False,
    }


def _same_currency_rate(base: str, quote: str) -> dict[str, Any]:
    return {
        "base_currency": base,
        "quote_currency": quote,
        "rate": "1",
        "source_name": "same_currency",
        "source_type": "deterministic",
        "collected_at": datetime.now(UTC).isoformat(),
        "manual_override": False,
    }


def _exchange_rate(item: Any, manual_override: bool) -> dict[str, Any]:
    return {
        "id": item.id,
        "base_currency": item.base_currency,
        "quote_currency": item.quote_currency,
        "rate": _decimal_text(item.rate),
        "source_name": item.source_name,
        "source_type": item.source_type,
        "collected_at": _iso(item.collected_at),
        "manual_override": manual_override,
    }


def _pricing_snapshot(item: PricingSnapshot) -> dict[str, Any]:
    data = {
        "id": item.id,
        "project_id": item.project_id,
        "source_currency": item.source_currency,
        "freight_template_snapshot": item.freight_template_snapshot_json,
        "exchange_rate_snapshot": item.exchange_rate_snapshot_json,
        "calculated_at": _iso(item.calculated_at),
    }
    for name in (
        "product_price", "domestic_shipping", "actual_weight_kg", "length_cm",
        "width_cm", "height_cm", "commission_rate", "target_net_margin",
        "volumetric_weight_kg", "billable_weight_kg", "international_shipping",
        "target_price", "commission_amount", "net_profit_amount",
    ):
        value = getattr(item, name)
        data[name] = _money_text(value) if name in {
            "international_shipping", "target_price", "commission_amount",
            "net_profit_amount",
        } else _decimal_text(value)
    return data


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), ".2f")


def _owned(repository: SelectionRepository, project_id: int, user_id: str):
    try:
        return repository.get_owned_project(project_id, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="选品项目不存在") from exc


def _project(item: Any) -> dict[str, Any]:
    return {name: getattr(item, name) for name in ("id", "name", "marketplace", "target_currency", "status", "current_stage")} | {
        "created_at": _iso(item.created_at), "updated_at": _iso(item.updated_at)
    }


def _run(item: KeywordResearchRun) -> dict[str, Any]:
    return {name: getattr(item, name) for name in ("id", "project_id", "input_type", "input_value", "marketplace", "category", "status", "error_summary")} | {
        "started_at": _iso(item.started_at), "completed_at": _iso(item.completed_at)
    }


def _run_detail(db: Session, run: KeywordResearchRun) -> dict[str, Any]:
    keywords = db.scalars(select(ResearchKeyword).where(ResearchKeyword.run_id == run.id).order_by(ResearchKeyword.id))
    snapshots = list(db.scalars(
        select(SourceSnapshot).where(SourceSnapshot.research_run_id == run.id).order_by(SourceSnapshot.id)
    ))
    return _run(run) | {
        "keywords": [_keyword(row) for row in keywords],
        "snapshots": [_snapshot(row, full=True) for row in snapshots],
        "pagination": _pagination(snapshots),
    }


def _pagination(snapshots: list[SourceSnapshot]) -> dict[str, int]:
    page_counts = [
        len(response.get("pages", []))
        for snapshot in snapshots
        if isinstance((response := snapshot.response_json_redacted), dict)
        and isinstance(response.get("pages"), list)
    ]
    return {"collected_pages": max(page_counts, default=0)}


def _keyword(item: ResearchKeyword) -> dict[str, Any]:
    data = {name: getattr(item, name) for name in (
        "id", "project_id", "run_id", "keyword", "normalized_keyword", "search_volume", "trend_rate",
        "trend_period", "product_count", "competition_index", "cpc", "conversion_rate", "relevance_score",
        "opportunity_score", "selected",
    )}
    data.update({"source_id": item.metrics_json.get("source_id"), "source_name": item.metrics_json.get("source_name"), "collected_at": item.metrics_json.get("collected_at"), "metrics": item.metrics_json, "field_lineage": item.field_lineage_json})
    return data


def _snapshot(item: SourceSnapshot, full: bool = False) -> dict[str, Any]:
    data = {"id": item.id, "project_id": item.project_id, "research_run_id": item.research_run_id, "source_id": item.source_id, "capability": item.capability, "tool_name": item.tool_name, "truncated": item.truncated, "collected_at": _iso(item.collected_at)}
    if full:
        data.update({"request": item.request_json_redacted, "response": item.response_json_redacted})
    return data


def _direction(item: ProductDirection) -> dict[str, Any]:
    market_metrics = item.market_metrics_json or {}
    return {
        "id": item.id,
        "project_id": item.project_id,
        "name": item.name,
        "keyword_cluster": item.keyword_cluster_json or {},
        "market_metrics": market_metrics,
        "competitors": item.competitors_json or {},
        "field_lineage": item.field_lineage_json or {},
        "data_completeness": item.data_completeness,
        "warnings": market_metrics.get("warnings", []),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _selection_report(item: SelectionReport) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "score_total": item.score_total,
        "score_dimensions": item.score_dimensions_json or {},
        "decision": item.decision,
        "evidence": item.evidence_json or {},
        "risks": item.risks_json or {},
        "llm_status": item.llm_status,
        "llm_report": item.llm_report,
        "generated_at": _iso(item.generated_at),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
