"""Alarm control panel platform for DinSafer."""

# pyright: reportMissingImports=false

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DinsaferCoordinator
from .const import (
    ARM_STATE_AWAY,
    ARM_STATE_DISARMED,
    ARM_STATE_HOME,
    CMD_ARM_AWAY,
    CMD_ARM_HOME,
    CMD_DISARM,
    DATA_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DinSafer alarm entity from a config entry."""
    coordinator: DinsaferCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([DinsaferAlarmControlPanel(coordinator, entry)])


class DinsaferAlarmControlPanel(CoordinatorEntity[DinsaferCoordinator], AlarmControlPanelEntity):
    """Representation of the DinSafer alarm control panel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    def __init__(self, coordinator: DinsaferCoordinator, entry: ConfigEntry) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alarm"

    @property
    def device_info(self):
        """Return device metadata."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and bool((self.coordinator.data or {}).get("available"))

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current alarm state."""
        state = (self.coordinator.data or {}).get("arm_state")
        if state == ARM_STATE_DISARMED:
            return AlarmControlPanelState.DISARMED
        if state == ARM_STATE_AWAY:
            return AlarmControlPanelState.ARMED_AWAY
        if state == ARM_STATE_HOME:
            return AlarmControlPanelState.ARMED_HOME
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return (self.coordinator.data or {}).get("name") or DEFAULT_NAME

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        data = self.coordinator.data or {}
        if data.get("last_updated"):
            attrs["last_updated"] = data["last_updated"]
        return attrs

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm."""
        await self.coordinator.async_send_command(CMD_DISARM, ARM_STATE_DISARMED)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm in away mode."""
        await self.coordinator.async_send_command(CMD_ARM_AWAY, ARM_STATE_AWAY)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the alarm in home mode."""
        await self.coordinator.async_send_command(CMD_ARM_HOME, ARM_STATE_HOME)
