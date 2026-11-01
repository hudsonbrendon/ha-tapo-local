"""Numbers Tapo Plus."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory

from .const import CONF_KIND, KIND_CLOUD
from .entity import Setting, TapoEntity


@dataclass(frozen=True, kw_only=True)
class TapoNumberDescription(NumberEntityDescription):
    setting: Setting


def n(key, get, module, section, field, set_) -> TapoNumberDescription:
    return TapoNumberDescription(
        key=key, translation_key=key, entity_category=EntityCategory.CONFIG,
        native_min_value=0, native_max_value=100, native_step=1, native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER, setting=Setting(get, module, section, field, set_),
    )


NUMBERS = (
    n("motion_sensitivity", "getDetectionConfig", "motion_detection", "motion_det", "digital_sensitivity", "setDetectionConfig"),
    n("person_sensitivity", "getPersonDetectionConfig", "people_detection", "detection", "sensitivity", "setPersonDetectionConfig"),
    n("tamper_sensitivity", "getTamperDetectionConfig", "tamper_detection", "tamper_det", "digital_sensitivity", "setTamperDetectionConfig"),
    n("baby_cry_sensitivity", "getBCDConfig", "sound_detection", "bcd", "digital_sensitivity", "setBCDConfig"),
    n("speaker_volume", "getAudioConfig", "audio_config", "speaker", "volume", "setSpeakerVolume"),
    n("microphone_volume", "getAudioConfig", "audio_config", "microphone", "volume", "setMicrophoneVolume"),
    # contraste/saturação/nitidez existem no get mas o firmware da C200 recusa gravar (-40209)
    n("brightness", "getDayNightModeConfig", "image", "common", "luma", "setImageLumaConfig"),
)


class TapoNumber(TapoEntity, NumberEntity):
    entity_description: TapoNumberDescription

    def __init__(self, coordinator, description) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        v = self.entity_description.setting.read(self.coordinator.data)
        return float(v) if v is not None and str(v).lstrip("-").isdigit() else None

    async def async_set_native_value(self, value: float) -> None:
        await self._write(self.entity_description.setting, str(int(value)))


class TapoPtzStep(TapoEntity, NumberEntity):
    """Quantos graus cada botão de seta move (só no HA, não vai pra câmera)."""

    _attr_translation_key = "ptz_step"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ptz_step")

    @property
    def native_value(self):
        return self.coordinator.ptz_step

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.ptz_step = int(value)
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    c = entry.runtime_data
    ents: list = [TapoNumber(c, d) for d in NUMBERS if d.setting.read(c.data) is not None]
    if c.has_ptz:
        ents.append(TapoPtzStep(c))
    async_add_entities(ents)
