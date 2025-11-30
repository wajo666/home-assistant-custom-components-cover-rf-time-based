# Migration Guide: YAML to UI Configuration

This guide explains how to migrate your Cover RF Time Based integration from YAML configuration to UI configuration.

## Benefits of UI Configuration

- **Easy Configuration**: Configure covers through the Home Assistant UI instead of editing YAML files
- **Live Updates**: Change settings without restarting Home Assistant
- **Validation**: Immediate feedback on configuration errors
- **User-Friendly**: No need to remember configuration keys and syntax

## Migration Steps

### 1. Note Your Current YAML Configuration

Before starting, note down your current configuration from `configuration.yaml`:

**Script-Based Example:**
```yaml
cover:
  - platform: cover_rf_time_based
    devices:
      bedroom_cover:
        name: "Bedroom Cover"
        travelling_time_down: 32
        travelling_time_up: 30
        tilting_time_down: 1.2
        tilting_time_up: 1.2
        command_delay: 0.5
        open_script_entity_id: script.bedroom_cover_open
        close_script_entity_id: script.bedroom_cover_close
        stop_script_entity_id: script.bedroom_cover_stop
        tilt_open_script_entity_id: script.bedroom_cover_tilt_open
        tilt_close_script_entity_id: script.bedroom_cover_tilt_close
        tilt_stop_script_entity_id: script.bedroom_cover_tilt_stop
        send_stop_at_ends: false
        always_confident: false
        tilt_only_when_closed: true
```

**Wrapper/Hybrid Example:**
```yaml
cover:
  - platform: cover_rf_time_based
    devices:
      living_room_cover:
        name: "Living Room Cover"
        travelling_time_down: 29
        travelling_time_up: 28
        cover_entity_id: cover.zigbee_blinds  # Wrapper mode
        tilting_time_down: 10
        tilting_time_up: 5
        tilt_open_script_entity_id: script.tilt_open_rf
        tilt_close_script_entity_id: script.tilt_close_rf
        command_delay: 0
        send_stop_at_ends: false
        availability_template: "{{ not (is_state('cover.zigbee_blinds', 'unavailable') or is_state('cover.zigbee_blinds', 'unknown')) }}"
```

### 2. Add New Cover via UI

**⚡ Automatic Migration (Recommended):**

When you use the automatic migration feature, the system **automatically detects** whether your YAML configuration is wrapper or script-based:

- **Has `cover_entity_id`?** → Migrates as **Wrapper mode**
- **Has scripts only?** → Migrates as **Script mode**

**You don't need to choose anything!** Just confirm the migration and all settings are preserved.

**To use automatic migration:**
1. Go to **Settings** → **Devices & Services**
2. Find **Cover Time Based** integration (appears automatically if you have YAML configs)
3. Click **Configure**
4. Select **"Migrate X YAML cover(s) to UI"**
5. Review device count
6. Check **Confirm** checkbox
7. Click **Submit**
8. Done! All covers migrated with correct mode automatically

---

**Manual Migration (Alternative):**

If you prefer to add covers manually instead of automatic migration:

#### For Script-Based Mode:

1. Go to **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for **"Cover Time Based"**
4. Select **"Script-based (recommended)"** mode
5. Fill in the configuration:
   - **Name**: Bedroom Cover
   - **Device Class**: shutter (or blind, curtain, etc.)
   - **Travel Time Down**: 32 seconds
   - **Travel Time Up**: 30 seconds
   - **Tilt Time Down**: 1.2 seconds
   - **Tilt Time Up**: 1.2 seconds
   - **Command Delay**: 0.5 seconds
   - **Open Script**: script.bedroom_cover_open
   - **Close Script**: script.bedroom_cover_close
   - **Stop Script**: script.bedroom_cover_stop
   - **Tilt Open Script**: script.bedroom_cover_tilt_open
   - **Tilt Close Script**: script.bedroom_cover_tilt_close
   - **Tilt Stop Script**: script.bedroom_cover_tilt_stop
   - **Send Stop at Ends**: unchecked
   - **Always Confident**: unchecked
   - **Tilt Only When Closed**: checked

6. Click **Submit**

#### For Wrapper/Hybrid Mode:

