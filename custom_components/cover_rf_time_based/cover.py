import logging

import voluptuous as vol

from datetime import timedelta

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

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

# Assuming TravelCalculator and TravelStatus are available in the integration
from .travelcalculator import TravelCalculator
from .travelcalculator import TravelStatus

_LOGGER = logging.getLogger(__name__)

# No need for manual SUPPORT constants - using CoverEntityFeature enum from HA 2025.x

CONF_DEVICES = 'devices'
CONF_ALIASES = 'aliases'
CONF_TRAVELLING_TIME_DOWN = 'travelling_time_down'
CONF_TRAVELLING_TIME_UP = 'travelling_time_up'
CONF_TILTING_TIME_DOWN = 'tilting_time_down'
CONF_TILTING_TIME_UP = 'tilting_time_up'
CONF_SEND_STOP_AT_ENDS = 'send_stop_at_ends'
CONF_ALWAYS_CONFIDENT = 'always_confident'
CONF_BLOCK_TILT_IF_OPEN = 'block_tilt_if_open'
# NEW: flag to allow tilt while open
CONF_TILT_ONLY_WHEN_CLOSED = 'tilt_only_when_closed'
DEFAULT_TRAVEL_TIME = 25
DEFAULT_TILT_TIME = 1
DEFAULT_SEND_STOP_AT_ENDS = False
DEFAULT_ALWAYS_CONFIDENT = False
DEFAULT_BLOCK_TILT_IF_OPEN = False
# Default False allows independent tilt control regardless of cover position
DEFAULT_TILT_ONLY_WHEN_CLOSED = False
DEFAULT_DEVICE_CLASS = 'shutter'
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
ATTR_DEVICE_ID = 'device_id'
SERVICE_SET_KNOWN_ACTION = 'set_known_action'
SERVICE_SEND_COMMAND = 'send_command'


TRAVEL_TIME_INTERVAL = timedelta(milliseconds=100)

# --- Configuration Schemas (omitted for brevity, assume they are correct) ---

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
        # NEW optional config
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

COVER_DEVICE_SCHEMA = vol.Any(
    vol.Schema(SCRIPT_DEVICE_SCHEMA),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICES): vol.Schema({cv.slug: COVER_DEVICE_SCHEMA}),
        vol.Optional(CONF_ALIASES): vol.Schema({cv.slug: COVER_DEVICE_SCHEMA}),
    }
)
# --- End of Configuration Schemas ---

def devices_from_config(domain_config):
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        name = config.pop(CONF_NAME)
        device_class = config.pop(CONF_DEVICE_CLASS)
        travel_time_down = config.pop(CONF_TRAVELLING_TIME_DOWN)
        travel_time_up = config.pop(CONF_TRAVELLING_TIME_UP)
        
        tilting_time_down = config.pop(CONF_TILTING_TIME_DOWN)
        tilting_time_up = config.pop(CONF_TILTING_TIME_UP)
        
        send_stop_at_ends = config.pop(CONF_SEND_STOP_AT_ENDS)
        always_confident = config.pop(CONF_ALWAYS_CONFIDENT)
        block_tilt_if_open = config.pop(CONF_BLOCK_TILT_IF_OPEN)
        tilt_only_when_closed = config.pop(CONF_TILT_ONLY_WHEN_CLOSED)
        availability_template = config.pop(CONF_AVAILABILITY_TEMPLATE, None)
        
        open_script_entity_id = config.pop(CONF_OPEN_SCRIPT_ENTITY_ID, None)
        close_script_entity_id = config.pop(CONF_CLOSE_SCRIPT_ENTITY_ID, None)
        stop_script_entity_id = config.pop(CONF_STOP_SCRIPT_ENTITY_ID, None)
        
        tilt_open_script_entity_id = config.pop(CONF_TILT_OPEN_SCRIPT_ENTITY_ID, None)
        tilt_close_script_entity_id = config.pop(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID, None)
        tilt_stop_script_entity_id = config.pop(CONF_TILT_STOP_SCRIPT_ENTITY_ID, None)

        cover_entity_id = config.pop(CONF_COVER_ENTITY_ID, None)
        
        device = CoverTimeBased(device_id,
                                name,
                                travel_time_down,
                                travel_time_up,
                                tilting_time_down,
                                tilting_time_up,
                                open_script_entity_id,
                                close_script_entity_id,
                                stop_script_entity_id,
                                tilt_open_script_entity_id,
                                tilt_close_script_entity_id,
                                tilt_stop_script_entity_id,
                                cover_entity_id,
                                send_stop_at_ends,
                                always_confident,
                                block_tilt_if_open,
                                tilt_only_when_closed,
                                device_class,
                                availability_template)
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities(devices_from_config(config))

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
        {
            vol.Required(ATTR_ACTION): cv.string,
        },
        "async_set_known_action",
    )

    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): cv.string,
        },
        "async_send_command",
    )


