# Kubernetes Provisioning with Ansible

This directory contains the Ansible configuration used to prepare and bootstrap the Kubernetes cluster for this project.

The cluster consists of one control-plane node and two worker nodes running Debian 13.

## Cluster Nodes

| Node       | IP Address  | Role                     |
| ---------- | ----------- | ------------------------ |
| controller | 10.10.20.11 | Kubernetes control plane |
| worker1    | 10.10.10.11 | Kubernetes worker        |
| worker2    | 10.10.10.12 | Kubernetes worker        |

Ansible is executed from the host machine and connects to all three nodes through SSH.

## Components

The cluster currently uses:

* Kubernetes 1.36.4
* containerd 2.3.5
* Helm 3.22.0
* Cilium 1.20.2
* kubeadm for cluster bootstrap

Cilium is configured in tunnel mode using VXLAN.

The Kubernetes Pod network is:

`10.200.0.0/16`

Current node allocations are:

```text
controller   10.200.0.0/24
worker1      10.200.1.0/24
worker2      10.200.2.0/24
```

The Kubernetes Service network is:

`10.96.0.0/12`

## Directory Structure

```text
ansible/
├── inventory.ini
├── preflight.yml
├── prepare-nodes.yml
├── bootstrap-control-plane.yml
├── install-helm.yml
├── install-cilium.yml
├── join-workers.yml
├── reset-cluster.yml
├── health-check.yml
└── roles/
    ├── k8s_prerequisites/
    ├── containerd/
    ├── kubernetes_packages/
    ├── control_plane/
    ├── helm/
    └── cilium/
```

## Roles

### k8s_prerequisites

Configures the operating system requirements needed by Kubernetes, including kernel modules, sysctl parameters, DNS configuration and node hostname resolution.

### containerd

Installs and configures containerd as the Kubernetes container runtime.

### kubernetes_packages

Installs the Kubernetes packages used by the cluster:

* kubeadm
* kubelet
* kubectl

The Kubernetes package version is pinned to prevent unexpected upgrades.

### control_plane

Generates the kubeadm configuration and initializes the Kubernetes control-plane node.

### helm

Installs the Helm client used to manage Kubernetes applications.

### cilium

Installs Cilium as the Kubernetes CNI.

Cilium uses VXLAN tunneling and cluster-pool IPAM with the `10.200.0.0/16` Pod network.

## Running the Playbooks

Before provisioning the cluster, verify SSH connectivity:

```bash
ansible k8s_cluster -i inventory.ini -m ping
```

Prepare all Kubernetes nodes:

```bash
ansible-playbook -i inventory.ini prepare-nodes.yml
```

Initialize the control plane:

```bash
ansible-playbook -i inventory.ini bootstrap-control-plane.yml
```

Install Helm:

```bash
ansible-playbook -i inventory.ini install-helm.yml
```

Install Cilium:

```bash
ansible-playbook -i inventory.ini install-cilium.yml
```

Join the worker nodes:

```bash
ansible-playbook -i inventory.ini join-workers.yml
```

## Cluster Health Check

`health-check.yml` can be used after a system restart or before deploying applications.

Run:

```bash
ansible-playbook -i inventory.ini health-check.yml
```

The playbook checks:

* containerd service
* kubelet service
* SOCKS proxy service
* Kubernetes API availability
* Kubernetes node status
* kube-system Pods
* Pod container readiness
* Cilium IPAM allocation

A healthy cluster should finish with no failed or unreachable hosts.

Example:

```text
controller   failed=0   unreachable=0
worker1      failed=0   unreachable=0
worker2      failed=0   unreachable=0
```

## Resetting the Cluster

The reset playbook removes the current kubeadm and CNI state:

```bash
ansible-playbook -i inventory.ini reset-cluster.yml
```

This playbook should only be used when rebuilding the cluster. It is not required after a normal reboot.

## Notes

SSH private keys, passwords, tokens and other credentials must not be committed to the repository.

After a normal system restart, the cluster does not need to be initialized again. Once the physical hosts and virtual machines are running, use `health-check.yml` to verify that the cluster has recovered correctly.

## Shared GitLab Runner

`playbooks/gitlab-runner.yml` maintains one shared GitLab Runner container on
the project server. It uses the Docker executor; teammates use it through
GitLab project permissions and do not need direct server access.

The `gitlab_runner` role creates the Compose directory, renders `compose.yml`,
starts or reconciles the container, and verifies its running state. Runner
configuration persists in the Docker volume `gitlab-runner-config`.

Use the separate project-server inventory for this playbook:

```bash
cp inventory/devops-server.ini.example inventory/devops-server.ini

ansible-playbook -i inventory/devops-server.ini \
  --syntax-check playbooks/gitlab-runner.yml

ansible-playbook -i inventory/devops-server.ini \
  playbooks/gitlab-runner.yml
```

`inventory/devops-server.ini` is ignored by Git. Never commit a real server
address, private-key path, password, or Runner token.

Runner registration is a separate manual step because the GitLab
authentication token must not be stored in Git:

```bash
docker exec -it gitlab-runner gitlab-runner register
docker exec gitlab-runner gitlab-runner verify
```

The Runner mounts `/var/run/docker.sock` so CI can build images. Docker-socket
access is highly privileged; use this Runner only for trusted project code.

## Argo CD and GitOps

`playbooks/argocd.yml` runs the `argocd` role. It installs the pinned Argo CD
release, creates Nexus image-pull credentials, rewrites Argo CD image sources
to the Nexus Docker group, and waits for the workloads to become available.

The complete sandbox runbook, verification commands, secure UI tunnel,
troubleshooting, and production Kubeadm adaptation are in the [Argo CD setup
manual](../docs/ansible/argocd-setup.md).

The Minikube sandbox role is separate: `playbooks/minikube-sandbox.yml` and
`roles/minikube_sandbox/`. Production Kubeadm provisioning uses the cluster
playbooks documented above; do not apply Minikube-specific variables to the
three-node production cluster.
