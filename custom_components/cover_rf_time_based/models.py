"""Datamodels for cover_rf_time_based."""
from dataclasses import dataclass
from typing import Optional, Any

@dataclass(slots=True)
class DeviceConfig:
    name: str
    device_class: str
    travel_time_down: int
    travel_time_up: int
    tilting_time_down: float
    tilting_time_up: float
    send_stop_at_ends: bool
    always_confident: bool
    block_tilt_if_open: bool
    tilt_only_when_closed: bool
    availability_template: Optional[Any]
    command_delay: float

@dataclass(slots=True)
class ScriptsConfig:
    open_script: Optional[str]
    close_script: Optional[str]
    stop_script: Optional[str]
    tilt_open_script: Optional[str]
    tilt_close_script: Optional[str]
    tilt_stop_script: Optional[str]

@dataclass(slots=True)
class WrapperConfig:
    cover_entity_id: Optional[str]

