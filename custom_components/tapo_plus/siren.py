"""Sirene (alarme manual) Tapo Plus."""

from __future__ import annotations

from homeassistant.components.siren import SirenEntity, SirenEntityFeature

from .api import TapoCommandError
from .const import CONF_KIND, KIND_CLOUD
from .entity import TapoEntity


class TapoSiren(TapoEntity, SirenEntity):
    _attr_translation_key = "siren"
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
    _attr_assumed_state = True  # a C200 não tem getManualAlarmStatus

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "siren")
        self._attr_is_on = False

    def _alarm(self, action: str) -> None:
        # app novo: doManualAlarm; firmwares antigos (C200) só o formato legado "do"
        try:
            self.local.call("doManualAlarm", {"msg_alarm": {"manual_alarm": {"action": action}}})
        except TapoCommandError:
            self.local.legacy({"method": "do", "msg_alarm": {"manual_msg_alarm": {"action": action}}})

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._alarm, "start")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._alarm, "stop")
        self._attr_is_on = False
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    c = entry.runtime_data
    if "getAlertConfig" in c.data:
        async_add_entities([TapoSiren(c)])
