"""Binários Tapo Plus."""

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
    TapoBinaryDescription(
        key="third_party", translation_key="third_party", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: on(g(d, "getThirdPartyCompatibility", "local_ctrl", "third_party_setting", "enabled")),
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


class TapoCloudOnline(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "cloud_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, dev: dict) -> None:
        super().__init__(coordinator)
        self._device_id = dev["deviceId"]
        self._attr_unique_id = f"cloud_{self._device_id}_online"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, format_mac(dev.get("deviceMac", "")))},
            manufacturer="TP-Link", model=dev.get("deviceModel"), name=dev.get("alias"),
        )

    @property
    def is_on(self):
        dev = next((d for d in self.coordinator.data["devices"] if d.get("deviceId") == self._device_id), None)
        return None if dev is None else dev.get("status") == 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        async_add_entities(TapoCloudOnline(coordinator, d) for d in coordinator.data["devices"])
        return
    async_add_entities(TapoLocalBinary(coordinator, desc) for desc in LOCAL_BINARIES)
