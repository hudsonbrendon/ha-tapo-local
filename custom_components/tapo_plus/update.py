"""Firmware Tapo Plus."""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature

from .const import CONF_KIND, KIND_CLOUD
from .entity import TapoEntity, g


class TapoFirmware(TapoEntity, UpdateEntity):
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_translation_key = "firmware"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def installed_version(self):
        return g(self.coordinator.data, "getDeviceInfo", "device_info", "basic_info", "sw_version")

    @property
    def latest_version(self):
        # upgrade_info.last_version = última versão que a nuvem ofereceu à câmera
        return g(self.coordinator.data, "getCloudConfig", "cloud_config", "upgrade_info", "last_version") \
            or self.installed_version

    @property
    def in_progress(self):
        return g(self.coordinator.data, "getFirmwareUpdateStatus", "cloud_config", "upgrade_status", "state") \
            not in (None, "normal")

    async def async_install(self, version, backup, **kwargs) -> None:
        await self._call("checkFirmwareVersionByCloud", {"cloud_config": {"check_fw_version": "null"}})
        await self._call("startFirmwareUpgrade", {"cloud_config": {"fw_download": "null"}})
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    async_add_entities([TapoFirmware(entry.runtime_data)])
