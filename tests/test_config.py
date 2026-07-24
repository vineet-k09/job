import os

from src.config import AppConfig, load_config


def test_load_config():
    """Verify that the default config file exists and loads cleanly."""
    config_path = "config.yaml"
    assert os.path.exists(config_path), "Default config.yaml should exist."

    cfg = load_config(config_path)
    assert isinstance(cfg, AppConfig)
    assert len(cfg.job_preferences.roles) > 0
    assert cfg.scoring.weights.role_match > 0
