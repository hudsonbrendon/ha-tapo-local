"""Tapo Plus: dados das câmeras Tapo tirados da engenharia reversa do app."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TapoAuthError, TapoCloud, TapoCloudError, TapoLocal, TapoMFARequired
from .const import CONF_KIND, CONF_TERMINAL_UUID, CONF_TOKEN, CONF_URL, DOMAIN, KIND_CLOUD

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        cloud = TapoCloud(
            async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
            entry.data.get(CONF_TERMINAL_UUID), entry.data.get(CONF_TOKEN), entry.data.get(CONF_URL),
        )

        async def update_cloud() -> dict:
            try:
                if not cloud.url:
                    await cloud.login()
                devices = await cloud.devices()
                msgs = {d["deviceId"]: await cloud.messages(d["deviceId"]) for d in devices}
            except TapoMFARequired as err:
                raise ConfigEntryAuthFailed("A TP-Link pediu código MFA de novo") from err
            except TapoCloudError as err:
                raise UpdateFailed(str(err)) from err
            if cloud.token != entry.data.get(CONF_TOKEN):
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_TOKEN: cloud.token, CONF_URL: cloud.url})
            return {"devices": devices, "messages": msgs}

        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} cloud",
            update_method=update_cloud, update_interval=timedelta(minutes=2),
        )
    else:
        local = TapoLocal(entry.data[CONF_HOST], entry.data[CONF_PASSWORD])

        async def update_local() -> dict:
            try:
                return await hass.async_add_executor_job(local.fetch)
            except TapoAuthError as err:
                # Para de tentar: cada login errado aproxima o lockout de 30 min da câmera.
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # pytapo/requests: erros genéricos de rede
                raise UpdateFailed(str(err)) from err

        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {entry.data[CONF_HOST]}",
            update_method=update_local, update_interval=timedelta(seconds=60),
        )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
