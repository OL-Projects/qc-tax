"""Shared fixtures and helpers for the qc-tax test suite."""

import random
from decimal import Decimal

import pytest


@pytest.fixture
def rq_example():
    """The worked example from Revenu Québec publication IN-256-V."""
    return Decimal("100.00")


def money_samples(n=400, *, seed=20261106, low=Decimal("0.01"), high=Decimal("100000")):
    """
    Deterministic pseudo-random cent amounts.

    A fixed seed keeps failures reproducible; the large sample is what turns a
    "looks right" implementation into a checked one.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        lo = int(low * 100)
        hi = int(high * 100)
        out.append(Decimal(rng.randint(lo, hi)) / 100)
    return out
