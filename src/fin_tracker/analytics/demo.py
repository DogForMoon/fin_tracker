"""Демо аналитики без бота: сидим данные методами командного Store.

Запуск: uv run python -m fin_tracker.analytics.demo
"""
from datetime import date, timedelta
from pathlib import Path

from fin_tracker.analytics.service import AnalyticsError, AnalyticsService
from fin_tracker.db import Store
from fin_tracker.money import format_amount

DEMO_DB = Path("demo.db")

# СЛОВАРЬ: тег -> список покупок (копейки, дней назад, комментарий)
SEED: dict[str, list[tuple[int, int, str]]] = {
    "еда": [(45000, 1, "продукты"), (82000, 4, "продукты на неделю"),
            (51000, 12, "продукты"), (99000, 20, "продукты"), (61000, 27, "продукты")],
    "транспорт": [(30000, 1, "такси"), (25000, 14, "метро"), (70000, 25, "такси в аэропорт")],
    "здоровье": [(64000, 9, "аптека"), (45000, 22, "витамины")],
    "развлечения": [(120000, 6, "концерт"), (30000, 16, "кино")],
}
# покупка с двумя тегами: попадёт в обе категории
MULTI_TAG = [(("еда", "развлечения"), 150000, 3, "ужин в ресторане")]


def seed(store: Store) -> str:
    user = store.ensure_user(telegram_id=1)
    tag_ids: dict[str, str] = {}
    for name in SEED:
        tag, _restored = store.create_tag(user.id, name)
        tag_ids[name] = tag.id
    for name, purchases in SEED.items():
        for kopecks, days_ago, comment in purchases:
            store.create_transaction(
                user.id, "expense", kopecks,
                date.today() - timedelta(days=days_ago),
                tag_ids=[tag_ids[name]], comment=comment,
            )
    for names, kopecks, days_ago, comment in MULTI_TAG:
        store.create_transaction(
            user.id, "expense", kopecks,
            date.today() - timedelta(days=days_ago),
            tag_ids=[tag_ids[n] for n in names], comment=comment,
        )
    return user.id


def main() -> None:
    if DEMO_DB.exists():
        DEMO_DB.unlink()
    store = Store(DEMO_DB)
    try:
        user_id = seed(store)
        service = AnalyticsService(store)
        try:
            spend = service.spend_by_tag(user_id)
            print("По тегам:", {k: format_amount(v) for k, v in spend.items()})
            print("Топ-3:", [(k, format_amount(v)) for k, v in service.top_tags(user_id, 3)])
            print(service.weekly_totals(user_id).to_string(index=False))
            for path in (
                service.save_pie(user_id, "pie.png"),
                service.save_top_bar(user_id, "top.png"),
                service.save_weekly_line(user_id, "weekly.png"),
            ):
                print("График сохранён:", path)
        except AnalyticsError as exc:
            print("Аналитика не смогла посчитать:", exc)
        except (ValueError, OSError) as exc:
            print("Ошибка при построении графика:", exc)
    finally:
        store.close()


if __name__ == "__main__":
    main()