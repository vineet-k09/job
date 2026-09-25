import os

from src.config import AppConfig, load_config


def test_load_config():
    """Verify that the example config file exists and loads cleanly."""
    config_path = "config.example.yaml"
    assert os.path.exists(config_path), "config.example.yaml should exist (it is the committed template)."

    cfg = load_config(config_path)
    assert isinstance(cfg, AppConfig)
    assert len(cfg.job_preferences.roles) > 0
    assert cfg.scoring.weights.role_match > 0
    assert cfg.pipeline.generate_resume is False
    assert cfg.pipeline.ai_resume_path == "/mnt/bridge/dev/personal/resume/resume_vineet_kushwaha_ai.typ"
    assert cfg.pipeline.base_resume_path == "/mnt/bridge/dev/personal/resume/resume_vineet_kushwaha.typ"
