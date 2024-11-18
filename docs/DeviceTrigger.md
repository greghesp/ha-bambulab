# Device Triggers

This integration implements a handful of device triggers to make some automation scenarios a little easier to achieve by point and click and without requiring a deeper understanding of the various sensors the printer exposes or where the information is not exposed from sensors such as transient print error notifications from the printer

All events include the name of the printer as part of the data payload.

Available events:
- Print started
- Print finished
- Print canceled
- Print failed (X1 only)
- HMS error detected. With additional data payload:
    - code
    - error
    - url (wiki link for error)
- Print error detected. This is a separate set of errors that aren't surfaced as HMS errors. No I don't know why. With additional data payload:
    - code
    - error

For the most part these are just conveniences - you could craft an automation triggering the same way but it takes a bit more effort to understand which sensor(s) to use to track the activity you want which requires understanding how the sensors and what the available states are.

The print canceled and print error events are only a transient event from the printer rather than a persistent state so these are not avaialble from sensors.

The printer sensor that exposes HMS errors as a list would very complex to effectively handle correctly in the multi-error case so the printer errors event just gives you the most recent error to allow much easier handling in a notification.

Event payload always contains the device_id and name. And the additional data where called out above. When crafting a notification or similar you can access the event data with a template of {{ trigger.event.data.[data_name]}} - e.g. {{ trigger.event.data.**error** }}.

# Actions for Device Triggers

These can be whatever you like. The most interesting case is the 'Printer Error' trigger. This has five pieces of data payload in it:
- device_id
- name
- type (unlocalized name for the event)
- code
- error
- url

These can be accessed using the Jinja2 templating syntax in the action. So for example if you wanted to trigger a notification you would be able to set the title text to

    'Printer Error on {{ trigger.event.data.name }}'

and the message text to

    '{{ trigger.event.data.code }}: {{ trigger.event.data.error }}'

Note that doing this will kick you out of the visual editor and into editing the raw yaml.

# Using Device Triggers

## Option 1 - from the device page

![image](images/AddDeviceAutomation1.png)

![image](images/AddDeviceAutomation2.png)

## Option 2 - from the general automations page

![image](images/AddDeviceTriggerAutomation1.png)

![image](images/AddDeviceTriggerAutomation2.png)

![image](images/AddDeviceTriggerAutomation3.png)

![image](images/AddDeviceTriggerAutomation4.png)

![image](images/AddDeviceTriggerAutomation5.png)
