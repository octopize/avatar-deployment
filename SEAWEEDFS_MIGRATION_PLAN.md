# SeaweedFS Helm Chart Migration Plan

## Problem

The current SeaweedFS deployment uses the **Bitnami helm chart** (`oci://registry-1.docker.io/bitnamicharts/seaweedfs` v4.5.4), managed via Pulumi in `scaleway-env-copy/`. This has two issues:

1. **Bitnami legacy dependency** — MariaDB sub-dependency uses `bitnamilegacy/mariadb`, which requires paid security updates
2. **Outdated** — Bitnami wraps the upstream SeaweedFS chart with their own conventions, adding lag. SeaweedFS upstream moves fast.

## Proposed Approach

Integrate the **official SeaweedFS helm chart** (v4.17.0 from `https://seaweedfs.github.io/seaweedfs/helm`) as a **sub-chart dependency** of our existing `services-api-helm-chart/`, similar to how authentik is already integrated. This brings SeaweedFS under the same Helm release as the rest of Avatar.

### Key Differences: Bitnami → Official Chart

| Feature | Bitnami (current) | Official (target) |
|---|---|---|
| S3 gateway | Separate `s3` component | Standalone `s3` deployment or embedded in filer |
| IAM service | Dedicated `iam` pod (separate endpoint) | **Embedded in S3 pod** (`-iam=true`, default). Same port 8333, standard AWS IAM API. |
| Dynamic user creation | Init container hack via `weed shell s3.configure` (users lost on restart) | Native: embedded IAM API + filer-persisted identities (survive restarts). Static + dynamic configs now **coexist** via `MergeS3ApiConfiguration()`. |
| Filer DB | MariaDB sub-chart | LevelDB2 (default, embedded) or external DB via env vars |
| Admin pod | Not available | New `admin` component (monitoring/management) |
| Worker pod | Not available | New `worker` component (vacuum, volume balance, erasure coding) |
| Volume config | `dataVolumes[]` array | `dataDirs[]` array |
| Image | Custom `quay.io/octopize/seaweedfs` | Default `chrislusf/seaweedfs` (or custom override) |
| CORS/allowedOrigins | CLI args on s3 and filer | Via `extraArgs` on s3/filer |
| Super user creation | Init container with `weed shell` | `s3.credentials.admin` in values + `s3.enableAuth: true` |

### Critical Migration Decisions

1. **Filer backend**: Drop MariaDB entirely, use **LevelDB2** (default, zero-dependency). The filer metadata store doesn't need a full RDBMS.
2. **IAM / Dynamic Credential Management** (see detailed analysis below)
3. **Super user creation**: Use `s3.credentials.admin.accessKey/secretKey` for the static admin + embedded IAM for dynamic users.
4. **CORS**: Set via `s3.extraArgs: ["-allowedOrigins=..."]` and `filer.extraArgs: ["-allowedOrigins=..."]`.

### Deep Dive: IAM & Dynamic Credential Management

#### Background (your issue #6442)

The Avatar API dynamically creates S3 users on-the-fly when users register. The old setup had a workaround: an init container runs `weed shell` to create a "power_user" admin via `s3.configure`, because using the static config file and dynamic `s3.configure` was mutually exclusive — dynamic users would disappear on S3 container restart, and static config reload would wipe dynamic users.

#### What changed in SeaweedFS since issue #6442

**Good news: this has been fundamentally fixed in the current codebase (v4.17).** The S3 API server now supports **coexistence of static and dynamic identities** via a proper merge mechanism:

1. **`MergeS3ApiConfiguration()`** (in `auth_credentials.go`): When a static config file is loaded, identities are marked `IsStatic: true` and tracked in `staticIdentityNames`. When dynamic config is loaded from the filer, the merge function:
   - **Preserves all static identities** (they are immutable, cannot be overwritten by dynamic config)
   - **Adds/updates dynamic identities** from the filer credential store
   - Skips any dynamic identity that would conflict with a static name

2. **Embedded IAM API** (`-iam=true`, default in v4.17): The S3 gateway now embeds a full IAM API on the same port. This means:
   - **No separate IAM pod needed** — the S3 pod itself serves IAM requests at the same endpoint
   - Supports `CreateUser`, `CreateAccessKey`, `AttachUserPolicy`, `ListUsers`, etc.
   - The `accessControlEndpointHost` in Avatar API can point to the **same S3 endpoint** (port 8333)

