"""A fake Telegram transport: records API calls and returns plausible objects.

Lets end-to-end handler tests run without network access.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import Chat, Message, Update, User


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, Any]] = []
        self._message_id = 1000

    def _next_id(self) -> int:
        self._message_id += 1
        return self._message_id

    def sent_texts(self, chat_id: int | None = None) -> list[str]:
        out = []
        for call in self.calls:
            if call["method"] not in ("SendMessage", "EditMessageText"):
                continue
            data = call["data"]
            if chat_id is not None and data.get("chat_id") != chat_id:
                continue
            if data.get("text"):
                out.append(data["text"])
        return out

    def last_call(self, method: str) -> dict[str, Any] | None:
        for call in reversed(self.calls):
            if call["method"] == method:
                return call
        return None

    async def close(self) -> None:
        return None

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        self.calls.append(
            {"method": "StreamContent", "data": {"url": url, "headers": headers or {}}}
        )
        yield b""

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,
    ) -> Any:
        name = type(method).__name__
        data = method.model_dump(exclude_none=True)
        self.calls.append({"method": name, "data": data})

        if name == "GetMe":
            return User(id=bot.id, is_bot=True, first_name="Test Bot", username="test_bot")
        if name == "SendMessage":
            chat_id = int(data["chat_id"])
            return Message(
                message_id=self._next_id(),
                date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="Test Bot"),
                text=data.get("text"),
            )
        if name == "EditMessageText":
            chat_id = int(data["chat_id"])
            return Message(
                message_id=int(data["message_id"]),
                date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="Test Bot"),
                text=data.get("text"),
            )
        if name in ("AnswerCallbackQuery", "DeleteMessage", "SendChatAction"):
            return True
        raise AssertionError(f"FakeSession got unexpected method {name}: {data}")


def make_message(
    *,
    user_id: int,
    text: str | None = None,
    message_id: int = 1,
    chat_id: int | None = None,
    contact: Any | None = None,
    first_name: str = "کاربر",
) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id if chat_id is not None else user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name=first_name),
        text=text,
        contact=contact,
    )


def message_update(message: Message, update_id: int = 1) -> Update:
    return Update(update_id=update_id, message=message)


def callback_update(
    *,
    user_id: int,
    data: str,
    message_id: int = 1,
    chat_id: int | None = None,
    update_id: int = 1,
) -> Update:
    from aiogram.types import CallbackQuery

    chat = chat_id if chat_id is not None else user_id
    msg = make_message(user_id=user_id, message_id=message_id, chat_id=chat, text="card")
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=f"cb-{update_id}",
            from_user=User(id=user_id, is_bot=False, first_name="کاربر"),
            chat_instance="test",
            message=msg,
            data=data,
        ),
    )
