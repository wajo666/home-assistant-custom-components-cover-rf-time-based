"""Migration helpers for Cover RF Time Based integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from .const import (
    DOMAIN,
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

_LOGGER = logging.getLogger(__name__)

MODE_SCRIPT = "script"
MODE_WRAPPER = "wrapper"


async def async_migrate_yaml_to_ui(hass: HomeAssistant, yaml_config: dict[str, Any]) -> bool:
    """Migrate YAML configuration to UI config entries.

    Args:
        hass: Home Assistant instance
        yaml_config: The platform configuration from YAML

    Returns:
        True if migration was successful, False otherwise
    """
    if "devices" not in yaml_config:
        _LOGGER.warning("No devices found in YAML config")
        return False

    devices = yaml_config["devices"]
    _LOGGER.info("Starting migration of %d devices from YAML to UI", len(devices))

    migrated_count = 0

    for device_id, device_config in devices.items():
        try:
            # Convert YAML config to UI config format
            ui_config = await _convert_yaml_device_to_ui(hass, device_id, device_config)

            if ui_config:
                # Trigger import flow for this device
                await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data={"device_config": ui_config},
                )
                migrated_count += 1
                _LOGGER.info("Successfully queued migration for device: %s", device_config.get(CONF_NAME, device_id))

        except Exception as ex:
            _LOGGER.error("Failed to migrate device %s: %s", device_id, ex, exc_info=True)

    _LOGGER.info("Migration complete: %d/%d devices queued for migration", migrated_count, len(devices))
    return migrated_count > 0


async def _convert_yaml_device_to_ui(
    hass: HomeAssistant,
    device_id: str,
    yaml_config: dict[str, Any]
) -> dict[str, Any] | None:
    """Convert a YAML device configuration to UI config format.

    Args:
        hass: Home Assistant instance
        device_id: Device identifier from YAML
        yaml_config: Device configuration from YAML

    Returns:
        UI-compatible configuration dictionary or None if conversion fails
    """
    try:
        # Determine mode based on configuration
        has_cover_entity = CONF_COVER_ENTITY_ID in yaml_config and yaml_config[CONF_COVER_ENTITY_ID]
        has_scripts = (
            CONF_OPEN_SCRIPT_ENTITY_ID in yaml_config and
            CONF_CLOSE_SCRIPT_ENTITY_ID in yaml_config and
            CONF_STOP_SCRIPT_ENTITY_ID in yaml_config
        )

        if has_cover_entity:
            mode = MODE_WRAPPER
            _LOGGER.debug("Device %s detected as WRAPPER mode", device_id)
        elif has_scripts:
            mode = MODE_SCRIPT
            _LOGGER.debug("Device %s detected as SCRIPT mode", device_id)
        else:
            _LOGGER.error("Device %s has neither cover entity nor scripts configured", device_id)
            return None

        # Build UI config
        ui_config = {
            "mode": mode,
            CONF_NAME: yaml_config.get(CONF_NAME, device_id),
            CONF_DEVICE_CLASS: yaml_config.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS),
            CONF_TRAVELLING_TIME_DOWN: yaml_config.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME),
            CONF_TRAVELLING_TIME_UP: yaml_config.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME),
            CONF_TILTING_TIME_DOWN: yaml_config.get(CONF_TILTING_TIME_DOWN, DEFAULT_TILT_TIME),
            CONF_TILTING_TIME_UP: yaml_config.get(CONF_TILTING_TIME_UP, DEFAULT_TILT_TIME),
            CONF_COMMAND_DELAY: yaml_config.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY),
            CONF_SEND_STOP_AT_ENDS: yaml_config.get(CONF_SEND_STOP_AT_ENDS, DEFAULT_SEND_STOP_AT_ENDS),
            CONF_ALWAYS_CONFIDENT: yaml_config.get(CONF_ALWAYS_CONFIDENT, DEFAULT_ALWAYS_CONFIDENT),
            CONF_BLOCK_TILT_IF_OPEN: yaml_config.get(CONF_BLOCK_TILT_IF_OPEN, DEFAULT_BLOCK_TILT_IF_OPEN),
            CONF_TILT_ONLY_WHEN_CLOSED: yaml_config.get(CONF_TILT_ONLY_WHEN_CLOSED, DEFAULT_TILT_ONLY_WHEN_CLOSED),
        }

        # Add mode-specific fields
        if mode == MODE_WRAPPER:
            ui_config[CONF_COVER_ENTITY_ID] = yaml_config[CONF_COVER_ENTITY_ID]
        else:  # MODE_SCRIPT
            ui_config[CONF_OPEN_SCRIPT_ENTITY_ID] = yaml_config.get(CONF_OPEN_SCRIPT_ENTITY_ID)
            ui_config[CONF_CLOSE_SCRIPT_ENTITY_ID] = yaml_config.get(CONF_CLOSE_SCRIPT_ENTITY_ID)
            ui_config[CONF_STOP_SCRIPT_ENTITY_ID] = yaml_config.get(CONF_STOP_SCRIPT_ENTITY_ID)

        # Add optional tilt scripts (available in both modes)
        if CONF_TILT_OPEN_SCRIPT_ENTITY_ID in yaml_config:
            ui_config[CONF_TILT_OPEN_SCRIPT_ENTITY_ID] = yaml_config[CONF_TILT_OPEN_SCRIPT_ENTITY_ID]
        if CONF_TILT_CLOSE_SCRIPT_ENTITY_ID in yaml_config:
            ui_config[CONF_TILT_CLOSE_SCRIPT_ENTITY_ID] = yaml_config[CONF_TILT_CLOSE_SCRIPT_ENTITY_ID]
        if CONF_TILT_STOP_SCRIPT_ENTITY_ID in yaml_config:
            ui_config[CONF_TILT_STOP_SCRIPT_ENTITY_ID] = yaml_config[CONF_TILT_STOP_SCRIPT_ENTITY_ID]

        # Handle availability template
        if CONF_AVAILABILITY_TEMPLATE in yaml_config:
            template = yaml_config[CONF_AVAILABILITY_TEMPLATE]
            if isinstance(template, Template):
                # Extract template string from Template object
                ui_config[CONF_AVAILABILITY_TEMPLATE] = template.template
            elif isinstance(template, str):
                ui_config[CONF_AVAILABILITY_TEMPLATE] = template

        _LOGGER.debug("Converted device %s to UI config: %s", device_id, ui_config)
        return ui_config

    except Exception as ex:
        _LOGGER.error("Failed to convert device %s: %s", device_id, ex, exc_info=True)
        return None


def get_migration_instructions(yaml_config: dict[str, Any]) -> str:
    """Generate migration instructions for the user.

    Args:
        yaml_config: The YAML configuration

    Returns:
        Formatted migration instructions
    """
    devices = yaml_config.get("devices", {})
    device_count = len(devices)

    instructions = f"""
