from unittest.mock import MagicMock, patch

from src.utils.timer_failsafe import check_and_manage_timer


def test_timer_heals_when_automation_true():
    # When automation is True and timer is inactive, it calls enable --now to self-heal
    calls = []

    def mock_subprocess(cmd, **kwargs):
        calls.append(cmd)
        mock_obj = MagicMock()
        mock_obj.returncode = 0
        if "is-active" in cmd:
            mock_obj.stdout = "inactive"
        elif "is-enabled" in cmd:
            mock_obj.stdout = "disabled"
        return mock_obj

    with patch("subprocess.run", side_effect=mock_subprocess):
        res = check_and_manage_timer(automation_enabled=True)
        assert res is True
        assert any("enable" in cmd and "--now" in cmd for cmd in calls)


def test_timer_kills_when_automation_false():
    # When automation is False and timer is active, it calls disable --now to kill it
    calls = []

    def mock_subprocess(cmd, **kwargs):
        calls.append(cmd)
        mock_obj = MagicMock()
        mock_obj.returncode = 0
        if "is-active" in cmd:
            mock_obj.stdout = "active"
        elif "is-enabled" in cmd:
            mock_obj.stdout = "enabled"
        return mock_obj

    with patch("subprocess.run", side_effect=mock_subprocess):
        res = check_and_manage_timer(automation_enabled=False)
        assert res is False
        assert any("disable" in cmd and "--now" in cmd for cmd in calls)


def test_timer_already_active_and_automation_true():
    # When automation is True and timer is already active, no enable call needed
    calls = []

    def mock_subprocess(cmd, **kwargs):
        calls.append(cmd)
        mock_obj = MagicMock()
        mock_obj.returncode = 0
        if "is-active" in cmd:
            mock_obj.stdout = "active"
        elif "is-enabled" in cmd:
            mock_obj.stdout = "enabled"
        return mock_obj

    with patch("subprocess.run", side_effect=mock_subprocess):
        res = check_and_manage_timer(automation_enabled=True)
        assert res is True
        assert not any("enable" in cmd for cmd in calls)
