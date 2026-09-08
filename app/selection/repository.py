from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    ExchangeRate,
    FreightTemplate,
    KeywordResearchRun,
    PricingSnapshot,
    ResearchKeyword,
    SelectionProject,
)


class SelectionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_owned_project(self, project_id: int, user_id: str) -> SelectionProject:
        project = self.session.scalar(
            select(SelectionProject).where(
                SelectionProject.id == project_id,
                SelectionProject.user_id == user_id,
            )
        )
        if project is None:
            raise LookupError("选品项目不存在")
        return project

    def create_project(
        self,
        user_id: str,
        name: str,
        marketplace: str,
        target_currency: str,
    ) -> SelectionProject:
        project = SelectionProject(
            user_id=user_id,
            name=name,
            marketplace=marketplace,
            target_currency=target_currency,
        )
        self.session.add(project)
        self.session.flush()
        self.session.commit()
        return project

    def list_projects(self, user_id: str) -> list[SelectionProject]:
        return list(
            self.session.scalars(
                select(SelectionProject)
                .where(SelectionProject.user_id == user_id)
                .order_by(SelectionProject.updated_at.desc(), SelectionProject.id.desc())
            )
        )

    def list_freight_templates(self) -> list[FreightTemplate]:
        return list(
            self.session.scalars(
                select(FreightTemplate).order_by(FreightTemplate.id)
            )
        )

    def get_freight_template(self, template_id: int) -> FreightTemplate:
        template = self.session.get(FreightTemplate, template_id)
        if template is None:
            raise LookupError("运费模板不存在")
        return template

    def save_exchange_rate(self, **values: object) -> ExchangeRate:
        rate = ExchangeRate(**values)
        self.session.add(rate)
        self.session.flush()
        self.session.commit()
        return rate

    def save_pricing_snapshot(self, **values: object) -> PricingSnapshot:
        snapshot = PricingSnapshot(**values)
        self.session.add(snapshot)
        self.session.flush()
        self.session.commit()
        return snapshot

    def latest_pricing_snapshot(self, project_id: int, user_id: str) -> PricingSnapshot:
        self.get_owned_project(project_id, user_id)
        snapshot = self.session.scalar(
            select(PricingSnapshot)
            .where(PricingSnapshot.project_id == project_id)
            .order_by(PricingSnapshot.calculated_at.desc(), PricingSnapshot.id.desc())
        )
        if snapshot is None:
            raise LookupError("定价快照不存在")
        return snapshot

    def create_keyword_run(
        self,
        project_id: int,
        user_id: str,
        input_type: str,
        input_value: str,
        marketplace: str,
        category: str | None,
        filters: Mapping[str, object] | None = None,
    ) -> KeywordResearchRun:
        self.get_owned_project(project_id, user_id)
        run = KeywordResearchRun(
            project_id=project_id,
            input_type=input_type,
            input_value=input_value,
            marketplace=marketplace,
            category=category,
            filters_json=dict(filters or {}),
        )
        self.session.add(run)
        self.session.flush()
        self.session.commit()
        return run

    def replace_keyword_results(
        self,
        run_id: int,
        user_id: str,
        results: Sequence[Mapping[str, object]],
    ) -> list[ResearchKeyword]:
        run = self._get_owned_run(run_id, user_id)
        self.session.execute(delete(ResearchKeyword).where(ResearchKeyword.run_id == run_id))
        self.session.flush()

        rows = [
            ResearchKeyword(project_id=run.project_id, run_id=run_id, **dict(result))
            for result in results
        ]
        self.session.add_all(rows)
        self.session.flush()
        self.session.commit()
        return rows

    def replace_selected_keywords(
        self,
        project_id: int,
        user_id: str,
        keyword_ids: list[int],
    ) -> list[ResearchKeyword]:
        self.get_owned_project(project_id, user_id)
        unique_ids = list(dict.fromkeys(keyword_ids))
        if unique_ids:
            owned_ids = set(
                self.session.scalars(
                    select(ResearchKeyword.id).where(
                        ResearchKeyword.project_id == project_id,
                        ResearchKeyword.id.in_(unique_ids),
                    )
                )
            )
            if owned_ids != set(unique_ids):
                raise LookupError("选品项目不存在")

        self.session.execute(
            update(ResearchKeyword)
            .where(ResearchKeyword.project_id == project_id)
            .values(selected=False)
        )
        if unique_ids:
            self.session.execute(
                update(ResearchKeyword)
                .where(
                    ResearchKeyword.project_id == project_id,
                    ResearchKeyword.id.in_(unique_ids),
                )
                .values(selected=True)
            )
        self.session.flush()
        selected = list(
            self.session.scalars(
                select(ResearchKeyword)
                .where(
                    ResearchKeyword.project_id == project_id,
                    ResearchKeyword.selected.is_(True),
                )
                .order_by(ResearchKeyword.id)
            )
        )
        self.session.commit()
        return selected

    def _get_owned_run(self, run_id: int, user_id: str) -> KeywordResearchRun:
        run = self.session.scalar(
            select(KeywordResearchRun)
            .join(SelectionProject, SelectionProject.id == KeywordResearchRun.project_id)
            .where(
                KeywordResearchRun.id == run_id,
                SelectionProject.user_id == user_id,
            )
        )
        if run is None:
            raise LookupError("选品项目不存在")
        return run
