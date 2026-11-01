"""Selects Tapo Local."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .const import CONF_KIND, KIND_CLOUD
from .entity import Setting, TapoEntity, g

# (key, setting, opções: valor da câmera -> opção do HA)
SELECTS = (
    ("night_vision", Setting("getDayNightModeConfig", "image", "common", "inf_type", "setDayNightModeConfig", chn=True),
     {"auto": "auto", "on": "on", "off": "off"}),
    ("light_frequency", Setting("getDayNightModeConfig", "image", "common", "light_freq_mode", "setLightFrequencyInfo"),
     {"auto": "auto", "50": "50hz", "60": "60hz"}),
    ("alarm_volume", Setting("getAlertConfig", "msg_alarm", "chn1_msg_alarm_info", "alarm_volume", "setAlertConfig"),
     {"low": "low", "normal": "normal", "high": "high"}),
)


class TapoSelect(TapoEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key: str, setting: Setting, options: dict[str, str]) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._setting = setting
        self._to_ha = options
        self._attr_options = list(options.values())

    @property
    def current_option(self):
        return self._to_ha.get(self._setting.read(self.coordinator.data))

    async def async_select_option(self, option: str) -> None:
        value = next(k for k, v in self._to_ha.items() if v == option)
        await self._write(self._setting, value)


class TapoSirenTypeSelect(TapoSelect):
    """alarm_type = índice em alert_type_list (Siren / Emergency / Red Alert…)."""

    def __init__(self, coordinator) -> None:
        names = g(coordinator.data, "getAlertTypeList", "msg_alarm", "alert_type", "alert_type_list") or []
        super().__init__(
            coordinator, "siren_type",
            Setting("getAlertConfig", "msg_alarm", "chn1_msg_alarm_info", "alarm_type", "setAlertConfig"),
            {str(i): name for i, name in enumerate(names)},
        )


class TapoPresetSelect(TapoEntity, SelectEntity):
    _attr_translation_key = "preset"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "preset")

    def _presets(self) -> dict[str, str]:
        p = g(self.coordinator.data, "getPresetConfig", "preset", "preset") or {}
        return dict(zip(p.get("name", []), p.get("id", []), strict=False))

    @property
    def options(self):
        return list(self._presets())

    @property
    def current_option(self):
        return None  # é uma ação, não um estado

    async def async_select_option(self, option: str) -> None:
        await self._call("motorMoveToPreset", {"preset": {"goto_preset": {"id": self._presets()[option]}}})


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    c = entry.runtime_data
    ents: list = [TapoSelect(c, k, st, opts) for k, st, opts in SELECTS if st.read(c.data) is not None]
    if g(c.data, "getAlertTypeList", "msg_alarm", "alert_type", "alert_type_list"):
        ents.append(TapoSirenTypeSelect(c))
    if c.has_ptz:
        ents.append(TapoPresetSelect(c))
    async_add_entities(ents)
