"""Короткие атомарные операции SQLite; наружу возвращаются простые данные."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from fin_tracker.tags import normalize_tag_name

MOSCOW = ZoneInfo("Europe/Moscow")


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    telegram_id: Mapped[int] = mapped_column(unique=True)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "normalized_name"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]
    normalized_name: Mapped[str]
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("kind IN ('income', 'expense')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str]
    amount_kopecks: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    comment: Mapped[str | None]


class TransactionTag(Base):
    __tablename__ = "transaction_tags"
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)


@dataclass(frozen=True)
class UserData:
    id: str
    telegram_id: int


@dataclass(frozen=True)
class TagData:
    id: str
    user_id: str
    name: str
    is_archived: bool


@dataclass(frozen=True)
class TransactionData:
    id: str
    user_id: str
    kind: str
    amount_kopecks: int
    occurred_at: datetime
    comment: str | None
    tags: tuple[TagData, ...]


def utc(value: date | datetime) -> datetime:
    """Календарные даты и naive datetime интерпретируются в Москве."""
    if not isinstance(value, datetime):
        value = datetime.combine(value, time.min, MOSCOW)
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW)
    return value.astimezone(UTC)


def tag_data(tag: Tag) -> TagData:
    return TagData(tag.id, tag.user_id, tag.name, tag.is_archived)


class Store:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False}
        )

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.initialize()

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    @staticmethod
    def _owned(session, model, user_id: str, entity_id: str):
        row = session.scalar(select(model).where(model.id == entity_id, model.user_id == user_id))
        if row is None:
            raise LookupError("Запись не найдена.")
        return row

    def ensure_user(self, telegram_id: int) -> UserData:
        with self.session_factory.begin() as session:
            user = session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id)
                session.add(user)
                session.flush()
            return UserData(user.id, user.telegram_id)

    def create_tag(self, user_id: str, name: str) -> tuple[TagData, bool]:
        normalized = normalize_tag_name(name)
        with self.session_factory.begin() as session:
            tag = session.scalar(select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized))
            restored = tag is not None
            if tag is not None:
                if not tag.is_archived:
                    raise ValueError("Тег с таким названием уже существует.")
                tag.is_archived = False
            else:
                tag = Tag(user_id=user_id, name=name.strip(), normalized_name=normalized)
                session.add(tag)
            session.flush()
            return tag_data(tag), restored

    def get_tag(self, user_id: str, tag_id: str) -> TagData:
        with self.session_factory() as session:
            return tag_data(self._owned(session, Tag, user_id, tag_id))

    def list_tags(self, user_id: str, include_archived: bool = False) -> list[TagData]:
        query = select(Tag).where(Tag.user_id == user_id)
        if not include_archived:
            query = query.where(Tag.is_archived.is_(False))
        with self.session_factory() as session:
            return [tag_data(tag) for tag in session.scalars(query.order_by(Tag.name, Tag.id))]

    def rename_tag(self, user_id: str, tag_id: str, name: str) -> TagData:
        normalized = normalize_tag_name(name)
        with self.session_factory.begin() as session:
            tag = self._owned(session, Tag, user_id, tag_id)
            conflict = session.scalar(select(Tag.id).where(
                Tag.user_id == user_id, Tag.normalized_name == normalized, Tag.id != tag_id
            ))
            if conflict is not None:
                raise ValueError("Тег с таким названием уже существует, возможно в архиве.")
            tag.name, tag.normalized_name = name.strip(), normalized
            return tag_data(tag)

    def archive_tag(self, user_id: str, tag_id: str) -> TagData:
        with self.session_factory.begin() as session:
            tag = self._owned(session, Tag, user_id, tag_id)
            tag.is_archived = True
            return tag_data(tag)

    @staticmethod
    def _amount(kind: str, amount_kopecks: int) -> None:
        if kind not in ("income", "expense"):
            raise ValueError("Неизвестный тип операции.")
        if type(amount_kopecks) is not int or amount_kopecks < 1:
            raise ValueError("Сумма должна быть положительным целым количеством копеек.")

    def _replace_tags(self, session, row: Transaction, tag_ids, allowed_archived=()):
        tags = [self._owned(session, Tag, row.user_id, tag_id) for tag_id in set(tag_ids)]
        for tag in tags:
            if tag.is_archived and tag.id not in allowed_archived:
                raise ValueError("Архивный тег нельзя назначить. Сначала восстановите его.")
        session.execute(delete(TransactionTag).where(TransactionTag.transaction_id == row.id))
        session.add_all(TransactionTag(transaction_id=row.id, tag_id=tag.id) for tag in tags)
        session.flush()

    @staticmethod
    def _transaction_data(session, row: Transaction) -> TransactionData:
        tags = session.scalars(select(Tag).join(TransactionTag, TransactionTag.tag_id == Tag.id)
                               .where(TransactionTag.transaction_id == row.id).order_by(Tag.name, Tag.id))
        return TransactionData(row.id, row.user_id, row.kind, int(row.amount_kopecks),
                               row.occurred_at.replace(tzinfo=UTC), row.comment,
                               tuple(tag_data(tag) for tag in tags))

    def create_transaction(self, user_id: str, kind: str, amount_kopecks: int,
                           occurred_at: datetime, tag_ids=(), comment: str | None = None) -> TransactionData:
        self._amount(kind, amount_kopecks)
        with self.session_factory.begin() as session:
            row = Transaction(user_id=user_id, kind=kind, amount_kopecks=str(amount_kopecks),
                              occurred_at=utc(occurred_at).replace(tzinfo=None), comment=comment)
            session.add(row)
            session.flush()
            self._replace_tags(session, row, tag_ids)
            return self._transaction_data(session, row)

    def update_transaction(self, user_id: str, transaction_id: str, kind: str,
                           amount_kopecks: int, tag_ids=(), comment: str | None = None,
                           retained_archived_tag_ids=None) -> TransactionData:
        self._amount(kind, amount_kopecks)
        with self.session_factory.begin() as session:
            row = self._owned(session, Transaction, user_id, transaction_id)
            original = set(session.scalars(select(TransactionTag.tag_id).where(
                TransactionTag.transaction_id == row.id)))
            allowed = original if retained_archived_tag_ids is None else original.intersection(retained_archived_tag_ids)
            row.kind, row.amount_kopecks, row.comment = kind, str(amount_kopecks), comment
            self._replace_tags(session, row, tag_ids, allowed)
            return self._transaction_data(session, row)

    def get_transaction(self, user_id: str, transaction_id: str) -> TransactionData:
        with self.session_factory() as session:
            return self._transaction_data(session, self._owned(session, Transaction, user_id, transaction_id))

    def delete_transaction(self, user_id: str, transaction_id: str) -> None:
        with self.session_factory.begin() as session:
            session.delete(self._owned(session, Transaction, user_id, transaction_id))

    def list_transactions(self, user_id: str, start: date | datetime | None = None,
                          end: date | datetime | None = None, kind: str | None = None,
                          tag_ids=()) -> list[TransactionData]:
        query = select(Transaction).where(Transaction.user_id == user_id)
        if start is not None:
            query = query.where(Transaction.occurred_at >= utc(start).replace(tzinfo=None))
        if end is not None:
            query = query.where(Transaction.occurred_at < utc(end).replace(tzinfo=None))
        if kind is not None:
            query = query.where(Transaction.kind == kind)
        with self.session_factory() as session:
            if tag_ids:
                query = query.where(select(TransactionTag.transaction_id).join(
                    Tag, Tag.id == TransactionTag.tag_id).where(
                    TransactionTag.transaction_id == Transaction.id,
                    Tag.user_id == user_id,
                    TransactionTag.tag_id.in_(tag_ids)).exists())
            return [self._transaction_data(session, row) for row in
                    session.scalars(query.order_by(Transaction.occurred_at.desc(), Transaction.id))]
