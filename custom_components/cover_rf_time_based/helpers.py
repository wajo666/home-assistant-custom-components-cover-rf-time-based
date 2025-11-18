"""Helper / factory functions for cover_rf_time_based."""
from __future__ import annotations
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from .const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_DEVICE_CLASS,
    CONF_COVER_ENTITY_ID,
    CONF_ALIASES,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONF_TILTING_TIME_DOWN,
    CONF_TILTING_TIME_UP,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
    CONF_BLOCK_TILT_IF_OPEN,
    CONF_TILT_ONLY_WHEN_CLOSED,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OPEN_SCRIPT_ENTITY_ID,
    CONF_CLOSE_SCRIPT_ENTITY_ID,
    CONF_STOP_SCRIPT_ENTITY_ID,
    CONF_TILT_OPEN_SCRIPT_ENTITY_ID,
    CONF_TILT_CLOSE_SCRIPT_ENTITY_ID,
    CONF_TILT_STOP_SCRIPT_ENTITY_ID,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_TRAVEL_TIME,
    DEFAULT_TILT_TIME,
    DEFAULT_SEND_STOP_AT_ENDS,
    DEFAULT_ALWAYS_CONFIDENT,
    DEFAULT_BLOCK_TILT_IF_OPEN,
    DEFAULT_TILT_ONLY_WHEN_CLOSED,
)
from .models import DeviceConfig, ScriptsConfig, WrapperConfig
from .entity import CoverTimeBased

_LOGGER = logging.getLogger(__name__)

BASE_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_COVER_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ALIASES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
    vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
    vol.Optional(CONF_TILTING_TIME_DOWN, default=DEFAULT_TILT_TIME): vol.Any(cv.positive_int, cv.positive_float),
    vol.Optional(CONF_TILTING_TIME_UP, default=DEFAULT_TILT_TIME): vol.Any(cv.positive_int, cv.positive_float),
    vol.Optional(CONF_SEND_STOP_AT_ENDS, default=DEFAULT_SEND_STOP_AT_ENDS): cv.boolean,
    vol.Optional(CONF_ALWAYS_CONFIDENT, default=DEFAULT_ALWAYS_CONFIDENT): cv.boolean,
    vol.Optional(CONF_BLOCK_TILT_IF_OPEN, default=DEFAULT_BLOCK_TILT_IF_OPEN): cv.boolean,
    vol.Optional(CONF_TILT_ONLY_WHEN_CLOSED, default=DEFAULT_TILT_ONLY_WHEN_CLOSED): cv.boolean,
    vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
})
SCRIPT_DEVICE_SCHEMA = BASE_DEVICE_SCHEMA.extend({
    vol.Required(CONF_OPEN_SCRIPT_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_CLOSE_SCRIPT_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_STOP_SCRIPT_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_TILT_OPEN_SCRIPT_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_TILT_STOP_SCRIPT_ENTITY_ID): cv.entity_id,
})
COVER_DEVICE_SCHEMA = vol.Any(vol.Schema(SCRIPT_DEVICE_SCHEMA))
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_DEVICES): vol.Schema({cv.slug: COVER_DEVICE_SCHEMA})})

# Duplicate guard
_REGISTERED_DEVICE_IDS: set[str] = set()

def devices_from_config(domain_config):
    devices = []
    raw_devices = domain_config.get(CONF_DEVICES, {})
    for dev_id, raw in raw_devices.items():
        if dev_id in _REGISTERED_DEVICE_IDS:
            _LOGGER.debug("Skipping duplicate device '%s' (already registered)", dev_id)
            continue
        c = dict(raw)
        base = DeviceConfig(
            name=c.get(CONF_NAME, dev_id),
            device_class=c.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            travel_time_down=c.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
            travel_time_up=c.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
            tilting_time_down=c.get(CONF_TILTING_TIME_DOWN, DEFAULT_TILT_TIME),
            tilting_time_up=c.get(CONF_TILTING_TIME_UP, DEFAULT_TILT_TIME),
            send_stop_at_ends=c.get(CONF_SEND_STOP_AT_ENDS, DEFAULT_SEND_STOP_AT_ENDS),
            always_confident=c.get(CONF_ALWAYS_CONFIDENT, DEFAULT_ALWAYS_CONFIDENT),
            block_tilt_if_open=c.get(CONF_BLOCK_TILT_IF_OPEN, DEFAULT_BLOCK_TILT_IF_OPEN),
            tilt_only_when_closed=c.get(CONF_TILT_ONLY_WHEN_CLOSED, DEFAULT_TILT_ONLY_WHEN_CLOSED),
            availability_template=c.get(CONF_AVAILABILITY_TEMPLATE),
        )
        scripts = ScriptsConfig(
            open_script=c.get(CONF_OPEN_SCRIPT_ENTITY_ID),
            close_script=c.get(CONF_CLOSE_SCRIPT_ENTITY_ID),
            stop_script=c.get(CONF_STOP_SCRIPT_ENTITY_ID),
            tilt_open_script=c.get(CONF_TILT_OPEN_SCRIPT_ENTITY_ID),
            tilt_close_script=c.get(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID),
            tilt_stop_script=c.get(CONF_TILT_STOP_SCRIPT_ENTITY_ID),
        )
        wrapper = WrapperConfig(cover_entity_id=c.get(CONF_COVER_ENTITY_ID))
        has_scripts = all([scripts.open_script, scripts.close_script, scripts.stop_script])
        if wrapper.cover_entity_id and has_scripts:
            _LOGGER.warning("Device '%s' defines both cover_entity_id and scripts; scripts take precedence.", dev_id)
        if not wrapper.cover_entity_id and not has_scripts:
            _LOGGER.error("Device '%s' missing cover_entity_id or script trio; skipping", dev_id)
            continue
        devices.append(CoverTimeBased(dev_id, base, scripts, wrapper))
        _REGISTERED_DEVICE_IDS.add(dev_id)
    return devices

