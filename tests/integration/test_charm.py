#!/usr/bin/env python3
# Copyright 2024 user
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
TEST_ACTION_NAME = "test"
# Allow e2e tests to run with up to 2 non-ready nodes
EXTRA_ARGS = "-allowed-not-ready-nodes 2"
# Run reduced test suite
SKIP_TESTS = r"\[(Flaky|Slow|Conformance|Feature:.*)\]"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")

    await ops_test.model.deploy(charm, application_name=APP_NAME)

    # Deploy the charm and wait for active/idle status
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=[APP_NAME], status="active", raise_on_blocked=True, timeout=1000, idle_period=1
        )
        assert ops_test.model.applications[APP_NAME].units[0].workload_status == "active"


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
