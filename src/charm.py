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
from charms.operator_libs_linux.v2 import snap

import ops
from ops import ActiveStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class OpsCharmKubernetesE2ECharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.test_action, self._on_test_action)

    def _on_config_changed(self, event):
        channel = self.config.get("channel")
        self._install_snaps(channel)


    def _install_snaps(self, channel: str):
        if not isinstance(channel, str) or channel == "":
            raise ValueError("Channel must be a non-empty string.")

        self.unit.status = ops.MaintenanceStatus(f"Installing core snap from channel {channel}")
        snap.add("core")

        self.unit.status = ops.MaintenanceStatus(f"Installing kubectl snap from channel {channel}")
        snap.add("kubectl", channel=channel, classic=True)

        self.unit.status = ops.MaintenanceStatus(f"Installing kubernetes-test from channel {channel}")
        snap.add("kubernetes-test", channel=channel, classic=True)

        #set_state("kubernetes-e2e.installed")


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
