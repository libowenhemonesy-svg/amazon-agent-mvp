from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInfo
from app.selection.contracts import McpCallResult, McpCapability
from app.routes.selection import get_report_llm_client


class FakeRegistry:
    def __init__(self, results: list[McpCallResult] | None = None) -> None:
        self.results = results or []
        self.calls: list[tuple[McpCapability, dict]] = []

    async def call(self, capability: McpCapability, arguments: dict):
        self.calls.append((capability, arguments))
        return self.results


def mcp_result(
    *,
    source_id: str = "seller-sprite",
    source_name: str = "卖家精灵",
    status: str = "succeeded",
    records: list[dict] | None = None,
    raw_data: object | None = None,
    warnings: list[str] | None = None,
    capability: McpCapability = McpCapability.KEYWORD_EXPAND,
) -> McpCallResult:
    rows = records or []
    return McpCallResult(
        source_id=source_id,
        source_name=source_name,
        capability=capability,
        tool_name="keyword_research",
        collected_at=datetime.now(UTC),
        status=status,
        records=rows,
        field_lineage=[{"keyword": {"raw_path": f"data[{index}].keyword"}} for index in range(len(rows))],
        warnings=warnings or [],
        raw_data=raw_data,
    )


def test_project_endpoint_starts_as_404(client_as_user):
    response = client_as_user.post(
        "/api/selection/projects",
        json={"name": "便携风扇", "marketplace": "US", "target_currency": "USD"},
    )
    assert response.status_code == 201


def _create_project(client, name: str = "便携风扇") -> dict:
    response = client.post(
        "/api/selection/projects",
        json={"name": name, "marketplace": "us", "target_currency": "usd"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize(
    ("input_type", "input_value", "capability", "argument_name", "argument_value"),
    [
        ("seed", "  Portable   Fan ", McpCapability.KEYWORD_EXPAND, "keyword", "Portable Fan"),
        ("asin", " b0abc12345 ", McpCapability.ASIN_KEYWORD_REVERSE, "asin", "B0ABC12345"),
        ("category", "  Home   Fans ", McpCapability.CATEGORY_KEYWORDS, "category", "Home Fans"),
    ],
)
def test_keyword_input_maps_to_explicit_capability(
    app, client_as_user, fake_registry, input_type, input_value, capability, argument_name, argument_value
):
    project = _create_project(client_as_user)
    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": f"mapping-{input_type}"},
        json={"input_type": input_type, "input_value": input_value, "category": "all"},
    )
    assert response.status_code == 200
    assert fake_registry.calls[0][0] is capability
    assert fake_registry.calls[0][1][argument_name] == argument_value


def test_keyword_research_saves_real_rows_snapshot_and_redacts_secrets(
    client_as_user, fake_registry
):
    fake_registry.results = [
        mcp_result(
            records=[{"keyword": "Portable Fan", "search_volume": 42000}],
            raw_data={
                "data": [{"keyword": "Portable Fan", "searchVolume": 42000}],
                "pages": [{"page": 1}, {"page": 2}],
                "Authorization": "Bearer secret-value",
                "nested": {"api_key": "secret-key"},
            },
        )
    ]
    project = _create_project(client_as_user)
    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "research-1"},
        json={"input_type": "seed", "input_value": "portable fan", "category": "all"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["keywords"][0]["keyword"] == "Portable Fan"
    assert body["keywords"][0]["normalized_keyword"] == "portable fan"
    assert body["keywords"][0]["source_name"] == "卖家精灵"
    assert body["pagination"] == {"collected_pages": 2}
    snapshot = client_as_user.get(
        f"/api/selection/source-snapshots/{body['snapshots'][0]['id']}"
    ).json()
    serialized = str(snapshot)
    assert "secret-value" not in serialized
    assert "secret-key" not in serialized
    assert snapshot["response"]["data"][0]["keyword"] == "Portable Fan"


def test_partial_and_all_failed_never_fabricate_keywords(client_as_user, fake_registry):
    project = _create_project(client_as_user)
    fake_registry.results = [
        mcp_result(records=[{"keyword": "real keyword", "search_volume": 10}]),
        mcp_result(source_id="other", source_name="其他源", status="failed", warnings=["超时"]),
    ]
    partial = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "partial"},
        json={"input_type": "seed", "input_value": "fan"},
    ).json()
    assert partial["status"] == "partial"
    assert [row["keyword"] for row in partial["keywords"]] == ["real keyword"]

    fake_registry.results = [mcp_result(status="failed", warnings=["调用失败"])]
    failed = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "failed"},
        json={"input_type": "seed", "input_value": "fan"},
    ).json()
    assert failed["status"] == "failed"
    assert failed["keywords"] == []