3. **Credential stores**: The filer-based store (`filer_etc`) persists dynamic users to the filer's metadata. Users created via IAM API → saved to filer → survive S3 restarts. The S3 server subscribes to filer metadata changes (`subscribeMetaEvents` in `auth_credentials_subscribe.go`) and reloads config automatically on IAM directory changes.

4. **`-iam.readOnly=true`** (default): IAM write operations are disabled by default. For Avatar's use case (dynamic user creation), we need to set `-iam.readOnly=false` via `s3.extraArgs: ["-iam.readOnly=false"]`.

#### Recommended approach

- **Static admin**: Use `s3.enableAuth: true` + `s3.credentials.admin.accessKey/secretKey` in the Helm values. This creates the admin identity via the chart's S3 secret, marked as static/immutable.
- **Dynamic users**: The Avatar API uses the admin credentials to call the embedded IAM API (same S3 endpoint, port 8333) to create per-user credentials dynamically. These are stored in the filer and survive restarts.
- **No more init container hack**: The `create-super-user` init container that ran `weed shell s3.configure` is no longer needed. The chart natively creates the admin via `s3-secret.yaml`.
- **No more `wait-for-master`/`wait-for-filer` init containers**: The chart's readiness probes handle startup ordering.
- **IAM endpoint**: Set `accessControlEndpointHost` to the **same S3 service** (e.g., `http://avatar-seaweedfs-s3:8333`). The embedded IAM API serves on the same port.
- **Enable writable IAM**: Add `-iam.readOnly=false` to `s3.extraArgs` so the Avatar API can create users.

#### Remaining risks

- **Verify Avatar API IAM client compatibility**: The Avatar API currently calls an IAM endpoint. Need to confirm it uses standard AWS IAM API calls (CreateUser, CreateAccessKey, etc.) which the embedded IAM supports, not a custom SeaweedFS-specific API.
- **Filer persistence for IAM data**: Dynamic identities are stored in the filer under `/etc/iam/`. With LevelDB2 as the filer backend, this data lives on the filer's PVC. Ensure the filer PVC is properly configured and backed up.

## Todos

### 1. Add SeaweedFS as sub-chart dependency
- Edit `services-api-helm-chart/Chart.yaml` to add:
  ```yaml
  - name: seaweedfs
    version: 4.17.0
    repository: https://seaweedfs.github.io/seaweedfs/helm
    condition: seaweedfs.enabled
  ```
- Run `helm dependency update` to pull the chart

### 2. Configure SeaweedFS values in values.yaml
Add a `seaweedfs:` section to `services-api-helm-chart/values.yaml` with:

- **Global**: Custom image (quay.io/octopize/seaweedfs if still needed), pull secrets
- **Master**: 1 replica, `volumeSizeLimitMB` matching current (100MB), nano resources, PVC storage
- **Volume**: 1 replica, PVC-based `dataDirs` with configurable size (replaces `dataVolumes`), resource limits matching current (256m-375m CPU, 512Mi-1Gi memory)
- **Filer**: 1 replica, LevelDB2 (default — drop MariaDB), resource limits matching current, CORS via extraArgs
- **S3**: enabled, `enableAuth: true`, credentials from values (admin access/secret key), CORS via extraArgs
- **Admin**: enabled, connects to master for monitoring/management
- **Worker**: enabled, jobs: vacuum + volume_balance + erasure_coding (automated maintenance)
- **Disabled**: sftp, cosi, allInOne, certificates/security (not currently used)

### 3. Update Pulumi integration (avatar.ts / storage.ts values)
Update the Pulumi values passed to the Avatar helm chart to include the new `seaweedfs:` sub-chart configuration:

- Map existing Pulumi config vars to new chart structure
- Remove `seaweedfsIamEndpoint` references (IAM pod is gone)
- Change `storageEndpointHost` to point to the sub-chart S3 service name (will be `avatar-seaweedfs-s3` instead of standalone `seaweedfs-s3`)
- Update `accessControlEndpointHost` — investigate if Avatar API still needs a separate IAM endpoint or if it can use S3 auth directly

