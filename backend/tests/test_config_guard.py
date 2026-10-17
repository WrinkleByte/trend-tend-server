"""Startup guard against insecure configuration (2026-08-19 review, S2).

The backend must refuse to boot with the published default JWT secret. These
tests construct Settings directly rather than going through get_settings(),
which is lru_cache'd and already populated by the time the suite runs.
"""

import pytest

from app.config import INSECURE_DEFAULT_JWT_SECRET, MIN_JWT_SECRET_BYTES, Settings

A_REAL_SECRET = "x" * MIN_JWT_SECRET_BYTES


def _settings(**overrides) -> Settings:
    # _env_file=None so a developer's own .env can't influence the result.
    return Settings(_env_file=None, **overrides)


def test_default_jwt_secret_is_rejected():
    with pytest.raises(ValueError, match="published in this project's source"):
        _settings(jwt_secret=INSECURE_DEFAULT_JWT_SECRET, dev_mode=False)


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValueError, match="shorter than"):
        _settings(jwt_secret="too-short", dev_mode=False)


def test_dev_mode_allows_the_default_secret():
    # The dev stack and this test suite both rely on this escape hatch.
    assert _settings(jwt_secret=INSECURE_DEFAULT_JWT_SECRET, dev_mode=True).jwt_secret == (
        INSECURE_DEFAULT_JWT_SECRET
    )


def test_a_real_secret_is_accepted_without_dev_mode():
    assert _settings(jwt_secret=A_REAL_SECRET, dev_mode=False).jwt_secret == A_REAL_SECRET


def test_guard_is_not_bypassed_by_a_secret_that_merely_contains_the_default():
    # Substring, not equality — a long secret that happens to embed the
    # default string is fine, and must not be mistaken for it.
    embedded = INSECURE_DEFAULT_JWT_SECRET + "-plus-plenty-of-additional-entropy"
    assert _settings(jwt_secret=embedded, dev_mode=False).jwt_secret == embedded


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_smtp_port_env_var_means_unset(monkeypatch, raw):
    # Both compose files pass `SMTP_PORT: ${SMTP_PORT:-}`, i.e. an empty
    # string on any instance without email configured. That used to crash
    # startup with an int-parsing error.
    monkeypatch.setenv("SMTP_PORT", raw)
    assert _settings(dev_mode=True).smtp_port is None


def test_smtp_port_env_var_still_parses(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "587")
    assert _settings(dev_mode=True).smtp_port == 587
