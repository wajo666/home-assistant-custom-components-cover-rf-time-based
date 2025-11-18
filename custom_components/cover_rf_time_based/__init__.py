"""Cover RF Time Based integration for Home Assistant.

This integration provides time-based cover control with optional tilt support.
Supports both script-based operation and wrapping existing cover entities.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "cover_rf_time_based"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cover RF Time Based component from YAML configuration.

    Platform setup is handled by cover.py's async_setup_platform.
    """
    return True

