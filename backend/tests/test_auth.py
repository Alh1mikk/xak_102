import hashlib
import hmac
import re
import unittest
from datetime import datetime, timedelta, timezone

import pytest

from app.routers.auth import (
    code_digest,
    email_configured,
    normalized_email,
    set_session_cookie,
    verified_telegram_user,
)


class TestSessionUtils(unittest.TestCase):
    def test_session_digest(self):
        self.assertEqual(len(session_digest("abc")), 64)

    def test_normalized_email(self):
        self.assertEqual(normalized_email("  Person@Example.org  "), "person@example.org")

    def test_normalized_email_invalid(self):
        with self.assertRaises(Exception):
            normalized_email("not-an-email")

    def test_code_digest(self):
        key = "secret"
        self.assertIsInstance(code_digest("a@b.com", "123456"), str)
        self.assertEqual(len(code_digest("a@b.com", "123456")), 64)

    def test_code_digest_different_inputs(self):
        self.assertNotEqual(
            code_digest("a@b.com", "123456"),
            code_digest("b@b.com", "123456"),
        )
        self.assertNotEqual(
            code_digest("a@b.com", "123456"),
            code_digest("a@b.com", "654321"),
        )

    def test_email_configured(self):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
            monkeypatch.setenv("SMTP_FROM", "from@example.com")
            monkeypatch.setenv("EMAIL_CODE_SECRET", "secret")
            self.assertTrue(email_configured())
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.delenv("EMAIL_CODE_SECRET", raising=False)
            self.assertFalse(email_configured())


class TestVerifiedTelegramUser:
    def test_valid_signature(self):
        payload = {
            "id": 123,
            "auth_date": 1000,
            "first_name": "Имя",
            "username": "user",
        }
        check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
        payload["hash"] = hmac.new(
            hashlib.sha256(b"token").digest(),
            check.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(verified_telegram_user(payload, "token", 1050), ("123", "Имя"))

    def test_invalid_signature(self):
        payload = {
            "id": 123,
            "auth_date": 1000,
            "first_name": "Имя",
            "username": "user",
        }
        check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
        payload["hash"] = hmac.new(
            hashlib.sha256(b"other").digest(),
            check.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertIsNone(verified_telegram_user(payload, "token", 1050))

    def test_expired(self):
        payload = {
            "id": 123,
            "auth_date": 1000,
            "first_name": "Имя",
        }
        check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
        payload["hash"] = hmac.new(
            hashlib.sha256(b"token").digest(),
            check.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertIsNone(verified_telegram_user(payload, "token", 2000))

    def test_missing_field(self):
        payload = {
            "id": 123,
            "auth_date": 1000,
        }
        self.assertIsNone(verified_telegram_user(payload, "token", 1050))

    def test_invalid_signature_format(self):
        payload = {
            "id": 123,
            "auth_date": 1000,
            "first_name": "Имя",
            "hash": "short",
        }
        self.assertIsNone(verified_telegram_user(payload, "token", 1050))


class TestSetSessionCookie:
    def test_cookies(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.routers import auth as auth_router

        app = FastAPI()
        app.include_router(auth_router.router)

        with TestClient(app) as client:
            response = client.get("/")
            set_session_cookie(response, "session123")
            cookie = response.cookies.get("afisha_session")
            self.assertIsNotNone(cookie)
            self.assertEqual(cookie.value, "session123")
            self.assertEqual(
                response.headers["set-cookie"],
                "afisha_session=session123; Max-Age=604800; HttpOnly; Path=/; SameSite=lax",
            )
