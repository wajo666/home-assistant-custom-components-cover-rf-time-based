"""Constants for cover_rf_time_based integration."""
from datetime import timedelta

# Warning / log messages
TILT_BLOCKED_LOG = "Tilt command ignored for '%s'. Main cover is not fully closed (position: %d) and tilt_only_when_closed is True."

# Configuration keys
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

# Attributes
ATTR_UNCONFIRMED_STATE = 'unconfirmed_state'
ATTR_CONFIDENT = 'confident'
ATTR_ACTION = 'action'
ATTR_POSITION_TYPE = 'position_type'
ATTR_POSITION_TYPE_CURRENT = 'current'
ATTR_POSITION_TYPE_TARGET = 'target'
ATTR_COMMAND = 'command'
ATTR_DEVICE_ID = 'device_id'
ATTR_TILT_POSITION = 'tilt_position'

# Defaults
DEFAULT_TRAVEL_TIME = 25
DEFAULT_TILT_TIME = 1
DEFAULT_SEND_STOP_AT_ENDS = False
DEFAULT_ALWAYS_CONFIDENT = False
DEFAULT_BLOCK_TILT_IF_OPEN = False
DEFAULT_TILT_ONLY_WHEN_CLOSED = False
DEFAULT_DEVICE_CLASS = 'shutter'

# Services
SERVICE_SET_KNOWN_ACTION = 'set_known_action'
SERVICE_SEND_COMMAND = 'send_command'

# Timing
TRAVEL_TIME_INTERVAL = timedelta(milliseconds=100)

