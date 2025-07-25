#!/usr/bin/env python3
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional

import ops
from charms.operator_libs_linux.v2 import snap
from ops.interface_kube_control import KubeControlRequirer
from ops.interface_tls_certificates import CertificatesRequires

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]
KUBE_CONFIG_PATH = "/home/ubuntu/.kube/config"


class KubeConfigResourceManager:
    """Manage the kubeconfig resource."""

    def __init__(self, model: ops.model.Model):
        self.kube_config_path = Path(KUBE_CONFIG_PATH)

        try:
            self.resource = model.resources.fetch("kubeconfig")
        except (ops.model.ModelError, NameError):
            logger.warning(
                "Error pulling an attached kubeconfig resource. Maybe nothing is attached."
            )
            self.resource = None

    def _ensure_directory_exists(self) -> None:
        os.makedirs(self.kube_config_path.parent, exist_ok=True)

    def _read_kubeconfig_resource(self) -> Optional[str]:
        self._ensure_directory_exists()

        if self.resource is not None:
            with open(self.resource, "r") as f:
                return f.read()

        return None

    def is_valid_kubeconfig_resource(self) -> bool:
        """Check if the kubeconfig resource is not an empty file."""
        if not self._read_kubeconfig_resource():
            return False
        return True

    def write_kubeconfig_resource(self) -> None:
        """Write the kubeconfig resource to the expected location."""
        if content := self._read_kubeconfig_resource():
            self.kube_config_path.write_text(content)


class KubernetesE2ECharm(ops.CharmBase):
    """Charm the service."""

    CA_CERT_PATH = Path("/srv/kubernetes/ca.crt")

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.kube_control = KubeControlRequirer(self, schemas="0,1")
        self.certificates = CertificatesRequires(self)

        self.CA_CERT_PATH.parent.mkdir(exist_ok=True)

        kubecontrol = self.on["kube-control"]
        self.framework.observe(kubecontrol.relation_broken, self._setup_environment)
        self.framework.observe(kubecontrol.relation_joined, self._kube_control_relation_joined)
        self.framework.observe(kubecontrol.relation_changed, self._setup_environment)

        certificates = self.on["certificates"]
        self.framework.observe(certificates.relation_broken, self._setup_environment)
        self.framework.observe(certificates.relation_created, self._setup_environment)
        self.framework.observe(certificates.relation_changed, self._setup_environment)

        self.framework.observe(self.on.test_action, self._on_test_action)
        self.framework.observe(self.on.config_changed, self._setup_environment)

    def _kube_control_relation_joined(self, event: ops.EventBase):
        self.kube_control.set_auth_request(self.unit.name, "system:masters")
        return self._setup_environment(event)

    def _ensure_kube_control_relation(self, event: ops.EventBase) -> bool:
        self.unit.status = ops.MaintenanceStatus("Evaluating kubernetes authentication.")
        evaluation = self.kube_control.evaluate_relation(event)
        if evaluation:
            if "Waiting" in evaluation:
                self.unit.status = ops.WaitingStatus(evaluation)
            else:
                self.unit.status = ops.BlockedStatus(evaluation)
            return False
        if not self.kube_control.get_auth_credentials(self.unit.name):
            self.unit.status = ops.WaitingStatus("Waiting for kube-control: unit credentials.")
            return False
        self.unit.status = ops.MaintenanceStatus("Kubernetes authentication completed.")
        self.kube_control.create_kubeconfig(
            self.CA_CERT_PATH, "/root/.kube/config", "root", self.unit.name
        )
        self.kube_control.create_kubeconfig(
            self.CA_CERT_PATH, "/home/ubuntu/.kube/config", "ubuntu", self.unit.name
        )
        return True

    def _ensure_certificates_relation(self, event: ops.EventBase) -> bool:
        if self.kube_control.get_ca_certificate():
            logger.info("CA Certificate is available from kube-control.")
            return True

        self.unit.status = ops.MaintenanceStatus("Evaluating certificates.")
        evaluation = self.certificates.evaluate_relation(event)
        if evaluation:
            if "Waiting" in evaluation:
                self.unit.status = ops.WaitingStatus(evaluation)
            else:
                self.unit.status = ops.BlockedStatus(evaluation)
            return False
        self.CA_CERT_PATH.write_text(self.certificates.ca)
        return True

    def _setup_environment(self, event: ops.EventBase) -> None:
        kubeconfig_resource_manager = KubeConfigResourceManager(self.model)

        if kubeconfig_resource_manager.is_valid_kubeconfig_resource():
            kubeconfig_resource_manager.write_kubeconfig_resource()
        else:
            if not self._ensure_certificates_relation(event):
                return

            if not self._ensure_kube_control_relation(event):
                return

        channel = str(self.config.get("channel"))
        self._install_snaps(channel)

        self.unit.status = ops.ActiveStatus("Ready to test.")

    def _install_snaps(self, channel: Optional[str]) -> None:
        self.unit.status = ops.MaintenanceStatus("Installing kubectl and kubernetes-test snaps.")
        snap.ensure("kubectl", snap.SnapState.Latest.value, channel=channel)
        snap.ensure("kubernetes-test", snap.SnapState.Latest.value, channel=channel, classic=True)
        self.unit.status = ops.MaintenanceStatus("Snaps installed successfully.")

    def _check_kube_config_exists(self, event: ops.ActionEvent) -> bool:
        if not Path(KUBE_CONFIG_PATH).exists():
            event.fail("Missing Kubernetes configuration. See logs for info.")
            event.log("Relate to the certificate authority and kubernetes-control-plane.")
            return False
        return True

    def _log_has_errors(self, event: ops.ActionEvent) -> bool:
        log_file_path = Path(f"/home/ubuntu/{event.id}.log")

        if not log_file_path.exists():
            msg = f"Logfile not found at expected location {log_file_path}"
            event.log(msg)
            event.fail(msg)
            return False

        return "Test Suite Failed" in log_file_path.read_text()

    def _on_test_action(self, event: ops.ActionEvent) -> None:
        def param_get(p):
            return str(event.params.get(p, ""))

        # Param order matters here because test.sh uses $1, $2, etc.
        args = [param_get(param) for param in ["focus", "skip", "parallelism", "timeout"]]
        args += shlex.split(param_get("extra"))

        command = ["scripts/test.sh", *args]

        if not self._check_kube_config_exists(event):
            return

        logger.info("Running scripts/test.sh: %s", "".join(command))

        previous_status = self.unit.status
        self.unit.status = ops.MaintenanceStatus("Tests running...")

        # Let check=False so the log and process return code can be checked below.
        process = subprocess.run(command, capture_output=False, check=False)

        try:
            if self._log_has_errors(event) or process.returncode != 0:
                event.fail("One or more tests failed.")
            else:
                event.set_results({"result": "Tests ran successfully."})
        finally:
            self.unit.status = previous_status


if __name__ == "__main__":  # pragma: nocover
    ops.main(KubernetesE2ECharm)  # type: ignore