1. Go to **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for **"Cover Time Based"**
4. Select **"Wrapper (existing cover entity)"** mode
5. Fill in the configuration:
   - **Name**: Living Room Cover
   - **Cover Entity**: cover.zigbee_blinds
   - **Device Class**: shutter
   - **Travel Time Down**: 29 seconds
   - **Travel Time Up**: 28 seconds
   - **Tilt Time Down**: 10 seconds
   - **Tilt Time Up**: 5 seconds
   - **Command Delay**: 0 seconds
   - **Stop Script** (optional): script.rf_stop (fallback if wrapper doesn't support stop)
   - **Tilt Open Script**: script.tilt_open_rf
   - **Tilt Close Script**: script.tilt_close_rf
   - **Send Stop at Ends**: unchecked
   - **Availability Template**: `{{ not (is_state('cover.zigbee_blinds', 'unavailable') or is_state('cover.zigbee_blinds', 'unknown')) }}`

6. Click **Submit**

**What is Wrapper Mode?**
- Wrapper mode uses an **existing cover entity** for main movement (open, close, stop, position)
- You can add **custom tilt scripts** for tilt functionality
- **Stop Script** (new in v2.2.2): Optional fallback if wrapper doesn't support stop command
- Perfect for adding tilt to covers that don't support it natively
- Automatically syncs state with the wrapped cover (v2.2.1+)

### 3. Test the New Configuration

Before removing your YAML configuration:

1. Test that the new cover entity works correctly
2. Verify all movements (open, close, stop, tilt)
3. Check that positions are calculated correctly
4. Test the tilt functionality

### 4. Remove YAML Configuration

Once you've verified everything works:

1. **Important**: The entity ID will change from the YAML device_id to a generated ID based on the name
   - Old: `cover.bedroom_cover` 
   - New: `cover.bedroom_cover` (should be the same if names match)
   
2. Remove the old YAML configuration from `configuration.yaml`:
   ```yaml
   # Remove or comment out:
   # cover:
   #   - platform: cover_rf_time_based
   #     devices:
   #       bedroom_cover:
   #         ...
   ```

3. Restart Home Assistant

### 5. Update Automations and Scripts (if needed)

If the entity ID changed, update any automations, scripts, or dashboards that reference the old entity ID.

## Configuration Mapping

| YAML Key | UI Field |
|----------|----------|
| `name` | Name |
| `device_class` | Device Class |
| `travelling_time_down` | Travel Time Down |
| `travelling_time_up` | Travel Time Up |
| `tilting_time_down` | Tilt Time Down |
| `tilting_time_up` | Tilt Time Up |
| `command_delay` | Command Delay |
| `open_script_entity_id` | Open Script |
| `close_script_entity_id` | Close Script |
| `stop_script_entity_id` | Stop Script |
| `tilt_open_script_entity_id` | Tilt Open Script |
| `tilt_close_script_entity_id` | Tilt Close Script |
| `tilt_stop_script_entity_id` | Tilt Stop Script |
| `send_stop_at_ends` | Send Stop at Ends |
| `always_confident` | Always Confident |
| `tilt_only_when_closed` | Tilt Only When Closed |
| `cover_entity_id` | Cover Entity (wrapper mode) |
| `availability_template` | Availability Template (UI has template editor) |

## Command Delay Support

The `command_delay` parameter is supported in both YAML and UI configurations:

**What it does:**
- Specifies the delay (in seconds) between sending a command and the actual start of cover movement
- Accounts for RF signal transmission delays, motor startup time, or other system delays
- Also accounts for STOP command delay - ensures motor stops exactly at target position

**How it works:**
1. Command sent at t=0
2. Motor starts moving at t=command_delay
3. For a 30% position (3 seconds of travel):
   - STOP command sent at t=3.0
   - Motor stops at t=3.0+command_delay (exactly at 30%)

**Default:** 0 seconds (no delay)

**Supports:** Float values (e.g., 0.5 for half-second delay)

**Example:**
- YAML: `command_delay: 0.5`
- UI: Set "Command Delay" field to 0.5

## Modifying Configuration Later

To change settings after initial setup:

1. Go to **Settings** → **Devices & Services**
2. Find **Cover Time Based (script/entity)** integration
3. Click **CONFIGURE** on the device
4. Modify the settings
5. Click **Submit**
6. The integration will automatically reload with new settings

## Wrapper Mode

If you're using wrapper mode (wrapping an existing cover entity), select **"Wrapper (existing cover entity)"** in step 1 and provide the cover entity ID instead of scripts.

### Hybrid Mode (Wrapper + Tilt Scripts)

You can combine wrapper mode with tilt scripts to get the best of both worlds:
- **Main movement** (open/close/stop) uses the wrapped cover entity
- **Tilt functionality** uses custom scripts

This is useful when:
- Your existing cover doesn't support tilt, but you want to add it
- You want to use different RF codes for tilt vs main movement
- You want to customize tilt behavior without changing main movement

**Configuration:**
1. Select **"Wrapper (existing cover entity)"** mode
2. Set **Cover Entity** to your existing cover (e.g., `cover.bedroom_blinds`)
3. Optionally add **Tilt Scripts**:
   - **Tilt Open Script**: Script to open tilt
   - **Tilt Close Script**: Script to close tilt
   - **Tilt Stop Script**: Script to stop tilt
4. Configure tilt timing parameters as needed

The integration will automatically use the wrapper cover for main commands and your scripts for tilt commands.

## Troubleshooting

### Entity not appearing
- Check Home Assistant logs for errors
- Verify all required scripts exist
- Make sure script entity IDs are correct

### Position not accurate
- Adjust travel times in the configuration
- Use the `set_known_position` service to calibrate

### Tilt not working
- Ensure tilt scripts are configured
- Check that `tilt_only_when_closed` is set correctly
- Verify the cover is in the correct position for tilting

## Reverting to YAML

If you need to go back to YAML configuration:

1. Remove the integration from UI (Settings → Devices & Services → Remove)
2. Add back your YAML configuration
3. Restart Home Assistant

## Notes

- You can have both YAML and UI configured devices, but each device should only be configured once
- UI configuration is stored in `.storage/core.config_entries` - don't edit this file manually
- Position and state are preserved during configuration changes (reload)
- All features including `availability_template` are now fully supported in UI configuration

## Availability Template

The `availability_template` field allows you to control when the cover entity is available based on other entities in your Home Assistant installation.

**Common use cases:**
- Monitor RF Bridge connectivity: `{{ is_state('binary_sensor.rf_bridge_status', 'on') }}`
- Track wrapper entity availability: `{{ not is_state('cover.original_cover', 'unavailable') }}`
- Complex conditions: `{{ is_state('binary_sensor.rf_bridge', 'on') and is_state('input_boolean.covers_enabled', 'on') }}`

**In UI:**
- Use the template editor with autocomplete and entity picker
- Live validation helps catch errors immediately
- Can be added during initial setup or modified later via Options

**Benefits:**
- Cover shows as "unavailable" when conditions aren't met
- Prevents sending commands when the underlying hardware is offline
- Better user experience and automation logic


