from pathlib import Path

from infra import DEPLOYMENT_CONFIG, DeploymentConfig, load_deployment_config


def test_deployment_config_defaults_to_requirements_txt() -> None:
    """The repository config should expose the canonical requirements file."""

    assert DEPLOYMENT_CONFIG.requirements_file == "requirements.txt"


def test_load_deployment_config_supports_custom_file(tmp_path: Path) -> None:
    """Custom TOML files should override version and requirements paths."""

    config_path = tmp_path / "deployment.toml"
    config_path.write_text(
        """
[python]
version = "3.12"
requirementsFile = "alt.txt"
""".strip()
    )

    config = load_deployment_config(config_path)
    assert isinstance(config, DeploymentConfig)
    assert config.python_version == "3.12"
    assert config.requirements_file == "alt.txt"
