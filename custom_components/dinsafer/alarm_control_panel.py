"""Alarm control panel platform for DinSafer."""

# pyright: reportMissingImports=false

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

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
    _attr_should_poll = False

    def __init__(self, coordinator: DinsaferCoordinator, entry: ConfigEntry) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alarm"
        self._local_state: AlarmControlPanelState | None = None
        self._cancel_timer: Callable[[], None] | None = None
        self._transition_id = 0
        self._transition_lock = asyncio.Lock()

    @property
    def device_info(self):
        """Return device metadata."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._local_state is not None:
            return True
        return self.coordinator.last_update_success and bool((self.coordinator.data or {}).get("available"))

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current alarm state."""
        if self._local_state is not None:
            return self._local_state

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

    def _cancel_pending_timer(self) -> None:
        """Cancel any scheduled transition verification timer."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    def _start_transition(self, state: AlarmControlPanelState) -> int:
        """Start a new local transition state."""
        self._cancel_pending_timer()
        self._transition_id += 1
        self._local_state = state
        self.async_write_ha_state()
        return self._transition_id

    def _schedule_transition_refresh(self, delay_seconds: int, transition_id: int) -> None:
        """Schedule a coordinator refresh after a transition delay."""

        async def _finish_transition(_now) -> None:
            """Refresh coordinator state and clear local transition state."""
            async with self._transition_lock:
                if transition_id != self._transition_id:
                    return

                self._cancel_timer = None
                try:
                    await self.coordinator.async_request_refresh()
                finally:
                    if transition_id == self._transition_id:
                        self._local_state = None
                        self.async_write_ha_state()

        self._cancel_timer = async_track_point_in_time(
            self.hass,
            _finish_transition,
            utcnow() + timedelta(seconds=delay_seconds),
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm."""
        async with self._transition_lock:
            transition_id = self._start_transition(AlarmControlPanelState.DISARMING)

            try:
                await self.coordinator.async_send_command(CMD_DISARM, ARM_STATE_DISARMED)
                self._schedule_transition_refresh(delay_seconds=3, transition_id=transition_id)
            except Exception:
                if transition_id == self._transition_id:
                    self._local_state = None
                    self.async_write_ha_state()
                raise

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm in away mode."""
        async with self._transition_lock:
            transition_id = self._start_transition(AlarmControlPanelState.ARMING)

            try:
                await self.coordinator.async_send_command(CMD_ARM_AWAY, ARM_STATE_AWAY)
                self._schedule_transition_refresh(delay_seconds=25, transition_id=transition_id)
            except Exception:
                if transition_id == self._transition_id:
                    self._local_state = None
                    self.async_write_ha_state()
                raise

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the alarm in home mode."""
        async with self._transition_lock:
            transition_id = self._start_transition(AlarmControlPanelState.ARMING)

            try:
                await self.coordinator.async_send_command(CMD_ARM_HOME, ARM_STATE_HOME)
                self._schedule_transition_refresh(delay_seconds=4, transition_id=transition_id)
            except Exception:
                if transition_id == self._transition_id:
                    self._local_state = None
                    self.async_write_ha_state()
                raise

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self._cancel_pending_timer()
        await super().async_will_remove_from_hass()
