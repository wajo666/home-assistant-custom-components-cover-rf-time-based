"""Cover RF Time Based integration for Home Assistant.

This integration provides time-based cover control with optional tilt support.
Supports both script-based operation and wrapping existing cover entities.
"""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cover RF Time Based component.

    This is called when the integration is loaded from configuration.yaml.
    YAML platform configurations (platform: cover_rf_time_based) are handled
    automatically by Home Assistant's platform loader, which will call
    async_setup_platform in cover.py.
    """
    _LOGGER.info("=== Cover RF Time Based Integration Setup ===")
    _LOGGER.debug("Config keys: %s", list(config.keys()))

    # Initialize domain data storage
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Check if there are YAML-configured covers
    has_yaml_config = False
    if "cover" in config:
        for cover_config in config.get("cover", []):
            if cover_config.get("platform") == DOMAIN:
                has_yaml_config = True
                break

    # If YAML config exists but no config entries, create a placeholder entry
    # This makes the integration visible in "Devices & Services" UI
    if has_yaml_config:
        _LOGGER.info("YAML configuration detected")

        # Check if we already have any config entries
        existing_entries = hass.config_entries.async_entries(DOMAIN)

        if not existing_entries:
            _LOGGER.info("Creating placeholder config entry to make integration visible in UI")
            # Create an ignored entry that represents YAML configuration
            # This is similar to how other integrations handle YAML + UI coexistence
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data={"yaml_config": True},
                )
            )

    _LOGGER.info("Integration setup complete")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cover RF Time Based from a config entry."""
    _LOGGER.info("Setting up cover_rf_time_based config entry: %s", entry.title)

    # If this is a YAML import entry, don't forward to platform
    # YAML entities are loaded via async_setup_platform in cover.py
    if entry.data.get("yaml_config"):
        _LOGGER.info("This is a YAML configuration placeholder entry - entities loaded via platform setup")
        return True

    # For UI-configured entries, forward the setup to the cover platform
    await hass.config_entries.async_forward_entry_setups(entry, ["cover"])

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading cover_rf_time_based config entry: %s", entry.title)

    return await hass.config_entries.async_unload_platforms(entry, ["cover"])


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)