def test_all_unsupported_sources_fail_without_saving_keywords(client_as_user, fake_registry):
    project = _create_project(client_as_user)
    fake_registry.results = [
        mcp_result(
            status="unsupported",
            records=[{"keyword": "must not be saved"}],
            warnings=["数据源不支持该能力"],
        )
    ]

    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "all-unsupported"},
        json={"input_type": "seed", "input_value": "fan"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["keywords"] == []
    assert len(response.json()["snapshots"]) == 1


def test_success_and_unsupported_sources_are_partial_and_ignore_unsupported_rows(
    client_as_user, fake_registry
):
    project = _create_project(client_as_user)
    fake_registry.results = [
        mcp_result(records=[{"keyword": "real keyword"}]),
        mcp_result(
            source_id="unsupported-source",
            source_name="不支持源",
            status="unsupported",
            records=[{"keyword": "must not be saved"}],
            warnings=["数据源不支持该能力"],
        ),
    ]

    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "success-and-unsupported"},
        json={"input_type": "seed", "input_value": "fan"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert [row["keyword"] for row in response.json()["keywords"]] == ["real keyword"]
    assert len(response.json()["snapshots"]) == 2


def test_idempotency_reuses_only_same_request_semantics(client_as_user, fake_registry):
    fake_registry.results = [mcp_result(records=[{"keyword": "portable fan"}])]
    project = _create_project(client_as_user)
    url = f"/api/selection/projects/{project['id']}/keyword-research"
    headers = {"Idempotency-Key": "same-key"}
    first = client_as_user.post(url, headers=headers, json={"input_type": "seed", "input_value": " fan "})
    second = client_as_user.post(url, headers=headers, json={"input_type": "seed", "input_value": "fan"})
    conflict = client_as_user.post(url, headers=headers, json={"input_type": "seed", "input_value": "desk fan"})
    assert first.json()["id"] == second.json()["id"]
    assert len(fake_registry.calls) == 1
    assert conflict.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"input_type": "seed", "input_value": "   "},
        {"input_type": "asin", "input_value": "BAD-ASIN"},
        {"input_type": "category", "input_value": ""},
    ],
)
def test_keyword_input_validation(client_as_user, fake_registry, payload):
    project = _create_project(client_as_user)
    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "invalid-input"},
        json=payload,
    )
    assert response.status_code == 422
    assert fake_registry.calls == []


def test_project_keywords_selection_and_snapshots_are_user_scoped(
    app, client_as_user, fake_registry
):
    fake_registry.results = [mcp_result(records=[{"keyword": "portable fan"}])]
    project = _create_project(client_as_user)
    run = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "owned"},
        json={"input_type": "seed", "input_value": "fan"},
    ).json()
    keyword_id = run["keywords"][0]["id"]
    selected = client_as_user.put(
        f"/api/selection/projects/{project['id']}/selected-keywords",
        json={"keyword_ids": [keyword_id]},
    )
    assert selected.status_code == 200
    assert selected.json()["items"][0]["selected"] is True
    assert client_as_user.get(f"/api/selection/projects/{project['id']}/keywords").status_code == 200
    assert client_as_user.get(f"/api/selection/projects/{project['id']}/keyword-runs").status_code == 200

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="bob", display_name="Bob", role="user", is_active=True
    )
    assert client_as_user.get(f"/api/selection/projects/{project['id']}").status_code == 404
    assert client_as_user.get(
        f"/api/selection/source-snapshots/{run['snapshots'][0]['id']}"
    ).status_code == 404


