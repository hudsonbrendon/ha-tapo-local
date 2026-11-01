"""Binários Tapo Local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_KIND, KIND_CLOUD
from .sensor import g, local_device, sd


@dataclass(frozen=True, kw_only=True)
class TapoBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], bool | None]


def on(v) -> bool | None:
    return None if v is None else v == "on"


LOCAL_BINARIES = (
    TapoBinaryDescription(
        key="sd_problem", translation_key="sd_problem", device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: None if sd(d, "status") is None else sd(d, "status") != "normal",
    ),
    TapoBinaryDescription(
        key="upnp", translation_key="upnp", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: on(g(d, "getUpnpInfo", "upnpc", "upnpc_info", "enabled")),
    ),
    TapoBinaryDescription(
        key="onvif_tls", translation_key="onvif_tls", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: on(g(d, "getOnvifSecurityConfig", "security_config", "onvif_security_config", "tls_enable")),
    ),
)


class TapoLocalBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    entity_description: TapoBinaryDescription

    def __init__(self, coordinator, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        mac = format_mac(g(coordinator.data, "getDeviceInfo", "device_info", "basic_info", "mac") or "")
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = local_device(coordinator.data)

    @property
    def is_on(self):
        return self.entity_description.value_fn(self.coordinator.data)


class TapoLiveBinary(CoordinatorEntity, BinarySensorEntity):
    """Movimento/pessoa agora: evento em andamento no searchDetectionList (polling 5 s)."""

    _attr_has_entity_name = True

    def __init__(self, live, base_info: DeviceInfo, mac: str, key: str, codes: tuple[int, ...],
                 device_class) -> None:
        super().__init__(live)
        self._attr_translation_key = key
        self._attr_unique_id = f"{mac}_{key}"
        self._attr_device_info = base_info
        self._attr_device_class = device_class
        self._codes = codes

    @property
    def is_on(self):
        d = self.coordinator.data or {}
        now = d.get("_fetched_at", 0)
        events = g(d, "searchDetectionList", "playback", "search_detection_list") or []
        # end_time vem no futuro enquanto o evento dura; folga de 10 s pra não piscar
        return any(e.get("alarm_type") in self._codes and e.get("end_time", 0) + 10 >= now for e in events)

    @property
    def extra_state_attributes(self):
        info = g(self.coordinator.data, "getLastAlarmInfo", "system", "last_alarm_info") or {}
        return {"last_type": info.get("last_alarm_type")}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        # Sem "online" da nuvem: status do getDeviceList é sempre 0 e o passthrough
        # responde -20571 (offline) mesmo com a câmera mandando notificações.
        return
    ents: list = [TapoLocalBinary(coordinator, desc) for desc in LOCAL_BINARIES]
    info = local_device(coordinator.data)
    mac = format_mac(g(coordinator.data, "getDeviceInfo", "device_info", "basic_info", "mac") or "")
    ents += [
        TapoLiveBinary(coordinator.live, info, mac, "motion", (2,), BinarySensorDeviceClass.MOTION),
        TapoLiveBinary(coordinator.live, info, mac, "person", (6,), BinarySensorDeviceClass.OCCUPANCY),
        TapoLiveBinary(coordinator.live, info, mac, "any_event", tuple(range(2, 40)), BinarySensorDeviceClass.MOTION),
    ]
    async_add_entities(ents)
