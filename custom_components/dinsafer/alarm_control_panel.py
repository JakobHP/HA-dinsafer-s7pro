"""Alarm control panel platform for DinSafer."""

# pyright: reportMissingImports=false

from __future__ import annotations

import asyncio
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
    _attr_code_arm_required = False
    _attr_code_disarm_required = False

    def __init__(self, coordinator: DinsaferCoordinator, entry: ConfigEntry) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alarm"
        self._previous_state: AlarmControlPanelState | None = None

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
        # Save current state to revert if timeout occurs
        self._previous_state = self.alarm_state
        
        # Set to disarming state immediately for user feedback
        self._attr_state = AlarmControlPanelState.DISARMING
        self.async_write_ha_state()
        
        try:
            # Send the disarm command
            await self.coordinator.async_send_command(CMD_DISARM, ARM_STATE_DISARMED)
            
            # Poll device state every 2 seconds until disarmed (max 60 seconds)
            timeout = 60
            poll_interval = 2
            elapsed = 0
            
            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                # Check if device is now disarmed
                current_arm_state = self.coordinator.data.get("arm_state")
                if current_arm_state == ARM_STATE_DISARMED:
                    # Device is disarmed, update state
                    self._attr_state = AlarmControlPanelState.DISARMED
                    self.async_write_ha_state()
                    return
            
            # Timeout occurred - revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            
        except Exception as err:
            # On error, revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            raise

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm in away mode."""
        # Save current state to revert if timeout occurs
        self._previous_state = self.alarm_state
        
        # Set to arming state immediately for user feedback
        self._attr_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()
        
        try:
            # Send the arm command
            await self.coordinator.async_send_command(CMD_ARM_AWAY, ARM_STATE_AWAY)
            
            # Poll device state every 2 seconds until armed (max 60 seconds)
            timeout = 60
            poll_interval = 2
            elapsed = 0
            
            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                # Check if device is now armed away
                current_arm_state = self.coordinator.data.get("arm_state")
                if current_arm_state == ARM_STATE_AWAY:
                    # Device is armed, update state
                    self._attr_state = AlarmControlPanelState.ARMED_AWAY
                    self.async_write_ha_state()
                    return
            
            # Timeout occurred - revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            
        except Exception as err:
            # On error, revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            raise

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the alarm in home mode."""
        # Save current state to revert if timeout occurs
        self._previous_state = self.alarm_state
        
        # Set to arming state immediately for user feedback
        self._attr_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()
        
        try:
            # Send the arm command
            await self.coordinator.async_send_command(CMD_ARM_HOME, ARM_STATE_HOME)
            
            # Poll device state every 2 seconds until armed (max 60 seconds)
            timeout = 60
            poll_interval = 2
            elapsed = 0
            
            while elapsed < timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                # Check if device is now armed home
                current_arm_state = self.coordinator.data.get("arm_state")
                if current_arm_state == ARM_STATE_HOME:
                    # Device is armed, update state
                    self._attr_state = AlarmControlPanelState.ARMED_HOME
                    self.async_write_ha_state()
                    return
            
            # Timeout occurred - revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            
        except Exception as err:
            # On error, revert to previous state
            self._attr_state = self._previous_state
            self.async_write_ha_state()
            raise
