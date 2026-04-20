# DinSafer S7pro Home Assistant Integration

Custom Home Assistant integration for the DinSafer S7pro alarm system.

## Features

- View current alarm state (Armed Away, Armed Home, Disarmed)
- Arm/Disarm the alarm from Home Assistant
- View device status (online, battery level, charging status)
- HTTP polling (no WebSocket conflicts with mobile app)

## Installation

### HACS (Recommended - when published)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add this repository URL
6. Select "Integration" as the category
7. Click "Install"
8. Restart Home Assistant

### Manual Installation

1. Download this repository
2. Copy the `custom_components/dinsafer` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "DinSafer S7pro"
6. Enter your DinSafer account credentials

## Configuration

The integration is configured via the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **DinSafer S7pro**
4. Enter your credentials:
   - Email: Your DinSafer account email
   - Password: Your DinSafer account password

## Usage

Once configured, the integration will:

- Create an `alarm_control_panel` entity for your DinSafer alarm
- Poll the alarm state every 30 seconds
- Allow you to arm/disarm via Home Assistant UI or automations

### Example Automation

```yaml
automation:
  - alias: "Arm alarm when leaving"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "not_home"
    action:
      - service: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.dinsafer_alarm
```

## Supported Devices

- DinSafer S7pro alarm panel

## Technical Details

- **API**: Uses DinSafer cloud API (api-nx.plutomen.com)
- **Polling Interval**: 30 seconds
- **Connection Type**: HTTP (cloud polling)
- **Dependencies**: None (uses built-in Python libraries)

## Troubleshooting

### Integration not showing up

- Make sure you've restarted Home Assistant after installation
- Check the logs for any errors: Settings → System → Logs

### Authentication failed

- Verify your email and password are correct
- Make sure you can log into the DinSafer mobile app with the same credentials

### State not updating

- The integration polls every 30 seconds
- Check that your alarm panel is online in the DinSafer mobile app
- Check Home Assistant logs for connection errors

## Credits

Reverse engineered from the DinSafer Android app.

## License

MIT License - See LICENSE file for details

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by DinSafer.
