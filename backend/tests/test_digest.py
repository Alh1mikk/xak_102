import pytest

from app.digest import connect_chat, weekly_round
from app.models import Preferences


class TestConnectChat:
    async def test_connects_chat(self, db):
        from app.routers.auth import session_digest
        token = "token"
        digest = session_digest(token)
        await db.execute(
            Preferences.__table__.insert().values(
                email="a@b.com", filters={}, link_hash=digest,
                link_expires=None,
            )
        )
        await db.commit()

        result = await connect_chat(token, "12345")
        assert result is True

        prefs = await db.get(Preferences, "a@b.com")
        assert prefs.telegram_chat == "12345"
        assert prefs.link_hash is None
        assert prefs.link_expires is None

    async def test_returns_false_on_integrity_error(self, db):
        from app.routers.auth import session_digest
        token = "token"
        digest = session_digest(token)
        await db.execute(
            Preferences.__table__.insert().values(
                email="a@b.com", filters={}, link_hash=digest,
                link_expires=None,
            )
        )
        await db.commit()

        result = await connect_chat(token, "12345")
        assert result is True

        result2 = await connect_chat(token, "67890")
        assert result2 is False
