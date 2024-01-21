### V2.014
- Improve handling of offline/unreachable printer in chamber image thread.

### V2.0.13
- Fix reconnect on lost connection to printer.
- Fix manual connection mode

### V2.0.12
- Fix for estimated usage hours
- Fix Exception data: name 'f' is not defined due to typo in change copied from pybambu repo when an HMS error is active

### V2.0.11
- Fix mishandled new current stage values
- Add estimated usage hours sensor

### V2.0.10
- Fix A1 Mini still missing chamber image

### V2.0.9
- Fix mishandling of printer power off/on when connected to bambu cloud mqtt.

### V2.0.8
- Fix missing chamber image on A1 Mini

### V2.0.7
- Add nozzle type & diameter sensors
- Get correct start time on integration start with P1/A1 from Bambu Cloud and fix incorrect end time in some cases.
- Expose X1 enclosure door state as a diagnostic sensor
- Reconnect to printer for chamber image if connection drops
- Fixes

### V2.0.5
- Rework P1/A1 chamber image handling to be a lot more efficient and maybe fix broken tight loop bug
- Make bambu cloud setup clearer w/ regards to camera and local connection.
- Make P1/A1 camera unavailable if either host IP or access code has not been provided.
- Detect P1/A1 rejecting camera connnection attempt and report error in the logs.

### V2.0.4
- Change start/end time to datetime object and revert the date removal change.
- Fix typos breaking LAN->Cloud config transition.

### V2.0.3
- Reduce work for X1 full payloads to only one HA update instead of three.
- Only log the payloads when the refresh button has been pressed.
- Simplify the start and end times to just times when they are for today.
- Don't throw away user input on error cases during setup/re-configure.
- Fix cover image to update automatically on new print.
- Fix cover image + print weight sensor updating to be more reliable on print start / printer reboot.
- Simplify image update plumbing.
- Various copy editing to UI/README.

### V2.0.2
- Fix mishandling of optional 'email' field when upgrading or if early 2.0 dev build was used.

### V2.0.1
- Fix P1/A1 chamber image not updating
- Missed localization of new strings

### V2.0.0
- Reworked the initial setup to get almost all printer data from Bambu Cloud for easier setup.
- Enables use of P1 camera when in cloud mqtt mode
- Adds cover image sensor to show the 3mf thumbnail of current or last print.
- Adds print weight, length and bed choice of current or last print.
- Adds A1 printer support.
- Adds best guess X1E printer support.
- Fixes potential mqtt thread hang made common with latest X1 firmware.
- Fixes mishandling of AMS removal from a printer leaving a gap in indices.
- Miscellaneous fixes.
- Localization improvements.

### V1.9.3
- Switch to turn off the connection to the printer to workaround P1 firmware bug.

### V1.9.2
- Added remaining filament to AMS tray attributes
- Improved localization

### V1.9.1
- Fix AMS Lite support for A1 Mini
- Improved localization

### V1.9.0
- Added support for A1 Mini
- Added support for P1P Camera

### V1.8.0
- Added support for A1 Mini

### V1.7.1
- Minor fixes

### V1.7.0
- Added a set of device triggers to make common automations easier

### V1.6.0
- Diagnostic by @greghesp in #224
- Fix start time sensor. Adjust end time sensor. by @AdrianGarside in #225
- Fix firmware check on X1 by @AdrianGarside in #228
- Generate start time for P1P/S by @AdrianGarside in #230
- Delete dead mc print support by @AdrianGarside in #229

### V1.5.0
- Fix syntax error by @AdrianGarside in #205
- New filaments by @faucherc in #204
- Readme updates by @AdrianGarside in #208
- Re-enable Bambu cloud MQTT connection to printer. by @AdrianGarside in #209
- Add mqtt mode diagnostic sensor by @AdrianGarside in #210
- Alternative fix for start time by @AdrianGarside in #212
- Avoid overlapping initialization and AMS reinitialization by @AdrianGarside in #214
- Fix mqtt mode change to reload integration by @AdrianGarside in #216
- Detect offline with bambu cloud mqtt mode connection by @AdrianGarside in #217

### V1.4.13
- Fixed some typos and correction to string comparison by @fmeus in #200
- Add pause print status by @piitaya in #202

### V1.4.12
- Gracefully handle print_status (gcode_state) being an empty string on printer power on by @AdrianGarside in #197

### V1.4.11
- Adrian/add failed state translation support by @AdrianGarside in #192
- Update french translations and add empty attribute translation by @piitaya in #190
- Update rtsp URL to use host address instead of one given in the mqtt payload due to report of the latter being incorrect.

### V1.4.9
- Add entity translation support by @piitaya in #178
- Support for adding LED chamber lights via the WLED integration by @dreed47 in #180
- Add Camera functionality by @greghesp in #184
- Add active tray sensor by @AdrianGarside in 8eca79e
- Add gcode filename and task name by @AdrianGarside in ee815b7

...
