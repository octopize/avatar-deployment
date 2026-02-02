## Plan: Add SeaweedFS Subchart to services-api-helm-chart

This plan integrates the Bitnami SeaweedFS Helm chart as a dependency subchart, exposing relevant configuration options and ensuring Apache 2.0 license compliance.

### Steps

1. **Update [Chart.yaml](services-api-helm-chart/Chart.yaml) with SeaweedFS dependency** — Add a `dependencies` section referencing `oci://registry-1.docker.io/bitnamicharts/seaweedfs` version `6.x.x` with a `seaweedfs.enabled` condition.

2. **Extend [values.yaml](services-api-helm-chart/values.yaml) with SeaweedFS configuration** — Add a `seaweedfs:` section with these configurable options:
   - `enabled: false` toggle
   - `image.registry`, `image.repository`, `image.tag` (defaults matching Pulumi script)
   - `global.security.allowInsecureImages: true`
   - `storageAdminAccessKeyId`, `storageAdminSecretAccessKey` as plain values
   - `storageSizeInGi: 100` and `nbVolumesPerKubernetesVolume: 100`
   - `volumeSizeLimitMB: 100`
   - `s3.enabled: true`, `s3.resourcesPreset: small`
   - `s3.initContainers.waitImage: curlimages/curl:8.8.0` (configurable with default)
   - `s3.initContainers.extraInitContainers: []` (list of additional initContainers to append after the default wait-for-master, wait-for-filer, and create-super-user containers)
   - `iam.enabled: true`, `iam.resourcesPreset: nano`
   - `filer.resources` with defaults (1000m CPU, 2Gi memory)
   - `volume.resources` with defaults (1000m CPU, 2Gi memory)
   - `master.resourcesPreset: nano`
   - `mariadb.image.repository`, `mariadb.image.tag`, `mariadb.resourcesPreset: nano`
   - `mariadb.auth.rootPassword`, `mariadb.auth.password` as plain values

3. **Update [_helpers.tpl](services-api-helm-chart/templates/_helpers.tpl) with SeaweedFS endpoint helpers** — Add helper templates:
   - `avatar.seaweedfs.s3Host` → `{{ .Release.Name }}-seaweedfs-s3`
   - `avatar.seaweedfs.s3Port` → `8333`
   - `avatar.seaweedfs.iamHost` → `{{ .Release.Name }}-seaweedfs-iam`
   - `avatar.seaweedfs.iamPort` → `8111`
   - Update `avatar.app_env` to conditionally use these when `seaweedfs.enabled`

4. **Update [api-deployment.yaml](services-api-helm-chart/templates/api-deployment.yaml) environment variables** — Ensure `STORAGE_ENDPOINT_HOST`, `STORAGE_ENDPOINT_PORT`, `ACCESS_CONTROL_ENDPOINT_HOST`, `ACCESS_CONTROL_ENDPOINT_PORT` use the SeaweedFS helpers when enabled, falling back to manual values otherwise.

5. **Add Apache 2.0 license attribution file** — Create `THIRD_PARTY_LICENSES.md` in `services-api-helm-chart/` documenting Bitnami SeaweedFS chart usage with link to source (`https://github.com/bitnami/charts/tree/main/bitnami/seaweedfs`) and Apache 2.0 license.
