"""Roda todos os sensores contra uma resposta real da C200 (fw 1.5.7).

uv run --python 3.14 --with homeassistant --with numpy --with ha-ffmpeg --with PyTurboJPEG --with av --with python-tapo-local python tests/check_sensors.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components"))
from tapo_local.binary_sensor import LOCAL_BINARIES  # noqa: E402
from tapo_local.sensor import LOCAL_SENSORS, fps, record_mode  # noqa: E402
from tapo_local import button, camera, number, select, siren, switch, update  # noqa: E402,F401
from tapo_local.entity import Setting  # noqa: E402

d = json.loads((Path(__file__).with_name("fixture_c200.json")).read_text())
vals = {s.key: s.value_fn(d) for s in LOCAL_SENSORS}
for s in LOCAL_SENSORS:
    if s.attrs_fn:
        s.attrs_fn(d)
bins = {b.key: b.value_fn(d) for b in LOCAL_BINARIES}

assert vals["last_event_type"] == "motion"
assert vals["events_24h"] == 336
assert vals["last_person"] is not None and vals["last_motion"] is not None
assert record_mode(d) == "events"  # plano "0000-2400:2" = só eventos
assert fps(d) == 15  # 65551 & 0xFFFF
assert vals["video_resolution"] == "1920x1080"
assert 99 < vals["sd_used"] < 100
assert vals["recordings_today"] == 0  # fixture capturada logo após a meia-noite
assert bins == {"sd_problem": False, "upnp": True, "onvif_tls": False}
# payload de escrita = mesmo formato testado ao vivo
st = Setting("getFirmwareAutoUpgradeConfig", "auto_upgrade", "common", "enabled", "setFirmwareAutoUpgradeConfig",
             include=("time", "random_range"))
assert st.payload({"getFirmwareAutoUpgradeConfig": {"auto_upgrade": {"common": {"enabled": "on", "time": "03:00", "random_range": "120"}}}}, "off") \
    == {"auto_upgrade": {"common": {"time": "03:00", "random_range": "120", "enabled": "off"}}}
assert Setting("x", "image", "common", "inf_type", "setDayNightModeConfig", chn=True).payload({}, "on") \
    == {"image": {"common": {"inf_type": "on"}, "chn_id": ["1"]}}
print("ok", {k: str(v) for k, v in vals.items()})
