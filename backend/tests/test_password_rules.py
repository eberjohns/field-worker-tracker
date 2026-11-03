"""Unit tests for pure password rules."""

from datetime import UTC, datetime, timedelta

import pytest

from fw.rules.password import (
    PasswordPolicyViolation,
    is_default_password_expired,
    validate_password_strength,
)


def test_default_password_expired() -> None:
    now = datetime.now(UTC)
    created_8_days_ago = now - timedelta(days=8)
    created_6_days_ago = now - timedelta(days=6)

    # Must change password and past 7 days -> expired / locked
    assert is_default_password_expired(True, created_8_days_ago, now, max_days=7) is True

    # Must change password within 7 days -> not expired yet
    assert is_default_password_expired(True, created_6_days_ago, now, max_days=7) is False

    # Already changed password -> never expired
    assert is_default_password_expired(False, created_8_days_ago, now, max_days=7) is False


def test_validate_password_strength() -> None:
    # Too short
    with pytest.raises(PasswordPolicyViolation) as exc:
        validate_password_strength("short", default_password="DefaultPass123")
    assert exc.value.code == "PASSWORD_TOO_SHORT"

    # Reusing default password
    with pytest.raises(PasswordPolicyViolation) as exc:
        validate_password_strength("DefaultPass123", default_password="DefaultPass123")
    assert exc.value.code == "CANNOT_REUSE_DEFAULT_PASSWORD"

    # Valid password
    validate_password_strength("NewSecurePassword123!", default_password="DefaultPass123")
