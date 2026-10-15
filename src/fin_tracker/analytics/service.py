"""Аналитика: независимый слой поверх данных.

Напрямую с таблицами и SQL не работает: берёт транзакции у командного
Store (fin_tracker.db), агрегирует в pandas, рисует в matplotlib/seaborn.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # рисуем в файл, без окон
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from fin_tracker.db import Store, TransactionData
from fin_tracker.money import format_amount

NO_TAG = "без тега"


class AnalyticsError(Exception):
    """Нечего считать: за период нет расходов."""


class AnalyticsService:
    """Читает транзакции из Store и превращает их в цифры и графики."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def _expenses(self, user_id: str, start=None, end=None) -> list[TransactionData]:
        rows = self._store.list_transactions(user_id, start=start, end=end, kind="expense")
        if not rows:
            raise AnalyticsError("За запрошенный период расходов нет.")
        return rows

    # ---- цифры ----
    def spend_by_tag(self, user_id: str, start=None, end=None) -> dict[str, int]:
        """Словарь {тег: копейки}. Транзакция с двумя тегами попадает в оба."""
        totals: dict[str, int] = {}
        for tx in self._expenses(user_id, start, end):
            names = [tag.name for tag in tx.tags] or [NO_TAG]
            for name in names:
                totals[name] = totals.get(name, 0) + tx.amount_kopecks
        return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))

    def weekly_totals(self, user_id: str, start=None, end=None) -> pd.DataFrame:
        """Динамика расходов по неделям."""
        rows = self._expenses(user_id, start, end)
        df = pd.DataFrame({
            "date": [tx.occurred_at for tx in rows],
            "kopecks": [tx.amount_kopecks for tx in rows],
        })
        weekly = df.resample("W", on="date")["kopecks"].sum().reset_index()
        weekly["rubles"] = weekly["kopecks"] / 100
        return weekly

    def top_tags(self, user_id: str, n: int = 3, start=None, end=None) -> list[tuple[str, int]]:
        """Топ-n тегов по сумме."""
        return list(self.spend_by_tag(user_id, start, end).items())[:n]

    # ---- графики ----
    def _spend_frame(self, user_id, start, end) -> pd.DataFrame:
        df = pd.DataFrame(self.spend_by_tag(user_id, start, end).items(),
                          columns=["tag", "kopecks"])
        df["rubles"] = df["kopecks"] / 100
        return df

    def save_pie(self, user_id: str, path: Path | str, start=None, end=None) -> Path:
        df = self._spend_frame(user_id, start, end)
        fig, ax = plt.subplots()
        ax.pie(df["rubles"], labels=df["tag"], autopct="%1.0f%%")
        ax.set_title("Куда ушли деньги (по тегам)")
        fig.savefig(Path(path), bbox_inches="tight")
        plt.close(fig)
        return Path(path)

    def save_top_bar(self, user_id: str, path: Path | str, n: int = 5,
                     start=None, end=None) -> Path:
        df = self._spend_frame(user_id, start, end).head(n)
        fig, ax = plt.subplots()
        sns.barplot(data=df, x="tag", y="rubles", hue="tag", palette="viridis", legend=False, ax=ax)
        ax.set_title("Топ тегов по тратам")
        fig.savefig(Path(path), bbox_inches="tight")
        plt.close(fig)
        return Path(path)

    def save_weekly_line(self, user_id: str, path: Path | str,
                         start=None, end=None) -> Path:
        weekly = self.weekly_totals(user_id, start, end)
        fig, ax = plt.subplots()
        ax.plot(weekly["date"], weekly["rubles"], marker="o", color="#e67e22")
        ax.set_title("Расходы по неделям")
        ax.tick_params(axis="x", labelrotation=30)
        fig.savefig(Path(path), bbox_inches="tight")
        plt.close(fig)
        return Path(path)