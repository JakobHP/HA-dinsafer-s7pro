"""Constants for the DinSafer integration."""

# pyright: reportMissingImports=false

from __future__ import annotations

DOMAIN = "dinsafer"
NAME = "DinSafer S7pro"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

PLATFORMS = ["alarm_control_panel"]

MANUFACTURER = "DinSafer"
MODEL = "S7pro"

DEFAULT_NAME = "DinSafer Alarm"

DATA_COORDINATOR = "coordinator"

ARM_STATE_DISARMED = 2
ARM_STATE_AWAY = 0
ARM_STATE_HOME = 1

CMD_ARM_AWAY = "TASK_ARM"
CMD_ARM_HOME = "TASK_HOMEARM"
CMD_DISARM = "TASK_DISARM"

INITIAL_RECONNECT_DELAY = 1
MAX_RECONNECT_DELAY = 60

__all__ = [
    "ARM_STATE_AWAY",
    "ARM_STATE_DISARMED",
    "ARM_STATE_HOME",
    "CMD_ARM_AWAY",
    "CMD_ARM_HOME",
    "CMD_DISARM",
    "CONF_EMAIL",
    "CONF_PASSWORD",
    "DATA_COORDINATOR",
    "DEFAULT_NAME",
    "DOMAIN",
    "INITIAL_RECONNECT_DELAY",
    "MANUFACTURER",
    "MAX_RECONNECT_DELAY",
    "MODEL",
    "NAME",
    "PLATFORMS",
]
