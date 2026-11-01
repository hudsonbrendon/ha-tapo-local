"""Switches Tapo Local."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from .const import CONF_KIND, KIND_CLOUD
from .entity import Setting, TapoEntity, g

CFG = EntityCategory.CONFIG


@dataclass(frozen=True, kw_only=True)
class TapoSwitchDescription(SwitchEntityDescription):
    setting: Setting
    on: str = "on"
    off: str = "off"


def s(key, get, module, section, field, set_, cat=CFG, on="on", off="off", **kw) -> TapoSwitchDescription:
    return TapoSwitchDescription(key=key, translation_key=key, entity_category=cat, on=on, off=off,
                                 setting=Setting(get, module, section, field, set_, **kw))


SWITCHES = (
    s("privacy", "getLensMaskConfig", "lens_mask", "lens_mask_info", "enabled", "setLensMaskConfig", cat=None),
    s("motion_detection", "getDetectionConfig", "motion_detection", "motion_det", "enabled", "setDetectionConfig", cat=None),
    s("person_detection", "getPersonDetectionConfig", "people_detection", "detection", "enabled", "setPersonDetectionConfig", cat=None),
    s("tamper_detection", "getTamperDetectionConfig", "tamper_detection", "tamper_det", "enabled", "setTamperDetectionConfig"),
    s("baby_cry_detection", "getBCDConfig", "sound_detection", "bcd", "enabled", "setBCDConfig"),
    s("vehicle_detection", "getVehicleDetectionConfig", "vehicle_detection", "detection", "enabled", "setVehicleDetectionConfig"),
    s("pet_detection", "getPetDetectionConfig", "pet_detection", "detection", "enabled", "setPetDetectionConfig"),
    s("auto_track", "getTargetTrackConfig", "target_track", "target_track_info", "enabled", "setTargetTrackConfig", cat=None),
    s("alarm", "getAlertConfig", "msg_alarm", "chn1_msg_alarm_info", "enabled", "setAlertConfig", cat=None),
    s("alarm_sound", "getAlertConfig", "msg_alarm", "chn1_msg_alarm_info", "sound_alarm_enabled", "setAlertConfig"),
    s("alarm_light", "getAlertConfig", "msg_alarm", "chn1_msg_alarm_info", "light_alarm_enabled", "setAlertConfig"),
    s("notifications", "getMsgPushConfig", "msg_push", "chn1_msg_push_info", "notification_enabled", "setMsgPushConfig"),
    s("rich_notifications", "getMsgPushConfig", "msg_push", "chn1_msg_push_info", "rich_notification_enabled", "setMsgPushConfig"),
    s("record_to_sd", "getRecordPlan", "record_plan", "chn1_channel", "enabled", "setRecordPlan"),
    s("loop_recording", "getCircularRecordingConfig", "harddisk_manage", "harddisk", "loop", "setCircularRecordingConfig"),
    s("record_audio", "getAudioConfig", "audio_config", "record_audio", "enabled", "setRecordAudio"),
    s("microphone_mute", "getAudioConfig", "audio_config", "microphone", "mute", "setMicrophoneVolume"),
    s("noise_cancelling", "getAudioConfig", "audio_config", "microphone", "noise_cancelling", "setMicrophoneVolume"),
    s("speaker_mute", "getAudioConfig", "audio_config", "speaker", "mute", "setSpeakerVolume"),
    s("led", "getLedStatus", "led", "config", "enabled", "setLedStatus"),
    s("flip", "getRotationStatus", "image", "switch", "flip_type", "setRotationStatus", on="center"),
    s("lens_distortion_correction", "getRotationStatus", "image", "switch", "ldc", "setLdc"),
    s("osd_date", "getOsd", "OSD", "date", "enabled", "setOsd"),
    s("privacy_zones", "getCoverConfig", "cover", "cover", "enabled", "setCoverConfig"),
    s("auto_upgrade", "getFirmwareAutoUpgradeConfig", "auto_upgrade", "common", "enabled",
      "setFirmwareAutoUpgradeConfig", include=("time", "random_range")),
    s("third_party", "getThirdPartyCompatibility", "local_ctrl", "third_party_setting", "enabled",
      "setThirdPartyCompatibility", cat=EntityCategory.DIAGNOSTIC),
)

# Rastreamento inteligente: só cria se smart_track_capability disser que suporta
SMART_TRACK = (("people", "smart_track_people"), ("pet", "smart_track_pet"), ("vehicle", "smart_track_vehicle"))


class TapoSwitch(TapoEntity, SwitchEntity):
    entity_description: TapoSwitchDescription

    def __init__(self, coordinator, description: TapoSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self):
        v = self.entity_description.setting.read(self.coordinator.data)
        return None if v is None else v == self.entity_description.on

    async def async_turn_on(self, **kwargs) -> None:
        await self._write(self.entity_description.setting, self.entity_description.on)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write(self.entity_description.setting, self.entity_description.off)


class TapoEventTableSwitch(TapoEntity, SwitchEntity):
    """Uma linha de msg_push_event (notificar) ou msg_alarm_type (disparar alarme)."""

    _attr_entity_category = CFG

    def __init__(self, coordinator, kind: str, event: str) -> None:
        super().__init__(coordinator, f"{kind}_{event}")
        self._kind, self._event = kind, event
        self._get, self._module, self._section, self._set = {
            "push": ("getMsgPushEventList", "msg_push", "msg_push_event", "setMsgPushEventList"),
            "alarm": ("getAlertEventType", "msg_alarm", "msg_alarm_type", "setAlertEventType"),
        }[kind]
        self._attr_translation_key = f"{kind}_{event}"

    def _rows(self) -> list[dict]:
        return g(self.coordinator.data, self._get, self._module, self._section) or []

    @property
    def is_on(self):
        row = next((r for r in self._rows() if r.get("name") == self._event), None)
        return None if row is None else row.get("enabled") == "on"

    async def _set_state(self, on: bool) -> None:
        rows = [dict(r) for r in self._rows()]
        for r in rows:
            if r.get("name") == self._event:
                r["enabled"] = "on" if on else "off"
        await self._call(self._set, {self._module: {self._section: rows}})
        g(self.coordinator.data, self._get, self._module)[self._section] = rows
        self.coordinator.async_update_listeners()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)


class TapoPatrolSwitch(TapoEntity, SwitchEntity):
    _attr_translation_key = "patrol"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "patrol")

    @property
    def is_on(self):
        v = g(self.coordinator.data, "getPatrolStatus", "patrol", "patrol", "value", 0)
        return None if v is None else v == "on"

    async def _set_state(self, on: bool) -> None:
        await self._call("setPatrolStatus", {"patrol": {"set_patrol_status": {"value": "on" if on else "off"}}})
        g(self.coordinator.data, "getPatrolStatus", "patrol", "patrol")["value"] = ["on" if on else "off"]
        self.coordinator.async_update_listeners()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        return
    c = entry.runtime_data
    d = c.data
    ents: list = [TapoSwitch(c, desc) for desc in SWITCHES if desc.setting.read(d) is not None]
    cap = g(d, "getSmartTrackCapability", "smart_track", "smart_track_capability") or {}
    for kind, key in SMART_TRACK:
        if cap.get(f"{kind}_support") == "1":
            ents.append(TapoSwitch(c, s(key, "getSmartTrackConfig", "smart_track", "smart_track_info",
                                        f"{kind}_enabled", "setSmartTrackConfig")))
    for r in g(d, "getMsgPushEventList", "msg_push", "msg_push_event") or []:
        ents.append(TapoEventTableSwitch(c, "push", r["name"]))
    for r in g(d, "getAlertEventType", "msg_alarm", "msg_alarm_type") or []:
        ents.append(TapoEventTableSwitch(c, "alarm", r["name"]))
    if g(d, "getPatrolStatus", "patrol", "patrol", "value") is not None:
        ents.append(TapoPatrolSwitch(c))
    async_add_entities(ents)
