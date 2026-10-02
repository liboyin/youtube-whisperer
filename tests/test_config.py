import pytest
from pydantic import ValidationError

import youtube_whisperer.config as testee


@pytest.mark.parametrize('environment', [False, True])
def test_settings_reject_negative_claim_idle(monkeypatch, environment):
    """Supplied and environment negative claim thresholds fail snapshot validation."""
    if environment:
        monkeypatch.setenv('WORKER_CLAIM_MIN_IDLE_SECONDS', '-1')
    with pytest.raises(ValidationError, match='greater than or equal to 0'):
        testee.Settings(**({} if environment else {'worker_claim_min_idle_seconds': -1}))


@pytest.mark.parametrize('value', [0, 7, 21600])
def test_settings_accept_nonnegative_claim_idle(value):
    """Snapshots preserve zero immediate-claim compatibility and positive thresholds."""
    assert testee.Settings(worker_claim_min_idle_seconds=value).worker_claim_min_idle_seconds == value


def test_settings_default_claim_idle_is_six_hours(monkeypatch):
    """Absent environment configuration retains the six-hour claim default."""
    monkeypatch.delenv('WORKER_CLAIM_MIN_IDLE_SECONDS')
    assert testee.Settings().worker_claim_min_idle_seconds == 21600
