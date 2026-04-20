"""The DinSafer integration."""

# pyright: reportMissingImports=false

from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APP_ID, DinsaferError, DinsaferWebSocketClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DATA_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the DinSafer component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DinSafer from a config entry."""
    coordinator = DinsaferCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        if str(err) not in {"WebSocket unavailable", "Connection failed"}:
            raise ConfigEntryNotReady(f"Unable to initialize DinSafer: {err}") from err

        try:
            metadata = await coordinator._async_authenticate_and_load_metadata(force=True)
        except (DinsaferError, OSError) as metadata_err:
            raise ConfigEntryNotReady(f"Unable to initialize DinSafer: {metadata_err}") from metadata_err

        coordinator.async_set_updated_data({**metadata, "available": False})
        _LOGGER.debug("DinSafer websocket unavailable during setup; entity will start unavailable")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.data.pop(DOMAIN, None)

    return unload_ok


class DinsaferCommandError(HomeAssistantError):
    """Raised when a panel command cannot be completed."""


class DinsaferCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate DinSafer device state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = entry
        self._email: str = entry.data[CONF_EMAIL]
        self._password: str = entry.data[CONF_PASSWORD]
        self._ws_client = DinsaferWebSocketClient(
            email=self._email,
            password=self._password,
            debug=False,
        )
        self._command_lock = asyncio.Lock()
        self._device_name = DEFAULT_NAME

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the alarm panel."""
        data = self.data or {}
        device_identifier = data.get("device_id") or self._ws_client.device_id or self.config_entry.entry_id
        device_name = data.get("name") or self._device_name or DEFAULT_NAME

        return DeviceInfo(
            identifiers={(DOMAIN, str(device_identifier))},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=str(device_name),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll current state via HTTP API."""
        try:
            metadata = await self._async_authenticate_and_load_metadata()
            device_state = await self.hass.async_add_executor_job(self._get_state_via_http)
        except DinsaferError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except OSError as err:
            _LOGGER.debug("DinSafer HTTP poll failed: %s", err)
            raise UpdateFailed("Connection failed") from err

        return {
            **metadata,
            **device_state,
            "available": True,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def async_send_command(self, command: str, target_state: int) -> None:
        """Send an arm/disarm command to the DinSafer panel."""
        async with self._command_lock:
            if not self._ws_client.token or not self._ws_client.device_token or not self._ws_client.home_id:
                await self._async_authenticate_and_load_metadata(force=True)

            try:
                response = await self.hass.async_add_executor_job(
                    self._send_command_sync,
                    command,
                )
            except DinsaferError as err:
                _LOGGER.error("Failed to send DinSafer command %s: %s", command, err)
                raise DinsaferCommandError(f"DinSafer command failed: {err}") from err

            status = response.get("Status") if isinstance(response, dict) else None
            if status != 1:
                raise DinsaferCommandError(f"DinSafer command rejected: {response}")

            data = {
                **(self.data or self._default_data()),
                "arm_state": target_state,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            self.async_set_updated_data(data)

    async def _async_authenticate_and_load_metadata(self, force: bool = False) -> dict[str, Any]:
        """Authenticate and load metadata needed by the integration."""
        if not force and self._ws_client.token and self.data is not None:
            return self.data

        await self.hass.async_add_executor_job(self._authenticate_sync)
        metadata = self._build_state_payload()
        self.async_set_updated_data(metadata)
        return metadata

    def _authenticate_sync(self) -> None:
        """Authenticate with DinSafer while silencing library stdout output."""
        http_client = self._ws_client.http_client

        with redirect_stdout(io.StringIO()):
            login_data = http_client.login()
            result = login_data.get("Result", {}) if isinstance(login_data, dict) else {}

            token = result.get("token") if isinstance(result, dict) else None
            user_id = result.get("user_id") if isinstance(result, dict) else None
            if not token or not user_id:
                raise DinsaferError("Failed to get token or user_id from login response")

            self._ws_client.token = token
            self._ws_client.user_id = user_id

            homes = http_client.list_homes()
            if not homes:
                raise DinsaferError("No homes found for this account")

            first_home = homes[0]
            home_id = first_home.get("home_id")
            if not isinstance(home_id, str) or not home_id:
                raise DinsaferError("Failed to get home_id from home list response")

            self._ws_client.home_id = home_id

            home_info_result = http_client.post(
                f"/home/get-info/{APP_ID}",
                json_payload={"home_id": home_id},
                token=token,
                include_token_suffix=True,
            )

        home_info = home_info_result.payload
        if not isinstance(home_info, dict):
            raise DinsaferError("Unexpected home info response payload")

        result_obj = home_info.get("Result")
        if not isinstance(result_obj, dict):
            raise DinsaferError("Missing Result object in home info response")

        device_info = result_obj.get("device")
        if not isinstance(device_info, dict):
            raise DinsaferError("Missing device information in home info response")

        device_id = device_info.get("deviceid") or device_info.get("device_id")
        device_token = device_info.get("token")
        if not isinstance(device_id, str) or not isinstance(device_token, str):
            raise DinsaferError("Failed to get device_id or device_token from home info response")

        self._ws_client.device_id = device_id
        self._ws_client.device_token = device_token

        if isinstance(device_info.get("name"), str):
            self._device_name = device_info["name"]

    def _default_data(self) -> dict[str, Any]:
        """Return default coordinator state."""
        return {
            "arm_state": None,
            "available": False,
            "last_updated": None,
            "online": None,
            "device_id": self._ws_client.device_id,
            "home_id": self._ws_client.home_id,
            "name": self._device_name,
            "device_token": self._ws_client.device_token,
            "token": self._ws_client.token,
            "user_id": self._ws_client.user_id,
        }

    def _build_state_payload(self, arm_state: int | None = None, available: bool = False) -> dict[str, Any]:
        """Build the state payload published by the coordinator."""
        current = self.data or self._default_data()
        return {
            **current,
            "arm_state": current.get("arm_state") if arm_state is None else arm_state,
            "available": available,
            "device_id": self._ws_client.device_id,
            "device_token": self._ws_client.device_token,
            "home_id": self._ws_client.home_id,
            "last_updated": current.get("last_updated"),
            "name": current.get("name") or self._device_name,
            "online": current.get("online"),
            "token": self._ws_client.token,
            "user_id": self._ws_client.user_id,
        }

    def _get_state_via_http(self) -> dict[str, Any]:
        """Get current device state via HTTP API."""
        if not self._ws_client.token or not self._ws_client.home_id or not self._ws_client.device_id:
            raise DinsaferError("DinSafer metadata incomplete; cannot get state")

        payload = {
            "home_id": self._ws_client.home_id,
            "device_ids": [self._ws_client.device_id]
        }

        with redirect_stdout(io.StringIO()):
            result = self._ws_client.http_client.post(
                f"/device/search-devices/{APP_ID}",
                json_payload=payload,
                token=self._ws_client.token,
                include_token_suffix=True,
            )

        if not isinstance(result.payload, dict):
            raise DinsaferError("Unexpected search-devices response payload")

        devices = result.payload.get("Result", {}).get("devices", [])
        if not devices or not isinstance(devices[0], dict):
            raise DinsaferError("No device found in search-devices response")

        device = devices[0]

        return {
            "arm_state": device.get("arm_state"),
            "online": device.get("online"),
            "battery_level": device.get("battery_level"),
            "charge": device.get("charge"),
            "firmware_version": device.get("firmware_version"),
            "ip": device.get("ip"),
            "wifi_mac_addr": device.get("wifi_mac_addr"),
        }

    def _send_command_sync(self, command: str) -> dict[str, Any]:
        """Send a command through the HTTP API."""
        if not self._ws_client.token or not self._ws_client.device_token or not self._ws_client.home_id or not self._ws_client.user_id:
            raise DinsaferError("DinSafer metadata incomplete; cannot send command")

        payload = {
            "userid": self._ws_client.user_id,
            "devtoken": self._ws_client.device_token,
            "message_id": str(int(time.time() * 1000)),
            "home_id": self._ws_client.home_id,
            "cmd": command,
            "force": 0,
        }

        with redirect_stdout(io.StringIO()):
            result = self._ws_client.http_client.post(
                f"/device/sendcmd/{APP_ID}",
                json_payload=payload,
                token=self._ws_client.token,
                include_token_suffix=True,
            )

        if not isinstance(result.payload, dict):
            raise DinsaferError("Unexpected sendcmd response payload")

        return result.payload
