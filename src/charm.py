#!/usr/bin/env python3
# Copyright 2024 user
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging
import subprocess
from charms.operator_libs_linux.v2.snap import SnapCache, SnapState

import ops
from ops import ActiveStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


def determine_arch():
    """dpkg wrapper to surface the architecture we are tied to"""
    cmd = ["dpkg", "--print-architecture"]
    output = subprocess.check_output(cmd).decode("utf-8")

    return output.rstrip()


class OpsCharmKubernetesE2ECharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.test_action, self._on_test_action)

        self.snap_cache = SnapCache()

    def _on_config_changed(self, event):
        channel = self.config.get("channel")
        self._install_snaps(channel)

    def _install_snaps(self, channel: str):
        self.unit.status = ops.MaintenanceStatus(f"Installing core snap")
        self._ensure_snap("core")

        self.unit.status = ops.MaintenanceStatus(f"Installing kubectl snap from channel {channel}")
        self._ensure_snap("kubectl", channel=channel)

        self.unit.status = ops.MaintenanceStatus(
            f"Installing kubernetes-test from channel {channel}"
        )
        self._ensure_snap("kubernetes-test", channel=channel, classic=True)

    def _ensure_snap(
        self,
        name: str,
        state: SnapState = SnapState.Latest,
        channel: str | None = "",
        classic: bool | None = False,
    ):
        if not isinstance(name, str) or name == "":
            raise ValueError("A name is required to ensure a snap.")

        snap = self.snap_cache[name]
        if not snap.present:
            snap.ensure(state=state, classic=classic, channel=channel)

    def _on_start(self, event):
        self.unit.status = ops.ActiveStatus()

    def _on_test_action(self, event):
        focus = str(event.params.get("focus", ""))
        parallelism = str(event.params.get("parallelism", ""))
        skip = str(event.params.get("skip", ""))
        timeout = str(event.params.get("timeout", ""))
        extra = str(event.params.get("extra", ""))

        command = ["scripts/test.sh", focus, skip, parallelism, timeout, extra]

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred: {e}.")


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpsCharmKubernetesE2ECharm)  # type: ignore
