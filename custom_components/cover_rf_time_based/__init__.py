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

    # Collect all YAML cover configs for this platform
    yaml_configs = []
    if "cover" in config:
        for cover_config in config.get("cover", []):
            if cover_config.get("platform") == DOMAIN:
                yaml_configs.append(cover_config)

    has_yaml_config = len(yaml_configs) > 0

    if has_yaml_config:
        _LOGGER.info("YAML configuration detected with %d platform entries", len(yaml_configs))

        # Store YAML configs for potential migration
        hass.data[DOMAIN]["yaml_configs"] = yaml_configs

        # Check if we should offer automatic migration
        existing_entries = hass.config_entries.async_entries(DOMAIN)
        yaml_placeholder_exists = any(
            entry.source == "import" and entry.data.get("yaml_config")
            for entry in existing_entries
        )

        # Count how many devices are in YAML
        total_yaml_devices = sum(
            len(cfg.get("devices", {})) for cfg in yaml_configs
        )

        # Count how many actual config entries we have (excluding placeholder)
        actual_entries = [
            entry for entry in existing_entries
            if not entry.data.get("yaml_config")
        ]

        _LOGGER.info(
            "Found %d YAML devices and %d UI config entries",
            total_yaml_devices,
            len(actual_entries)
        )

        # If no placeholder exists yet, create one
        if not yaml_placeholder_exists:
            _LOGGER.info("Creating placeholder config entry to make integration visible in UI")
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data={"yaml_config": True},
                )
            )

        # Offer migration if we have YAML devices but fewer UI entries
        if total_yaml_devices > len(actual_entries):
            _LOGGER.info(
                "Automatic migration available: %d YAML devices can be migrated to UI",
                total_yaml_devices - len(actual_entries)
            )

            # Create a persistent notification about migration
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"**Cover Time Based**: You have {total_yaml_devices} cover(s) configured in YAML.\n\n"
                               f"You can migrate them to UI configuration for easier management.\n\n"
                               f"The integration will continue to work with YAML, but UI configuration "
                               f"provides a better experience with live updates and validation.\n\n"
                               f"To migrate, go to **Settings** → **Devices & Services** → **Cover Time Based**.",
                    "title": "Cover Time Based - Migration Available",
                    "notification_id": f"{DOMAIN}_migration_available",
                },
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



