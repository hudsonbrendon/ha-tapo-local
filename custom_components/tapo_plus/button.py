"""Botões Tapo Plus: reboot, formatar SD, calibrar e mover o PTZ."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory

from .const import CONF_KIND, KIND_CLOUD
from .entity import TapoEntity

# (key, método, params, categoria, precisa de PTZ) — formatos do app/pytapo
ACTIONS = (
    ("reboot", "rebootDevice", {"system": {"reboot": "null"}}, EntityCategory.CONFIG, False),
    ("format_sd", "formatSdCard", {"harddisk_manage": {"format_hd": "1"}}, EntityCategory.CONFIG, False),
    ("calibrate", "manualCalibrate", {"motor": {"manual_cali": ""}}, EntityCategory.CONFIG, True),
)
MOVES = {"move_up": (0, 1), "move_down": (0, -1), "move_left": (-1, 0), "move_right": (1, 0)}


class TapoButton(TapoEntity, ButtonEntity):
    def __init__(self, coordinator, key, method, params, category) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._attr_entity_category = category
        self._method, self._params = method, params
        if key == "reboot":
            self._attr_device_class = ButtonDeviceClass.RESTART

    async def async_press(self) -> None:
        await self._call(self._method, self._params)


class TapoMoveButton(TapoEntity, ButtonEntity):
    def __init__(self, coordinator, key, direction) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._dir = direction

    async def async_press(self) -> None:
        step = self.coordinator.ptz_step
        x, y = self._dir
        await self._call("motorMove", {"motor": {"move": {"x_coord": str(x * step), "y_coord": str(y * step)}}})


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    c = entry.runtime_data
    ents: list = [TapoButton(c, k, m, p, cat) for k, m, p, cat, ptz in ACTIONS if c.has_ptz or not ptz]
    if c.has_ptz:
        ents += [TapoMoveButton(c, k, d) for k, d in MOVES.items()]
    async_add_entities(ents)
