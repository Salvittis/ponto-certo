# Pipeline DevSecOps

`Deploy Blindado` runs on **every push**, on pull requests and by manual dispatch. There are no path filters. Gitleaks, Semgrep, API tests, all three container builds/Trivy scans are independent jobs, so a failure does not cancel the other required checks. All must pass before publication. Only a **push to `main`** can publish and deploy; manual runs and other branches cannot deploy.

## Gates and provenance

- **Gitleaks 8.30.1:** full fetched Git history, built-in rules, exit code 1 on findings. Reports redact 100% of detected secret values. No repository allowlist.
- **Semgrep CE 1.186.0:** the versioned policy in `security/semgrep.yml` rejects dynamic execution, unsafe deserialization, shell subprocesses, disabled TLS validation and production debug mode. Scans Python, JavaScript and TypeScript. `--strict --error` makes findings and scanning errors blocking. No remote ruleset or Semgrep account is needed; usage metrics are disabled. This finite policy does not prove the absence of every weakness.
- **Trivy 0.76.2:** all three production images (API, local LLM and Caddy HTTPS proxy), HIGH and CRITICAL vulnerabilities and secrets. No `ignore-unfixed`, severity downgrade or global suppression. A new database entry may block a previously valid build; fix/upgrade the affected dependency and rerun.
- **Regression tests:** install the same `requirements.lock` as the runtime image, then install `requirements-dev.txt` constrained by that lock and run `pip check` before `python -m pytest tests -q`. There is no alternate pytest version when the development requirements are present. These test app behavior with controlled dependencies; successful CI is not a substitute for the real LLM/public URL test required for the final delivery.
- Actions use verified full commit SHAs. Scanner images use release tags plus immutable registry digests. See `security/tool-images.env`. Version/digest verification date: 19 November 2026.
- The API, LLM and HTTPS proxy Linux amd64 images are built **once**, exported as Docker archives, scanned and handed to the publication job as run-scoped artifacts. That job loads and pushes those archives without rebuilding. Deployment receives the registry **digest**, plus the source commit SHA.
- The proxy is built from `Dockerfile.proxy`, using the standard Caddy 2.11.9 modules with the pinned dependency corrections in `proxy/go.mod` and `proxy/go.sum`. It is scanned, published as `ponto-certo-proxy` and deployed by digest exactly like the app/LLM. The real `deploy/Caddyfile` is also validated by the built image as UID/GID 10001, with a read-only filesystem, dropped capabilities and no network access.
- Build artifacts expire after 2 days to reduce storage. Sanitized scanner/test reports remain for 14 days; copy the final rubric evidence into the delivery before expiry.

## Credentials and deployment

Deployment targets the Ponto Certo Azure VM, isolated in its own academic subscription/resource group. The `production` GitHub Environment holds these values:

| Kind | Name | Purpose |
| --- | --- | --- |
| Secret | `AZURE_CLIENT_ID` | Client ID of the federated deploy identity |
| Secret | `AZURE_TENANT_ID` | Microsoft Entra tenant ID |
| Secret | `AZURE_SUBSCRIPTION_ID` | Academic Azure subscription ID |
| Secret | `METRICS_TOKEN` | Server-side credential protecting the metrics endpoint |
| Secret, optional | `SPTRANS_TOKEN` | Server-side SPTrans credential; required before selecting live data |
| Variable | `AZURE_RESOURCE_GROUP` | Resource group containing only this project's resources |
| Variable | `AZURE_VM_NAME` | Exact VM created by Terraform |
| Variable | `PUBLIC_URL` | Public HTTPS endpoint used for post-deploy checks |
| Variable, optional | `DATA_MODE` | Defaults to `demo`; use `live` only after supplying/validating SPTrans access |

`azure/login` uses GitHub OIDC and a short-lived token; no Azure client secret, private SSH key, or cloud account password is stored in GitHub. Only the deploy job receives `id-token: write`. Configure the Azure federated credential with issuer `https://token.actions.githubusercontent.com`, audience `api://AzureADTokenExchange` and subject `repo:Salvittis/ponto-certo:environment:production`. Change the subject deliberately if repository ownership/name changes. Limit the GitHub Environment's deployment branch to `main`; do not configure a required human reviewer when automatic deployment after the checks is intended.

The deploy identity needs a custom role scoped to the **specific VM**, containing only VM read and the Run Command operations actually used by `scripts/deploy-azure.py`. It does not need subscription-wide Contributor or permission to create/update networks, identities, role assignments or other VMs. Provisioning Terraform uses a separate authorized operator identity. Run Command operates through the Azure control plane; it requires neither a public SSH port nor credentials in an image. Its effective access to the guest is privileged, so keep environment and workflow changes restricted.

The publish job alone receives `packages: write` through GitHub's short-lived `GITHUB_TOKEN`; the deploy job receives `packages: read`. Security checks need only `contents: read`. Newly created GHCR packages may remain private even when the source repository is public. Deployment sends that job's short-lived `GITHUB_TOKEN` as `REGISTRY_TOKEN` through a protected Run Command parameter; `REGISTRY_USERNAME` is the public GitHub actor. The guest creates a temporary Docker configuration directory (0700), logs in using `--password-stdin`, pulls the approved digests, and removes the directory on success or failure. It unsets the token before pulling and never writes it into runtime.env, release manifests, Terraform, images or logs. The VM does not retain registry credentials; already-pulled images survive a normal reboot. A new host needs a new authenticated, approved deployment. Public package visibility can later remove the need for authenticated pulls; the source repository and MVP remain public as required. `scripts/deploy-azure.py` owns deployment and the public readiness/version check. It receives all three immutable image refs (`IMAGE_REF`, `LLM_IMAGE_REF`, `PROXY_IMAGE_REF`), `APP_REVISION`, the configuration table above and the Azure CLI session established by OIDC.

