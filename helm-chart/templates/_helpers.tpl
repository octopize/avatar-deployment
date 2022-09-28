{{/*
Expand the name of the chart.
*/}}
{{- define "avatar.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "avatar.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "avatar.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "avatar.labels" -}}
helm.sh/chart: {{ include "avatar.chart" . }}
{{ include "avatar.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "avatar.selectorLabels" -}}
app.kubernetes.io/name: {{ include "avatar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "avatar.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "avatar.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Define the default app env variables
*/}}
{{- define "avatar.app_env" }}
            - name: ENV_NAME
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: ENV_NAME
            - name: CELERY_BROKER_URL
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: CELERY_BROKER_URL
            - name: CELERY_RESULT_BACKEND
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: CELERY_RESULT_BACKEND
            - name: BASE_API_URL
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: BASE_API_URL
            - name: IS_SENTRY_ENABLED
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: IS_SENTRY_ENABLED
            - name: IS_TELEMETRY_ENABLED
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: IS_TELEMETRY_ENABLED
            - name: DB_HOST
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: DB_HOST
            - name: DB_PORT
              valueFrom:
                configMapKeyRef:
                  name: avatar-config
                  key: DB_PORT
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: api
                  key: db_username
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: api
                  key: db_password
            - name: FILE_ENCRYPTION_KEY
              valueFrom:
                secretKeyRef:
                  name: api
                  key: file_encryption_key
{{- end }}

{{/*
Define the Google Cloud SQL proxy if necessary
*/}}
{{- define "avatar.db_proxy" }}
{{- if .Values.gcp.dbInstanceConnectionName }}
        - name: cloud-sql-proxy
          image: gcr.io/cloudsql-docker/gce-proxy:1.31.2 # make sure the use the latest version
          command:
            - "/cloud_sql_proxy"
            - "-log_debug_stdout"
            # Unused for now
            # - "-enable_iam_login"
            - "-instances={{ .Values.gcp.dbInstanceConnectionName }}=tcp:5432"
          securityContext:
            runAsNonRoot: true
          resources:
            requests:
              memory: "1Gi"
              cpu:    "1"
{{- end }}
{{- end }}