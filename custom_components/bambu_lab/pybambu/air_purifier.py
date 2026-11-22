"""Bambu E1 air purifier telemetry and controls."""


PURIFIER_GEARS = {"off": 0, "silent": 1, "standard": 2, "max": 3, "auto": 15}


class AirPurifier:
    """An optional air purifier connected to a printer's accessory bus."""

    def __init__(self, client):
        self._client = client
        self.connected = None
        self.serial = ""
        self.model = ""
        self.hw_version = ""
        self.sw_version = ""
        self._identity_confirmed = False
        self.gear = None
        self.pm = None
        self.rpm = None
        self.filter_type = None
        self.filter_used_raw = None
        self.filter_total_raw = None

    @property
    def ready(self):
        return self.connected is True and self._identity_confirmed and bool(self.serial)

    @property
    def identity(self):
        return self.serial if self.ready else None

    def info_update(self, data):
        """Read the purifier's actual identity from get_version."""
        old = (self.serial, self.model, self.hw_version, self.sw_version, self._identity_confirmed)
        for module in data.get("module") or []:
            if not isinstance(module, dict) or module.get("name") != "aps":
                continue
            serial = module.get("sn")
            if not isinstance(serial, str) or not serial.strip():
                continue
            self.serial = serial.strip()
            self.model = module.get("product_name") or "E1 Air Purifier"
            self.hw_version = module.get("hw_ver") or ""
            self.sw_version = module.get("sw_ver") or ""
            self._identity_confirmed = True
            break
        return old != (self.serial, self.model, self.hw_version, self.sw_version, self._identity_confirmed)

    def print_update(self, data):
        """Merge partial APS reports without interpreting absent fields as zero."""
        old = (self.connected, self._identity_confirmed, self.gear, self.pm, self.rpm,
               self.filter_type, self.filter_used_raw, self.filter_total_raw)
        aux = data.get("aux")
        try:
            if isinstance(aux, str) and aux:
                bits = int(aux, 16)
            elif type(aux) is int:
                bits = aux
            else:
                bits = None
            if bits is not None and bits >= 0:
                self.connected = bool(bits & (1 << 37))
        except ValueError:
            pass

        device = data.get("device")
        aps = device.get("aps") if isinstance(device, dict) else None
        if self.connected is None and isinstance(aps, dict) and aps:
            self.connected = True
        if self.connected is False:
            self._identity_confirmed = False
            self.gear = self.pm = self.rpm = None
            self.filter_type = self.filter_used_raw = self.filter_total_raw = None
        elif isinstance(aps, dict):
            for key, attribute in (("gear", "gear"), ("pm", "pm"), ("rpm", "rpm"),
                                   ("f_type", "filter_type"), ("f_use", "filter_used_raw"),
                                   ("f_to", "filter_total_raw")):
                value = aps.get(key)
                if type(value) is int and value >= 0:
                    setattr(self, attribute, value)

        return old != (self.connected, self._identity_confirmed, self.gear, self.pm, self.rpm,
                       self.filter_type, self.filter_used_raw, self.filter_total_raw)

    def set_mode(self, mode):
        """Request a mode using the Bambu Studio APS protocol."""
        if not self.ready or mode not in PURIFIER_GEARS:
            return False
        return bool(self._client.publish({"print": {
            "sequence_id": "0", "command": "part_control", "module": "aps",
            "action": str(PURIFIER_GEARS[mode]),
        }}))
