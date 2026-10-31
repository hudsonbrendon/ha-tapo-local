"""Config flow Tapo Plus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import TapoAuthError, TapoCloud, TapoCloudError, TapoLocal, TapoMFARequired
from .const import CONF_KIND, CONF_TERMINAL_UUID, CONF_TOKEN, CONF_URL, DOMAIN, KIND_CAMERA, KIND_CLOUD

CONF_SOURCE_ENTRY = "source_entry"
CONF_CODE = "code"


class TapoPlusFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._cloud: TapoCloud | None = None
        self._mfa_id: str | None = None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        menu = ["camera", "cloud"]
        if self._tapo_control_entries():
            menu.insert(0, "import_tapo_control")
        return self.async_show_menu(step_id="user", menu_options=menu)

    # -------------------------------------------------------- câmera

    def _tapo_control_entries(self):
        mine = {e.data.get(CONF_HOST) for e in self._async_current_entries()}
        return [e for e in self.hass.config_entries.async_entries("tapo_control")
                if e.data.get("cloud_password") and e.data.get("ip_address") not in mine]

    async def async_step_import_tapo_control(self, user_input=None) -> ConfigFlowResult:
        entries = {e.entry_id: e for e in self._tapo_control_entries()}
        if user_input is not None:
            src = entries[user_input[CONF_SOURCE_ENTRY]]
            return await self._create_camera(src.data["ip_address"], src.data["cloud_password"])
        return self.async_show_form(step_id="import_tapo_control", data_schema=vol.Schema({
            vol.Required(CONF_SOURCE_ENTRY): vol.In({k: e.title for k, e in entries.items()}),
        }))

    async def async_step_camera(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create_camera(user_input[CONF_HOST], user_input[CONF_PASSWORD])
        return self._camera_form("camera", {})

    def _camera_form(self, step: str, errors: dict) -> ConfigFlowResult:
        return self.async_show_form(step_id=step, errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): str}))

    async def _create_camera(self, host: str, password: str) -> ConfigFlowResult:
        local = TapoLocal(host, password)
        try:
            data = await self.hass.async_add_executor_job(
                local._multi, [("getDeviceInfo", {"device_info": {"name": ["basic_info"]}})])
        except TapoAuthError:
            return self._camera_form("camera", {"base": "invalid_auth"})
        except Exception:  # pytapo: rede/timeout
            return self._camera_form("camera", {"base": "cannot_connect"})
        info = data["getDeviceInfo"]["device_info"]["basic_info"]
        await self.async_set_unique_id(format_mac(info["mac"]))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PASSWORD: password})
        return self.async_create_entry(
            title=(info.get("device_alias") or info.get("device_model") or host).strip(),
            data={CONF_KIND: KIND_CAMERA, CONF_HOST: host, CONF_PASSWORD: password},
        )

    # -------------------------------------------------------- nuvem

    async def async_step_cloud(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._cloud = TapoCloud(async_get_clientsession(self.hass),
                                    user_input[CONF_USERNAME].strip(), user_input[CONF_PASSWORD])
            try:
                await self._cloud.login()
            except TapoMFARequired as err:
                self._mfa_id = err.process_id
                try:
                    await self._cloud.send_mfa_email()
                except TapoCloudError:
                    errors["base"] = "mfa_send_failed"
                else:
                    return await self.async_step_mfa()
            except TapoCloudError as err:
                errors["base"] = "invalid_auth" if err.code in (-20600, -20601, -20602, -20607, -20615) else "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return await self._create_cloud(user_input[CONF_PASSWORD])
        return self.async_show_form(step_id="cloud", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}))

    async def async_step_mfa(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._cloud.check_mfa(self._mfa_id, user_input[CONF_CODE].strip())
            except TapoCloudError:
                errors["base"] = "invalid_code"
            else:
                return await self._create_cloud(self._cloud._password)
        return self.async_show_form(step_id="mfa", errors=errors,
                                    data_schema=vol.Schema({vol.Required(CONF_CODE): str}))

    async def _create_cloud(self, password: str) -> ConfigFlowResult:
        c = self._cloud
        await self.async_set_unique_id(f"cloud_{c.username.lower()}")
        data = {CONF_KIND: KIND_CLOUD, CONF_USERNAME: c.username, CONF_PASSWORD: password,
                CONF_TERMINAL_UUID: c.terminal_uuid, CONF_TOKEN: c.token, CONF_URL: c.url}
        if self.source == "reauth":
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=f"Nuvem TP-Link ({c.username})", data=data)

    # -------------------------------------------------------- reauth

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        if entry.data.get(CONF_KIND) == KIND_CLOUD:
            return await self.async_step_cloud()
        errors: dict[str, str] = {}
        if user_input is not None:
            local = TapoLocal(entry.data[CONF_HOST], user_input[CONF_PASSWORD])
            try:
                await self.hass.async_add_executor_job(
                    local._multi, [("getDeviceInfo", {"device_info": {"name": ["basic_info"]}})])
            except TapoAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]})
        return self.async_show_form(step_id="reauth_confirm", errors=errors,
                                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}))