### 4. Handle S3 credentials and auth
- Use `s3.enableAuth: true` + `s3.credentials.admin.accessKey/secretKey` in values for the **static admin** identity
- The chart's `s3-secret.yaml` template auto-generates the identity JSON config from these credentials
- **Enable writable embedded IAM**: Add `-iam.readOnly=false` to `s3.extraArgs` so Avatar API can dynamically create per-user credentials via the standard AWS IAM API (CreateUser, CreateAccessKey, etc.)
- Dynamic users are stored in the filer's `/etc/iam/` directory and survive S3 pod restarts
- Remove the `create-super-user` init container — the chart handles admin creation natively
- Remove `wait-for-master` and `wait-for-filer` init containers — the chart's own readiness probes handle ordering
- Create a Secret template if we want to avoid plain-text credentials in values (recommended)

### 5. Handle CORS configuration
- Add `s3.extraArgs: ["-allowedOrigins=<webClientUrl>,http://localhost:3000"]`
- Add `filer.extraArgs: ["-allowedOrigins=<webClientUrl>,http://localhost:3000"]`
- These replace the custom `args` arrays in the Bitnami config

### 6. Handle service naming and IAM endpoint
The sub-chart services will be prefixed with the parent release name. For a release named `avatar`:
- Master: `avatar-seaweedfs-master` (port 9333)
- Filer: `avatar-seaweedfs-filer` (port 8888)  
- S3: `avatar-seaweedfs-s3` (port 8333)
- **IAM**: Same as S3 — embedded IAM API on port 8333 (no separate pod/service)

Update all references in:
- `values.yaml`: `storageEndpointHost`, `storageEndpointInternalHost`
- `values.yaml`: `accessControlEndpointHost` → point to S3 service (same endpoint, port 8333)
- `api-config-map.yaml`: if it references SeaweedFS service names
- Pulumi `avatar.ts`: update endpoint construction, remove `seaweedfsIamEndpoint` (use S3 endpoint for both)

### 7. Add admin and worker pods (modernization)
- **Admin** (`admin.enabled: true`): Management UI/API for SeaweedFS cluster health, volume balancing, etc.
- **Worker** (`worker.enabled: true`): Automated maintenance — vacuum (reclaim space), volume balance (distribute data evenly), erasure coding
- Configure worker job types and concurrency limits

### 8. Validate and test
- Run `just lint` to validate the chart renders correctly
- Run `just template` with representative values to verify all templates render
- Verify service names and ports match what the Avatar API expects
- Test with a local/dev cluster if possible

## Risk Assessment

- **Avatar API IAM client compatibility**: The Avatar API calls `accessControlEndpointHost` for IAM operations. Need to verify it uses standard AWS IAM API calls (CreateUser, CreateAccessKey, AttachUserPolicy) which the embedded IAM supports. If it uses SeaweedFS-specific `s3.configure` shell commands instead, the API code would need updating.
- **Filer PVC for IAM persistence**: Dynamic identities are stored in the filer under `/etc/iam/`. With LevelDB2, this lives on the filer PVC. Must ensure `filer.enablePVC: true` with adequate storage and backup strategy.
- **Service name changes**: All internal references (storageEndpointHost, accessControlEndpointHost, etc.) must be updated to the new sub-chart naming convention.
- **LevelDB2 migration**: If the filer currently has data in MariaDB, we need a data migration strategy. For fresh deployments this is a non-issue.
- **Chart version pinning**: Pin to `4.17.0` initially, but the official chart moves fast — we'll need a strategy for staying current.
- **`-iam.readOnly=false` security**: Enabling writable IAM on the S3 endpoint means any client with admin credentials can create/modify users. This is the intended behavior for Avatar but should be documented.

## Files to Create/Modify

| File | Action |
|---|---|
| `services-api-helm-chart/Chart.yaml` | Add seaweedfs dependency |
| `services-api-helm-chart/values.yaml` | Add seaweedfs: section with full config |
| `scaleway-env-copy/src/storage.ts` | Update to pass seaweedfs sub-chart values |
| `scaleway-env-copy/src/avatar.ts` | Update endpoint references |
| `scaleway-env-copy/src/avatar-config.ts` | May need new config vars, remove mariadb ones |
| `scaleway-env-copy/Pulumi.*.yaml` | Update config keys (remove mariadb, add new ones) |
