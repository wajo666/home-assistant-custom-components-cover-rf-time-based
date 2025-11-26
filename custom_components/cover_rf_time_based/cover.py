"""Thin orchestrator for cover_rf_time_based platform using split modules."""
from __future__ import annotations
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    ATTR_CONFIDENT,
    ATTR_POSITION_TYPE,
    ATTR_POSITION_TYPE_TARGET,
    ATTR_ACTION,
    ATTR_COMMAND,
    SERVICE_SET_KNOWN_ACTION,
    SERVICE_SEND_COMMAND,
    CONF_NAME,
    CONF_DEVICE_CLASS,
    CONF_COVER_ENTITY_ID,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONF_TILTING_TIME_DOWN,
    CONF_TILTING_TIME_UP,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
    CONF_BLOCK_TILT_IF_OPEN,
    CONF_TILT_ONLY_WHEN_CLOSED,
    CONF_OPEN_SCRIPT_ENTITY_ID,
    CONF_CLOSE_SCRIPT_ENTITY_ID,
    CONF_STOP_SCRIPT_ENTITY_ID,
    CONF_TILT_OPEN_SCRIPT_ENTITY_ID,
    CONF_TILT_CLOSE_SCRIPT_ENTITY_ID,
    CONF_TILT_STOP_SCRIPT_ENTITY_ID,
    CONF_COMMAND_DELAY,
    CONF_AVAILABILITY_TEMPLATE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_TRAVEL_TIME,
    DEFAULT_TILT_TIME,
    DEFAULT_SEND_STOP_AT_ENDS,
    DEFAULT_ALWAYS_CONFIDENT,
    DEFAULT_BLOCK_TILT_IF_OPEN,
    DEFAULT_TILT_ONLY_WHEN_CLOSED,
    DEFAULT_COMMAND_DELAY,
)
from .helpers import PLATFORM_SCHEMA, devices_from_config
from .models import DeviceConfig, ScriptsConfig, WrapperConfig
from .entity import CoverTimeBased

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover from a config entry."""
    _LOGGER.info("Setting up cover_rf_time_based from config entry: %s", entry.title)

    # Merge data and options (options take precedence)
    config_data = {**entry.data, **entry.options}

    # Process availability_template if present
    availability_template = None
    if CONF_AVAILABILITY_TEMPLATE in config_data and config_data[CONF_AVAILABILITY_TEMPLATE]:
        try:
            from homeassistant.helpers.template import Template
            template_str = config_data[CONF_AVAILABILITY_TEMPLATE]
            availability_template = Template(template_str, hass)
        except Exception as ex:
            _LOGGER.warning("Failed to parse availability_template for %s: %s", entry.title, ex)

    # Build device config from entry data
    device_config = DeviceConfig(
        name=config_data.get(CONF_NAME, entry.title),
        device_class=config_data.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
        travel_time_down=config_data.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
        travel_time_up=config_data.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
        tilting_time_down=config_data.get(CONF_TILTING_TIME_DOWN, DEFAULT_TILT_TIME),
        tilting_time_up=config_data.get(CONF_TILTING_TIME_UP, DEFAULT_TILT_TIME),
        send_stop_at_ends=config_data.get(CONF_SEND_STOP_AT_ENDS, DEFAULT_SEND_STOP_AT_ENDS),
        always_confident=config_data.get(CONF_ALWAYS_CONFIDENT, DEFAULT_ALWAYS_CONFIDENT),
        block_tilt_if_open=config_data.get(CONF_BLOCK_TILT_IF_OPEN, DEFAULT_BLOCK_TILT_IF_OPEN),
        tilt_only_when_closed=config_data.get(CONF_TILT_ONLY_WHEN_CLOSED, DEFAULT_TILT_ONLY_WHEN_CLOSED),
        availability_template=availability_template,
        command_delay=config_data.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY),
    )

    scripts_config = ScriptsConfig(
        open_script=config_data.get(CONF_OPEN_SCRIPT_ENTITY_ID),
        close_script=config_data.get(CONF_CLOSE_SCRIPT_ENTITY_ID),
        stop_script=config_data.get(CONF_STOP_SCRIPT_ENTITY_ID),
        tilt_open_script=config_data.get(CONF_TILT_OPEN_SCRIPT_ENTITY_ID),
        tilt_close_script=config_data.get(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID),
        tilt_stop_script=config_data.get(CONF_TILT_STOP_SCRIPT_ENTITY_ID),
    )

    wrapper_config = WrapperConfig(
        cover_entity_id=config_data.get(CONF_COVER_ENTITY_ID),
    )

    # Use entry_id as device_id for config flow entries
    device_id = entry.entry_id

    entity = CoverTimeBased(device_id, device_config, scripts_config, wrapper_config)
    async_add_entities([entity])

    # Register services
    await _async_register_services(hass)

    _LOGGER.info("Config entry setup complete for: %s", entry.title)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover from YAML configuration."""
    _LOGGER.info("=== YAML Platform Setup Started ===")
    _LOGGER.info("Config: %s", config)
    _LOGGER.info("Discovery info: %s", discovery_info)

    try:
        entities = devices_from_config(config)
        if not entities:
            _LOGGER.warning("No entities to add (duplicates skipped or empty config)")
        else:
            async_add_entities(entities)
            _LOGGER.info("Added %d entities from YAML", len(entities))
    except Exception as ex:
        _LOGGER.error("Setup failed: %s", ex, exc_info=True)
        return False

    await _async_register_services(hass)

    _LOGGER.info("cover_rf_time_based YAML setup complete")
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register entity services (only once)."""
    platform = entity_platform.async_get_current_platform()

    # Check if services are already registered to avoid duplicates
    if hasattr(platform, "_cover_rf_registered"):
        return

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

    # Mark as registered
    platform._cover_rf_registered = True
