"""Application configuration loaded from environment / .env.

Secrets are ONLY readable from the environment (or .env, gitignored).
Anything here is validated at startup so a misconfigured deployment fails fast.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BotMode = Literal["polling", "webhook"]


def _parse_int_list(raw: object) -> list[int]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, str):
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    return []


def _parse_str_list(raw: object) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _parse_roles(raw: object) -> dict[str, str]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if not isinstance(raw, str):
        return {}
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            tg_id, role = part.split(":", 1)
            out[tg_id.strip()] = role.strip()
        else:
            out[part] = "owner"
    return out


class Settings(BaseSettings):
    """All runtime configuration. Prefix is empty (plain env vars)."""

    # enable_decoding=False keeps env values as raw strings so the before-
    # validators below can split comma-separated lists instead of forcing JSON.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", enable_decoding=False)

    # ── Telegram ──────────────────────────────────────────────────────────
    bot_token: str
    bot_mode: BotMode = "polling"
    webhook_base_url: str | None = None
    webhook_secret: str | None = None
    # NoDecode keeps env values as strings so the before-validators below can
    # split comma-separated lists instead of forcing JSON.
    admin_ids: Annotated[list[int], NoDecode] = []
    admin_roles: Annotated[dict[str, str], NoDecode] = {}
    admin_group_chat_id: int | None = None

    # ── Infrastructure ────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://fanic:fanic@postgres:5432/fanic"
    redis_url: str = "redis://redis:6379/0"

    # ── Receiving card (payment) ──────────────────────────────────────────
    shop_card_number: str | None = None  # full PAN, env only, never logged
    shop_card_holder: str | None = None
    shop_bank_code: str | None = None

    # ── SMS ingestion ─────────────────────────────────────────────────────
    sms_hmac_secret: str | None = None
    sms_device_ids: list[str] = []
    store_raw_sms: bool = False

    # ── Payment policies ──────────────────────────────────────────────────
    payment_window_minutes: int = 15
    suffix_min_toman: int = 1
    suffix_max_toman: int = 999
    sms_grace_minutes: int = 120

    # ── Runtime ───────────────────────────────────────────────────────────
    tz: str = "Asia/Tehran"
    log_level: str = "INFO"
    http_host: str = "0.0.0.0"
    http_port: int = 8080

    # pydantic-settings v2 wants a validator to turn comma lists into lists
    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_int_list(cls, v: object) -> object:
        return _parse_int_list(v)

    @field_validator("sms_device_ids", mode="before")
    @classmethod
    def _split_str_list(cls, v: object) -> object:
        return _parse_str_list(v)

    @field_validator("admin_roles", mode="before")
    @classmethod
    def _split_roles(cls, v: object) -> object:
        return _parse_roles(v)

    @field_validator("admin_group_chat_id", mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @property
    def admin_telegram_ids(self) -> set[int]:
        return set(self.admin_ids)

    @property
    def role_of(self) -> dict[int, str]:
        """Map telegram id -> role ('owner' | 'support')."""
        out: dict[int, str] = {}
        for tg_id, role in self.admin_roles.items():
            try:
                out[int(tg_id)] = role
            except (TypeError, ValueError):
                continue
        # ids listed in ADMIN_IDS but not in ADMIN_ROLES are owners
        for uid in self.admin_ids:
            out.setdefault(uid, "owner")
        return out


@lru_cache
def get_settings() -> Settings:
    # bot_token & friends come from the environment / .env at runtime; mypy
    # can't see that source, hence the ignore.
    return Settings()  # type: ignore[call-arg]
