"""Entity class for cover_rf_time_based split out from monolithic cover.py."""
from __future__ import annotations
import logging
from typing import Any
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_STOP_COVER_TILT,
    SERVICE_SET_COVER_TILT_POSITION,
    ATTR_TILT_POSITION,
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
)
from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    TILT_BLOCKED_LOG,
    TRAVEL_TIME_INTERVAL,
    ATTR_UNCONFIRMED_STATE,
    ATTR_CONFIDENT,
    ATTR_ACTION,
    ATTR_POSITION_TYPE_TARGET,
    ATTR_POSITION_TYPE_CURRENT,
    ATTR_COMMAND,
    ATTR_DEVICE_ID,
    CONF_TILTING_TIME_DOWN,
    CONF_TILTING_TIME_UP,
    CONF_TILT_STOP_SCRIPT_ENTITY_ID,
    CONF_TILT_ONLY_WHEN_CLOSED,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONF_BLOCK_TILT_IF_OPEN,
    CONF_COMMAND_DELAY,
)
from .models import DeviceConfig, ScriptsConfig, WrapperConfig
from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

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
        self._command_delay = config.command_delay
        self.tc = TravelCalculator(config.travel_time_down, config.travel_time_up, config.command_delay)
        self.tilt_tc = TravelCalculator(config.tilting_time_down, config.tilting_time_up, config.command_delay)
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

    @property
    def device_class(self):
        return self._device_class

    @property
    def should_poll(self):
        return False

    @property
    def is_closed(self):
        return self.tc.is_closed()

    @property
    def current_cover_position(self):
        return self.tc.current_position()

    @property
    def current_cover_tilt_position(self):
        if not self._has_tilt:
            return None
        return float(self.tilt_tc.current_position())

    @property
    def assumed_state(self):
        return self._assume_uncertain_position

    @property
    def available(self):
        if self._availability_template is None:
            return True
        try:
            return bool(self._availability_template.async_render())
        except Exception:
            return True

    @property
    def is_opening(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closing(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def extra_state_attributes(self):
        attr: dict[str, Any] = {
            ATTR_UNCONFIRMED_STATE: str(self._assume_uncertain_position),
            ATTR_CONFIDENT: not self._assume_uncertain_position,
            ATTR_DEVICE_ID: self._device_id,
            'tilt_is_allowed': (not self._tilt_only_when_closed) or self.tc.current_position() == 0,
        }
        if self._has_tilt:
            attr[ATTR_CURRENT_TILT_POSITION] = self.current_cover_tilt_position
            attr[CONF_TILTING_TIME_DOWN] = self._config.tilting_time_down
            attr[CONF_TILTING_TIME_UP] = self._config.tilting_time_up
            attr[CONF_TILT_STOP_SCRIPT_ENTITY_ID] = self._tilt_stop_script_entity_id
            attr[CONF_TILT_ONLY_WHEN_CLOSED] = self._tilt_only_when_closed
        attr[CONF_TRAVELLING_TIME_DOWN] = self._config.travel_time_down
        attr[CONF_TRAVELLING_TIME_UP] = self._config.travel_time_up
        attr[CONF_BLOCK_TILT_IF_OPEN] = self._config.block_tilt_if_open
        attr[CONF_COMMAND_DELAY] = self._config.command_delay
        return attr

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
        def _template_updated(event, updates):
            self.async_write_ha_state()
        try:
            from homeassistant.helpers.event import async_track_template_result, TrackTemplate
            track_tpl = TrackTemplate(tpl, None)
            self._unsub_availability_tracker = async_track_template_result(
                self.hass, [track_tpl], _template_updated
            ).async_remove
        except Exception as ex:
            _LOGGER.error("%s: availability template setup failed: %s", self._name, ex, exc_info=True)

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
        pos = kwargs.get('position')
        tilt = kwargs.get('tilt_position')
        confident = kwargs.get('confident', False)
        ptype = kwargs.get('position_type', ATTR_POSITION_TYPE_TARGET)
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
        target = self.tilt_tc.travel_to_position
        self.tilt_tc.stop()
        intermediate = target not in (0, 100)
        separate = self._tilt_stop_script_entity_id is not None
        # Send stop command if:
        # 1. It's an intermediate position, OR
        # 2. send_stop_at_ends is True, OR
        # 3. Tilt has separate stop script and main stop wasn't sent
        should_send_stop = intermediate or self._send_stop_at_ends or (separate and not main_stop_done)
        if should_send_stop:
            await self._handle_command(SERVICE_STOP_COVER_TILT)

    async def _handle_command(self, command, *args, **kwargs):
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False
        entity_id = self._resolve_script_entity(command)

        # Determine if this is a tilt command
        is_tilt_command = command in [
            SERVICE_OPEN_COVER_TILT,
            SERVICE_CLOSE_COVER_TILT,
            SERVICE_STOP_COVER_TILT,
            SERVICE_SET_COVER_TILT_POSITION
        ]

        # Hybrid mode: use wrapper for main commands, scripts for tilt commands
        use_wrapper = self._cover_entity_id is not None and (not is_tilt_command or entity_id is None)
        use_script = entity_id is not None and (not use_wrapper or is_tilt_command)

        if use_wrapper:
            service_data = {"entity_id": self._cover_entity_id}
            if command == SERVICE_SET_COVER_TILT_POSITION and 'tilt_position' in kwargs:
                service_data[ATTR_TILT_POSITION] = kwargs['tilt_position']
            await self.hass.services.async_call("cover", command, service_data, False)
        elif use_script:
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": entity_id}, False)
        elif not self._cover_entity_id and entity_id is None:
            # Fallback to stop script if nothing else is configured
            if self._stop_script_entity_id:
                await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._stop_script_entity_id}, False)

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
