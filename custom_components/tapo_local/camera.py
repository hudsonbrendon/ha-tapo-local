"""Câmeras HD/SD (RTSP) Tapo Local."""

from __future__ import annotations

from urllib.parse import quote

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import async_get_image

from .const import CONF_KIND, CONF_RTSP_PASSWORD, CONF_RTSP_USERNAME, KIND_CLOUD
from .entity import TapoEntity

STREAMS = (("hd", "stream1"), ("sd", "stream2"))


class TapoCamera(TapoEntity, Camera):
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator, key: str, path: str, url: str) -> None:
        TapoEntity.__init__(self, coordinator, f"camera_{key}")
        Camera.__init__(self)
        self._attr_translation_key = f"camera_{key}"
        self._url = url
        if key == "sd":
            self._attr_entity_registry_enabled_default = False

    async def stream_source(self) -> str:
        return self._url

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        return await async_get_image(self.hass, self._url, width=width, height=height)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD or not entry.data.get(CONF_RTSP_USERNAME):
        return
    c = entry.runtime_data
    auth = f"{quote(entry.data[CONF_RTSP_USERNAME], safe='')}:{quote(entry.data[CONF_RTSP_PASSWORD], safe='')}"
    async_add_entities(
        TapoCamera(c, key, path, f"rtsp://{auth}@{c.local.host}:554/{path}") for key, path in STREAMS
    )
