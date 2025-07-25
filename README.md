# Kubernetes end to end

End-to-end (e2e) tests for Kubernetes provide a mechanism to test end-to-end
behavior of the system, and is the last signal to ensure end user operations
match developer specifications. Although unit and integration tests provide a
good signal, in a distributed system like Kubernetes it is not uncommon that a
minor change may pass all unit and integration tests, but cause unforeseen
changes at the system level.

The primary objectives of the e2e tests are to ensure a consistent and reliable
behavior of the kubernetes code base, and to catch hard-to-test bugs before
users do, when unit and integration tests are insufficient.

## Usage with Canonical K8s

> Note: This charm can be used to test both Canonical K8s and
Charmed Kubernetes. The information for testing Charmed Kubernetes is
in the next section.

Running the end-to-end test suite on Canonical K8s requires integrating the
`k8s-operator` and `k8s-worker` charms and deploying the `kubernetes-e2e` charm.

First, deploy k8s-operator and k8s-worker, and relate them.

```shell
juju deploy k8s
juju deploy k8s-worker
juju expose k8s
juju integrate k8s k8s-worker:cluster
```

Next, deploy the kubernetes-e2e charm:

```shell
juju deploy kubernetes-e2e
juju integrate kubernetes-e2e:kube-control k8s:kube-control
```

## Usage with Charmed Kubernetes

To test Charmed Kubernetes, we suggest deploying the
[kubernetes-core bundle](https://github.com/juju-solutions/bundle-kubernetes-core)
and then relating the `kubernetes-e2e` charm.

```shell
juju deploy kubernetes-core
juju deploy kubernetes-e2e
juju integrate kubernetes-e2e:kube-control kubernetes-control-plane:kube-control
juju integrate kubernetes-e2e easyrsa
juju add-unit kubernetes-worker  # to test with 2 worker nodes
```

Once the relations have settled, and the `kubernetes-e2e` charm reports
 `Ready to test.` - you may kick off an end to end validation test.

### Running the e2e test

The e2e test is encapsulated as an action to ensure consistent runs of the
end to end test. The defaults are sensible for most deployments.

```shell
juju run kubernetes-e2e/0 test --wait=2h
```

## Tuning the e2e test

The e2e test is configurable for both Canonical K8s and Charmed K8s testing. By default it will focus on or skip the declared
conformance tests in a cloud agnostic way. Default behaviors are configurable.
This allows the operator to test only a subset of the conformance tests, or to
test more behaviors not enabled by default. You can see all tunable options on
the charm by inspecting the schema output of the actions:

```shell
$ juju actions kubernetes-e2e --format=yaml --schema
test:
  description: Execute an end to end test.
  properties:
    extra:
      default: ""
      description: Extra arguments for kubernetes-e2e test suite
      type: string
    focus:
      default: \[Conformance\]
      description: Run tests matching the focus regex pattern.
      type: string
    parallelism:
      default: 25
      description: The number of test nodes to run in parallel.
      type: integer
    skip:
      default: \[Flaky\]|\[Serial\]
      description: Skip tests matching the skip regex pattern.
      type: string
    timeout:
      default: 30000
      description: Timeout in nanoseconds
      type: integer
  title: test
  type: object
```


As an example, you can run a more limited set of tests for rapid validation of
a deployed cluster. The following example will skip the `Flaky`, `Slow`, and
`Feature` labeled tests:

```shell
juju run kubernetes-e2e/0 test skip='\[(Flaky|Slow|Feature:.*)\]'
```

> Note: the escaping of the regex due to how bash handles brackets.

To see the different types of tests the Kubernetes end-to-end charm has access
to, we encourage you to see the upstream documentation on the different types
of tests, and to strongly understand what subsets of the tests you are running.

[Kinds of tests](https://git.k8s.io/community/contributors/devel/sig-testing/e2e-tests.md#kinds-of-tests)

### More information on end-to-end testing

Along with the above descriptions, end-to-end testing is a much larger subject
than this readme can encapsulate. There is far more information in the
[end-to-end testing guide](https://git.k8s.io/community/contributors/devel/sig-testing/e2e-tests.md).

### Evaluating end-to-end results

It is not enough to just simply run the test. Result output is stored in two
places. The output of the e2e run is available as a flat file ending in ".log" on disk of the `kubernetes-e2e` unit that executed the test. The output is also
available through `juju show-task`.

> Note: The results will only be available once the action has
completed the test run. End-to-end testing can be quite time intensive. Often
times taking **greater than 1 hour**, depending on configuration.

##### Flat file

```shell
$ juju run kubernetes-e2e/0 test --wait=2h
Running operation 2 with 1 task
  - task 3 on unit-kubernetes-e2e-0

Waiting for task 3...

$ juju scp kubernetes-e2e/0:3.log .
```

##### Action result output

```shell
$ juju run kubernetes-e2e/0 test
Running operation 2 with 1 task
  - task 3 on unit-kubernetes-e2e-0

Waiting for task 3...

$ juju show-task 3
```

## Known issues

The e2e test suite assumes egress network access. It will pull container
images from `gcr.io`. You will need to have this registry unblocked in your
firewall to successfully run e2e test results. Or you may use the exposed
proxy settings [properly configured](https://github.com/juju-solutions/bundle-canonical-kubernetes#proxy-configuration)
on the kubernetes-worker units.

## Contributing

If you are interested in fixing issues, updating docs or helping with
development of this charm, please see the [CONTRIBUTING.md](./CONTRIBUTING.md) page.

## Help resources:

- [Bug Tracker](https://github.com/juju-solutions/bundle-canonical-kubernetes/issues)
- [Github Repository](https://github.com/kubernetes/kubernetes/)
- [Mailing List](mailto:juju@lists.ubuntu.com)