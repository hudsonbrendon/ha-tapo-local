"""Sensores Tapo Plus (local por câmera + nuvem por conta)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_KIND, DOMAIN, EVENT_TYPES, KIND_CLOUD, RECORD_TYPES


def g(d: Any, *path: Any) -> Any:
    for p in path:
        try:
            d = d[p]
        except (KeyError, IndexError, TypeError):
            return None
    return d


def ts(v: Any) -> datetime | None:
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v > 10**12:  # nuvem às vezes manda em ms
        v //= 1000
    return datetime.fromtimestamp(v, UTC)


def events(d: dict) -> list[dict]:
    return g(d, "searchDetectionList", "playback", "search_detection_list") or []


def last_of(d: dict, code: int) -> datetime | None:
    times = [e["start_time"] for e in events(d) if e.get("alarm_type") == code]
    return ts(max(times)) if times else None


def videos_today(d: dict) -> list[dict]:
    items = g(d, "searchVideoOfDay", "playback", "search_video_results") or []
    return [v for item in items for v in item.values()]


def sd(d: dict, key: str) -> Any:
    return g(d, "getSdCardStatus", "harddisk_manage", "hd_info", 0, "hd_info_1", key)


def sd_bytes(d: dict, key: str) -> float | None:
    v = sd(d, key)
    return int(v.rstrip("B")) if isinstance(v, str) and v.rstrip("B").isdigit() else None


def sd_used_pct(d: dict) -> float | None:
    total, free = sd_bytes(d, "total_space_accurate"), sd_bytes(d, "free_space_accurate")
    return round(100 * (total - free) / total, 1) if total else None


def retention_days(d: dict) -> float | None:
    start = sd(d, "record_start_time")
    if not start or not str(start).isdigit() or int(start) == 0:
        return None
    return round((d["_fetched_at"] - int(start)) / 86400, 1)


def record_mode(d: dict) -> str | None:
    plan = g(d, "getRecordPlan", "record_plan", "chn1_channel")
    if not plan:
        return None
    if plan.get("enabled") != "on":
        return "off"
    kinds = set()
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        try:
            kinds |= {seg.rsplit(":", 1)[1] for seg in json.loads(plan.get(day, "[]"))}
        except (ValueError, IndexError):
            continue
    if not kinds:
        return "off"
    return RECORD_TYPES.get(kinds.pop(), "mixed") if len(kinds) == 1 else "mixed"


def video(d: dict, key: str) -> Any:
    return g(d, "getVideoQualities", "video", "main", key)


def fps(d: dict) -> int | None:
    v = video(d, "frame_rate")
    # 65551 = 0x1000F: os 16 bits baixos são o fps (o app faz & 0xFFFF)
    return int(v) & 0xFFFF if v and str(v).isdigit() else None


def enabled_list(items: list | None) -> dict[str, bool]:
    return {i["name"]: i.get("enabled") == "on" for i in items or []}


@dataclass(frozen=True, kw_only=True)
class TapoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None


LOCAL_SENSORS: tuple[TapoSensorDescription, ...] = (
    TapoSensorDescription(
        key="last_event", translation_key="last_event", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: ts(g(d, "getLastAlarmInfo", "system", "last_alarm_info", "last_alarm_time")),
        attrs_fn=lambda d: {"type": g(d, "getLastAlarmInfo", "system", "last_alarm_info", "last_alarm_type")},
    ),
    TapoSensorDescription(
        key="last_event_type", translation_key="last_event_type",
        value_fn=lambda d: g(d, "getLastAlarmInfo", "system", "last_alarm_info", "last_alarm_type"),
    ),
    TapoSensorDescription(
        key="events_24h", translation_key="events_24h", state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="eventos",
        value_fn=lambda d: len(events(d)),
        attrs_fn=lambda d: {
            "by_type": dict(Counter(EVENT_TYPES.get(e.get("alarm_type"), str(e.get("alarm_type"))) for e in events(d))),
            "recent": [
                {"type": EVENT_TYPES.get(e.get("alarm_type"), e.get("alarm_type")),
                 "start": ts(e.get("start_time")).isoformat() if ts(e.get("start_time")) else None,
                 "duration_s": (e.get("end_time") or 0) - (e.get("start_time") or 0)}
                for e in sorted(events(d), key=lambda e: e.get("start_time", 0), reverse=True)[:10]
            ],
        },
    ),
    TapoSensorDescription(
        key="last_motion", translation_key="last_motion", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: last_of(d, 2),
    ),
    TapoSensorDescription(
        key="last_person", translation_key="last_person", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: last_of(d, 6),
    ),
    TapoSensorDescription(
        key="recordings_today", translation_key="recordings_today", state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="clipes",
        value_fn=lambda d: len(videos_today(d)) if "searchVideoOfDay" in d else None,
    ),
    TapoSensorDescription(
        key="recorded_today", translation_key="recorded_today", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: round(sum(v.get("endTime", 0) - v.get("startTime", 0) for v in videos_today(d)) / 60, 1)
        if "searchVideoOfDay" in d else None,
    ),
    TapoSensorDescription(
        key="record_mode", translation_key="record_mode", device_class=SensorDeviceClass.ENUM,
        options=["off", "continuous", "events", "aov", "mixed"], value_fn=record_mode,
        attrs_fn=lambda d: {"loop_recording": g(d, "getCircularRecordingConfig", "harddisk_manage", "harddisk", "loop") == "on",
                            "record_audio": g(d, "getAudioConfig", "audio_config", "record_audio", "enabled") == "on"},
    ),
    TapoSensorDescription(
        key="sd_used", translation_key="sd_used", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, value_fn=sd_used_pct,
        attrs_fn=lambda d: {"status": sd(d, "status"), "total": sd(d, "total_space"), "free": sd(d, "free_space")},
    ),
    TapoSensorDescription(
        key="sd_oldest_recording", translation_key="sd_oldest_recording", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: ts(sd(d, "record_start_time")),
    ),
    TapoSensorDescription(
        key="sd_retention", translation_key="sd_retention", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS, value_fn=retention_days,
    ),
    TapoSensorDescription(
        key="video_resolution", translation_key="video_resolution", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (video(d, "resolution") or "").replace("*", "x") or None,
        attrs_fn=lambda d: {"codec": video(d, "encode_type"), "fps": fps(d), "bitrate_type": video(d, "bitrate_type"),
                            "quality": video(d, "quality"), "smart_codec": video(d, "smart_codec"),
                            "supported": g(d, "getVideoCapability", "video_capability")},
    ),
    TapoSensorDescription(
        key="video_bitrate", translation_key="video_bitrate", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DATA_RATE, native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        value_fn=lambda d: int(video(d, "bitrate")) if str(video(d, "bitrate") or "").isdigit() else None,
    ),
    TapoSensorDescription(
        key="video_codec", translation_key="video_codec", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: video(d, "encode_type"),
    ),
    TapoSensorDescription(
        key="video_fps", translation_key="video_fps", entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="fps", value_fn=fps,
    ),
    TapoSensorDescription(
        key="wifi_signal", translation_key="wifi_signal", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH, native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: g(d, "getConnectionType", "rssiValue"),
        attrs_fn=lambda d: {"ssid": g(d, "getConnectionType", "ssid"), "link_type": g(d, "getConnectionType", "link_type"),
                            "level": g(d, "getConnectionType", "rssi")},
    ),
    TapoSensorDescription(
        key="ip_address", translation_key="ip_address", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: g(d, "getDeviceIpAddress", "network", "wan", "ipaddr"),
        attrs_fn=lambda d: {k: g(d, "getDeviceIpAddress", "network", "wan", k)
                            for k in ("netmask", "gateway", "pri_dns", "snd_dns", "proto")},
    ),
    TapoSensorDescription(
        key="connected_since", translation_key="connected_since", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        # up_time oscila alguns segundos entre leituras; arredonda pro minuto pra não spammar o histórico
        value_fn=lambda d: ts((d["_fetched_at"] - up) // 60 * 60)
        if (up := g(d, "getDeviceIpAddress", "network", "wan", "up_time")) else None,
    ),
    TapoSensorDescription(
        key="clock_offset", translation_key="clock_offset", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: s - d["_fetched_at"]
        if (s := g(d, "getClockStatus", "system", "clock_status", "seconds_from_1970")) else None,
        attrs_fn=lambda d: {"local_time": g(d, "getClockStatus", "system", "clock_status", "local_time"),
                            **(g(d, "getTimezone", "system", "basic") or {})},
    ),
    TapoSensorDescription(
        key="firmware_state", translation_key="firmware_state", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: g(d, "getFirmwareUpdateStatus", "cloud_config", "upgrade_status", "state"),
        attrs_fn=lambda d: {
            "last_upgrade_ok": g(d, "getFirmwareUpdateStatus", "cloud_config", "upgrade_status", "lastUpgradingSuccess"),
            "auto_upgrade": g(d, "getFirmwareAutoUpgradeConfig", "auto_upgrade", "common", "enabled") == "on",
            "auto_upgrade_time": g(d, "getFirmwareAutoUpgradeConfig", "auto_upgrade", "common", "time"),
            "latest_known": g(d, "getCloudConfig", "cloud_config", "upgrade_info", "last_version"),
        },
    ),
    TapoSensorDescription(
        key="notifications", translation_key="notifications", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: sum(enabled_list(g(d, "getMsgPushEventList", "msg_push", "msg_push_event")).values()),
        attrs_fn=lambda d: {
            "push": enabled_list(g(d, "getMsgPushEventList", "msg_push", "msg_push_event")),
            "alarm": enabled_list(g(d, "getAlertEventType", "msg_alarm", "msg_alarm_type")),
            "motion_sensitivity": g(d, "getDetectionConfig", "motion_detection", "motion_det", "digital_sensitivity"),
            "person_sensitivity": g(d, "getPersonDetectionConfig", "people_detection", "detection", "sensitivity"),
            "tapo_care": g(d, "getTapoCareServiceList", "tapo_care", "service_list"),
        },
    ),
)


def local_device(d: dict) -> DeviceInfo:
    info = g(d, "getDeviceInfo", "device_info", "basic_info") or {}
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, format_mac(info.get("mac", "")))},
        manufacturer="TP-Link", model=info.get("device_model"), hw_version=info.get("hw_version"),
        sw_version=info.get("sw_version"), name=(info.get("device_alias") or "").strip() or None,
    )


class TapoLocalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    entity_description: TapoSensorDescription

    def __init__(self, coordinator, description: TapoSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        info = g(coordinator.data, "getDeviceInfo", "device_info", "basic_info") or {}
        self._attr_unique_id = f"{format_mac(info.get('mac', ''))}_{description.key}"
        self._attr_device_info = local_device(coordinator.data)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None


# ---------------------------------------------------------------- nuvem


def msg_attach(m: dict) -> dict:
    a = m.get("attachments")
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            a = {}
    return a if isinstance(a, dict) else {}


class TapoCloudSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._key = key
        self._attr_translation_key = f"cloud_{key}"
        self._attr_unique_id = f"cloud_{device_id}_{key}"
        dev = self._dev
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, format_mac(dev.get("deviceMac", "")))},
            manufacturer="TP-Link", model=dev.get("deviceModel"), name=dev.get("alias"),
        )
        if key == "last_notification":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key == "firmware":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == "notifications_24h":
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "notificações"

    @property
    def _dev(self) -> dict:
        return next((d for d in self.coordinator.data["devices"] if d.get("deviceId") == self._device_id), {})

    @property
    def _msgs(self) -> list[dict]:
        return self.coordinator.data["messages"].get(self._device_id, [])

    @property
    def native_value(self):
        if self._key == "firmware":
            return self._dev.get("fwVer")
        if self._key == "notifications_24h":
            now = datetime.now(UTC).timestamp()
            return sum(1 for m in self._msgs if (t := ts(m.get("time"))) and now - t.timestamp() < 86400)
        return ts(self._msgs[0].get("time")) if self._msgs else None

    @property
    def extra_state_attributes(self):
        if self._key == "firmware":
            dev = self._dev
            return {k: dev.get(k) for k in ("deviceHwVer", "deviceId", "hwId", "fwId", "oemId", "role",
                                            "deviceRegion", "appServerUrl")}
        if self._key == "last_notification" and self._msgs:
            m = self._msgs[0]
            a = msg_attach(m)
            return {"title": m.get("title"), "content": m.get("content"), "type": m.get("msgType"),
                    "category": m.get("msgCategory"), "image_url": a.get("imgUrl"),
                    "sub_type": a.get("msgSubType")}
        return None


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    if entry.data.get(CONF_KIND) == KIND_CLOUD:
        async_add_entities(
            TapoCloudSensor(coordinator, d["deviceId"], key)
            for d in coordinator.data["devices"]
            for key in ("last_notification", "notifications_24h", "firmware")
        )
        return
    async_add_entities(TapoLocalSensor(coordinator, desc) for desc in LOCAL_SENSORS)
