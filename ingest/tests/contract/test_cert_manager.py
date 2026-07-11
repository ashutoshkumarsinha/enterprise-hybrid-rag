"""cert-manager production PKI contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CM_DIR = REPO_ROOT / "infra" / "k8s" / "cert-manager"
CM_DOC = REPO_ROOT / "infra" / "docs" / "CERT_MANAGER.md"
HELM_CERT_INGRESS = REPO_ROOT / "deploy/helm/hybrid-rag/templates/certificate-ingress-tls.yaml"
HELM_CERT_QUERY = REPO_ROOT / "deploy/helm/hybrid-rag/templates/certificate-query-mtls.yaml"
HELM_CERT_CLIENT = REPO_ROOT / "deploy/helm/hybrid-rag/templates/certificate-ingress-client.yaml"
HELM_CA_BOOT = REPO_ROOT / "deploy/helm/hybrid-rag/templates/cert-manager-ca-bootstrap.yaml"


def test_cert_manager_infra_manifests_exist() -> None:
    assert CM_DOC.is_file()
    for name in (
        "install.sh",
        "healthcheck.sh",
        "sync-root-ca.sh",
        "cluster-issuer-selfsigned.yaml",
        "ca-certificate.yaml",
        "cluster-issuer-ca.yaml",
        "cluster-issuer-letsencrypt-prod.yaml",
    ):
        assert (CM_DIR / name).is_file(), name


def test_helm_certificate_templates_exist() -> None:
    for path in (HELM_CERT_INGRESS, HELM_CERT_QUERY, HELM_CERT_CLIENT, HELM_CA_BOOT):
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "cert-manager.io/v1" in text
        assert "kind: Certificate" in text


def test_helm_template_renders_certificates() -> None:
    import shutil

    if not shutil.which("helm"):
        text = HELM_CERT_QUERY.read_text(encoding="utf-8")
        assert "hybrid-rag-query-mtls" in text or "query.mtls.certSecret" in text
        return
    result = subprocess.run(
        [
            "helm",
            "template",
            "hybrid-rag",
            str(REPO_ROOT / "deploy/helm/hybrid-rag"),
            "-f",
            str(REPO_ROOT / "deploy/helm/hybrid-rag/values-prod.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        assert result.returncode == 0, result.stderr
        return
    out = result.stdout
    assert "kind: Certificate" in out
    assert "hybrid-rag-query-mtls" in out
    assert "hybrid-rag-ingress-mtls-client" in out
