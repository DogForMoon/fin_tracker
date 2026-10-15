"""Only external Telegram API is replaced; app dispatcher, FSM and DB stay real."""

from datetime import UTC, datetime

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    GetMe,
    SendMessage,
)
from aiogram.types import CallbackQuery, Chat, Message, Update, User


class TelegramSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.messages = []
        self.serial = 1000

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        raise AssertionError("Unexpected Telegram download")
        yield b""

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109 - aiogram BaseSession API
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=123456, is_bot=True, first_name="TestBot", username="test_fin_bot")
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, (SendMessage, EditMessageText, EditMessageReplyMarkup)):
            self.serial += 1
            message = Message(
                message_id=self.serial,
                date=datetime.now(UTC),
                chat=Chat(id=int(method.chat_id), type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="TestBot"),
                text=getattr(method, "text", None),
                reply_markup=method.reply_markup,
            )
            self.messages.append(message)
            return message
        raise AssertionError(f"Unexpected Telegram API method: {type(method).__name__}")


class TelegramDriver:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.session = TelegramSession()
        self.bot = Bot("123456:TEST_TOKEN_FOR_OFFLINE_TESTS_ONLY", session=self.session)
        self.serial = 0

    async def text(self, value, user_id=101, at=None):
        self.serial += 1
        message = Message(
            message_id=self.serial,
            date=at or datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name=f"User{user_id}"),
            text=value,
        )
        return await self.dispatcher.feed_update(self.bot, Update(update_id=self.serial, message=message))

    def button(self, label, user_id=101):
        for message in reversed(self.session.messages):
            if message.chat.id == user_id and message.reply_markup:
                for row in message.reply_markup.inline_keyboard:
                    for button in row:
                        if button.text == label or button.text.removeprefix("✓ ") == label:
                            return button.callback_data
        raise AssertionError(f"Button not found: {label}; responses: {self.texts(user_id)}")

    async def click(self, label=None, user_id=101, data=None, message_date=None):
        data = data or self.button(label, user_id)
        self.serial += 1
        message = Message(
            message_id=self.serial,
            date=message_date or datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=self.bot.id, is_bot=True, first_name="TestBot"),
            text="Historical bot keyboard",
        )
        callback = CallbackQuery(id=str(self.serial), from_user=User(id=user_id, is_bot=False, first_name="User"), chat_instance=str(user_id), message=message, data=data)
        return await self.dispatcher.feed_update(self.bot, Update(update_id=self.serial, callback_query=callback))

    def texts(self, user_id=101):
        return "\n".join(message.text or "" for message in self.session.messages if message.chat.id == user_id)

    def latest(self, user_id=101):
        return next(message for message in reversed(self.session.messages) if message.chat.id == user_id)

    async def close(self):
        await self.dispatcher.storage.close()
        await self.bot.session.close()
