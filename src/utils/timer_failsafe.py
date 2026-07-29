import logging
import subprocess

logger = logging.getLogger("recruiting-platform.utils.timer_failsafe")


def check_and_manage_timer(automation_enabled: bool = True, timer_name: str = "careerpilot.timer") -> bool:
    """
    Manages the background automation timer (careerpilot.timer) according to config:
    - If automation_enabled is True: Self-heals by enabling and starting the timer if inactive or disabled.
    - If automation_enabled is False: Kills and disables the background timer if active or enabled.
    Returns True if timer is active or successfully healed, False otherwise.
    """
    try:
        res_active = subprocess.run(
            ["systemctl", "--user", "is-active", timer_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        is_active = res_active.returncode == 0 and res_active.stdout.strip() == "active"

        res_enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", timer_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        is_enabled = res_enabled.returncode == 0 and res_enabled.stdout.strip() == "enabled"

        if automation_enabled:
            # Self-healing logic
            if not is_active or not is_enabled:
                logger.warning(
                    f"Failsafe triggered: Automation is enabled (true), but timer '{timer_name}' is inactive/disabled. "
                    f"Auto-healing and enabling background timer..."
                )
                heal_res = subprocess.run(
                    ["systemctl", "--user", "enable", "--now", timer_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if heal_res.returncode == 0:
                    logger.info(f"Successfully self-healed and started systemd timer '{timer_name}'.")
                    return True
                else:
                    logger.error(f"Failed to self-heal systemd timer '{timer_name}': {heal_res.stderr}")
                    return False
            return True
        else:
            # Shutdown/kill logic
            if is_active or is_enabled:
                logger.warning(
                    f"Automation is disabled (false) in config. Killing and disabling timer '{timer_name}'..."
                )
                kill_res = subprocess.run(
                    ["systemctl", "--user", "disable", "--now", timer_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if kill_res.returncode == 0:
                    logger.info(f"Successfully stopped and disabled systemd timer '{timer_name}'.")
                else:
                    logger.error(f"Failed to stop systemd timer '{timer_name}': {kill_res.stderr}")
            return False

    except Exception as e:
        logger.warning(f"Unable to check or manage systemd timer '{timer_name}': {e}")
        return False


# Alias for backward compatibility
check_and_revive_timer = check_and_manage_timer
