# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pytest fixtures for functional tests."""

import logging
import pytest

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--kubernetes-e2e-channel",
        action="store",
        default=None,
        help="Optional charm channel for kubernetes-e2e deployment",
    )

    parser.addoption(
        "--kubernetes-distribution",
        action="store",
        default="charmed-kubernetes",
        choices=["canonical-kubernetes", "charmed-kubernetes"],
        help="Kubernetes distribution to use for the tests",
    )


@pytest.fixture(scope="session")
def kubernetes_e2e_channel(pytestconfig):
    """Return the kubernetes-e2e channel if specified."""
    return pytestconfig.getoption("kubernetes_e2e_channel")


@pytest.fixture(scope="session")
def kubernetes_distribution(pytestconfig):
    """Return the kubernetes distribution to use for the tests."""
    return pytestconfig.getoption("kubernetes_distribution")
