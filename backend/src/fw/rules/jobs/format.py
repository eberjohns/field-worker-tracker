"""Job number format validation and outdoor rules per BR-JB-01."""

import re

JOB_NUMBER_REGEX = re.compile(r"^\d{2}[ABC]\d{5}$")


class InvalidJobNumberError(ValueError):
    """Raised when a job number violates BR-JB-01."""

    pass


def validate_job_number(job_number: str) -> str:
    """Validate that a job number matches 2 digits + letter (A/B/C) + 5 digits.

    Rejects hyphens, slashes, or combined numbers per BR-JB-01 and DEC-23.
    Returns normalized uppercase job number string.
    """
    if not job_number or not isinstance(job_number, str):
        raise InvalidJobNumberError("Job number must be a non-empty string.")

    cleaned = job_number.strip()
    if "-" in cleaned or "/" in cleaned or "," in cleaned or " " in cleaned:
        raise InvalidJobNumberError(
            f"Job number '{job_number}' contains hyphen, slash, or combined format. "
            "Only single uncombined numbers matching 2 digits + letter (A/B/C) + 5 digits are allowed."
        )

    if not JOB_NUMBER_REGEX.match(cleaned):
        raise InvalidJobNumberError(
            f"Job number '{job_number}' does not match required format: "
            "2 digits + letter (A outdoor, B indoor, C water feature) + 5 digits (e.g. 12A14301)."
        )

    return cleaned


def is_job_outdoor(job_number: str) -> bool:
    """Determine whether a worksite is outdoor from its job number letter (BR-JB-01).

    Letter 'A' means outdoor (True).
    Letters 'B' (indoor) and 'C' (water feature) are not outdoor (False).
    """
    valid_number = validate_job_number(job_number)
    return valid_number[2] == "A"
