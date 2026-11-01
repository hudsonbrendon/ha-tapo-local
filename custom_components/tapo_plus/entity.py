"""Base das entidades locais + tabela de configurações graváveis.

Toda configuração da câmera é lida com get<X> {módulo:{name:[seção]}} e gravada
com set<X> {módulo:{seção:{campo:valor}}} — mesmo formato que o app usa
(mv0/zk.java). Cada linha abaixo foi testada (grava → relê → reverte) numa C200.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TapoCommandError


def g(d: Any, *path: Any) -> Any:
    for p in path:
        try:
            d = d[p]
        except (KeyError, IndexError, TypeError):
            return None
    return d


@dataclass(frozen=True)
class Setting:
    get: str            # método get* cuja resposta está em coordinator.data
    module: str
    section: str
    field: str
    set: str            # método set* correspondente
    chn: bool = False   # alguns set exigem "chn_id": ["1"] (ex.: setDayNightModeConfig)
    include: tuple[str, ...] = ()  # campos atuais reenviados junto (ex.: auto-update)
    extra: dict = field(default_factory=dict)  # campos fixos enviados junto

    def read(self, data: dict) -> Any:
        return g(data, self.get, self.module, self.section, self.field)

    def payload(self, data: dict, value: Any) -> dict:
        current = g(data, self.get, self.module, self.section) or {}
        body = {k: current[k] for k in self.include if k in current}
        body.update(self.extra)
        body[self.field] = value
        params: dict = {self.module: {self.section: body}}
        if self.chn:
            params[self.module]["chn_id"] = ["1"]
        return params


class TapoEntity(CoordinatorEntity):
    """Entidade local: mesmo dispositivo do tapo_control (vínculo por MAC)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        info = g(coordinator.data, "getDeviceInfo", "device_info", "basic_info") or {}
        self._mac = format_mac(info.get("mac", ""))
        self._attr_unique_id = f"{self._mac}_{key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            manufacturer="TP-Link", model=info.get("device_model"), hw_version=info.get("hw_version"),
            sw_version=info.get("sw_version"), name=(info.get("device_alias") or "").strip() or None,
        )

    @property
    def local(self):
        return self.coordinator.local

    async def _call(self, method: str, params: dict) -> None:
        try:
            await self.hass.async_add_executor_job(self.local.call, method, params)
        except TapoCommandError as err:
            raise HomeAssistantError(f"A câmera recusou {method} ({err.code})") from err
        except Exception as err:  # pytapo/rede
            raise HomeAssistantError(str(err)) from err

    async def _write(self, setting: Setting, value: Any) -> None:
        await self._call(setting.set, setting.payload(self.coordinator.data, value))
        # Atualiza na hora (o firmware só confirma; a releitura vem no próximo ciclo)
        section = g(self.coordinator.data, setting.get, setting.module, setting.section)
        if isinstance(section, dict):
            section[setting.field] = value
            self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()
