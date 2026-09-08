from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.selection.contracts import McpCallResult, McpCapability
from app.selection.keyword_service import _keyword_rows
from app.selection.repository import SelectionRepository


def test_project_and_selected_keywords_are_scoped_to_user(session):
    repo = SelectionRepository(session)
    project = repo.create_project("alice", "便携风扇", "US", "USD")
    run = repo.create_keyword_run(
        project.id,
        "alice",
        "seed",
        "portable fan",
        "US",
        "all",
    )
    rows = repo.replace_keyword_results(
        run.id,
        "alice",
        [
            {
                "keyword": "portable fan",
                "normalized_keyword": "portable fan",
                "search_volume": 42000,
            }
        ],
    )

    selected = repo.replace_selected_keywords(project.id, "alice", [rows[0].id])

    assert selected[0].selected is True
    assert repo.list_projects("bob") == []
    with pytest.raises(LookupError, match="^选品项目不存在$"):
        repo.create_keyword_run(project.id, "bob", "seed", "fan", "US", "all")


def test_foreign_keyword_cannot_be_selected(session):
    repo = SelectionRepository(session)
    alice_project = repo.create_project("alice", "便携风扇", "US", "USD")
    bob_project = repo.create_project("bob", "露营灯", "US", "USD")
    bob_run = repo.create_keyword_run(bob_project.id, "bob", "seed", "camp light", "US", None)
    bob_rows = repo.replace_keyword_results(
        bob_run.id,
        "bob",
        [{"keyword": "camp light", "normalized_keyword": "camp light"}],
    )

    with pytest.raises(LookupError, match="^选品项目不存在$"):
        repo.replace_selected_keywords(alice_project.id, "alice", [bob_rows[0].id])


def test_client_as_user_overrides_current_user(client_as_user):
    response = client_as_user.get("/__test__/current-user")

    assert response.status_code == 200
    assert response.json() == {"username": "alice", "role": "user"}


def test_client_as_admin_overrides_current_user(client_as_admin):
    response = client_as_admin.get("/__test__/current-user")

    assert response.status_code == 200
    assert response.json() == {"username": "admin", "role": "admin"}


def test_keyword_rows_keep_extended_mcp_metrics_in_metrics_json():
    result = McpCallResult(
        source_id="seller",
        source_name="卖家精灵",
        capability=McpCapability.KEYWORD_EXPAND,
        tool_name="keyword_research",
        collected_at=datetime.now(UTC),
        status="succeeded",
        records=[
            {
                "keyword": "dog bowls",
                "monthly_search_volume": 188462,
                "ppc_bid": "$0.98",
            }
        ],
        field_lineage=[{}],
        warnings=[],
        raw_data={},
    )

    row = _keyword_rows(1, 2, [result])[0]

    assert row.search_volume is None
    assert row.metrics_json["monthly_search_volume"] == 188462
    assert row.metrics_json["ppc_bid"] == "$0.98"
