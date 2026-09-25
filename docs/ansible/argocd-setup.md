# Argo CD setup manual

This manual installs the project’s pinned Argo CD release with Ansible, makes
its images available through Nexus, and connects it to the TaskFlow GitOps
repository. It describes the current sandbox and how to adapt the same role for
a three-node production cluster.

## What the role manages

`ansible/playbooks/argocd.yml` runs `roles/argocd` for the target hosts. The
role:

1. Creates the `argocd` namespace.
2. Creates the `nexus-pull-credentials` image-pull secret from the runtime
   user's Docker login configuration.
3. Creates Argo CD service accounts with that pull secret before workloads are
   created.
4. Downloads the pinned official manifest, rewrites its image references to the
   Nexus Docker group, and applies it using server-side apply.
5. Waits for Argo CD deployments and its application-controller StatefulSet.

The current sandbox settings are in
`ansible/inventory/group_vars/devops_server/argocd.yml`. They use Argo CD
`v3.5.3` and `nexus.server:8084`. The Nexus endpoint is HTTP for this lab;
production must use a TLS-protected registry.

## Prerequisites

- `kubectl` is installed on the target and can access the cluster through the
  configured kubeconfig.
- The account selected by `kubernetes_admin_user` owns and can read its
  kubeconfig and `~/.docker/config.json`.
- That Docker configuration contains a successful login to the Nexus Docker
  group. It is used to create a Kubernetes secret and must never be committed.
- The cluster nodes can pull from Nexus. In the Minikube sandbox this also
  requires the containerd `hosts.toml` configuration made by the
  `minikube_sandbox` role.
- Ansible can SSH to the selected control-plane host and use privilege
  escalation only when the target needs it.

Check the two important credentials without exposing secret values:

```bash
sudo -u k8s-admin test -r /home/k8s-admin/.kube/config
sudo -u k8s-admin test -r /home/k8s-admin/.docker/config.json
```

## Sandbox installation

Run these commands from the `ansible/` directory on the Ansible control
machine:

```bash
ansible-playbook -i inventory/devops-server.ini \
  --syntax-check playbooks/argocd.yml

ansible-playbook -i inventory/devops-server.ini \
  playbooks/argocd.yml --ask-become-pass
```

Use `--ask-become-pass` only when the remote account requires a sudo password.
Do not use it as `k8s-admin` if that account is intentionally non-sudo.

Verify the installation as the Kubernetes administration account:

```bash
export KUBECONFIG=/home/k8s-admin/.kube/config
kubectl get pods --namespace argocd
kubectl get secret nexus-pull-credentials --namespace argocd
kubectl get applications -n argocd
```

All Argo CD Pods should eventually be `Running` and `Ready`. Image pull errors
such as `no basic auth credentials` normally mean the secret is missing, is in
the wrong namespace, or has not been attached to the service account.

## Open the UI safely

Keep the Argo CD service private and use a temporary tunnel. On the server:

```bash
kubectl --kubeconfig=/home/k8s-admin/.kube/config \
  --namespace=argocd port-forward service/argocd-server 8080:443 \
  --address=127.0.0.1
```

From your workstation, tunnel to that server:

```bash
ssh -N -L 8443:127.0.0.1:8080 <server-user>@<server-host>
```

Then open `https://localhost:8443`. For the initial password:

```bash
kubectl --kubeconfig=/home/k8s-admin/.kube/config \
  -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode; echo
```

Change the initial password after first login. Do not expose port 8080 directly
on the public server.

## GitOps bootstrap

Argo CD deploys from the separate GitOps repository, not directly from the
application repository or from Nexus:

```text
application source -> CI builds and pushes an immutable image to Nexus
CI or a reviewed merge request -> updates image digest in GitOps repository
Argo CD -> detects the Git commit and reconciles the cluster
```

Create a GitLab deploy token with `read_repository` only. Store it as an Argo
CD repository Secret in the `argocd` namespace, not in Git:

```bash
kubectl --kubeconfig=/home/k8s-admin/.kube/config -n argocd \
  create secret generic taskflow-gitops-repo \
  --from-literal=type=git \
  --from-literal=url='https://gitlab.example/group/taskflow-gitops.git' \
  --from-literal=username='<deploy-token-user>' \
  --from-literal=password='<deploy-token-value>' \
  --dry-run=client -o yaml | kubectl --kubeconfig=/home/k8s-admin/.kube/config apply -f -

kubectl --kubeconfig=/home/k8s-admin/.kube/config -n argocd \
  label secret taskflow-gitops-repo \
  argocd.argoproj.io/secret-type=repository --overwrite
```

Apply the repository's `argocd/taskflow-sandbox-application.yaml` once to
bootstrap the `Application`. After that, application manifests belong to the
GitOps repository and Argo CD continuously reconciles them.

## Production: three-node Kubeadm cluster

Do not copy Minikube variables into production. Point the same Argo CD role at
the Kubeadm control-plane inventory group and define only portable variables:

```yaml
kubernetes_admin_user: k8s-admin
kubernetes_admin_home: /home/k8s-admin
kubernetes_kubeconfig: /home/k8s-admin/.kube/config
kubernetes_kubectl_binary: /usr/local/bin/kubectl
```

Before running the role, confirm that this kubeconfig reaches the production
API server and that every node trusts and can reach the TLS-enabled Nexus
registry. Run the playbook against a control-plane node, not every worker.

The current pinned upstream manifest is the standard Argo CD installation; it
is suitable for the sandbox, but it is not automatically an HA design. Before
production, plan the HA installation, resource requests and limits, Pod
Disruption Budgets, backup/recovery, RBAC/SSO, TLS ingress, and an external
secret-management approach. Keep image tags immutable and promote the exact
digest tested in sandbox.

## Troubleshooting

| Symptom | Likely cause and check |
| --- | --- |
| `http: server gave HTTP response to HTTPS client` | A node runtime is treating the lab's HTTP Nexus registry as HTTPS. Fix the container runtime registry configuration; production should use HTTPS instead. |
| `no basic auth credentials` | Recreate `nexus-pull-credentials` in the same namespace as the workload and ensure the service account references it. |
| `Apply failed ... conflict` | Another field manager owns an existing object. Inspect it first. `--force-conflicts` is appropriate only for resources this bootstrap role intentionally takes over. |
| `metadata.annotations: Too long` | Use server-side apply for the large official Argo CD manifest; client-side apply stores an oversized last-applied annotation. |
| Argo CD UI does not open | Check the server-side port-forward and SSH tunnel are both running; browse the workstation's `https://localhost:8443`, not the server's private loopback address. |
