# Тестирование этапа apply

## Роли и последовательность

Единственный автор всех тестов, фикстур, тестовых вспомогательных функций, настроек и full-gate — `/root/tester`. Код приложения пишет только `/root/implementation`. Оркестратор решает, когда задача выполнена; verify и archive назначаются отдельно. Тестировщик не писал код приложения, не выполнял verify/archive, не отмечал задачи и не делал коммиты.

1. До написания тестов прочитаны proposal, design, tasks и все четыре спецификации.
2. После согласования money/tag API добавлены 6 unit-тестов при остановленной перед БД реализации. Допустимые/недопустимые ASCII-формы, минимум, 4096 цифр, ведущие нули, точность выше int64, отображение, нормализация и пустые имена: 6/6 успешно. Только после подтверждения оркестратора начат DB-блок.
3. До готовности Store написаны 7 интеграционных тестов на реальной временной SQLite. После появления Store: 7/7 успешно. Проверены FK/UNIQUE/каскад напрямую, канонический TEXT и большие суммы, повторное открытие, изоляция владельцев, теги/история/архив, реальная ошибка записи связей через SQLite trigger и откат создания/редактирования, московские границы и фильтры. Предупреждение ruff по приложению направлено автору кода, тестировщик его код не менял.
4. Перед MVP написаны 7 unit-тестов Draft: дата/идентификатор, навигация с сохранением значений, неверная сумма без смены состояния, пропуск необязательных данных, комментарий и правила архивных тегов. 13/13 unit и ruff успешно; после этого оркестратор разрешил MVP.
5. Добавлены 3 unit-теста конфигурации и обеих команд запуска. Первоначальные ошибки отсутствующих entry point были переданы автору кода; после реализации все 16 unit успешно.
6. После MVP добавлены проверки bot ↔ db и e2e: реальные входящие updates, Dispatcher, MemoryStorage/FSM и временная SQLite. Подменяется только `BaseSession` внешнего Telegram API. Внутренние модули не подменяются. Проверены доход/расход, теги, комментарии, навигация/дата, просмотр/изменение/удаление, чужие ID, архивирование между выбором и сохранением, ошибки реальной записи и повторные/старые кнопки.
7. Параллельные пять завершений создания дают одну запись; параллельные пять завершений редактирования дают один UPDATE, измеренный реальным SQLite trigger. Реальный токен и пользовательская база не используются.
8. Два дефекта, найденных оркестратором, получили отдельные регрессии: старая отмена ввода имени тега не сбрасывает новый ввод операции; ошибка INSERT users откатывается и показывается пользователю. Оба теста успешно проходят после исправлений автора кода. Тесты не ослаблялись; Change Request на изменение неверного теста не потребовался.

Команды последовательных проверок: `.venv/bin/python -m unittest discover -s tests/unit -v`, `.venv/bin/python -m unittest discover -s tests/integration -v`, `.venv/bin/python -m unittest tests.e2e.test_finance_bot -v`.

## Воспроизводимый full-gate

Из корня репозитория:

```sh
uv sync --locked --dev
.venv/bin/python -m tests.full_gate
```

Требуются Python >=3.13 и OpenSpec CLI в PATH. Ruff 0.17.0 зафиксирован в uv.lock; проверки ruff заданы явно в pyproject.toml. Используется стандартный unittest.

Gate последовательно выполняет `openspec validate add-telegram-finance-tracker --strict`, `python -m compileall -q src tests`, `python -m ruff check src tests`, все unit/integration/e2e. Пустой уровень, ошибка, skip/xfail, дубли идентификаторов и объявленный, но необнаруженный test-метод блокируют успех. Все 35 сценариев функциональных спецификаций сверяются с tests/scenarios.py и фактически обнаруженными успешными тестами. Правила процесса и ручная приёмка подтверждаются отдельным отчётом verify.

