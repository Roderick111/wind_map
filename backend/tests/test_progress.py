"""Progress logging tests."""

from wind_track.services.progress import log_step, step


def test_log_step_writes_stderr(capsys):
    log_step("test message", area="lyon_full")
    captured = capsys.readouterr()
    assert "[wind-track" in captured.err
    assert "test message" in captured.err
    assert "area=lyon_full" in captured.err


def test_step_context_logs_start_and_done(capsys):
    with step("unit_test"):
        pass
    captured = capsys.readouterr()
    assert "START unit_test" in captured.err
    assert "DONE unit_test" in captured.err