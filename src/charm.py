#!/usr/bin/env python3
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import logging
import os
import pathlib
import subprocess
import sys
from pathlib import Path
from typing import Optional

import ops
from charms.operator_libs_linux.v2.snap import SnapCache, SnapState
from ops import (
    ActionEvent,
    BlockedStatus,
    EventBase,
    MaintenanceStatus,
    WaitingStatus,
)
from ops.interface_kube_control import KubeControlRequirer
from ops.interface_tls_certificates import CertificatesRequires

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]
KUBE_CONFIG_PATH = "/home/ubuntu/.kube/config"


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

        kubecontrol = self.on["kube-control"]
        self.framework.observe(kubecontrol.relation_broken, self._check_config)
        self.framework.observe(kubecontrol.relation_joined, self._kube_control)
        self.framework.observe(kubecontrol.relation_changed, self._check_config)

        certificates = self.on["certificates"]
        self.framework.observe(certificates.relation_broken, self._check_config)
        self.framework.observe(certificates.relation_created, self._check_config)
        self.framework.observe(certificates.relation_changed, self._check_config)

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.test_action, self._on_test_action)
        self.framework.observe(self.on.config_changed, self._check_config)
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

        self.unit.status = ops.MaintenanceStatus("Installing kubectl snap.")
        self._ensure_snap("kubectl", channel=channel)

        self.unit.status = ops.MaintenanceStatus("Installing kubernetes-test snap.")
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

    def _check_kube_config(self, event: ActionEvent) -> bool:
        if not pathlib.Path(KUBE_CONFIG_PATH).exists():
            event.fail("Missing Kubernetes configuration. See logs for info.")
            logger.error("Relate to the certificate authority and kubernetes-control-plane.")
            return False
        return True

    def _log_has_errors(self, event: ActionEvent) -> bool:
        action_uuid = os.getenv("JUJU_ACTION_UUID")

        log_file_path = pathlib.Path(f"{action_uuid}.log")

        if not log_file_path.exists():
            msg = f"Logfile not found at expected location {log_file_path}"
            logger.error(msg)
            event.fail(msg)
            return False

        return "Test Suite failed" in log_file_path.read_text()

    def _on_test_action(self, event: ActionEvent) -> None:
        def param_get(p):
            return str(event.params.get(p, ""))

        args = [param_get(param) for param in ["focus", "parallelism", "skip", "timeout", "extra"]]
        command = ["scripts/test.sh", *args]
        if not self._check_kube_config(event):
            return

        command = ["./scripts/test.sh", *args]

        event.log(f"Running this command: {' '.join(command)}")

        process = subprocess.run(command, capture_output=False, check=True)

        if self._log_has_errors or process.returncode != 0:
            sys.exit(process.returncode)
        else:
            event.set_results({"result": "Tests ran successfully."})


if __name__ == "__main__":  # pragma: nocover
    ops.main(KubernetesE2ECharm)  # type: ignore
