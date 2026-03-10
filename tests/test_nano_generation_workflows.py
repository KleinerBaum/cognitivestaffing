from __future__ import annotations

import config.models as model_config


def test_core_workflow_tasks_resolve_to_nano_in_strict_mode() -> None:
    model_config.configure_models(reasoning_effort="minimal", strict_nano_only=True)

    for task in (
        model_config.ModelTask.EXTRACTION,
        model_config.ModelTask.FOLLOW_UP_QUESTIONS,
        model_config.ModelTask.JOB_AD,
        model_config.ModelTask.INTERVIEW_GUIDE,
        model_config.ModelTask.PROFILE_SUMMARY,
        model_config.ModelTask.EXPLANATION,
    ):
        assert model_config.get_model_for(task) == model_config.GPT51_NANO


def test_export_related_tasks_keep_nano_family_across_modes() -> None:
    model_config.configure_models(reasoning_effort="minimal", strict_nano_only=True)
    quick_job_ad = model_config.get_model_for(model_config.ModelTask.JOB_AD)
    quick_interview = model_config.get_model_for(model_config.ModelTask.INTERVIEW_GUIDE)

    model_config.configure_models(reasoning_effort="low", strict_nano_only=True)
    precise_job_ad = model_config.get_model_for(model_config.ModelTask.JOB_AD)
    precise_interview = model_config.get_model_for(model_config.ModelTask.INTERVIEW_GUIDE)

    assert quick_job_ad == precise_job_ad == model_config.GPT51_NANO
    assert quick_interview == precise_interview == model_config.GPT51_NANO
