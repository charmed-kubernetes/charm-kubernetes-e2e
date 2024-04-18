# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://juju.is/docs/sdk/testing

# pylint: disable=duplicate-code,missing-function-docstring
"""Unit tests."""


from unittest import mock

import ops
import ops.testing
import pytest
from charm import KubernetesE2ECharm


@pytest.fixture
def harness(tmp_path):
    """Craft a ops test harness."""
    KubernetesE2ECharm.CA_CERT_PATH = tmp_path
    harness = ops.testing.Harness(KubernetesE2ECharm)
    harness.disable_hooks()
    harness.begin()
    yield harness
    harness.cleanup()


@mock.patch("charm.KubernetesE2ECharm._setup_environment")
def test_kube_control_relation_joined(mock_setup_environment, harness):
    mock_event = mock.MagicMock()
    harness.charm._kube_control_relation_joined(mock_event)
    mock_setup_environment.assert_called_once_with(mock_event)
