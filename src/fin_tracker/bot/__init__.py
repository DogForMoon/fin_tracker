"""Telegram-диспетчер с настоящими FSM и короткими вызовами хранилища."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from aiogram import Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.strategy import FSMStrategy
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.exc import SQLAlchemyError

from fin_tracker.bot.dialog import Draft
from fin_tracker.db import MOSCOW, Store, TransactionData
from fin_tracker.money import format_amount


def keyboard(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows
    ])


def menu():
    return keyboard([
        [("Получил", "new:income"), ("Потратил", "new:expense")],
        [("Операции", "transactions"), ("Теги", "tags")],
    ])


async def say(message: Message, text: str, reply_markup=None):
    # Длинные точные суммы и комментарии не должны превышать лимит Telegram.
    while len(text) > 4000:
        await message.answer(text[:4000])
        text = text[4000:]
    await message.answer(text, reply_markup=reply_markup)


def transaction_text(row: TransactionData) -> str:
    kind = "Доход" if row.kind == "income" else "Расход"
    tags = ", ".join(tag.name + (" (архив)" if tag.is_archived else "") for tag in row.tags) or "нет"
    return (f"{kind}: {format_amount(row.amount_kopecks)}\n"
            f"Дата: {row.occurred_at.astimezone(MOSCOW):%d.%m.%Y %H:%M} (Москва)\n"
            f"Теги: {tags}\nКомментарий: {row.comment if row.comment is not None else 'нет'}")


def create_dispatcher(store: Store) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation(),
                            fsm_strategy=FSMStrategy.GLOBAL_USER)
    router = Router()
    dispatcher.include_router(router)
    dispatcher["store"] = store

    async def db(method, *args, **kwargs):
        return await asyncio.to_thread(method, *args, **kwargs)

    async def owner(telegram_id):
        return (await db(store.ensure_user, telegram_id)).id

    async def render(message, draft, user_id):
        prefix = f"d:{draft.token}:{draft.stage}:"
        rows = []
        if draft.stage == "type":
            text = "Выберите тип операции."
            rows.append([("Получил", prefix + "income"), ("Потратил", prefix + "expense")])
        elif draft.stage == "amount":
            text = "Введите сумму в рублях, например 125,50."
            if draft.amount_kopecks is not None:
                text += "\nТекущая сумма: " + format_amount(draft.amount_kopecks)
        elif draft.stage == "tags":
            text = "Выберите теги или нажмите «Далее»."
            tags = await db(store.list_tags, user_id, include_archived=True)
            for tag in tags:
                if not tag.is_archived or tag.id in draft.tag_ids:
                    label = ("✓ " if tag.id in draft.tag_ids else "") + tag.name
                    if tag.is_archived:
                        label += " (архив)"
                    rows.append([(label, prefix + tag.id)])
        else:
            text = "Введите комментарий или нажмите «Далее» для сохранения."
            text += "\nКомментарий: " + (draft.comment if draft.comment is not None else "нет")
            rows.append([("Очистить комментарий", prefix + "clear")])
        rows.append([("Назад", prefix + "back"), ("Отменить", prefix + "cancel"),
                     ("Далее", prefix + "next")])
        await say(message, text, keyboard(rows))

    async def begin(message, state, user_id, kind, occurred_at):
        if await state.get_state() is not None:
            await say(message, "Предыдущий незавершённый ввод сброшен.")
        await state.clear()
        draft = Draft.new(kind, occurred_at)
        await state.set_state("dialog")
        await state.set_data({"draft": draft})
        await render(message, draft, user_id)

    async def show_transactions(message, user_id):
        rows = await db(store.list_transactions, user_id)
        if not rows:
            await say(message, "Операций пока нет.", menu())
        for row in rows:
            await say(message, transaction_text(row), keyboard([
                [("Редактировать", "edit:" + row.id), ("Удалить", "delete:" + row.id)],
                [("Главное меню", "menu")],
            ]))

    async def show_tags(message, state, user_id):
        await state.clear()
        token = uuid4().hex[:12]
        await state.set_state("tag_menu")
        await state.set_data({"tag_token": token})
        rows = [[("Создать тег", f"t:{token}:create")]]
        tags = await db(store.list_tags, user_id, include_archived=True)
        text = "Ваши теги. Удаление архивирует тег и сохраняет историю."
        if not tags:
            text += "\nТегов пока нет."
        for tag in tags:
            text += "\n" + tag.name + (" (архив)" if tag.is_archived else "")
            rows.append([("Переименовать: " + tag.name, f"t:{token}:rename:{tag.id}")])
            if not tag.is_archived:
                rows.append([("Архивировать: " + tag.name, f"t:{token}:archive:{tag.id}")])
        rows.append([("Главное меню", f"t:{token}:cancel")])
        await say(message, text, keyboard(rows))

    @router.message()
    async def on_message(message: Message, state: FSMContext):
        if message.from_user is None:
            return
        text = message.text or ""
        command = text.split("@", 1)[0]
        try:
            user_id = await owner(message.from_user.id)
            if command in ("/income", "/expense") or text in ("Получил", "Потратил"):
                kind = "income" if command == "/income" or text == "Получил" else "expense"
                await begin(message, state, user_id, kind, message.date)
                return
            if command in ("/start", "/cancel") or text == "Отменить":
                await state.clear()
                await say(message, "Ввод отменён. Главное меню.", menu())
                return
            data = await state.get_data()
            draft = data.get("draft")
            if draft is not None:
                if draft.stage == "amount":
                    draft.set_amount(text)
                    draft.next()
                elif draft.stage == "comment":
                    draft.set_comment(text)
                else:
                    await say(message, "Используйте кнопки текущего шага.")
                    return
                await state.update_data(draft=draft)
                await render(message, draft, user_id)
            elif await state.get_state() == "tag_name":
                if data.get("rename_id"):
                    await db(store.rename_tag, user_id, data["rename_id"], text)
                    result = "Тег переименован."
                else:
                    _, restored = await db(store.create_tag, user_id, text)
                    result = "Тег восстановлен из архива" if restored else "Тег создан."
                await say(message, result)
                await show_tags(message, state, user_id)
            else:
                await say(message, "Главное меню.", menu())
        except (ValueError, LookupError) as error:
            await say(message, str(error))
        except SQLAlchemyError:
            await say(message, "Ошибка записи. Данные не сохранены; попробуйте ещё раз или отмените ввод.")

    @router.callback_query(F.data)
    async def on_callback(query: CallbackQuery, state: FSMContext):
        if not isinstance(query.message, Message):
            await query.answer("Сообщение недоступно.")
            return
        message = query.message
        try:
            user_id = await owner(query.from_user.id)
            parts = query.data.split(":")
            action = parts[0]
            if action == "new" and len(parts) == 2:
                await begin(message, state, user_id, parts[1], datetime.now(UTC))
            elif action == "menu":
                await say(message, "Главное меню.", menu())
            elif action == "transactions":
                await show_transactions(message, user_id)
            elif action == "tags":
                await show_tags(message, state, user_id)
            elif action == "delete" and len(parts) == 2:
                await db(store.delete_transaction, user_id, parts[1])
                await say(message, "Операция удалена. Теги сохранены.", menu())
            elif action == "edit" and len(parts) == 2:
                row = await db(store.get_transaction, user_id, parts[1])
                if await state.get_state() is not None:
                    await say(message, "Предыдущий незавершённый ввод сброшен.")
                await state.clear()
                draft = Draft.edit(row)
                await state.set_state("dialog")
                await state.set_data({"draft": draft})
                await render(message, draft, user_id)
            elif action == "d" and len(parts) == 4:
                draft = (await state.get_data()).get("draft")
                if draft is None or not draft.matches(parts[1], parts[2]):
                    await query.answer("Эта кнопка устарела.")
                    return
                button = parts[3]
                if button == "cancel":
                    await state.clear()
                    await say(message, "Ввод отменён.", menu())
                elif button == "next":
                    if draft.next() == "save":
                        if draft.transaction_id is None:
                            await db(store.create_transaction, user_id, draft.kind,
                                     draft.amount_kopecks, draft.occurred_at,
                                     tag_ids=draft.tag_ids, comment=draft.comment)
                        else:
                            await db(store.update_transaction, user_id, draft.transaction_id,
                                     draft.kind, draft.amount_kopecks, tag_ids=draft.tag_ids,
                                     comment=draft.comment, retained_archived_tag_ids=draft.retained_tag_ids)
                        await state.clear()
                        await say(message, "Операция сохранена.", menu())
                    else:
                        await state.update_data(draft=draft)
                        await render(message, draft, user_id)
                else:
                    if button == "back":
                        draft.back()
                    elif button in ("income", "expense") and draft.stage == "type":
                        draft.set_kind(button)
                        draft.next()
                    elif button == "clear" and draft.stage == "comment":
                        draft.clear_comment()
                    elif draft.stage == "tags":
                        tag = await db(store.get_tag, user_id, button)
                        if draft.toggle_tag(tag):
                            await say(message, "Архивный тег снят. Для повторного назначения восстановите его через создание с тем же названием.")
                    else:
                        raise ValueError("Действие недоступно на текущем шаге.")
                    await state.update_data(draft=draft)
                    await render(message, draft, user_id)
            elif action == "t" and len(parts) in (3, 4):
                data = await state.get_data()
                if data.get("tag_token") != parts[1] or await state.get_state() != "tag_menu":
                    await query.answer("Эта кнопка устарела.")
                    return
                button = parts[2]
                if button == "cancel" and len(parts) == 3:
                    await state.clear()
                    await say(message, "Ввод отменён. Главное меню.", menu())
                elif button == "archive" and len(parts) == 4:
                    await db(store.archive_tag, user_id, parts[3])
                    await say(message, "Тег архивирован. История сохранена; для новых операций он недоступен.")
                    await show_tags(message, state, user_id)
                elif button == "create" or button == "rename" and len(parts) == 4:
                    if button == "rename":
                        await db(store.get_tag, user_id, parts[3])
                    await state.set_state("tag_name")
                    await state.set_data({"rename_id": parts[3] if button == "rename" else None,
                                          "tag_token": parts[1]})
                    await say(message, "Введите название тега.", keyboard([[("Отменить", f"n:{parts[1]}:cancel")]]))
                else:
                    raise ValueError("Действие недоступно.")
            elif action == "n" and len(parts) == 3 and parts[2] == "cancel":
                data = await state.get_data()
                if data.get("tag_token") != parts[1] or await state.get_state() != "tag_name":
                    await query.answer("Эта кнопка устарела.")
                    return
                await state.clear()
                await say(message, "Ввод отменён. Главное меню.", menu())
            else:
                await query.answer("Эта кнопка устарела.")
                return
            await query.answer()
        except (ValueError, LookupError) as error:
            await say(message, str(error))
            await query.answer()
        except SQLAlchemyError:
            await say(message, "Ошибка записи. Данные не сохранены; попробуйте ещё раз или отмените ввод.")
            await query.answer()

    return dispatcher
