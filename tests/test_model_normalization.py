from __future__ import annotations

import config.models as model_config


def test_normalise_model_name_handles_gpt52_variants() -> None:
    """New GPT-5.2 model identifiers should normalise to canonical names."""

    assert model_config.normalise_model_name("gpt-5.2") == model_config.GPT52
    assert model_config.normalise_model_name("gpt-5.2-mini-latest") == model_config.GPT52_MINI
    assert model_config.normalise_model_name("gpt-5.2-nano") == model_config.GPT52_NANO
