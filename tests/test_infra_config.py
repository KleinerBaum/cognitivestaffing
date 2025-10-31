from pathlib import Path

from infra import DEPLOYMENT_CONFIG, DeploymentConfig, load_deployment_config


def test_deployment_config_defaults_to_install_command() -> None:
    """The repository config should expose the canonical install command."""

    assert DEPLOYMENT_CONFIG.install_command == "pip install ."


def test_load_deployment_config_supports_custom_file(tmp_path: Path) -> None:
    """Custom TOML files should override version and derived install commands."""

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
    assert config.install_command == "pip install -r alt.txt"


def test_load_deployment_config_prefers_install_command(tmp_path: Path) -> None:
    """Explicit install commands should take precedence over requirements entries."""

    config_path = tmp_path / "deployment.toml"
    config_path.write_text(
        """
[python]
installCommand = "pip install -e .[dev]"
requirements = "ignored.txt"
""".strip()
    )

    config = load_deployment_config(config_path)
    assert isinstance(config, DeploymentConfig)
    assert config.install_command == "pip install -e .[dev]"
