#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from pathlib import Path

import yaml
import pytest
import shlex
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
READY_MESSAGE = "Ready to test."


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the kubernetes-e2e charm and deploy it 
    
    Assert on the unit status before any relations/configurations take place.
    """
    logger.info("Build charm...")
    charm = await ops_test.build_charm(".")

    overlays = [
        ops_test.Bundle("kubernetes-core", channel="edge"),
        Path("tests/data/charm.yaml"),
    ]

    logger.info("Rendering overlays...")
    bundle, *overlays = await ops_test.render_overlays(*overlays, charm=charm)

    logger.info("Deploy charm...")
    model = ops_test.model_full_name

    cmd = f"juju deploy -m {model} {bundle} " + " ".join(
        f"--overlay={f}" for f in overlays
    )

    logger.info(cmd)
    rc, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    assert rc == 0, f"Bundle deploy failed: {(stderr or stdout).strip()}"

    logger.info(stdout)
    await ops_test.model.block_until(
        lambda: "kubernetes-e2e" in ops_test.model.applications, timeout=60
    )

    try:
        await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 60)
    except asyncio.TimeoutError:
        if "kubernetes-e2e" not in ops_test.model.applications:
            raise
        app = ops_test.model.applications["kubernetes-e2e"]
        if not app.units:
            raise

    # Check unit status
    assert ops_test.model.applications[APP_NAME] == READY_MESSAGE