def test_product_direction_sends_complete_selected_keyword_data_to_llm(
    app, client_as_user, fake_registry
):
    prompts: list[tuple[str, str]] = []

    class RecordingLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            prompts.append((system_prompt, user_prompt))
            return '''{
                "primary_keyword": "portable fan",
                "long_tail_keywords": ["portable fan for bedroom"],
                "product_direction": "便携风扇，适合卧室使用。"
            }'''

    app.dependency_overrides[get_report_llm_client] = RecordingLLM
    fake_registry.results = [mcp_result(records=[
        {"keyword": "portable fan", "relevance_score": 0.95, "monthly_search_volume": 12000},
        {
            "keyword": "portable fan for bedroom",
            "relevance_score": 0.8,
            "monthly_search_volume": 3200,
            "custom_sellersprite_metric": "完整字段必须保留",
        },
    ])]
    project = _create_project(client_as_user)
    run = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "direction-keywords"},
        json={"input_type": "seed", "input_value": "portable fan"},
    ).json()
    client_as_user.put(
        f"/api/selection/projects/{project['id']}/selected-keywords",
        json={"keyword_ids": [item["id"] for item in run["keywords"]]},
    )
    fake_registry.calls.clear()
    fake_registry.results = []

    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/product-direction"
    )

    assert response.status_code == 200
    assert fake_registry.calls == []
    assert len(prompts) == 1
    assert "目标用户" in prompts[0][0]
    assert "差异化" in prompts[0][0]
    assert "custom_sellersprite_metric" in prompts[0][1]
    assert "完整字段必须保留" in prompts[0][1]
    assert response.json()["keyword_cluster"]["all"] == [
        "portable fan", "portable fan for bedroom"
    ]
    assert response.json()["keyword_cluster"]["primary"] == ["portable fan"]
    assert response.json()["keyword_cluster"]["long_tail"] == ["portable fan for bedroom"]
    assert response.json()["market_metrics"]["llm_research"]["product_direction"] == "便携风扇，适合卧室使用。"
    assert response.json()["market_metrics"]["llm_input"]["selected_keywords"][1]["metrics"]["custom_sellersprite_metric"] == "完整字段必须保留"
    assert response.json()["warnings"] == []
    fetched = client_as_user.get(
        f"/api/selection/projects/{project['id']}/product-direction"
    )
    assert fetched.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="bob", display_name="Bob", role="user", is_active=True
    )
    assert client_as_user.get(
        f"/api/selection/projects/{project['id']}/product-direction"
    ).status_code == 404


def test_product_direction_requires_selected_keywords(client_as_user, fake_registry):
    project = _create_project(client_as_user)
    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/product-direction"
    )
    assert response.status_code == 422
    assert fake_registry.calls == []


def _freight_payload(**overrides):
    payload = {
        "name": "美国空运",
        "marketplace": "US",
        "country": "US",
        "channel": "air",
        "currency": "USD",
        "pricing_mode": "per_kg",
        "minimum_billable_weight_kg": "0",
        "per_kg_rate": "15",
        "volume_divisor": "6000",
        "effective_from": "2026-07-14",
        "enabled": True,
    }
    payload.update(overrides)
    return payload


def test_freight_templates_require_admin_for_writes_and_allow_user_reads(
    app, client_as_admin
):
    created = client_as_admin.post(
        "/api/selection/freight-templates", json=_freight_payload()
    )
    assert created.status_code == 201
    template_id = created.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    assert client_as_admin.get("/api/selection/freight-templates").status_code == 200
    assert client_as_admin.put(
        f"/api/selection/freight-templates/{template_id}",
        json={"name": "禁止普通用户修改"},
    ).status_code == 403
    assert client_as_admin.delete(
        f"/api/selection/freight-templates/{template_id}"
    ).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        _freight_payload(per_kg_rate=None),
        _freight_payload(volume_divisor="0"),
        _freight_payload(minimum_billable_weight_kg="-1"),
        _freight_payload(
            pricing_mode="first_additional",
            per_kg_rate=None,
            first_weight_kg="1",
            first_weight_fee="10",
            additional_weight_unit_kg="0.5",
            additional_weight_fee="4",
        ),
    ],
)
def test_freight_template_validates_modes_and_numeric_fields(client_as_admin, payload):
    response = client_as_admin.post("/api/selection/freight-templates", json=payload)
    if payload["pricing_mode"] == "first_additional":
        assert response.status_code == 201
    else:
        assert response.status_code == 422


def _pricing_payload(template_id: int, **overrides):
    payload = {
        "product_price": "30",
        "domestic_shipping": "0",
        "source_currency": "USD",
        "actual_weight_kg": "1",
        "length_cm": "0",
        "width_cm": "0",
        "height_cm": "0",
        "freight_template_id": template_id,
        "commission_rate": "0.15",
        "target_net_margin": "0.40",
    }
    payload.update(overrides)
    return payload


