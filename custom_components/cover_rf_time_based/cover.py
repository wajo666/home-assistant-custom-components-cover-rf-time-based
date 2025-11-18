"""Refactored version of cover.py implementing:
- Dataclasses for configuration (DeviceConfig, ScriptsConfig, WrapperConfig)
- Reduced cognitive complexity of async_set_known_position, auto_stop_if_necessary, _handle_command
- Centralized tilt blocked warning constant

This file is a staging refactor; once validated it can replace cover.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_TILT_POSITION,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER_TILT,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

# Warning constant
TILT_BLOCKED_LOG = "Tilt command ignored for '%s'. Main cover is not fully closed (position: %d) and tilt_only_when_closed is True."

# Configuration constants (reused from original)
CONF_DEVICES = 'devices'
CONF_ALIASES = 'aliases'
CONF_TRAVELLING_TIME_DOWN = 'travelling_time_down'
CONF_TRAVELLING_TIME_UP = 'travelling_time_up'
CONF_TILTING_TIME_DOWN = 'tilting_time_down'
CONF_TILTING_TIME_UP = 'tilting_time_up'
CONF_SEND_STOP_AT_ENDS = 'send_stop_at_ends'
CONF_ALWAYS_CONFIDENT = 'always_confident'
CONF_BLOCK_TILT_IF_OPEN = 'block_tilt_if_open'
CONF_TILT_ONLY_WHEN_CLOSED = 'tilt_only_when_closed'
CONF_OPEN_SCRIPT_ENTITY_ID = 'open_script_entity_id'
CONF_CLOSE_SCRIPT_ENTITY_ID = 'close_script_entity_id'
CONF_STOP_SCRIPT_ENTITY_ID = 'stop_script_entity_id'
CONF_TILT_OPEN_SCRIPT_ENTITY_ID = 'tilt_open_script_entity_id'
CONF_TILT_CLOSE_SCRIPT_ENTITY_ID = 'tilt_close_script_entity_id'
CONF_TILT_STOP_SCRIPT_ENTITY_ID = 'tilt_stop_script_entity_id'
CONF_COVER_ENTITY_ID = 'cover_entity_id'
CONF_AVAILABILITY_TEMPLATE = 'availability_template'
ATTR_UNCONFIRMED_STATE = 'unconfirmed_state'
ATTR_CONFIDENT = 'confident'
ATTR_ACTION = 'action'
ATTR_POSITION_TYPE = 'position_type'
ATTR_POSITION_TYPE_CURRENT = 'current'
ATTR_POSITION_TYPE_TARGET = 'target'
ATTR_COMMAND = 'command'
ATTR_TILT_POSITION = ATTR_TILT_POSITION

DEFAULT_TRAVEL_TIME = 25
DEFAULT_TILT_TIME = 1
DEFAULT_SEND_STOP_AT_ENDS = False
DEFAULT_ALWAYS_CONFIDENT = False
DEFAULT_BLOCK_TILT_IF_OPEN = False
DEFAULT_TILT_ONLY_WHEN_CLOSED = False
DEFAULT_DEVICE_CLASS = 'shutter'

SERVICE_SET_KNOWN_ACTION = 'set_known_action'
SERVICE_SEND_COMMAND = 'send_command'

TRAVEL_TIME_INTERVAL = timedelta(milliseconds=100)

# Dataclasses
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
    availability_template: any | None

@dataclass(slots=True)
class ScriptsConfig:
    open_script: str | None
    close_script: str | None
    stop_script: str | None
    tilt_open_script: str | None
    tilt_close_script: str | None
    tilt_stop_script: str | None

@dataclass(slots=True)
class WrapperConfig:
    cover_entity_id: str | None

# Schemas (minimal reuse for YAML fallback)
BASE_DEVICE_SCHEMA = vol.Schema(
    {
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
    }
)
SCRIPT_DEVICE_SCHEMA = BASE_DEVICE_SCHEMA.extend(
    {
        vol.Required(CONF_OPEN_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_CLOSE_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_STOP_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_TILT_OPEN_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_TILT_STOP_SCRIPT_ENTITY_ID): cv.entity_id,
    }
)
COVER_DEVICE_SCHEMA = vol.Any(vol.Schema(SCRIPT_DEVICE_SCHEMA))
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICES): vol.Schema({cv.slug: COVER_DEVICE_SCHEMA}),
    }
)

# YAML fallback builder

def devices_from_config(domain_config):
    devices = []
    raw_devices = domain_config.get(CONF_DEVICES, {})
    for dev_id, raw in raw_devices.items():
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
    return devices

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    ents = devices_from_config(config)
    async_add_entities(ents)
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        "set_known_position",
        {
            vol.Optional(ATTR_POSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(ATTR_TILT_POSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(ATTR_CONFIDENT, default=False): cv.boolean,
            vol.Optional(ATTR_POSITION_TYPE, default=ATTR_POSITION_TYPE_TARGET): cv.string,
        },
        "async_set_known_position",
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_ACTION,
        {vol.Required(ATTR_ACTION): cv.string},
        "async_set_known_action",
    )
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {vol.Required(ATTR_COMMAND): cv.string},
        "async_send_command",
    )

class CoverTimeBased(CoverEntity, RestoreEntity):
    def __init__(self, device_id: str, config: DeviceConfig, scripts: ScriptsConfig, wrapper: WrapperConfig):
        self._device_id = device_id
        self._unique_id = device_id
        self._config = config
        self._scripts = scripts
        self._wrapper = wrapper
        self._name = config.name
        self._device_class = config.device_class
        self._send_stop_at_ends = config.send_stop_at_ends
        self._always_confident = config.always_confident
        self._tilt_only_when_closed = config.tilt_only_when_closed
        self._assume_uncertain_position = not self._always_confident
        self._target_position = 0
        self._target_tilt_position = 0
        self._stopping = False
        self._processing_known_position = False
        self._cover_entity_id = wrapper.cover_entity_id
        self._availability_template = config.availability_template
        # Scripts
        self._open_script_entity_id = scripts.open_script
        self._close_script_entity_id = scripts.close_script
        self._stop_script_entity_id = scripts.stop_script
        self._tilt_open_script_entity_id = scripts.tilt_open_script
        self._tilt_close_script_entity_id = scripts.tilt_close_script
        self._tilt_stop_script_entity_id = scripts.tilt_stop_script
        self._effective_tilt_open_script = self._tilt_open_script_entity_id or self._open_script_entity_id
        self._effective_tilt_close_script = self._tilt_close_script_entity_id or self._close_script_entity_id
        self._effective_tilt_stop_script = self._tilt_stop_script_entity_id or self._stop_script_entity_id
        self._has_tilt = any([
            self._tilt_open_script_entity_id,
            self._tilt_close_script_entity_id,
            self._tilt_stop_script_entity_id,
        ])
        # Travel calculators
        self.tc = TravelCalculator(config.travel_time_down, config.travel_time_up)
        self.tilt_tc = TravelCalculator(config.tilting_time_down, config.tilting_time_up)
        self._unsubscribe_auto_update = None
        self._unsub_availability_tracker = None
        self.hass = None

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"cover_rf_timebased_uuid_{self._unique_id}"

    @property
    def supported_features(self):
        feats = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )
        if self._has_tilt:
            feats |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )
        return feats

    async def async_added_to_hass(self):
        self.hass = self.platform.hass
        await super().async_added_to_hass()
        await self._restore_state()
        self._setup_availability()

    async def _restore_state(self):
        old = await self.async_get_last_state()
        if not old:
            return
        pos = old.attributes.get(ATTR_CURRENT_POSITION)
        if pos is not None:
            try:
                self.tc.set_position(int(pos))
            except Exception:
                _LOGGER.debug("%s: Invalid stored position '%s' ignored", self._name, pos)
        unconfirmed = old.attributes.get(ATTR_UNCONFIRMED_STATE)
        if unconfirmed is not None and not self._always_confident:
            self._assume_uncertain_position = bool(unconfirmed) if isinstance(unconfirmed, bool) else str(unconfirmed).lower() == 'true'

    def _setup_availability(self):
        tpl = self._availability_template
        if tpl is None:
            return
        tpl.hass = self.hass
        @callback
        def _avail(_):
            self.async_write_ha_state()
        try:
            self._unsub_availability_tracker = tpl.async_render_to_info(self.hass, _avail)
        except Exception as ex:
            _LOGGER.error("%s: availability template failed: %s", self._name, ex)

    @property
    def is_tilting(self):
        return self._has_tilt and self.tilt_tc.is_traveling()

    @callback
    def _update_cover_position(self, _now):
        moving_main = self.tc.is_traveling()
        if moving_main:
            self.tc.update_position()
        moving_tilt = self._has_tilt and self.tilt_tc.is_traveling()
        if moving_tilt:
            self.tilt_tc.update_position()
        if moving_main or moving_tilt:
            self.async_write_ha_state()
        if not moving_main and not moving_tilt:
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def start_auto_updater(self):
        if self._unsubscribe_auto_update is None:
            self._unsubscribe_auto_update = async_track_time_interval(
                self.hass, self._update_cover_position, TRAVEL_TIME_INTERVAL
            )

    def stop_auto_updater(self):
        if self._unsubscribe_auto_update is not None:
            self._unsubscribe_auto_update()
            self._unsubscribe_auto_update = None

    # Helper decisions
    def _should_block_tilt(self) -> bool:
        return self._tilt_only_when_closed and self.tc.current_position() > 0

    def _apply_main_target(self, pos: int):
        self._target_position = pos
        self.tc.start_travel(self._target_position)
        self.start_auto_updater()

    def _apply_main_current(self, pos: int):
        self.tc.set_position(pos)
        self._target_position = pos

    def _apply_tilt_target(self, tilt: int):
        self._target_tilt_position = tilt
        self.tilt_tc.start_travel(self._target_tilt_position)
        self.start_auto_updater()

    def _apply_tilt_current(self, tilt: int):
        self.tilt_tc.set_position(tilt)
        self._target_tilt_position = tilt

    async def async_set_known_position(self, **kwargs):
        pos = kwargs.get(ATTR_POSITION)
        tilt = kwargs.get(ATTR_TILT_POSITION)
        confident = kwargs.get(ATTR_CONFIDENT, False)
        ptype = kwargs.get(ATTR_POSITION_TYPE, ATTR_POSITION_TYPE_TARGET)
        if ptype not in (ATTR_POSITION_TYPE_TARGET, ATTR_POSITION_TYPE_CURRENT):
            raise ValueError("Invalid position_type")
        self._assume_uncertain_position = not confident if not self._always_confident else False
        self._processing_known_position = True
        if pos is not None:
            if ptype == ATTR_POSITION_TYPE_TARGET:
                self._apply_main_target(pos)
            else:
                self._apply_main_current(pos)
        if self._has_tilt and tilt is not None:
            if self._should_block_tilt():
                self._apply_tilt_current(0)
            else:
                if ptype == ATTR_POSITION_TYPE_TARGET:
                    self._apply_tilt_target(tilt)
                else:
                    self._apply_tilt_current(tilt)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel_up()
        self._target_position = 100
        self.start_auto_updater()
        self.tc.update_position()
        self.async_write_ha_state()
        await self._handle_command(SERVICE_OPEN_COVER)

    async def async_close_cover(self, **kwargs):
        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel_down()
        self._target_position = 0
        self.start_auto_updater()
        self.tc.update_position()
        self.async_write_ha_state()
        await self._handle_command(SERVICE_CLOSE_COVER)

    async def async_stop_cover(self, **kwargs):
        if self._stopping or not self.tc.is_traveling():
            return
        self._stopping = True
        try:
            self.tc.stop()
            await self._handle_command(SERVICE_STOP_COVER)
            self.async_write_ha_state()
        finally:
            self._stopping = False

    async def async_open_cover_tilt(self, **kwargs):
        if not self._has_tilt:
            return
        if self._should_block_tilt():
            _LOGGER.warning(TILT_BLOCKED_LOG, self.name, self.tc.current_position())
            return
        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel_up()
        self._target_tilt_position = 100
        self.start_auto_updater()
        self.tilt_tc.update_position()
        self.async_write_ha_state()
        await self._handle_command(SERVICE_OPEN_COVER_TILT)

    async def async_close_cover_tilt(self, **kwargs):
        if not self._has_tilt:
            return
        if self._should_block_tilt():
            _LOGGER.warning(TILT_BLOCKED_LOG, self.name, self.tc.current_position())
            return
        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel_down()
        self._target_tilt_position = 0
        self.start_auto_updater()
        self.tilt_tc.update_position()
        self.async_write_ha_state()
        await self._handle_command(SERVICE_CLOSE_COVER_TILT)

    async def async_stop_cover_tilt(self, **kwargs):
        if not self._has_tilt or not self.tilt_tc.is_traveling():
            return
        self.tilt_tc.stop()
        await self._handle_command(SERVICE_STOP_COVER_TILT)
        self.async_write_ha_state()

    async def async_set_cover_position(self, position, **kwargs):
        cur = self.tc.current_position()
        if position == cur:
            if self.tc.is_traveling():
                await self._handle_command(SERVICE_STOP_COVER)
            self.async_write_ha_state()
            return
        cmd = SERVICE_OPEN_COVER if position > cur else SERVICE_CLOSE_COVER
        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel(position)
        self._target_position = position
        self.start_auto_updater()
        await self._handle_command(cmd)
        self.tc.update_position()
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, tilt_position, **kwargs):
        if not self._has_tilt:
            _LOGGER.warning("Attempted to set tilt position on cover '%s', but tilt is not configured.", self.name)
            return
        if self._should_block_tilt():
            _LOGGER.warning(TILT_BLOCKED_LOG, self.name, self.tc.current_position())
            return
        cur = self.tilt_tc.current_position()
        self._target_tilt_position = tilt_position
        if self._cover_entity_id is not None:
            self._assume_uncertain_position = not self._always_confident
            self.tilt_tc.start_travel(tilt_position)
            self.start_auto_updater()
            await self._handle_command(SERVICE_SET_COVER_TILT_POSITION, tilt_position=tilt_position)
            self.tilt_tc.update_position()
            self.async_write_ha_state()
            return
        if tilt_position == cur:
            if self.tilt_tc.is_traveling():
                await self._handle_command(SERVICE_STOP_COVER_TILT)
            self.async_write_ha_state()
            return
        cmd = SERVICE_OPEN_COVER_TILT if tilt_position > cur else SERVICE_CLOSE_COVER_TILT
        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel(tilt_position)
        self.start_auto_updater()
        await self._handle_command(cmd)
        self.tilt_tc.update_position()
        self.async_write_ha_state()

    async def async_set_known_action(self, **kwargs):
        action = kwargs.get(ATTR_ACTION)
        if action not in ("open", "close", "stop"):
            raise ValueError("action must be one of open, close or stop")
        if action == "stop":
            self.tc.stop()
            if self._has_tilt:
                self.tilt_tc.stop()
            self.async_write_ha_state()
            return
        self._assume_uncertain_position = not self._always_confident
        if action == "open":
            self.tc.start_travel_up(); self._target_position = 100
        elif action == "close":
            self.tc.start_travel_down(); self._target_position = 0
        self.start_auto_updater()
        self.async_write_ha_state()

    async def async_send_command(self, **kwargs):
        cmd = kwargs.get(ATTR_COMMAND)
        mapping = {
            'open_cover': self.async_open_cover,
            'close_cover': self.async_close_cover,
            'stop_cover': self.async_stop_cover,
            'open_cover_tilt': self.async_open_cover_tilt if self._has_tilt else None,
            'close_cover_tilt': self.async_close_cover_tilt if self._has_tilt else None,
            'stop_cover_tilt': self.async_stop_cover_tilt if self._has_tilt else None,
        }
        fn = mapping.get(cmd)
        if fn is None:
            _LOGGER.warning("%s: Unknown or unsupported command: %s", self._name, cmd)
            return
        await fn()

    async def auto_stop_if_necessary(self):
        self._processing_known_position = False
        if self._stopping:
            return
        main_done = self.tc.position_reached()
        tilt_done = self._has_tilt and self.tilt_tc.position_reached()
        main_stopped = False
        if main_done:
            main_stopped = await self._auto_stop_main()
        if tilt_done:
            await self._auto_stop_tilt(main_stopped)
        if main_done or tilt_done:
            self.async_write_ha_state()
        if not self.tc.is_traveling() and not self.is_tilting:
            self.stop_auto_updater()

    async def _auto_stop_main(self):
        target = self.tc.travel_to_position
        self.tc.stop()
        intermediate = target not in (0, 100)
        if intermediate or self._send_stop_at_ends:
            await self._handle_command(SERVICE_STOP_COVER)
            return True
        return False

    async def _auto_stop_tilt(self, main_stop_done: bool):
        self.tilt_tc.stop()
        separate = self._tilt_stop_script_entity_id is not None
        if separate or not main_stop_done:
            await self._handle_command(SERVICE_STOP_COVER_TILT)

    async def _handle_command(self, command, *args, **kwargs):
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False
        entity_id = self._resolve_script_entity(command)
        service_data = {"entity_id": self._cover_entity_id} if self._cover_entity_id else {}
        if command == SERVICE_SET_COVER_TILT_POSITION and self._has_tilt and 'tilt_position' in kwargs:
            service_data[ATTR_TILT_POSITION] = kwargs['tilt_position']
        if entity_id is None and not self._cover_entity_id:
            entity_id = self._stop_script_entity_id
        if self._cover_entity_id is not None:
            await self.hass.services.async_call("cover", command, service_data, False)
        elif entity_id:
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": entity_id}, False)

    def _resolve_script_entity(self, command):
        if command == SERVICE_CLOSE_COVER:
            return self._close_script_entity_id
        if command == SERVICE_OPEN_COVER:
            return self._open_script_entity_id
        if command == SERVICE_STOP_COVER:
            return self._stop_script_entity_id
        if command == SERVICE_CLOSE_COVER_TILT and self._has_tilt:
            return self._effective_tilt_close_script
        if command == SERVICE_OPEN_COVER_TILT and self._has_tilt:
            return self._effective_tilt_open_script
        if command == SERVICE_STOP_COVER_TILT:
            return self._effective_tilt_stop_script
        return None

