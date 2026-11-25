"""Pure password policy rules (DEC-53, docs/02-roles-and-permissions.md).

Pure Python logic with no database, framework, or module dependencies.
"""

from datetime import datetime


class PasswordPolicyViolation(Exception):
    """Raised when password policy rules are violated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def is_default_password_expired(
    must_change_password: bool,
    default_issued_at: datetime | None,
    current_time_utc: datetime,
    max_days: int = 7,
) -> bool:
    """Return True if the user is still on the default password and has exceeded max_days.

    `default_issued_at` is when the current default password was given: the last Admin reset
    (`password_changed_at`), else the account's creation. Counting from creation alone locked
    an old account again straight after a reset (19 Nov meeting item 7).
    """
    if not must_change_password or default_issued_at is None:
        return False
    elapsed_seconds = (current_time_utc - default_issued_at).total_seconds()
    return elapsed_seconds > (max_days * 86400)


def validate_password_strength(
    password: str,
    default_password: str | None = None,
    min_length: int = 8,
) -> None:
    """Validate strength of a newly provided password."""
    if len(password) < min_length:
        raise PasswordPolicyViolation(
            code="PASSWORD_TOO_SHORT",
            message=f"Password must be at least {min_length} characters long.",
        )
    if default_password and password == default_password:
        raise PasswordPolicyViolation(
            code="CANNOT_REUSE_DEFAULT_PASSWORD",
            message="New password cannot be the company default password.",
        )
