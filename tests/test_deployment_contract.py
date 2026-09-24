from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_container_runs_as_non_root_on_cloud_run_port() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()

    assert "USER app" in dockerfile
    assert "--host 0.0.0.0" in dockerfile
    assert "--port ${PORT}" in dockerfile


def test_container_does_not_copy_local_secrets() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text().splitlines()

    assert ".env" in dockerignore
    assert ".env.*" in dockerignore


def test_staging_uses_square_sandbox_and_admin_reporting() -> None:
    staging_config = (
        PROJECT_ROOT / "deploy" / "cloudrun.staging.env.yaml.example"
    ).read_text()

    assert 'SQUARE_ENVIRONMENT: "sandbox"' in staging_config
    assert 'ADMIN_NOTIFICATION_EMAIL: "notifications@example.com"' in staging_config
    assert 'SMTP_HOST: "smtp.gmail.com"' in staging_config
