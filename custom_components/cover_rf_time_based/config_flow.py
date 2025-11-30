"""Config flow for Cover RF Time Based integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    CONF_COVER_ENTITY_ID,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    CONF_TILTING_TIME_DOWN,
    CONF_TILTING_TIME_UP,
    CONF_SEND_STOP_AT_ENDS,
    CONF_ALWAYS_CONFIDENT,
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
    DEFAULT_TILT_ONLY_WHEN_CLOSED,
    DEFAULT_COMMAND_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_MODE = "mode"
MODE_SCRIPT = "script"
MODE_WRAPPER = "wrapper"


class CoverRfTimeBasedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover RF Time Based."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from YAML configuration.

        This can either create individual device entries or a placeholder.
        When device_config is provided, it creates a proper config entry for that device.
        """
        _LOGGER.info("Import step called with data: %s", import_data)

        # Check if this is a device import (from automatic migration)
        if "device_config" in import_data:
            device_config = import_data["device_config"]
            device_name = device_config.get(CONF_NAME, "Unknown")

            # Check if this device is already configured (by name)
            existing_entries = self._async_current_entries()
            for entry in existing_entries:
                if entry.data.get(CONF_NAME) == device_name:
                    _LOGGER.info("Device '%s' already configured, skipping import", device_name)
                    return self.async_abort(reason="already_configured")

            # Set unique ID based on device name
            await self.async_set_unique_id(f"yaml_import_{device_name}")
            self._abort_if_unique_id_configured()

            # Create entry for this device
            _LOGGER.info("Creating config entry for imported device: %s", device_name)
            return self.async_create_entry(
                title=device_name,
                data=device_config,
            )

        # Otherwise, create a placeholder entry for YAML configuration visibility
        existing_entries = self._async_current_entries()
        for entry in existing_entries:
            if entry.source == "import" and entry.data.get("yaml_config"):
                _LOGGER.debug("YAML placeholder entry already exists, skipping")
                return self.async_abort(reason="already_configured")

        # Create a special entry for YAML configuration
        _LOGGER.info("Creating placeholder config entry for YAML configuration")
        return self.async_create_entry(
            title="YAML Configuration",
            data={"yaml_config": True},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose mode or migrate."""
        if user_input is not None:
            if user_input.get("action") == "migrate":
                return await self.async_step_migrate_yaml()
            else:
                self.mode = user_input.get(CONF_MODE, MODE_SCRIPT)
                return await self.async_step_device_config()

        # Check if YAML configs are available for migration
        yaml_configs = self.hass.data.get(DOMAIN, {}).get("yaml_configs", [])
        total_yaml_devices = sum(len(cfg.get("devices", {})) for cfg in yaml_configs)

        # Build options based on available migrations
        if total_yaml_devices > 0:
            # Offer migration option
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("action", default="add"): vol.In({
                        "add": "Add new cover",
                        "migrate": f"Migrate {total_yaml_devices} YAML cover(s) to UI",
                    }),
                    vol.Optional(CONF_MODE, default=MODE_SCRIPT): vol.In({
                        MODE_SCRIPT: "Script-based (recommended)",
                        MODE_WRAPPER: "Wrapper (existing cover entity)",
                    }),
                }),
            )
        else:
            # No migration available, just show mode selection
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_MODE, default=MODE_SCRIPT): vol.In({
                        MODE_SCRIPT: "Script-based (recommended)",
                        MODE_WRAPPER: "Wrapper (existing cover entity)",
                    }),
                }),
            )

    async def async_step_migrate_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle YAML to UI migration."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Perform migration
                from .migration import async_migrate_yaml_to_ui

                yaml_configs = self.hass.data.get(DOMAIN, {}).get("yaml_configs", [])

                for yaml_config in yaml_configs:
                    await async_migrate_yaml_to_ui(self.hass, yaml_config)

                # Clear the notification if it exists
                await self.hass.services.async_call(
                    "persistent_notification",
                    "dismiss",
                    {"notification_id": f"{DOMAIN}_migration_available"},
                )

                return self.async_create_entry(
                    title="Migration Complete",
                    data={"migration_completed": True},
                )
            else:
                return self.async_abort(reason="migration_cancelled")

        # Show confirmation form
        yaml_configs = self.hass.data.get(DOMAIN, {}).get("yaml_configs", [])
        total_devices = sum(len(cfg.get("devices", {})) for cfg in yaml_configs)

        return self.async_show_form(
            step_id="migrate_yaml",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            description_placeholders={
                "device_count": str(total_devices),
            },
        )

    async def async_step_device_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device configuration step."""
        errors = {}

        if user_input is not None:
            # Validate based on mode
            if self.mode == MODE_SCRIPT:
                if not all([
                    user_input.get(CONF_OPEN_SCRIPT_ENTITY_ID),
                    user_input.get(CONF_CLOSE_SCRIPT_ENTITY_ID),
                    user_input.get(CONF_STOP_SCRIPT_ENTITY_ID),
                ]):
                    errors["base"] = "missing_scripts"
            elif self.mode == MODE_WRAPPER:
                if not user_input.get(CONF_COVER_ENTITY_ID):
                    errors["base"] = "missing_cover_entity"

            if not errors:
                # Create unique_id from name
                await self.async_set_unique_id(user_input[CONF_NAME])
                self._abort_if_unique_id_configured()

                # Store mode in data
                user_input[CONF_MODE] = self.mode

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        # Build schema based on mode
        if self.mode == MODE_SCRIPT:
            schema = self._get_script_schema()
        else:
            schema = self._get_wrapper_schema()

        return self.async_show_form(
            step_id="device_config",
            data_schema=schema,
            errors=errors,
        )

    def _get_base_schema(self) -> vol.Schema:
        """Get base configuration schema shared by both modes."""
        return vol.Schema({
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["awning", "blind", "curtain", "damper", "door", "garage", "gate", "shade", "shutter", "window"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=300,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=300,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_TILTING_TIME_DOWN, default=DEFAULT_TILT_TIME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=60,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_TILTING_TIME_UP, default=DEFAULT_TILT_TIME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=60,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_COMMAND_DELAY, default=DEFAULT_COMMAND_DELAY): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_SEND_STOP_AT_ENDS, default=DEFAULT_SEND_STOP_AT_ENDS): selector.BooleanSelector(),
            vol.Optional(CONF_ALWAYS_CONFIDENT, default=DEFAULT_ALWAYS_CONFIDENT): selector.BooleanSelector(),
            vol.Optional(CONF_TILT_ONLY_WHEN_CLOSED, default=DEFAULT_TILT_ONLY_WHEN_CLOSED): selector.BooleanSelector(),
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): selector.TemplateSelector(),
        })

    def _get_script_schema(self) -> vol.Schema:
        """Get schema for script-based mode."""
        base = self._get_base_schema().schema
        base.update({
            vol.Required(CONF_OPEN_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Required(CONF_CLOSE_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Required(CONF_STOP_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_OPEN_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_STOP_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
        })
        return vol.Schema(base)

    def _get_wrapper_schema(self) -> vol.Schema:
        """Get schema for wrapper mode."""
        base = self._get_base_schema().schema
        base.update({
            vol.Required(CONF_COVER_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="cover")
            ),
            vol.Optional(CONF_STOP_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_OPEN_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_TILT_STOP_SCRIPT_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
        })
        return vol.Schema(base)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CoverRfTimeBasedOptionsFlow:
        """Get the options flow for this handler."""
        return CoverRfTimeBasedOptionsFlow(config_entry)


class CoverRfTimeBasedOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Cover RF Time Based."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.mode = config_entry.data.get(CONF_MODE, MODE_SCRIPT)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build schema based on mode with current values
        if self.mode == MODE_SCRIPT:
            schema = self._get_script_options_schema()
        else:
            schema = self._get_wrapper_options_schema()

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    def _get_current_value(self, key: str, default: Any = None) -> Any:
        """Get current value from options or data."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    def _get_base_options_schema(self) -> vol.Schema:
        """Get base options schema."""
        return vol.Schema({
            vol.Optional(
                CONF_TRAVELLING_TIME_DOWN,
                default=self._get_current_value(CONF_TRAVELLING_TIME_DOWN, DEFAULT_TRAVEL_TIME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=300,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_TRAVELLING_TIME_UP,
                default=self._get_current_value(CONF_TRAVELLING_TIME_UP, DEFAULT_TRAVEL_TIME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=300,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_TILTING_TIME_DOWN,
                default=self._get_current_value(CONF_TILTING_TIME_DOWN, DEFAULT_TILT_TIME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=60,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_TILTING_TIME_UP,
                default=self._get_current_value(CONF_TILTING_TIME_UP, DEFAULT_TILT_TIME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=60,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_COMMAND_DELAY,
                default=self._get_current_value(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10,
                    step=0.1,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_SEND_STOP_AT_ENDS,
                default=self._get_current_value(CONF_SEND_STOP_AT_ENDS, DEFAULT_SEND_STOP_AT_ENDS)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ALWAYS_CONFIDENT,
                default=self._get_current_value(CONF_ALWAYS_CONFIDENT, DEFAULT_ALWAYS_CONFIDENT)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_TILT_ONLY_WHEN_CLOSED,
                default=self._get_current_value(CONF_TILT_ONLY_WHEN_CLOSED, DEFAULT_TILT_ONLY_WHEN_CLOSED)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_AVAILABILITY_TEMPLATE,
                default=self._get_current_value(CONF_AVAILABILITY_TEMPLATE)
            ): selector.TemplateSelector(),
        })

    def _get_script_options_schema(self) -> vol.Schema:
        """Get options schema for script mode."""
        base = self._get_base_options_schema().schema
        base.update({
            vol.Optional(
                CONF_OPEN_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_OPEN_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_CLOSE_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_CLOSE_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_STOP_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_STOP_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_OPEN_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_OPEN_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_CLOSE_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_STOP_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_STOP_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
        })
        return vol.Schema(base)

    def _get_wrapper_options_schema(self) -> vol.Schema:
        """Get options schema for wrapper mode."""
        base = self._get_base_options_schema().schema
        base.update({
            vol.Optional(
                CONF_COVER_ENTITY_ID,
                default=self._get_current_value(CONF_COVER_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="cover")
            ),
            vol.Optional(
                CONF_STOP_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_STOP_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_OPEN_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_OPEN_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_CLOSE_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_CLOSE_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(
                CONF_TILT_STOP_SCRIPT_ENTITY_ID,
                default=self._get_current_value(CONF_TILT_STOP_SCRIPT_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
        })
        return vol.Schema(base)

