#!/usr/bin/env python3
# Copyright 2024 user
# See LICENSE file for licensing details.

import logging
import shlex
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
CHARM_CHANNEL = METADATA["config"]["options"]["channel"]["default"]
TEST_ACTION_NAME = "test"
READY_MESSAGE = "Ready to test."
# Allow e2e tests to run with up to 2 non-ready nodes
EXTRA_ARGS = "-allowed-not-ready-nodes 2"
# Run reduced test suite
SKIP_TESTS = r"\[(Flaky|Slow|Conformance|Feature:.*)\]"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(
    ops_test: OpsTest,
    kubernetes_e2e_channel: str,
    kubernetes_distribution: str,
):
    """Build the kubernetes-e2e charm and deploy it.

    Assert on the unit status before any relations/configurations take place.
    """
    assert ops_test.model is not None, "Model is not set up."
    if kubernetes_e2e_channel:
        logger.info(f"Using kubernetes-e2e channel: {kubernetes_e2e_channel}")
        charm = APP_NAME
        channel = kubernetes_e2e_channel
    else:
        logger.info("Using local charm source.")
        channel = None
        charm = next(Path(".").glob(f"{APP_NAME}*.charm"), None)
        if not charm:
            logger.info(f"Building {APP_NAME} charm.")
            charm = await ops_test.build_charm(".")
        charm = charm.resolve() if charm else None

    bundle_vars = {"charm": charm, "channel": channel}
    overlays = [
        ops_test.Bundle(kubernetes_distribution, channel=CHARM_CHANNEL),
        Path(f"tests/data/{kubernetes_distribution}.yaml"),
    ]

    logger.info("Rendering overlays...")
    bundle, *overlays = await ops_test.async_render_bundles(*overlays, **bundle_vars)

    logger.info("Deploy charm...")
    model = ops_test.model_full_name

    cmd = f"juju deploy -m {model} {bundle} " + " ".join(f"--overlay={f}" for f in overlays)

    logger.info(cmd)
    rc, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    assert rc == 0, f"Bundle deploy failed: {(stderr or stdout).strip()}"

    logger.info(stdout)
    await ops_test.model.block_until(
        lambda: "kubernetes-e2e" in ops_test.model.applications, timeout=60
    )

    await ops_test.model.wait_for_idle(status="active", timeout=60 * 60)

    unit = ops_test.model.applications[APP_NAME].units[0]
    # Check unit status message
    assert unit.workload_status_message == READY_MESSAGE


async def test_action_test(ops_test: OpsTest):
    logger.info("Queue action run...")
    # Get application unit
    unit = ops_test.model.applications[APP_NAME].units[0]
    action = await unit.run_action(TEST_ACTION_NAME, extra=EXTRA_ARGS, skip=SKIP_TESTS)

    logger.info("Wait for action...")
    action = await action.wait()

    logger.info("Action finished...")
    # Get action status from queued action id
    result = action.results
    # Assert the completion and generation of report
    status = action.status
    logger.info(
        "Action finished with status \n"
        f"rc={result['return-code']}\n"
        f"stdout={result['stdout']}\n"
        f"stderr={result['stderr']}\n"
    )
    assert status in ["completed", "failed"]