Runtime metrics/SPTrans secrets and the ephemeral registry token are passed only to the deployment step. The deploy script transfers them through Azure Managed Run Command `protectedParameters` and writes a protected server-side runtime file; they do not belong in the public script body or ordinary parameters. They must never enter build arguments, frontend code, screenshots or command output. `AZURE_CORE_OUTPUT=none` suppresses incidental Azure CLI output; any machine-readable response requested by the deploy script must be handled without printing secrets or the full Run Command payload. Demo mode must remain visibly synthetic until live data is validated.

Production publication requires all three Dockerfiles, dependency locks, tests, deploy script, Terraform resources, a usable academic subscription, federated identity/role assignment, permission for the job token to read its repository-linked GHCR packages and the GitHub Environment values. The workflow file alone is **configured**, not proof that authentication, provisioning, a run or deployment succeeded. Credit eligibility, remaining balance and the maintenance budget must be verified before resource creation; a student offer is not proof of unlimited free use.

## Reproducing locally

Docker must be running. From the repository root:

```bash
scripts/check-security.sh gitleaks
scripts/check-security.sh semgrep
docker build --platform linux/amd64 -t ponto-certo:check .
docker save -o /tmp/ponto-certo-app.tar ponto-certo:check
scripts/check-security.sh image /tmp/ponto-certo-app.tar
docker build --platform linux/amd64 -f Dockerfile.llm -t ponto-certo-llm:check .
docker save -o /tmp/ponto-certo-llm.tar ponto-certo-llm:check
scripts/check-security.sh image /tmp/ponto-certo-llm.tar
docker build --platform linux/amd64 -f Dockerfile.proxy -t ponto-certo-proxy:check .
docker save -o /tmp/ponto-certo-proxy.tar ponto-certo-proxy:check
scripts/check-security.sh image /tmp/ponto-certo-proxy.tar
```

Each image scan replaces `reports/security/trivy-image.json`; copy it to a component-specific evidence file before scanning the next image. A missing scanner image/database, network error or invalid scan also fails the command. Gitleaks uses full Git history when a repository exists; before `git init`, it scans the working directory.

## Proxy dependency remediation

The [first CI run](https://github.com/Salvittis/ponto-certo/actions/runs/44515603367/job/135530687329) rejected the original official Caddy image with **two HIGH vulnerabilities and zero secret findings**. Its Alpine 3.24.4 OS packages had no HIGH/CRITICAL findings. The vulnerable dependencies were:

| CVE | Original dependency | Correction in the rebuilt proxy |
| --- | --- | --- |
| CVE-2026-116587 | `github.com/go-jose/go-jose/v3 v3.0.5` | Remove the v3 dependency through the official Smallstep certificates migration commit `cddde30af36e238f156bb557bfd1f11a05ffe6f9`; use `go.step.sm/crypto v0.92.0` and `go-jose/v4 v4.1.9` |
| CVE-2026-78661 | `golang.org/x/net v0.60.0` | Pin `golang.org/x/net v0.62.0` |

The [go-jose advisory](https://github.com/go-jose/go-jose/security/advisories/GHSA-mgcc-cww5-fp2q) has no patched v3 release; merely rebuilding the original dependency graph would retain the finding. The [official migration commit](https://github.com/smallstep/certificates/commit/cddde30af36e238f156bb557bfd1f11a05ffe6f9) changes the dependency to the maintained major version. This dependency snapshot is upstream code pinned to a commit and is not represented as a released Smallstep version. The top-level Caddy stays at released **2.11.9**. Go **1.27.4**, the build image, runtime image and all module checksums are pinned. The old runtime Caddy binary is replaced by the rebuilt binary; the build toolchain and module cache do not enter the runtime image.

There is no CVE suppression, altered threshold or scanner exception. The following run must establish that compilation, configuration validation and the unchanged Trivy gate pass; see `docs/STATUS-CLOUD.md` for actual execution evidence. Updating upstream dependencies can affect compatibility, which is why configuration validation and public HTTPS/assistant tests remain required.

## Controlled blocked/corrected demonstration

The helper below writes one Python function containing an unsafe operation. It is static test data, carries no credential, and is never imported by the application. The function must never be executed. The normal Semgrep policy rejects it.

1. On a dedicated evidence branch, run `python3 scripts/security-demo.py introduce`.
2. Commit the generated `security/controlled_finding.py` and push. Wait for `Semgrep / security policy` to fail with `python-no-dynamic-evaluation`; the run must not deploy. Save the run URL, commit, redacted report and a legible screenshot.
3. Run `python3 scripts/security-demo.py correct`, commit its removal and push. The unchanged policy must pass. Save the second run URL/commit/report.
4. Merge or apply the clean approved version to `main`. The normal run must pass every gate and automatically deploy; record its run URL, source SHA, image digests, public URL and functional checks.

No `continue-on-error`, security job disabling, exclusion of the controlled fixture, or rule weakening is part of the correction. Never use a real credential for the demonstration. This page describes the procedure; actual run evidence belongs in `docs/STATUS-CLOUD.md` and the Cloud PDF.

## Primary references

- [GitHub Actions: secure use and immutable action pinning](https://docs.github.com/en/actions/reference/security/secure-use)
- [Docker build-push-action](https://github.com/docker/build-push-action)
- [Gitleaks official repository](https://github.com/gitleaks/gitleaks)
- [Semgrep CLI and blocking exit codes](https://docs.semgrep.dev/cli-reference)
- [Trivy image scanning options](https://trivy.dev/docs/latest/references/configuration/cli/trivy_image/)

- [Azure Login: OIDC configuration](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Azure Login official action](https://github.com/Azure/login)
- [Azure Managed Run Command and protected parameters](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed)
