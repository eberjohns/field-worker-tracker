"""Unique values for test rows within one run (the test database is recreated every run)."""

import itertools

_counters: dict[str, "itertools.count[int]"] = {}


def unique_job_number(prefix: str = "26A") -> str:
    """A valid job number (2 digits, A/B/C, 5 digits) that no other test in this run uses.

    A random 5-digit suffix collided now and then in a run that creates a few hundred worksites.
    The count starts at 50001, clear of the fixed numbers some tests use (12A10604, 12A14301,
    12A99905).
    """
    n = next(_counters.setdefault(prefix, itertools.count(50001)))
    return f"{prefix}{n:05d}"
