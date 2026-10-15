"""Explicit specification scenario to runnable test IDs; checked by full_gate."""

E2E = "tests.e2e.test_finance_bot.FinanceBotTests."
STORAGE = "tests.integration.test_storage.StorageTests."
BOT_DB = "tests.integration.test_bot_storage.BotStorageTests."
MONEY = "tests.unit.test_money_tags.MoneyTests."

SCENARIOS = {
    "transaction-management": {
        "Операция без необязательных полей": [E2E + "test_income_multiple_tags_comment_and_expense_optional_skip"],
        "Несколько тегов": [E2E + "test_income_multiple_tags_comment_and_expense_optional_skip"],
        "Допустимые формы": [MONEY + "test_valid_forms_and_minimum"],
        "Недопустимая сумма": [MONEY + "test_rejects_invalid_forms_without_rounding", E2E + "test_invalid_amounts_retry_and_large_amount_exact"],
        "Большая сумма": [MONEY + "test_exact_large_amount_up_to_telegram_message_size", E2E + "test_invalid_amounts_retry_and_large_amount_exact"],
        "Ввод через полночь": [E2E + "test_navigation_date_midnight_cancel_and_new_start"],
        "Возврат": [E2E + "test_navigation_date_midnight_cancel_and_new_start"],
        "Отмена или перезапуск": [E2E + "test_navigation_date_midnight_cancel_and_new_start", E2E + "test_stale_buttons_completed_cancelled_restart_and_wrong_stage"],
        "Продолжение без необязательных данных": [E2E + "test_income_multiple_tags_comment_and_expense_optional_skip"],
        "Сохранение комментария без изменений": [E2E + "test_comment_preserve_replace_clear_cancel_and_create_clear"],
        "Замена комментария": [E2E + "test_comment_preserve_replace_clear_cancel_and_create_clear"],
        "Очистка при редактировании": [E2E + "test_comment_preserve_replace_clear_cancel_and_create_clear"],
        "Отмена очистки": [E2E + "test_comment_preserve_replace_clear_cancel_and_create_clear"],
        "Очистка при создании": [E2E + "test_comment_preserve_replace_clear_cancel_and_create_clear"],
        "Повторное завершение": [E2E + "test_concurrent_finish_creates_once_and_edits_once"],
        "Старая кнопка": [E2E + "test_stale_buttons_completed_cancelled_restart_and_wrong_stage"],
        "Новый ввод вместо незавершённого": [E2E + "test_navigation_date_midnight_cancel_and_new_start"],
        "Изменение и отмена": [E2E + "test_edit_cancel_complete_and_delete_preserves_tags"],
        "Завершение изменения": [E2E + "test_edit_cancel_complete_and_delete_preserves_tags"],
        "Удаление": [E2E + "test_edit_cancel_complete_and_delete_preserves_tags"],
    },
    "tag-management": {
        "Повтор активного названия": [E2E + "test_tag_interface_conflicts_rename_archive_restore_history"],
        "Независимые пользователи": [E2E + "test_tag_blank_rejected_and_names_independent_per_user"],
        "Архивирование": [E2E + "test_tag_interface_conflicts_rename_archive_restore_history", STORAGE + "test_tag_lifecycle_conflicts_and_history"],
        "Восстановление": [E2E + "test_tag_interface_conflicts_rename_archive_restore_history"],
        "Исторические операции": [E2E + "test_tag_interface_conflicts_rename_archive_restore_history"],
        "Конфликт": [E2E + "test_tag_interface_conflicts_rename_archive_restore_history", STORAGE + "test_tag_lifecycle_conflicts_and_history"],
        "Снятие архивного тега": [E2E + "test_archived_tag_edit_keep_remove_warning_and_forbid_new"],
        "Изменение другого поля": [E2E + "test_archived_tag_edit_keep_remove_warning_and_forbid_new"],
    },
    "user-data-storage": {
        "Повторное обращение": [STORAGE + "test_reopen_preserves_user_and_exact_transaction", E2E + "test_stale_buttons_completed_cancelled_restart_and_wrong_stage"],
        "Чужой идентификатор": [E2E + "test_forged_foreign_ids_never_read_modify_delete_or_assign", STORAGE + "test_all_owner_boundaries"],
        "Перезапуск": [STORAGE + "test_reopen_preserves_user_and_exact_transaction", E2E + "test_stale_buttons_completed_cancelled_restart_and_wrong_stage"],
        "Ошибка записи связей": [BOT_DB + "test_actual_sqlite_error_no_partial_data_or_success_and_retry", STORAGE + "test_real_link_failure_rolls_back_create_and_update"],
        "Несколько совпавших тегов": [STORAGE + "test_moscow_day_half_open_filters_and_any_tag_without_duplicates"],
        "Границы периода": [STORAGE + "test_moscow_day_half_open_filters_and_any_tag_without_duplicates"],
        "Архивный тег": [STORAGE + "test_moscow_day_half_open_filters_and_any_tag_without_duplicates"],
    },
}
