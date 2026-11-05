"""Tapo Local: dados das câmeras Tapo tirados da engenharia reversa do app."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from tapolocal import TapoAuthError, TapoCloud, TapoCloudError, TapoLocal, TapoMFARequired
from .const import (
    CONF_KIND, CONF_RTSP_PASSWORD, CONF_RTSP_USERNAME, CONF_TERMINAL_UUID, CONF_TOKEN, CONF_URL,
    DOMAIN, KIND_CLOUD,
)

_LOGGER = logging.getLogger(__name__)
MAIN_INTERVAL = timedelta(seconds=60)
LIVE_INTERVAL = timedelta(seconds=5)
PLATFORMS = [
    Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT,
    Platform.BUTTON, Platform.SIREN, Platform.UPDATE, Platform.CAMERA,
]


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
                msgs: dict[str, list] = {}
                for n in sorted(await cloud.notifications(), key=lambda n: int(n.get("time") or 0), reverse=True):
                    att = n.get("attachments") if isinstance(n.get("attachments"), dict) else {}
                    msgs.setdefault(att.get("deviceId"), []).append(n)
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
        if not hass.is_running:
            # Ler 40+ métodos de 3 câmeras durante o boot estoura o "Bootstrap stage 2
            # timeout" do HA; adiando, o retry roda fora do bootstrap segundos depois.
            raise ConfigEntryNotReady("Aguardando o Home Assistant terminar de iniciar")
        local = TapoLocal(entry.data[CONF_HOST], entry.data[CONF_PASSWORD])

        fails = {"main": 0, "live": 0}

        def transient(key: str, coord, err: Exception, base: timedelta, cap: timedelta) -> dict:
            """Erro passageiro: espaça as tentativas e segura o último estado por um tempo."""
            fails[key] += 1
            coord.update_interval = min(base * 2 ** fails[key], cap)
            if coord.data and fails[key] < 4:
                _LOGGER.debug("%s: falha %s em %s (%s)", entry.title, fails[key], key, err)
                return coord.data
            raise UpdateFailed(str(err)) from err

        def ok(key: str, coord, base: timedelta) -> None:
            fails[key] = 0
            coord.update_interval = base

        async def update_local() -> dict:
            try:
                data = await hass.async_add_executor_job(local.fetch)
            except TapoAuthError as err:
                # A C200 v3 às vezes recusa um login bom. Com a câmera já funcionando, só pede
                # reautenticação após 3 ciclos seguidos (backoff de minutos não chega ao lockout).
                if coordinator.data and fails["main"] < 3:
                    return transient("main", coordinator, err, MAIN_INTERVAL, timedelta(minutes=5))
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # pytapo/requests: código da câmera ou rede
                return transient("main", coordinator, err, MAIN_INTERVAL, timedelta(minutes=5))
            ok("main", coordinator, MAIN_INTERVAL)
            return data

        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {entry.data[CONF_HOST]}",
            update_method=update_local, update_interval=MAIN_INTERVAL,
        )

        async def update_live() -> dict:
            live = coordinator.live
            try:
                data = await hass.async_add_executor_job(local.fetch_live)
            except TapoAuthError as err:
                # Login recusado: o ao-vivo não insiste; o coordinator principal decide (reauth).
                live.update_interval = timedelta(minutes=5)
                raise UpdateFailed(str(err)) from err
            except Exception as err:
                return transient("live", live, err, LIVE_INTERVAL, timedelta(seconds=60))
            ok("live", live, LIVE_INTERVAL)
            return data

        coordinator.local = local
        coordinator.ptz_step = 15
        coordinator.live = DataUpdateCoordinator(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {entry.data[CONF_HOST]} live",
            update_method=update_live, update_interval=LIVE_INTERVAL,
        )
        _adopt_rtsp_credentials(hass, entry)

    try:
        # No boot o executor do HA fica disputado; sem teto, uma câmera lenta estoura o
        # "Bootstrap stage 2 timeout" global. NotReady faz o HA tentar de novo depois.
        async with asyncio.timeout(90):
            await coordinator.async_config_entry_first_refresh()
            if hasattr(coordinator, "live"):
                coordinator.has_ptz = "getPresetConfig" in coordinator.data
                await coordinator.live.async_config_entry_first_refresh()
    except TimeoutError as err:
        raise ConfigEntryNotReady("A câmera demorou a responder") from err
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _adopt_rtsp_credentials(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Pega usuário/senha RTSP da conta de câmera já cadastrada no tapo_control."""
    if entry.data.get(CONF_RTSP_USERNAME):
        return
    for other in hass.config_entries.async_entries("tapo_control"):
        if other.data.get("ip_address") == entry.data[CONF_HOST] and other.data.get("username"):
            hass.config_entries.async_update_entry(entry, data={
                **entry.data, CONF_RTSP_USERNAME: other.data["username"],
                CONF_RTSP_PASSWORD: other.data["password"]})
            return


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
