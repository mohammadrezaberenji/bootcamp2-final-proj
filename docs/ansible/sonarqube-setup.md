# SonarQube setup and CI quality gate

This manual describes the TaskFlow sandbox SonarQube installation and the
GitLab CI static-analysis quality gate. SonarQube analyzes source code; it is
not a replacement for dependency, container-image, or Kubernetes manifest
scanning.

## What the Ansible role manages

`ansible/playbooks/sonarqube.yml` runs `roles/sonarqube` on the shared server.
The role:

1. Validates that the PostgreSQL password is available from Ansible Vault.
2. Configures the Linux kernel limits required by SonarQube.
3. Renders a private Docker Compose file in the remote user's SonarQube
   directory.
4. Starts SonarQube and its dedicated PostgreSQL database, then waits for the
   API to report `UP`.

The sandbox override is
`ansible/inventory/group_vars/devops_server/sonarqube.yml`. It binds the web
port to the Docker bridge address (`172.17.0.1:9000`) so GitLab Runner job
containers can reach it through `host.docker.internal`, without publishing the
dashboard on every server interface.

## Secrets and prerequisites

The encrypted Vault file contains `sonarqube_postgres_password`. This is the
database credential; it is different from both the Vault password and the
SonarQube analysis token.

Before installation, ensure the target server has Docker and Docker Compose,
and that it can pull the configured SonarQube and PostgreSQL images from
Nexus. The Docker registry configuration must permit the sandbox HTTP Nexus
endpoint. Production must use a TLS-protected registry instead.

Run these commands from the repository's `ansible/` directory on the Ansible
control machine:

```bash
ansible-playbook -i inventory/devops-server.ini \
  --syntax-check playbooks/sonarqube.yml

ansible-playbook -i inventory/devops-server.ini \
  playbooks/sonarqube.yml --ask-vault-pass --ask-become-pass
```

Use `--ask-become-pass` only if the SSH account needs sudo authentication.
Never commit a Vault password, database password, SonarQube token, or Docker
login configuration.

Verify the service on the server:

```bash
docker ps --filter name=sonarqube \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

curl http://172.17.0.1:9000/api/system/status
```

The API response should contain `"status":"UP"`.

## First SonarQube configuration

Open the dashboard through an SSH tunnel from a workstation. On the server,
SonarQube is already reachable on the Docker bridge; no server-side
port-forward is required:

```bash
ssh -N -L 9001:172.17.0.1:9000 <server-user>@<server-host>
```

Open `http://127.0.0.1:9001` on the workstation. Sign in using the initial
administrator account, change its password, create the `TaskFlow` project, and
set its main branch to `develop`.

Create a project analysis token for GitLab CI. In GitLab, add these CI/CD
variables:

| Variable | Value | Protection |
| --- | --- | --- |
| `SONAR_TOKEN` | Project analysis token | Masked; protect it only after the pipeline runs exclusively on protected branches. |
| `SONAR_HOST_URL` | `http://host.docker.internal:9000` | Not secret. |

The GitLab Runner Docker executor must map `host.docker.internal` to the host
gateway. Its runner configuration therefore includes:

```toml
extra_hosts = ["host.docker.internal:host-gateway"]
```

Restart the runner after changing its configuration.

## CI quality gate

`sonar-project.properties` defines the `TaskFlow` project key and scans
`backend` plus `frontend/src`. Backend tests are declared separately and common
generated directories are excluded.

The `sonarqube_check` job in `.gitlab-ci.yml` runs after test jobs and before
image build/publish. It caches the scanner cache, requests complete Git history
with `GIT_DEPTH: "0"`, and uses:

```text
sonar.qualitygate.wait=true
sonar.qualitygate.timeout=300
```

Therefore GitLab waits up to five minutes for the configured Quality Gate. The
job uses `allow_failure: false`, so a failed Quality Gate blocks image build
and publication.

To test safely, push a small source-only commit to the branch being analyzed
and inspect the `sonarqube_check` job log. A successful run reports the
dashboard URL and the Quality Gate result.

## Reports and current scope

The SonarQube `TaskFlow` project dashboard provides:

- bugs, code smells, and maintainability metrics;
- vulnerabilities and Security Hotspots;
- Quality Gate status and branch analysis history;
- issue locations and remediation guidance.

The current pipeline does not publish test coverage. Add Python `pytest-cov`
XML coverage and frontend Vitest LCOV coverage later, then configure their
report paths in `sonar-project.properties`. Add a dedicated tool such as Trivy
later for dependency, image, and Kubernetes/IaC vulnerability scanning.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `Failed to query server version` in CI | Check `SONAR_HOST_URL`, the Runner `extra_hosts` mapping, and `curl http://172.17.0.1:9000/api/system/status` on the server. |
| `You're not authorized to analyze this project` | Verify `sonar.projectKey=TaskFlow` exactly matches the SonarQube project key and replace the CI token if needed. |
| `username is empty` or a secret appears blank | Check the GitLab CI/CD variable scope and protected setting; do not print secret values in logs. |
| SonarQube never becomes ready | Inspect `docker logs sonarqube` and confirm the PostgreSQL container is healthy. Also verify `vm.max_map_count` was applied. |
| Dashboard does not open | Ensure the SSH tunnel is still running and browse `http://127.0.0.1:9001`, not the server address. |

## Production notes

Keep SonarQube private behind TLS and authenticated access. Use a dedicated
database backup plan, a TLS Nexus registry, restricted runner permissions, and
separate protected CI variables for each environment. Review compute and
storage sizing before moving this single-server sandbox design to production.
