"""M0 smoke tests: config loads, logging masks secrets, /healthz responds."""

from __future__ import annotations

from app.config import Settings
from app.logging import mask


def test_settings_loads_with_minimal_env() -> None:
    s = Settings(bot_token="123:ABC")
    assert s.bot_mode == "polling"
    assert s.payment_window_minutes == 15
    assert s.admin_ids == []
    assert s.role_of == {}


def test_admin_ids_and_roles_parsing() -> None:
    s = Settings(
        bot_token="t",
        admin_ids="111,222",
        admin_roles="111:owner,222:support",
    )
    assert s.admin_ids == [111, 222]
    assert s.role_of == {111: "owner", 222: "support"}


def test_mask_hides_tokens_and_pans() -> None:
    assert "***" in mask("BOT_TOKEN=abc123")
    assert "6037-****-****-1234" in mask("60379912345678901234")


async def test_healthz(aiohttp_client) -> None:
    from app.main import build_app

    client = await aiohttp_client(build_app())
    resp = await client.get("/healthz")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