def test_pricing_same_currency_is_immutable_and_enforces_fixed_margin(
    app, client_as_admin
):
    template = client_as_admin.post(
        "/api/selection/freight-templates", json=_freight_payload()
    ).json()
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    project = _create_project(client_as_admin)
    url = f"/api/selection/projects/{project['id']}/pricing"
    response = client_as_admin.put(url, json=_pricing_payload(template["id"]))
    assert response.status_code == 200
    body = response.json()
    assert body["exchange_rate_snapshot"] == {
        "base_currency": "USD",
        "quote_currency": "USD",
        "rate": "1",
        "source_name": "same_currency",
        "source_type": "deterministic",
        "collected_at": body["exchange_rate_snapshot"]["collected_at"],
        "manual_override": False,
    }
    assert body["target_price"] == "100.00"
    assert body["commission_amount"] == "15.00"
    assert body["net_profit_amount"] == "40.00"
    assert body["actual_weight_kg"] == "1"
    assert body["volumetric_weight_kg"] == "0"
    assert body["billable_weight_kg"] == "1"
    assert body["international_shipping"] == "15.00"

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", display_name="Admin", role="admin", is_active=True
    )
    client_as_admin.put(
        f"/api/selection/freight-templates/{template['id']}",
        json={"per_kg_rate": "99"},
    )
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    assert client_as_admin.get(url).json()["freight_template_snapshot"]["per_kg_rate"] == "15"
    assert client_as_admin.put(
        url,
        json=_pricing_payload(template["id"], target_net_margin="0.39"),
    ).status_code == 422


def test_pricing_manual_and_automatic_exchange_and_cross_user_404(
    app, client_as_admin, fake_registry
):
    template = client_as_admin.post(
        "/api/selection/freight-templates",
        json=_freight_payload(currency="CNY", per_kg_rate="15"),
    ).json()
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    project = _create_project(client_as_admin)
    url = f"/api/selection/projects/{project['id']}/pricing"
    manual = client_as_admin.put(
        url,
        json=_pricing_payload(
            template["id"], source_currency="CNY", manual_exchange_rate="0.5"
        ),
    )
    assert manual.status_code == 200
    assert manual.json()["exchange_rate_snapshot"]["manual_override"] is True
    assert fake_registry.calls == []

    fake_registry.results = [mcp_result(
        source_id="priority-source",
        source_name="真实汇率源",
        capability=McpCapability.EXCHANGE_RATE,
        records=[{"base_currency": "CNY", "quote_currency": "USD", "rate": "0.2"}],
    )]
    automatic = client_as_admin.put(
        url, json=_pricing_payload(template["id"], source_currency="CNY")
    )
    assert automatic.status_code == 200
    assert automatic.json()["exchange_rate_snapshot"]["source_name"] == "真实汇率源"
    assert automatic.json()["exchange_rate_snapshot"]["rate"] == "0.2"
    assert fake_registry.calls[-1] == (
        McpCapability.EXCHANGE_RATE,
        {"base_currency": "CNY", "quote_currency": "USD"},
    )

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="bob", display_name="Bob", role="user", is_active=True
    )
    assert client_as_admin.get(url).status_code == 404
    assert client_as_admin.put(url, json=_pricing_payload(template["id"])).status_code == 404


def test_pricing_rejects_freight_currency_mismatch_before_exchange_call(
    app, client_as_admin, fake_registry
):
    template = client_as_admin.post(
        "/api/selection/freight-templates",
        json=_freight_payload(currency="USD", per_kg_rate="15"),
    ).json()
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    project = _create_project(client_as_admin)
    url = f"/api/selection/projects/{project['id']}/pricing"

    response = client_as_admin.put(
        url,
        json=_pricing_payload(template["id"], source_currency="CNY"),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "运费模板币种必须与商品源币种一致"
    assert fake_registry.calls == []
    assert client_as_admin.get(url).status_code == 404


def test_exchange_refresh_and_pricing_fail_without_real_rate(
    app, client_as_user, fake_registry
):
    fake_registry.results = [mcp_result(
        status="failed", capability=McpCapability.EXCHANGE_RATE, warnings=["调用失败"]
    )]
    refresh = client_as_user.post(
        "/api/selection/exchange-rates/refresh",
        json={"base_currency": "CNY", "quote_currency": "USD"},
    )
    assert refresh.status_code == 502


@pytest.fixture
def fake_registry(app):
    from app.routes.selection import get_mcp_registry

    registry = FakeRegistry()
    app.dependency_overrides[get_mcp_registry] = lambda: registry
    try:
        yield registry
    finally:
        app.dependency_overrides.pop(get_mcp_registry, None)
