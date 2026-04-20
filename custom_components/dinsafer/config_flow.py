"""Config flow for the DinSafer integration."""

# pyright: reportMissingImports=false, reportCallIssue=false, reportGeneralTypeIssues=false

from __future__ import annotations

from contextlib import redirect_stdout
import io
import logging
from typing import Any

import voluptuous as vol

from dinsafer_poc import APP_ID, DinsaferClient, DinsaferError
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def _validate_input(hass, data: dict[str, Any]) -> dict[str, str]:
    """Validate user input allows us to connect."""

    def _login_and_probe() -> dict[str, str]:
        client = DinsaferClient(email=data[CONF_EMAIL], password=data[CONF_PASSWORD], debug=False)

        try:
            with redirect_stdout(io.StringIO()):
                login_data = client.login()
                homes = client.list_homes()

                if homes:
                    home_id = homes[0].get("home_id")
                    if home_id:
                        client.post(
                            f"/home/get-info/{APP_ID}",
                            json_payload={"home_id": home_id},
                            token=client.token,
                            include_token_suffix=True,
                        )
        except DinsaferError as err:
            message = str(err).lower()
            if "login failed" in message or "status=-12" in message or "token is illegal" in message:
                raise InvalidAuth from err
            raise CannotConnect from err
        except OSError as err:
            raise CannotConnect from err

        title_email = login_data.get("Result", {}).get("mail") if isinstance(login_data, dict) else None
        return {"title": title_email or data[CONF_EMAIL]}

    return await hass.async_add_executor_job(_login_and_probe)


class DinsaferConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DinSafer."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during DinSafer config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{NAME} ({info['title']})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
