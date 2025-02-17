### V2.1.4
- ???

### V2.1.3
- Fix lan mode ftp download regression

### V2.1.2
- Lots of card improvements
- New service actions

### V2.1.1
- Fix A1/P1 FTP download
- AMS card improvements
- Print control card improvements

### V2.1.0
- Add the new cards frontends into the releases including the AMS card ingesting from the cards repo
- Fix mishandling of X1C/E causing setup failure
- Enable ability to load model data from printer via FTP
- Add support for new print control/skip objects card
- Add the new print control card to the cards repro.

### V2.0.46
- Fix integration setup failures with older printer firmwares take 2

### V2.0.45
- Fix integration setup failures with older printer firmwares

### V2.0.44
- Fix for model FTP download being active when it shouldn't be yet (not fully ready)
- Add start of timelapse download support (disabled)

### V2.0.43
- Fix for camera take 2

### V2.0.42
- Fix for ip address not present in mqtt payload with older firmwares

### V2.0.41
- Updated config/options cloud flows to get printer IP address from the cloud mqtt payload
- Converted auto translation script to python and updated it to delete removed strings and re-localized changed English strings.
- Delete cloud authentication data if a printer is reconfigured to lan mode.
- Updated P1/A1 camera access to use IP address from mqtt payload.
- Add new print from file service.

### V2.0.40
- Allow phone numbers with the home assistant form complaining
- Only do slicer setting retrieval on successful printer connection to reduce triggering cloudflare throttling.
- Addition of Danish, Slovak and Portuguese
- Add control for A1 prompt sound
- Fix detection of reusable credentials
- Addition of A1 specific "check nozzle" 'error' when loading a filament.

### V2.0.39
- Removed unsupported wled blueprint
- Simplified hms errors
- Fallback to requests if cloudscraper isn't available
- Updated translations
- Allow different credentials to be provided when adding a printer
- Add service to send arbitrary gcode
- Improvements email and sms code handling
- Misc fixes

### V2.0.38
- Fix to handle authentication changes in China
- Improved Spanish translations
- Cleanup device trigger events and add print error device trigger events
- Update filament list
- Update errors list

### V2.0.37
- Switch back to cloudscraper from curl_cffi as Bambu cloudflare has stopped blocking it
- Re-enable custom filament retrieval
- Cleanup all the rapid login flow changes to be exception based and more maintainable
- Update translations

### V2.0.36
- Reuse credentials from other instances to streamline multiple printer setup
- Disable custom filament retrieval in case it's contributing to cloudflare woes
- Add image camera back with switch to use that
- Add switch to disable camera

### V2.0.35
- Switch to dictionary for initialization settings
- Allow cameras to be turned off
- Use working credentials from other integration instances if present

### V2.0.34
- Update translations for new strings
- Fix off by one error in print weight attributes
- Set curl_cffi to impersonate Chrome

### V2.0.33
- Switch to curl_cffi to get past cloudflare
- Fix greek localization filename

### V2.0.32
- Fix error when printer IP address isn't provided due to incorrect logging addition

### V2.0.31
- Fix China phone login

### V2.0.30
- Switch to cloudscraper to address cloudflare issues
- Fix another 2FA bug.
- Fix tag_uid
- Miscellaneous improvements

### V2.0.29
- Fix 2FA bug

### V2.0.28
- Adds 2FA and email code
- Added back tag_uuid
- Corrected greek localization file naming
- Fix blocking error if the printer is running in pure Bambu cloud mode

### V2.0.27
- Fix disconnect from printer at end of print.
- Suppress remaining filament attribute on AMS Lite as it doesn't get reported.
- Switch to tray_uuid to match Bambu Studio (to come - add back tag_uuid to match Bambu Handy)
- Cleanly handle AMS being removed and/or added after integation is set up.
- Add German localization
- Fix HA complaint about blocking SSL lookup
- Improve header generation on REST calls
- Hide aux fan on A1 printers since they don't have it
- Don't tie end time availability to whether we have a start time available to us.
- Miscellaneous minor fixes

### V2.0.26
- Add Greek translation
- Fix regression in error sensor never turning off
- Update contribution rules

### V2.0.25
- Re-enable slicer settings with fix and improved resilience to http errors
- More authentication fixes
- Fix blocking IO warning for MQTT TLS setup
- Miscellaneous fixes

### V2.0.24
- Disable slicer settings retrieval as it is getting access denied and breaking the integration.

### V2.0.23
- Fix cloud connection to meet cloudfare requirement for HTTP2.0 thanks to @TheDuffman85
- Miscellaneous fixes
- Bump min version of HA to 24.8.1

### V2.0.22
- Miscellaneous fixes

### V2.0.21
- Fix syntax error in RTSP URL redaction.

### V2.0.20
- Redact RTSP URL in debug logs.
- Fix missing start/end time for X1 printers.
- Add Bambu PLA Galaxy filament - thanks @meishild
- Improve README for X1 camera notes - thanks @tubalainen

### V2.0.19
- Fix syntax error in polling fallback scenario.

### V2.0.18
- Fix regression in AMS initialization from cleanup

### V2.0.17
- Fix warning about light mode being required
- Fix X1C/E printer detection after firmware change
- Reverse AMS humidity index to match Bambu Handy/Studio UX change
- Fix unknown 'system' print_type error when doing things like performing calibration

### V2.0.16
- Handle home assistant shutdown more gracefully
- Fix threading bug causing severe instability for some folk on newer HA versions.

### V2.0.15
- Add lost fix for usage hours from prototype branch
- Fix missed usage hours paused at print end if the AMS fails to retract
- Fix 24 hour jump in usage hours if print almost immediately cancelled
- Persist manual refresh mode choice across integration restart
- Add local/cloud print job type sensor
- Add AMS slot length/weight as extra attributes to the global length/weight sensors

### V2.0.14
- Improve handling of offline/unreachable printer in chamber image thread

### V2.0.13
- Fix reconnect on lost connection to printer
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
- Fix mishandling of printer power off/on when connected to bambu cloud mqtt

### V2.0.8
- Fix missing chamber image on A1 Mini

### V2.0.7
- Add nozzle type & diameter sensors
- Get correct start time on integration start with P1/A1 from Bambu Cloud and fix incorrect end time in some cases
- Expose X1 enclosure door state as a diagnostic sensor
- Reconnect to printer for chamber image if connection drops
- Fixes

### V2.0.5
- Rework P1/A1 chamber image handling to be a lot more efficient and maybe fix broken tight loop bug.
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
