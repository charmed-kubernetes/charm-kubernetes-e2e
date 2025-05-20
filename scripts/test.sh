#!/usr/bin/env bash

set -ex

export PATH="$PATH:/snap/bin"

# Grab the action parameter values
FOCUS=${1}
SKIP=${2}
PARALLELISM=${3}
TIMEOUT=${4}
EXTRA_ARGS="${@:5}"

# get the host from the config file
SERVER=$(cat /home/ubuntu/.kube/config | grep server | sed 's/    server: //')

ACTION_HOME=/home/ubuntu
ACTION_LOG=$ACTION_HOME/${JUJU_ACTION_UUID}.log
ACTION_LOG_TGZ=$ACTION_LOG.tar.gz
ACTION_JUNIT=$ACTION_HOME/${JUJU_ACTION_UUID}-junit
ACTION_JUNIT_TGZ=$ACTION_JUNIT.tar.gz

# This initializes an e2e build log with the START TIMESTAMP.
echo "JUJU_E2E_START=$(date -u +%s)" | tee $ACTION_LOG
# Append if using extra args
echo "Using extra args = $EXTRA_ARGS" | tee -a $ACTION_LOG
echo "Skip tests matching: $SKIP" | tee -a $ACTION_LOG
echo "JUJU_E2E_VERSION=$(kubectl version | grep Server | cut -d " " -f 5 | cut -d ":" -f 2 | sed s/\"// | sed s/\",//)" | tee -a $ACTION_LOG
GINKGO_ARGS="-nodes=$PARALLELISM" kubernetes-test.e2e \
  -kubeconfig /home/ubuntu/.kube/config \
  -host $SERVER \
  -ginkgo.focus $FOCUS \
  -ginkgo.skip "$SKIP" \
  ${EXTRA_ARGS[@]} \
  -report-dir $ACTION_JUNIT 2>&1 | tee -a $ACTION_LOG

# This appends the END TIMESTAMP to the e2e build log
echo "JUJU_E2E_END=$(date -u +%s)" | tee -a $ACTION_LOG

# set cwd to /home/ubuntu and tar the artifacts using a minimal directory
# path. Extracting "home/ubuntu/1412341234/foobar.log is cumbersome in ci
cd $ACTION_HOME/${JUJU_ACTION_UUID}-junit
tar -czf $ACTION_JUNIT_TGZ *
cd ..
tar -czf $ACTION_LOG_TGZ ${JUJU_ACTION_UUID}.log

action-set log="$ACTION_LOG_TGZ"
action-set junit="$ACTION_JUNIT_TGZ"