Последний полный прогон apply: **PASS, 40 тестов: 16 unit, 11 integration, 13 e2e, 0 пропусков, 0 ожидаемых падений; 35/35 сценариев**. Строгая валидация, синтаксис и статический анализ успешно завершены. Это результат apply; отдельный verify ещё должен самостоятельно выполнить gate.

## Чистая установка

Во временный каталог `fin-tracker-clean-szx45qa7` скопированы только pyproject.toml, uv.lock, README.md и src без кэша. Выполнена команда `uv sync --locked --dev --project <временный каталог>`: успешно установлены 21 пакет в новую .venv, Python 3.13.7. Затем обе команды `.venv/bin/python -m fin_tracker` и `.venv/bin/fin-tracker` без BOT_TOKEN завершились кодом 1 с понятным сообщением BOT_TOKEN, без traceback. Реальный polling с токеном проверит пользователь при обязательной приёмке.

## Соответствие сценариев автоматическим тестам

Идентификаторы ниже совпадают с unittest discovery; единая команда проверяет полноту таблицы программно по tests/scenarios.py.

| Спецификация / сценарий | Автоматические тесты |
|---|---|
| `transaction-management` / Операция без необязательных полей | `tests.e2e.test_finance_bot.FinanceBotTests.test_income_multiple_tags_comment_and_expense_optional_skip` |
| `transaction-management` / Несколько тегов | `tests.e2e.test_finance_bot.FinanceBotTests.test_income_multiple_tags_comment_and_expense_optional_skip` |
| `transaction-management` / Допустимые формы | `tests.unit.test_money_tags.MoneyTests.test_valid_forms_and_minimum` |
| `transaction-management` / Недопустимая сумма | `tests.unit.test_money_tags.MoneyTests.test_rejects_invalid_forms_without_rounding`<br>`tests.e2e.test_finance_bot.FinanceBotTests.test_invalid_amounts_retry_and_large_amount_exact` |
| `transaction-management` / Большая сумма | `tests.unit.test_money_tags.MoneyTests.test_exact_large_amount_up_to_telegram_message_size`<br>`tests.e2e.test_finance_bot.FinanceBotTests.test_invalid_amounts_retry_and_large_amount_exact` |
| `transaction-management` / Ввод через полночь | `tests.e2e.test_finance_bot.FinanceBotTests.test_navigation_date_midnight_cancel_and_new_start` |
| `transaction-management` / Возврат | `tests.e2e.test_finance_bot.FinanceBotTests.test_navigation_date_midnight_cancel_and_new_start` |
| `transaction-management` / Отмена или перезапуск | `tests.e2e.test_finance_bot.FinanceBotTests.test_navigation_date_midnight_cancel_and_new_start`<br>`tests.e2e.test_finance_bot.FinanceBotTests.test_stale_buttons_completed_cancelled_restart_and_wrong_stage` |
| `transaction-management` / Продолжение без необязательных данных | `tests.e2e.test_finance_bot.FinanceBotTests.test_income_multiple_tags_comment_and_expense_optional_skip` |
| `transaction-management` / Сохранение комментария без изменений | `tests.e2e.test_finance_bot.FinanceBotTests.test_comment_preserve_replace_clear_cancel_and_create_clear` |
| `transaction-management` / Замена комментария | `tests.e2e.test_finance_bot.FinanceBotTests.test_comment_preserve_replace_clear_cancel_and_create_clear` |
| `transaction-management` / Очистка при редактировании | `tests.e2e.test_finance_bot.FinanceBotTests.test_comment_preserve_replace_clear_cancel_and_create_clear` |
| `transaction-management` / Отмена очистки | `tests.e2e.test_finance_bot.FinanceBotTests.test_comment_preserve_replace_clear_cancel_and_create_clear` |
| `transaction-management` / Очистка при создании | `tests.e2e.test_finance_bot.FinanceBotTests.test_comment_preserve_replace_clear_cancel_and_create_clear` |
| `transaction-management` / Повторное завершение | `tests.e2e.test_finance_bot.FinanceBotTests.test_concurrent_finish_creates_once_and_edits_once` |
| `transaction-management` / Старая кнопка | `tests.e2e.test_finance_bot.FinanceBotTests.test_stale_buttons_completed_cancelled_restart_and_wrong_stage` |
| `transaction-management` / Новый ввод вместо незавершённого | `tests.e2e.test_finance_bot.FinanceBotTests.test_navigation_date_midnight_cancel_and_new_start` |
| `transaction-management` / Изменение и отмена | `tests.e2e.test_finance_bot.FinanceBotTests.test_edit_cancel_complete_and_delete_preserves_tags` |
| `transaction-management` / Завершение изменения | `tests.e2e.test_finance_bot.FinanceBotTests.test_edit_cancel_complete_and_delete_preserves_tags` |
| `transaction-management` / Удаление | `tests.e2e.test_finance_bot.FinanceBotTests.test_edit_cancel_complete_and_delete_preserves_tags` |
| `tag-management` / Повтор активного названия | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_interface_conflicts_rename_archive_restore_history` |
| `tag-management` / Независимые пользователи | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_blank_rejected_and_names_independent_per_user` |
| `tag-management` / Архивирование | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_interface_conflicts_rename_archive_restore_history`<br>`tests.integration.test_storage.StorageTests.test_tag_lifecycle_conflicts_and_history` |
| `tag-management` / Восстановление | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_interface_conflicts_rename_archive_restore_history` |
| `tag-management` / Исторические операции | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_interface_conflicts_rename_archive_restore_history` |
| `tag-management` / Конфликт | `tests.e2e.test_finance_bot.FinanceBotTests.test_tag_interface_conflicts_rename_archive_restore_history`<br>`tests.integration.test_storage.StorageTests.test_tag_lifecycle_conflicts_and_history` |
| `tag-management` / Снятие архивного тега | `tests.e2e.test_finance_bot.FinanceBotTests.test_archived_tag_edit_keep_remove_warning_and_forbid_new` |
| `tag-management` / Изменение другого поля | `tests.e2e.test_finance_bot.FinanceBotTests.test_archived_tag_edit_keep_remove_warning_and_forbid_new` |
| `user-data-storage` / Повторное обращение | `tests.integration.test_storage.StorageTests.test_reopen_preserves_user_and_exact_transaction`<br>`tests.e2e.test_finance_bot.FinanceBotTests.test_stale_buttons_completed_cancelled_restart_and_wrong_stage` |
| `user-data-storage` / Чужой идентификатор | `tests.e2e.test_finance_bot.FinanceBotTests.test_forged_foreign_ids_never_read_modify_delete_or_assign`<br>`tests.integration.test_storage.StorageTests.test_all_owner_boundaries` |
| `user-data-storage` / Перезапуск | `tests.integration.test_storage.StorageTests.test_reopen_preserves_user_and_exact_transaction`<br>`tests.e2e.test_finance_bot.FinanceBotTests.test_stale_buttons_completed_cancelled_restart_and_wrong_stage` |
| `user-data-storage` / Ошибка записи связей | `tests.integration.test_bot_storage.BotStorageTests.test_actual_sqlite_error_no_partial_data_or_success_and_retry`<br>`tests.integration.test_storage.StorageTests.test_real_link_failure_rolls_back_create_and_update` |
| `user-data-storage` / Несколько совпавших тегов | `tests.integration.test_storage.StorageTests.test_moscow_day_half_open_filters_and_any_tag_without_duplicates` |
| `user-data-storage` / Границы периода | `tests.integration.test_storage.StorageTests.test_moscow_day_half_open_filters_and_any_tag_without_duplicates` |
| `user-data-storage` / Архивный тег | `tests.integration.test_storage.StorageTests.test_moscow_day_half_open_filters_and_any_tag_without_duplicates` |

Ручная приёмка: **ожидается**. Тестировщик не подтверждает её от имени пользователя; archive до явного подтверждения запрещён.
