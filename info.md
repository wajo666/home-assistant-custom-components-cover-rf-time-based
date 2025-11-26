# Cover Time Based (script/entity)

With this component you can add a time-based cover with optional **TILT support**. You can either set triggering scripts to open, close and stop the cover, or use an existing cover entity provided by another integration. Position (and tilt position if configured) is calculated based on the fraction of time spent by the cover travelling up or down. You can set position from within Home Assistant using service calls. When you use this component, you can forget about the cover's original remote controllers or switches, because there's no feedback from the cover about its real state, state is assumed based on the last command sent from Home Assistant. There are custom services available where you can update the real state of the cover (including tilt position) based on external sensors if you want to.

[Configuration details and documentation](https://github.com/wajo666/home-assistant-custom-components-cover-rf-time-based)

## Supported features:
- **Full TILT support** - independent tilt control with configurable behavior (can work independently or only when closed)
- **Dual operation mode** - use with scripts (RF/Tasmota/ESPHome) or wrap existing cover entities to add position tracking
- Usable with covers which support only triggering, and give no feedback about their state (position is assumed based on commands sent from HA)
- State can be updated based on independent, external sensors (for example a contact or reed sensor at closed or opened state)
- State can mimic the operation based on external sensors (for example by monitoring the air for closing or opening RF codes) so usage in parallel with controllers outside HA is possible
- Ability to take care of queuing the transmission of the codes and keeping an appropriate delay between them to minimize 'missed' commands
- Can be used on top of any existing cover integration, or directly with ESPHome or Tasmota firmwares running on various ESP-based modules
- **Three custom services**: `set_known_position` (supports both position and tilt), `set_known_action`, and `send_command` (supports all cover and tilt commands)
- Separate tilt scripts support or automatic fallback to main cover scripts
- Configurable tilt behavior with `tilt_only_when_closed` option

## Component authors & contributors
    "@davidramosweb",
    "@nagyrobi",
    "@Alfiegerner",
    "@regevbr",
    "@wajo666"

[Support forum](https://community.home-assistant.io/t/custom-component-cover-time-based/187654/3)
