"""Thin orchestrator for cover_rf_time_based platform using split modules."""
from __future__ import annotations
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.components.cover import PLATFORM_SCHEMA
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
)
from .helpers import PLATFORM_SCHEMA as SPLIT_PLATFORM_SCHEMA, devices_from_config
_LOGGER = logging.getLogger(__name__)
PLATFORM_SCHEMA = SPLIT_PLATFORM_SCHEMA
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("Setting up cover_rf_time_based (split modules)")
    try:
        entities = devices_from_config(config)
        if not entities:
            _LOGGER.warning("No entities to add (duplicates skipped or empty config)")
        else:
            async_add_entities(entities)
            _LOGGER.info("Added %d entities", len(entities))
    except Exception as ex:
        _LOGGER.error("Setup failed: %s", ex, exc_info=True)
        return False
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
    _LOGGER.info("cover_rf_time_based setup complete")
    return True
