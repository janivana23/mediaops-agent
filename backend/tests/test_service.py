from __future__ import annotations

import pytest

from app import config, service
from app.models import JobStatus
from app.providers import mock_seedance
from app.providers.base import ProviderError


def _job(session, client, **overrides):
    kwargs = dict(
        client_id=client.id,
        campaign="Test Campaign",
        prompt="a friendly mascot",
        kind="image",
        resolution="512x512",
        reference_image_path=None,
    )
    kwargs.update(overrides)
    job = service.create_job(session, **kwargs)
    return service.run_job(session, job.id)


def test_no_api_key_fails_over_to_mock_provider(session, client, monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    job = _job(session, client)
    assert job.status == JobStatus.DELIVERED.value
    assert job.provider_used == "mock-seedance"
    assert job.actual_cost_cents == 20  # mock-seedance 512x512


def test_budget_rejected_outright_when_even_cheapest_option_too_costly(session, client):
    client.monthly_budget_cents = 5
    session.commit()
    job = _job(session, client)
    assert job.status == JobStatus.REJECTED.value
    assert "budget_exceeded" in job.status_reason


def test_approval_checkpoint_triggers_above_threshold(session, client):
    client.monthly_budget_cents = 100_000
    session.commit()
    job = _job(session, client, resolution="2048x2048")
    assert job.status == JobStatus.AWAITING_APPROVAL.value
    pending = service.list_pending_approvals(session)
    assert len(pending) == 1
    assert pending[0].job_id == job.id


def test_approve_job_runs_generation(session, client):
    client.monthly_budget_cents = 100_000
    session.commit()
    job = _job(session, client, resolution="2048x2048")
    assert job.status == JobStatus.AWAITING_APPROVAL.value

    approved = service.approve_job(session, job.id, decided_by="founder@3echo.sg")
    assert approved.status == JobStatus.DELIVERED.value
    assert approved.actual_cost_cents is not None


def test_reject_job_leaves_it_rejected_and_ungenerated(session, client):
    client.monthly_budget_cents = 100_000
    session.commit()
    job = _job(session, client, resolution="2048x2048")

    rejected = service.reject_job(session, job.id, decided_by="founder@3echo.sg", reason="not on brief")
    assert rejected.status == JobStatus.REJECTED.value
    assert rejected.output_path is None


def test_resolution_steps_down_to_fit_remaining_budget(session, client):
    # Requesting 1024x1024 stays under the approval threshold (gemini
    # 1024=50c < 100c), so this exercises the resolution ladder rather than
    # the approval checkpoint. gemini 512=25c, 1024=50c — a 30c budget
    # covers 512 but not 1024.
    client.monthly_budget_cents = 30
    session.commit()
    job = _job(session, client, resolution="1024x1024")
    assert job.status == JobStatus.DELIVERED.value
    assert job.resolution_used == "512x512"
    assert "stepped down" in job.status_reason


def test_usage_ledger_accumulates_across_jobs(session, client):
    _job(session, client, resolution="512x512")
    _job(session, client, resolution="512x512")
    usage = service.usage_summary(session, client.id)
    assert usage["used_cents"] == 40  # 2 jobs x 20c mock-seedance


def test_all_providers_failing_marks_job_failed(session, client, monkeypatch):
    def _boom(**kwargs):
        raise ProviderError("simulated total outage")

    monkeypatch.setattr(mock_seedance, "generate", _boom)
    job = _job(session, client)
    assert job.status == JobStatus.FAILED.value
    assert "all providers failed" in job.status_reason


def test_video_job_generates_at_requested_frame_resolution(session, client):
    # Video is priced flat (see costs.py) but the frame resolution passed to
    # the provider still has to be a real WxH, not the "video" cost-table
    # key — regression test for a bug where _affordable_resolution returned
    # the literal string "video", which broke every video job.
    client.monthly_budget_cents = 100_000
    session.commit()
    job = _job(session, client, kind="video", resolution="512x512")
    assert job.status == JobStatus.AWAITING_APPROVAL.value  # video always exceeds the threshold

    approved = service.approve_job(session, job.id, decided_by="founder@3echo.sg")
    assert approved.status == JobStatus.DELIVERED.value
    assert approved.resolution_used == "512x512"
    assert approved.output_path.endswith("keyframes.png")


def test_create_job_rejects_unknown_kind(session, client):
    with pytest.raises(service.MediaOpsError, match="unknown kind"):
        service.create_job(session, client_id=client.id, campaign="c", prompt="p", kind="audio")


def test_create_job_rejects_unknown_resolution(session, client):
    with pytest.raises(service.MediaOpsError, match="unknown resolution"):
        service.create_job(session, client_id=client.id, campaign="c", prompt="p", resolution="9999x9999")


def test_create_job_rejects_reference_path_outside_allowed_dirs(session, client, tmp_path):
    outside = tmp_path.parent / "outside-reference.png"
    from PIL import Image

    Image.new("RGB", (64, 64), (1, 2, 3)).save(outside)
    with pytest.raises(service.MediaOpsError, match="must be inside"):
        service.create_job(
            session, client_id=client.id, campaign="c", prompt="p", reference_image_path=str(outside)
        )


def test_create_job_rejects_missing_reference_file(session, client, tmp_path):
    missing = tmp_path / "does-not-exist.png"
    with pytest.raises(service.MediaOpsError, match="does not exist"):
        service.create_job(
            session, client_id=client.id, campaign="c", prompt="p", reference_image_path=str(missing)
        )


def test_create_client_rejects_empty_name(session):
    with pytest.raises(service.MediaOpsError, match="must not be empty"):
        service.create_client(session, name="  ", monthly_budget_cents=1000)


def test_create_client_rejects_non_positive_budget(session):
    with pytest.raises(service.MediaOpsError, match="must be positive"):
        service.create_client(session, name="New Client", monthly_budget_cents=0)


def test_create_client_succeeds_and_is_listed(session):
    created = service.create_client(session, name="New Client", monthly_budget_cents=2500)
    assert created.monthly_budget_cents == 2500
    assert created.id in [c.id for c in service.list_clients(session)]


def test_list_jobs_pagination(session, client):
    for i in range(5):
        _job(session, client, campaign=f"Campaign {i}")
    page1 = service.list_jobs(session, client_id=client.id, limit=2, offset=0)
    page2 = service.list_jobs(session, client_id=client.id, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {j.id for j in page1}.isdisjoint({j.id for j in page2})


def test_identity_qa_gate_fails_job_against_mismatched_reference(session, client, reference_image, tmp_path):
    from PIL import Image

    from app import qa

    other_ref = tmp_path / "other.png"
    Image.new("RGB", (256, 256), (250, 10, 10)).save(other_ref)

    monkeypatch_threshold = config.QA_IDENTITY_THRESHOLD
    config.QA_IDENTITY_THRESHOLD = 99  # force a near-impossible bar
    try:
        job = _job(session, client, reference_image_path=str(other_ref))
    finally:
        config.QA_IDENTITY_THRESHOLD = monkeypatch_threshold

    assert job.qa_identity_score is not None
    assert job.status in (JobStatus.QA_FAILED.value, JobStatus.DELIVERED.value)


def test_failover_reason_is_recorded_on_a_delivered_job(session, client, monkeypatch):
    """A job that quietly came from the mock must say why on the job itself.

    Before this, `errors` was only surfaced when *every* provider failed, so
    the common case — real provider down, mock succeeds — left no trace
    anywhere except container logs.
    """
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    job = _job(session, client)

    assert job.status == JobStatus.DELIVERED.value
    assert job.provider_used == "mock-seedance"
    assert job.status_reason is not None
    assert "gemini-openrouter" in job.status_reason
    assert "OPENROUTER_API_KEY not set" in job.status_reason


def test_upscale_is_disclosed_on_the_job(session, client, monkeypatch):
    """A provider that renders below the requested size and upscales must say
    so. Otherwise the job row claims a resolution the pixels can't back up —
    the same self-reported-success problem the QA gate exists to catch."""
    from app.providers.base import GenerationResult

    def fake_generate(**kw):
        real = mock_seedance.generate(**kw)
        return GenerationResult(
            output_path=real.output_path,
            provider_name=real.provider_name,
            seed=real.seed,
            native_size="768x768",
        )

    monkeypatch.setattr(service.REGISTRY["gemini-openrouter"], "generate", fake_generate)
    job = _job(session, client, resolution="1024x1024")

    assert job.status == JobStatus.DELIVERED.value
    assert "upscaled from 768x768" in job.status_reason


def test_no_upscale_note_when_provider_renders_natively(session, client, monkeypatch):
    monkeypatch.setattr(
        service.REGISTRY["gemini-openrouter"],
        "generate",
        lambda **kw: mock_seedance.generate(**kw),
    )
    job = _job(session, client, resolution="1024x1024")
    assert job.status_reason is None


def test_status_reason_never_exceeds_the_column_limit(session, client, monkeypatch):
    """status_reason is String(300) and is built from provider error text we
    don't control. Postgres raises DataError on overflow; SQLite (used here)
    silently accepts any length — so this asserts the length directly rather
    than relying on the DB to reject it. Caught in production, not by tests:
    a real OpenRouter 402 body plus an upscale note ran past 300 and 500'd
    the endpoint while every local test still passed.
    """
    from app.providers.base import ProviderError

    def verbose_failure(**kw):
        raise ProviderError("x" * 400)

    for name in ("gemini-openrouter", "openai-images", "pollinations"):
        monkeypatch.setattr(service.REGISTRY[name], "generate", verbose_failure)

    job = _job(session, client, resolution="1024x1024")

    assert job.status_reason is not None
    assert len(job.status_reason) <= 300
    # The trail must still name the providers, not just be a wall of x's.
    assert "gemini-openrouter" in job.status_reason


def test_every_provider_appears_in_a_clipped_failover_trail(session, client, monkeypatch):
    """One verbose upstream must not crowd the others out of the trail."""
    from app.providers.base import ProviderError

    def boom(name):
        def _f(**kw):
            raise ProviderError(f"{name}-detail " + "y" * 300)
        return _f

    for name in ("gemini-openrouter", "openai-images", "pollinations"):
        monkeypatch.setattr(service.REGISTRY[name], "generate", boom(name))

    job = _job(session, client)

    for name in ("gemini-openrouter", "openai-images", "pollinations"):
        assert name in job.status_reason


def test_no_failover_note_when_first_provider_succeeds(session, client, monkeypatch):
    monkeypatch.setattr(
        service.REGISTRY["gemini-openrouter"],
        "generate",
        lambda **kw: mock_seedance.generate(**kw),
    )
    job = _job(session, client)
    assert job.provider_used == "gemini-openrouter"
    assert job.status_reason is None


def test_stranded_generating_jobs_are_failed_on_recovery(session, client):
    """A container restart mid-generation leaves GENERATING rows with no
    owner. Without recovery they stay 'generating' forever — which is what
    a redeploy during traffic actually produced in the deployed app."""
    job = service.create_job(
        session,
        client_id=client.id,
        campaign="C",
        prompt="p",
        kind="image",
        resolution="512x512",
    )
    job.status = JobStatus.GENERATING.value
    session.commit()

    assert service.recover_stranded_jobs(session) == 1
    session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert "interrupted" in job.status_reason
    assert "resubmit" in job.status_reason


def test_recovery_leaves_settled_jobs_alone(session, client, monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    delivered = _job(session, client)
    assert delivered.status == JobStatus.DELIVERED.value

    assert service.recover_stranded_jobs(session) == 0
    session.refresh(delivered)
    assert delivered.status == JobStatus.DELIVERED.value


def test_recovery_does_not_charge_the_client(session, client):
    """A job can die after a paid provider call but before the ledger
    commits, so recovery must never invent spend."""
    job = service.create_job(
        session, client_id=client.id, campaign="C", prompt="p", kind="image", resolution="512x512"
    )
    job.status = JobStatus.GENERATING.value
    session.commit()

    service.recover_stranded_jobs(session)
    assert service.get_client_usage_cents(session, client.id) == 0
