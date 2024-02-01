#!/usr/bin/env python3
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import logging
import subprocess
from pathlib import Path
from typing import Optional

import ops
from charms.operator_libs_linux.v2.snap import SnapCache, SnapState
from ops import (
    ActionEvent,
    ActiveStatus,
    BlockedStatus,
    EventBase,
    MaintenanceStatus,
    WaitingStatus,
)
from ops.interface_kube_control import KubeControlRequirer
from ops.interface_tls_certificates import CertificatesRequires

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


def determine_arch() -> str:
    """Dpkg wrapper to surface the architecture we are tied to."""
    cmd = ["dpkg", "--print-architecture"]
    output = subprocess.check_output(cmd).decode("utf-8")

    return output.rstrip()


class KubernetesE2ECharm(ops.CharmBase):
    """Charm the service."""

    CA_CERT_PATH = Path("/srv/kubernetes/ca.crt")

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.kube_control = KubeControlRequirer(self)
        self.certificates = CertificatesRequires(self)

        self.CA_CERT_PATH.parent.mkdir(exist_ok=True)

        self.snap_cache = SnapCache()

        self.framework.observe(self.on.kube_control_relation_created, self._kube_control)
        self.framework.observe(self.on.kube_control_relation_joined, self._kube_control)
        self.framework.observe(self.on.kube_control_relation_changed, self._check_config)
        self.framework.observe(self.on.kube_control_relation_broken, self._check_config)

        self.framework.observe(self.on.certificates_relation_created, self._check_config)
        self.framework.observe(self.on.certificates_relation_changed, self._check_config)
        self.framework.observe(self.on.certificates_relation_broken, self._check_config)

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._check_config)
        self.framework.observe(self.on.test_action, self._on_test_action)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)

    def _kube_control(self, event: EventBase):
        self.kube_control.set_auth_request(self.unit.name)
        return self._check_config(event)

    def _check_kube_control(self, event: EventBase) -> bool:
        self.unit.status = MaintenanceStatus("Evaluating kubernetes authentication.")
        evaluation = self.kube_control.evaluate_relation(event)
        if evaluation:
            if "Waiting" in evaluation:
                self.unit.status = WaitingStatus(evaluation)
            else:
                self.unit.status = BlockedStatus(evaluation)
            return False
        if not self.kube_control.get_auth_credentials(self.unit.name):
            self.unit.status = WaitingStatus("Waiting for kube-control: unit credentials.")
            return False
        self.unit.status = MaintenanceStatus("Kubernetes authentication completed.")
        self.kube_control.create_kubeconfig(
            self.CA_CERT_PATH, "/root/.kube/config", "root", self.unit.name
        )
        self.kube_control.create_kubeconfig(
            self.CA_CERT_PATH, "/home/ubuntu/.kube/config", "ubuntu", self.unit.name
        )
        return True

    def _check_certificates(self, event: EventBase) -> bool:
        self.unit.status = MaintenanceStatus("Evaluating certificates.")
        evaluation = self.certificates.evaluate_relation(event)
        if evaluation:
            if "Waiting" in evaluation:
                self.unit.status = WaitingStatus(evaluation)
            else:
                self.unit.status = BlockedStatus(evaluation)
            return False
        self.CA_CERT_PATH.write_text(self.certificates.ca)
        return True

    def _check_config(self, event: EventBase) -> None:  # TODO: Not the best name
        if not self._check_certificates(event):
            return

        if not self._check_kube_control(event):
            return

        channel = self.config.get("channel")
        self._install_snaps(channel)

        self.unit.status = ops.ActiveStatus("Ready to test.")

    def _upgrade_charm(self, event: EventBase) -> None:
        channel = self.config.get("channel")
        self._install_snaps(channel)

    def _install_snaps(self, channel: Optional[str]) -> None:
        self.unit.status = ops.MaintenanceStatus("Installing core snap.")
        self._ensure_snap("core")

        # TODO : What happens to this f-string if channel is "" ?
        self.unit.status = ops.MaintenanceStatus(
            f"Installing kubectl snap from channel {channel}."
        )
        self._ensure_snap("kubectl", channel=channel)

        self.unit.status = ops.MaintenanceStatus(
            f"Installing kubernetes-test from channel {channel}."
        )
        self._ensure_snap("kubernetes-test", channel=channel, classic=True)

    def _ensure_snap(
        self,
        name: str,
        state: SnapState = SnapState.Latest,
        channel: Optional[str] = "",
        classic: Optional[bool] = False,
    ) -> None:
        if not isinstance(name, str) or name == "":
            raise ValueError("A name is required to ensure a snap.")

        snap = self.snap_cache[name]
        if not snap.present:
            snap.ensure(state=state, classic=classic, channel=channel)

    def _on_start(self, event: EventBase) -> None:
        self.unit.status = ops.ActiveStatus()

    def _on_test_action(self, event: ActionEvent) -> None:
        focus = str(event.params.get("focus", ""))
        parallelism = str(event.params.get("parallelism", ""))
        skip = str(event.params.get("skip", ""))
        timeout = str(event.params.get("timeout", ""))
        extra = str(event.params.get("extra", ""))

        command = ["scripts/test.sh", focus, skip, parallelism, timeout, extra]

        try:
            self.unit.status = MaintenanceStatus("Running e2e tests.")
            subprocess.run(command, check=True)
            self.unit.status = ActiveStatus("Tests completed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred: {e}.")
            self.unit.status = BlockedStatus("Test run failed.")


if __name__ == "__main__":  # pragma: nocover
    ops.main(KubernetesE2ECharm)  # type: ignore