class CoverTimeBased(CoverEntity, RestoreEntity):
    def __init__(self,
                 device_id,
                 name,
                 travel_time_down,
                 travel_time_up,
                 tilting_time_down,
                 tilting_time_up,
                 open_script_entity_id,
                 close_script_entity_id,
                 stop_script_entity_id,
                 tilt_open_script_entity_id,
                 tilt_close_script_entity_id,
                 tilt_stop_script_entity_id,
                 cover_entity_id,
                 send_stop_at_ends,
                 always_confident,
                 block_tilt_if_open,
                 tilt_only_when_closed,
                 device_class,
                 availability_template):
        self.hass = None
        self._device_id = device_id
        self._name = name
        self._device_class = device_class
        self._is_available = True
        self._send_stop_at_ends = send_stop_at_ends
        self._always_confident = always_confident
        self._block_tilt_if_open = block_tilt_if_open  # kept for backward compatibility (currently unused logic)
        self._tilt_only_when_closed = tilt_only_when_closed  # NEW behavior control flag
        self._assume_uncertain_position = not self._always_confident
        self._state = False
        self._unsubscribe_auto_update = None
        self._unsub_availability_tracker = None
        self._processing_known_position = False
        self._target_position = 0
        self._target_tilt_position = 0

        self._travel_time_down = travel_time_down
        self._travel_time_up = travel_time_up
        self._tilting_time_down = tilting_time_down
        self._tilting_time_up = tilting_time_up
        self._open_script_entity_id = open_script_entity_id
        self._close_script_entity_id = close_script_entity_id
        self._stop_script_entity_id = stop_script_entity_id
        self._tilt_open_script_entity_id = tilt_open_script_entity_id
        self._tilt_close_script_entity_id = tilt_close_script_entity_id
        self._tilt_stop_script_entity_id = tilt_stop_script_entity_id
        self._cover_entity_id = cover_entity_id
        self._availability_template = availability_template
        self._unique_id = device_id

        # Flexible mapping: if a TILT script is missing, use the main script
        self._effective_tilt_open_script = self._tilt_open_script_entity_id if self._tilt_open_script_entity_id else self._open_script_entity_id
        self._effective_tilt_close_script = self._tilt_close_script_entity_id if self._tilt_close_script_entity_id else self._close_script_entity_id
        self._effective_tilt_stop_script = self._tilt_stop_script_entity_id if self._tilt_stop_script_entity_id else self._stop_script_entity_id

        # TILT is active if at least one TILT script is defined
        self._has_tilt = (
            self._tilt_open_script_entity_id is not None or 
            self._tilt_close_script_entity_id is not None
        )

        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)
        self.tilt_tc = TravelCalculator(self._tilting_time_down, self._tilting_time_up)


    async def async_added_to_hass(self):
        self.hass = self.platform.hass
        await super().async_added_to_hass()
        if self._availability_template is not None:
            self._availability_template.hass = self.hass

        old_state = await self.async_get_last_state()
        
        # --- MAIN POSITION RESTORE ---
        main_position_restored = None
        if (old_state is not None and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None):
            main_position_restored = int(old_state.attributes.get(ATTR_CURRENT_POSITION))
            self.tc.set_position(main_position_restored)
            self._target_position = main_position_restored
        
        # --- TILT POSITION RESTORE LOGIC ---
        if self._has_tilt:
            tilt_position_restored = None
            if (old_state is not None and old_state.attributes.get(ATTR_CURRENT_TILT_POSITION) is not None):
                # Restore value as integer
                try:
                    # Handle both old `int` and new `float` states
                    tilt_position_restored = int(float(old_state.attributes.get(ATTR_CURRENT_TILT_POSITION)))
                except (ValueError, TypeError):
                    tilt_position_restored = 0
            
            restored_tilt = 0 # Default TILT position if no better state is found

            # Only enforce tilt=0 when cover is open if tilt_only_when_closed is True
            if self._tilt_only_when_closed and main_position_restored is not None and main_position_restored > 0:
                restored_tilt = 0
                _LOGGER.debug(f"Cover {self.name}: Main position > 0 ({main_position_restored}%), TILT set to 0% due to tilt_only_when_closed.")
            elif tilt_position_restored is not None:
                # Restore saved tilt state regardless of main position
                restored_tilt = tilt_position_restored
                _LOGGER.debug(f"Cover {self.name}: TILT restored to {tilt_position_restored}%.")

            self.tilt_tc.set_position(restored_tilt)
            self._target_tilt_position = restored_tilt
        
        # --- Remainder (Original logic for assumed_state) ---
        if (old_state is not None and old_state.attributes.get(ATTR_UNCONFIRMED_STATE) is not None and not self._always_confident):
           if type(old_state.attributes.get(ATTR_UNCONFIRMED_STATE)) == bool:
             self._assume_uncertain_position = old_state.attributes.get(ATTR_UNCONFIRMED_STATE)
           else:
             self._assume_uncertain_position = str(old_state.attributes.get(ATTR_UNCONFIRMED_STATE)) == str(True)

    @property
    def name(self):
        return self._name

    @property
    def device_class(self):
        return self._device_class

    @property
    def should_poll(self):
        return False

    @property
    def unique_id(self):
        return "cover_rf_timebased_uuid_" + self._unique_id

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

        # Return actual tilt position regardless of main cover position (independent control)
        return float(self.tilt_tc.current_position())

    @property
    def supported_features(self):
        """Flag supported features."""
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )

        if self._has_tilt:
            features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )

        return features

    @property
    def assumed_state(self):
        return self._assume_uncertain_position

    @property
    def is_opening(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_UP

    @property
    def is_closing(self):
        return self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN

    @property
    def is_tilting(self):
        return self._has_tilt and self.tilt_tc.is_traveling()

    @property
    def available(self):
        if self._availability_template is None:
            return True
        else:
            self._availability_template.hass = self.hass
            return self._availability_template.async_render()

    @property
    def extra_state_attributes(self):
        attr = {}
        attr[ATTR_UNCONFIRMED_STATE] = str(self._assume_uncertain_position)
        
        # Tilt is allowed if tilt_only_when_closed is False, or if cover is fully closed
        attr['tilt_is_allowed'] = (not self._tilt_only_when_closed) or self.tc.current_position() == 0

        if self._has_tilt:
            attr[ATTR_CURRENT_TILT_POSITION] = self.current_cover_tilt_position
            attr[CONF_TILTING_TIME_DOWN] = self._tilting_time_down
            attr[CONF_TILTING_TIME_UP] = self._tilting_time_up
            attr[CONF_TILT_STOP_SCRIPT_ENTITY_ID] = self._tilt_stop_script_entity_id
            attr[CONF_TILT_ONLY_WHEN_CLOSED] = self._tilt_only_when_closed

        attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up 
        attr[CONF_BLOCK_TILT_IF_OPEN] = self._block_tilt_if_open # Keeping the legacy config entry

        return attr

    def start_auto_updater(self):
        if self._unsubscribe_auto_update is None:
            self._unsubscribe_auto_update = async_track_time_interval(
                self.hass, self._update_cover_position, TRAVEL_TIME_INTERVAL
            )

    def stop_auto_updater(self):
        if self._unsubscribe_auto_update is not None:
            self._unsubscribe_auto_update()
            self._unsubscribe_auto_update = None

    @callback
    def _update_cover_position(self, now):
        is_moving_position = self.tc.is_traveling()
        if is_moving_position:
            # FIX: Use update_position() which we added to travelcalculator.py
            self.tc.update_position()

        is_moving_tilt = self._has_tilt and self.tilt_tc.is_traveling()
        if is_moving_tilt:
            # FIX: Use update_position() which we added to travelcalculator.py
            self.tilt_tc.update_position()

        if is_moving_position or is_moving_tilt:
            self.async_write_ha_state()

        if not is_moving_position and not is_moving_tilt:
            self.stop_auto_updater()
        
        self.hass.async_create_task(self.auto_stop_if_necessary())

    async def async_set_cover_position(self, position, **kwargs):
        current_position = self.tc.current_position()
        self._target_position = position
        
        if position < current_position:
            new_command = SERVICE_CLOSE_COVER
            new_direction = TravelStatus.DIRECTION_DOWN
        elif position > current_position:
            new_command = SERVICE_OPEN_COVER
            new_direction = TravelStatus.DIRECTION_UP
        else:
            if self.tc.is_traveling():
                # FIX: Use _handle_command 
                await self._handle_command(SERVICE_STOP_COVER)
            self.async_write_ha_state() 
            return
            
        is_traveling = self.tc.is_traveling()
        current_direction = self.tc.travel_direction
        
        # Send command only if movement is not already in the target direction
        send_command = not is_traveling or (new_direction != current_direction)

        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel(position)
        self.start_auto_updater()

        if send_command:
            # FIX: Use _handle_command 
            await self._handle_command(new_command)
        
        # Update internal position based on current time (not used for calculation here, just for consistency)
        self.tc.update_position()
        self.async_write_ha_state()
            
    async def async_set_cover_tilt_position(self, tilt_position, **kwargs):
        if not self._has_tilt:
            _LOGGER.warning("Attempted to set tilt position on cover '%s', but tilt is not configured.", self.name)
            return

        # Only block if explicitly configured to do so
        if self._tilt_only_when_closed and self.tc.current_position() != 0:
            _LOGGER.warning("Tilt command ignored for '%s'. Main cover is not fully closed (position: %d) and tilt_only_when_closed is True.", self.name, self.tc.current_position())
            return
        
        current_tilt_position = self.tilt_tc.current_position()
        self._target_tilt_position = tilt_position
        
        # If using cover_entity_id, try to use set_cover_tilt_position service directly
        if self._cover_entity_id is not None:
            self._assume_uncertain_position = not self._always_confident
            self.tilt_tc.start_travel(tilt_position)
            self.start_auto_updater()
            # Call set_cover_tilt_position on the underlying cover entity
            await self._handle_command(SERVICE_SET_COVER_TILT_POSITION, tilt_position=tilt_position)
            self.tilt_tc.update_position()
            self.async_write_ha_state()
            return

        # For script-based covers, use directional commands
        if tilt_position < current_tilt_position:
            new_command = SERVICE_CLOSE_COVER_TILT
            new_direction = TravelStatus.DIRECTION_DOWN
        elif tilt_position > current_tilt_position:
            new_command = SERVICE_OPEN_COVER_TILT
            new_direction = TravelStatus.DIRECTION_UP
        else:
            if self.tilt_tc.is_traveling():
                await self._handle_command(SERVICE_STOP_COVER_TILT)
            self.async_write_ha_state()
            return

        is_traveling = self.tilt_tc.is_traveling()
        current_direction = self.tilt_tc.travel_direction
        
        send_command = not is_traveling or (new_direction != current_direction)

        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel(tilt_position)
        self.start_auto_updater()

        if send_command:
            await self._handle_command(new_command)

        # Update internal position based on current time
        self.tilt_tc.update_position()
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        # Check if already moving in the DOWN direction
        is_already_closing = self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN
        
        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel_down()
        self._target_position = 0
        self.start_auto_updater()
        # Update internal position based on current time
        self.tc.update_position()
        self.async_write_ha_state()
        
        # Only send command if it wasn't already closing
        if not is_already_closing:
            # FIX: Use _handle_command 
            await self._handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs):
        # Check if already moving in the UP direction
        is_already_opening = self.tc.is_traveling() and self.tc.travel_direction == TravelStatus.DIRECTION_UP
        
        self._assume_uncertain_position = not self._always_confident
        self.tc.start_travel_up()
        self._target_position = 100
        self.start_auto_updater()

        # Update internal position based on current time
        self.tc.update_position()
        self.async_write_ha_state()
        
        # Only send command if it wasn't already opening
        if not is_already_opening:
            # FIX: Use _handle_command 
            await self._handle_command(SERVICE_OPEN_COVER)

    async def async_close_cover_tilt(self, **kwargs):
        if not self._has_tilt:
            _LOGGER.warning("Attempted to close cover tilt on cover '%s', but tilt is not configured.", self.name)
            return

        if self._tilt_only_when_closed and self.tc.current_position() != 0:
            _LOGGER.warning("Tilt command ignored for '%s'. Main cover is not fully closed (position: %d) and tilt_only_when_closed is True.", self.name, self.tc.current_position())
            return

        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel_down()
        self._target_tilt_position = 0
        self.start_auto_updater()
        # Update internal position based on current time
        self.tilt_tc.update_position()
        self.async_write_ha_state()
        # FIX: Use _handle_command 
        await self._handle_command(SERVICE_CLOSE_COVER_TILT)

    async def async_open_cover_tilt(self, **kwargs):
        if not self._has_tilt:
            _LOGGER.warning("Attempted to open cover tilt on cover '%s', but tilt is not configured.", self.name)
            return

        if self._tilt_only_when_closed and self.tc.current_position() != 0:
            _LOGGER.warning("Tilt command ignored for '%s'. Main cover is not fully closed (position: %d) and tilt_only_when_closed is True.", self.name, self.tc.current_position())
            return

        self._assume_uncertain_position = not self._always_confident
        self.tilt_tc.start_travel_up()
        self._target_tilt_position = 100
        self.start_auto_updater()
        # Update internal position based on current time
        self.tilt_tc.update_position()
        self.async_write_ha_state()
        # FIX: Use _handle_command 
        await self._handle_command(SERVICE_OPEN_COVER_TILT)

    async def async_stop_cover(self, **kwargs):
        self.tc.stop()
        # FIX: Use _handle_command 
        await self._handle_command(SERVICE_STOP_COVER)
        self.async_write_ha_state()

    async def async_stop_cover_tilt(self, **kwargs):
        if not self._has_tilt:
            return
            
        self.tilt_tc.stop()
        # FIX: Use _handle_command 
        await self._handle_command(SERVICE_STOP_COVER_TILT)
        self.async_write_ha_state()

    async def async_set_known_position(self, **kwargs):
        position = kwargs.get(ATTR_POSITION)
        tilt_position = kwargs.get(ATTR_TILT_POSITION)
        confident = kwargs.get(ATTR_CONFIDENT, False)
        position_type = kwargs.get(ATTR_POSITION_TYPE, ATTR_POSITION_TYPE_TARGET)

        if position_type not in [ATTR_POSITION_TYPE_TARGET, ATTR_POSITION_TYPE_CURRENT]:
            raise ValueError(f"{ATTR_POSITION_TYPE} must be one of {ATTR_POSITION_TYPE_TARGET}, {ATTR_POSITION_TYPE_CURRENT}")

        _LOGGER.debug('%s: set_known_position :: position %s, tilt_position %s, confident %s, position_type %s, is_traveling %s',
                      self._name, position, tilt_position, confident, position_type, self.tc.is_traveling())

        self._assume_uncertain_position = not confident if not self._always_confident else False
        self._processing_known_position = True

        if position is not None:
            if position_type == ATTR_POSITION_TYPE_TARGET:
                self._target_position = position
                if self.tc.is_traveling():
                    self.tc.start_travel(self._target_position)
                    self.start_auto_updater()
                else:
                    self.tc.start_travel(self._target_position)
                    self.start_auto_updater()
            else:  # ATTR_POSITION_TYPE_CURRENT
                self.tc.set_position(position)
                self._target_position = position

        if self._has_tilt and tilt_position is not None:
            # If tilt restricted and cover is open, force 0 else accept provided
            if self._tilt_only_when_closed and self.tc.current_position() > 0:
                self.tilt_tc.set_position(0)
                self._target_tilt_position = 0
            else:
                if position_type == ATTR_POSITION_TYPE_TARGET:
                    self._target_tilt_position = tilt_position
                    if self.tilt_tc.is_traveling():
                        self.tilt_tc.start_travel(self._target_tilt_position)
                        self.start_auto_updater()
                    else:
                        self.tilt_tc.start_travel(self._target_tilt_position)
                        self.start_auto_updater()
                else:  # ATTR_POSITION_TYPE_CURRENT
                    self.tilt_tc.set_position(tilt_position)
                    self._target_tilt_position = tilt_position

        self.async_write_ha_state()

    async def async_set_known_action(self, **kwargs):
        """Handle action captured outside of HA (open, close, stop)."""
        action = kwargs.get(ATTR_ACTION)

        if action not in ["open", "close", "stop"]:
            raise ValueError("action must be one of open, close or stop.")

        _LOGGER.debug('%s: set_known_action :: action %s', self._name, action)

        if action == "stop":
            self.tc.stop()
            if self._has_tilt:
                self.tilt_tc.stop()
            self.async_write_ha_state()
            return

        if action == "open":
            self.tc.start_travel_up()
            self._target_position = 100
        elif action == "close":
            self.tc.start_travel_down()
            self._target_position = 0

        self.start_auto_updater()
        self.async_write_ha_state()

    async def async_send_command(self, **kwargs):
        """Send device command through Cover."""
        command = kwargs.get(ATTR_COMMAND)

        _LOGGER.debug('%s: send_command :: command %s', self._name, command)

        # Map command strings to actual methods
        command_map = {
            'open_cover': self.async_open_cover,
            'close_cover': self.async_close_cover,
            'stop_cover': self.async_stop_cover,
            'open_cover_tilt': self.async_open_cover_tilt if self._has_tilt else None,
            'close_cover_tilt': self.async_close_cover_tilt if self._has_tilt else None,
            'stop_cover_tilt': self.async_stop_cover_tilt if self._has_tilt else None,
        }

        if command in command_map and command_map[command] is not None:
            await command_map[command]()
        else:
            _LOGGER.warning('%s: Unknown or unsupported command: %s', self._name, command)

    async def auto_stop_if_necessary(self):
        self._processing_known_position = False
        
        position_reached = self.tc.position_reached()
        tilt_reached = self._has_tilt and self.tilt_tc.position_reached()
        
        stop_called = False
        state_needs_update = position_reached or tilt_reached

        if position_reached:
            target_position = self.tc.travel_to_position
            self.tc.stop() 
            is_intermediate_stop = target_position > 0 and target_position < 100

            if is_intermediate_stop or self._send_stop_at_ends:
                # FIX: Use _handle_command 
                await self._handle_command(SERVICE_STOP_COVER)
                stop_called = True
            
        if tilt_reached:
            self.tilt_tc.stop()
            is_separate_tilt_stop = self._tilt_stop_script_entity_id is not None
            
            if is_separate_tilt_stop or not stop_called:
                # FIX: Use _handle_command 
                await self._handle_command(SERVICE_STOP_COVER_TILT)
                stop_called = True

        # Update state immediately if movement stopped
        if state_needs_update:
            self.async_write_ha_state()

        if not self.tc.is_traveling() and not self.is_tilting:
            self.stop_auto_updater()


    # FIX: Renamed method from _async_handle_command to _handle_command
    async def _handle_command(self, command, *args, **kwargs):
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False

        entity_id = None
        service_data = {"entity_id": self._cover_entity_id} if self._cover_entity_id else {}

        if command == SERVICE_CLOSE_COVER:
            entity_id = self._close_script_entity_id
        elif command == SERVICE_OPEN_COVER:
            entity_id = self._open_script_entity_id
        elif command == SERVICE_STOP_COVER:
            entity_id = self._stop_script_entity_id
        
        # TILT Commands use effective scripts (fall back to main if specific TILT script is missing)
        elif command == SERVICE_CLOSE_COVER_TILT and self._has_tilt:
            entity_id = self._effective_tilt_close_script
        elif command == SERVICE_OPEN_COVER_TILT and self._has_tilt:
            entity_id = self._effective_tilt_open_script
        elif command == SERVICE_STOP_COVER_TILT:
            entity_id = self._effective_tilt_stop_script

        # Position commands - pass position data if provided (only used with cover_entity_id)
        elif command == SERVICE_SET_COVER_TILT_POSITION and self._has_tilt:
            if self._cover_entity_id and "tilt_position" in kwargs:
                service_data[ATTR_TILT_POSITION] = kwargs["tilt_position"]
        else:
            return

        if entity_id is None and not self._cover_entity_id:
            entity_id = self._stop_script_entity_id # Fallback to main STOP
            
        if self._cover_entity_id is not None:
            await self.hass.services.async_call("cover", command, service_data, False)
        else:
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": entity_id}, False)

