import logging

import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .api import Air352ApiClient, Air352AuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Air352ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                api = Air352ApiClient(session, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                await api.authenticate()
                devices = await api.get_device_list()
            except Air352AuthError:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.warning("352 setup failed (%s)", type(e).__name__)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                title = f"352 ({user_input[CONF_USERNAME]}) - {len(devices)} devices"
                self.hass.data.setdefault(f"{DOMAIN}_pending", {})[user_input[CONF_USERNAME]] = api
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            session = async_get_clientsession(self.hass)
            try:
                api = Air352ApiClient(session, entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
                await api.authenticate()
            except Air352AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
                self.hass.data.setdefault(f"{DOMAIN}_pending", {})[entry.data[CONF_USERNAME]] = api
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
