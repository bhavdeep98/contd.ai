{{/*
Expand the name of the chart.
*/}}
{{- define "contd.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "contd.fullname" -}}
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
{{- define "contd.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "contd.labels" -}}
helm.sh/chart: {{ include "contd.chart" . }}
{{ include "contd.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "contd.selectorLabels" -}}
app.kubernetes.io/name: {{ include "contd.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "contd.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "contd.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "contd.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
postgresql://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "contd.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else }}
postgresql://{{ .Values.contd.database.user }}:$(DATABASE_PASSWORD)@{{ .Values.contd.database.host }}:{{ .Values.contd.database.port }}/{{ .Values.contd.database.name }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "contd.redisUrl" -}}
{{- if .Values.redis.enabled }}
redis://{{ include "contd.fullname" . }}-redis-master:6379
{{- else }}
redis://{{ .Values.contd.redis.host }}:{{ .Values.contd.redis.port }}
{{- end }}
{{- end }}