# YAML to UI Migration Instructions

You have {device_count} cover(s) configured in YAML that can be migrated to UI configuration.

## Automatic Migration

To automatically migrate your YAML configuration to UI:

1. Go to **Settings** → **Devices & Services**
2. Find **Cover Time Based** integration
3. Click **Configure**
4. Select **Migrate from YAML**
5. Review and confirm the migration

## Manual Migration

If you prefer to migrate manually:

"""

    for device_id, device_config in devices.items():
        name = device_config.get(CONF_NAME, device_id)
        has_cover_entity = CONF_COVER_ENTITY_ID in device_config
        mode = "Wrapper" if has_cover_entity else "Script-based"

        instructions += f"""
### {name}
- **Mode**: {mode}
- **Device Class**: {device_config.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS)}
- **Travel Time Down**: {device_config.get(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)}s
- **Travel Time Up**: {device_config.get(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)}s
"""

        if CONF_TILTING_TIME_DOWN in device_config or CONF_TILTING_TIME_UP in device_config:
            instructions += f"""- **Tilt Time Down**: {device_config.get(CONF_TILTING_TIME_DOWN, DEFAULT_TILT_TIME)}s
- **Tilt Time Up**: {device_config.get(CONF_TILTING_TIME_UP, DEFAULT_TILT_TIME)}s
"""

    instructions += """
## After Migration

Once migrated to UI, you can safely remove the YAML configuration from `configuration.yaml`.

**Note**: Entity IDs should remain the same if you use the same device names.
"""

    return instructions

