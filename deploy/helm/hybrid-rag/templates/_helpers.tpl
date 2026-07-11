{{/*
Enterprise Hybrid RAG Helm helpers
*/}}
{{- define "hybrid-rag.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "hybrid-rag.fullname" -}}
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

{{- define "hybrid-rag.labels" -}}
app.kubernetes.io/name: {{ include "hybrid-rag.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "hybrid-rag.image" -}}
{{- $registry := .global.imageRegistry -}}
{{- $repo := .repo -}}
{{- $tag := default .global.imageTag .tag -}}
{{- if $registry -}}
{{ printf "%s/%s:%s" $registry $repo $tag }}
{{- else -}}
{{ printf "%s:%s" $repo $tag }}
{{- end -}}
{{- end }}
