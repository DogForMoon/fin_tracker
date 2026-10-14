"""Правила черновика; запись в БД выполняется только после завершения."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from fin_tracker.db import TagData, TransactionData, utc
from fin_tracker.money import parse_amount

STAGES = ("type", "amount", "tags", "comment")


@dataclass
class Draft:
    kind: str
    occurred_at: datetime
    token: str = field(default_factory=lambda: uuid4().hex[:12])
    stage: str = "amount"
    amount_kopecks: int | None = None
    tag_ids: list[str] = field(default_factory=list)
    comment: str | None = None
    transaction_id: str | None = None
    retained_tag_ids: list[str] = field(default_factory=list)

    @classmethod
    def new(cls, kind: str, occurred_at: datetime) -> "Draft":
        draft = cls(kind=kind, occurred_at=utc(occurred_at))
        draft.set_kind(kind)
        return draft

    @classmethod
    def edit(cls, transaction: TransactionData) -> "Draft":
        return cls(kind=transaction.kind, occurred_at=transaction.occurred_at,
                   stage="type", amount_kopecks=transaction.amount_kopecks,
                   tag_ids=[tag.id for tag in transaction.tags], comment=transaction.comment,
                   transaction_id=transaction.id,
                   retained_tag_ids=[tag.id for tag in transaction.tags])

    def matches(self, token: str, stage: str) -> bool:
        return self.token == token and self.stage == stage

    def set_kind(self, kind: str) -> None:
        if kind not in ("income", "expense"):
            raise ValueError("Неизвестный тип операции.")
        self.kind = kind

    def set_amount(self, text: str) -> None:
        self.amount_kopecks = parse_amount(text)

    def set_comment(self, text: str) -> None:
        self.comment = text

    def clear_comment(self) -> None:
        self.comment = None

    def back(self) -> str:
        self.stage = STAGES[max(0, STAGES.index(self.stage) - 1)]
        return self.stage

    def next(self) -> str:
        if self.stage == "amount" and self.amount_kopecks is None:
            raise ValueError("Сначала введите сумму.")
        index = STAGES.index(self.stage)
        if index == len(STAGES) - 1:
            return "save"
        self.stage = STAGES[index + 1]
        return self.stage

    def toggle_tag(self, tag: TagData) -> bool:
        if tag.id in self.tag_ids:
            self.tag_ids.remove(tag.id)
            if tag.id in self.retained_tag_ids:
                self.retained_tag_ids.remove(tag.id)
            return tag.is_archived
        if tag.is_archived:
            raise ValueError("Сначала восстановите тег через создание с тем же названием.")
        self.tag_ids.append(tag.id)
        return False
