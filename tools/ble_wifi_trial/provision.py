#!/usr/bin/env python3
"""Manually started, five-minute BlueZ BLE Wi-Fi provisioning trial."""

import secrets
import signal
import threading

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from network import connect, validate


BLUEZ = "org.bluez"
PROPS = "org.freedesktop.DBus.Properties"
OBJECTS = "org.freedesktop.DBus.ObjectManager"
SERVICE = "org.bluez.GattService1"
CHAR = "org.bluez.GattCharacteristic1"
ADVERT = "org.bluez.LEAdvertisement1"
ROOT = "/org/fencewall/wifi_trial"
UUID = "26c40000-61a8-4fd9-bd50-70ed531f"
SERVICE_UUID = UUID + "0000"
SSID_UUID = UUID + "0001"
PASS_UUID = UUID + "0002"
GO_UUID = UUID + "0003"
STATUS_UUID = UUID + "0004"


class TrialError(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.Failed"


class ReadOnlyError(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


class InvalidLengthError(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.InvalidValueLength"


class Application(dbus.service.Object):
    def __init__(self, bus, trial):
        self.trial = trial
        self.path = ROOT
        super().__init__(bus, self.path)
        self.service = GattService(bus)
        self.chars = [GattChar(bus, self.service, index, uuid, trial)
                      for index, uuid in enumerate((SSID_UUID, PASS_UUID, GO_UUID, STATUS_UUID))]

    @dbus.service.method(OBJECTS, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        result = {self.service.path: {SERVICE: self.service.properties()}}
        for char in self.chars:
            result[char.path] = {CHAR: char.properties()}
        return result


class GattService(dbus.service.Object):
    def __init__(self, bus):
        self.path = ROOT + "/service0"
        super().__init__(bus, self.path)

    def properties(self):
        return {"UUID": SERVICE_UUID, "Primary": dbus.Boolean(True)}

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.properties() if interface == SERVICE else {}


class GattChar(dbus.service.Object):
    def __init__(self, bus, service, index, uuid, trial):
        self.path = service.path + "/char" + str(index)
        self.service = service
        self.uuid = uuid
        self.trial = trial
        super().__init__(bus, self.path)

    def properties(self):
        flags = ["read"] if self.uuid == STATUS_UUID else ["encrypt-write"]
        return {"UUID": self.uuid, "Service": dbus.ObjectPath(self.service.path),
                "Flags": dbus.Array(flags, signature="s")}

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.properties() if interface == CHAR else {}

    @dbus.service.method(CHAR, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        if self.uuid != STATUS_UUID:
            raise ReadOnlyError("Write only")
        return dbus.Array(self.trial.status.encode("utf-8"), signature="y")

    @dbus.service.method(CHAR, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        if self.uuid == STATUS_UUID:
            raise ReadOnlyError("Read only")
        if int(options.get("offset", 0)) != 0 or len(value) > 64:
            raise InvalidLengthError("Use one complete UTF-8 write")
        try:
            text = bytes(value).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TrialError("UTF-8 required") from exc
        self.trial.write(self.uuid, text)


class Advertisement(dbus.service.Object):
    def __init__(self, bus):
        self.path = ROOT + "/advertisement0"
        super().__init__(bus, self.path)

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADVERT:
            return {}
        return {"Type": "peripheral", "ServiceUUIDs": dbus.Array([SERVICE_UUID], signature="s"),
                "LocalName": "FW-WIFI"}

    @dbus.service.method(ADVERT)
    def Release(self):
        pass


class Trial:
    def __init__(self, loop):
        self.loop = loop
        self.pin = f"{secrets.randbelow(1000000):06d}"
        self.ssid = None
        self.password = None
        self.status = "READY"

    def write(self, uuid, value):
        if self.status != "READY":
            raise TrialError("Trial already used")
        if uuid == SSID_UUID:
            if not value or len(value.encode("utf-8")) > 32:
                raise InvalidLengthError("SSID: 1-32 bytes")
            self.ssid = value
        elif uuid == PASS_UUID:
            if not 8 <= len(value.encode("utf-8")) <= 63:
                raise InvalidLengthError("Password: 8-63 bytes")
            self.password = value
        elif uuid == GO_UUID:
            if value != self.pin:
                raise TrialError("PIN errato")
            try:
                validate(self.ssid, self.password)
            except (ValueError, TypeError) as exc:
                raise TrialError("SSID o password mancanti/non validi") from exc
            self.status = "CONNECTING"
            threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        try:
            connect(self.ssid, self.password)
            self.status = "CONNECTED"
            print("Wi-Fi collegato. Profilo di prova creato; Ethernet invariata.", flush=True)
        except Exception:
            self.status = "FAILED"
            # No SSID/password or raw subprocess errors in the terminal.
            print("Collegamento Wi-Fi non riuscito; verifica nmcli e rete.", flush=True)
        finally:
            self.password = None


def find_adapter(bus):
    manager = dbus.Interface(bus.get_object(BLUEZ, "/"), OBJECTS)
    for path, interfaces in manager.GetManagedObjects().items():
        if "org.bluez.GattManager1" in interfaces and "org.bluez.LEAdvertisingManager1" in interfaces:
            return path
    raise RuntimeError("Adapter BLE con GATT e advertising non trovato")


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    props = dbus.Interface(bus.get_object(BLUEZ, adapter), PROPS)
    was_powered = bool(props.Get("org.bluez.Adapter1", "Powered"))
    props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    gatt = dbus.Interface(bus.get_object(BLUEZ, adapter), "org.bluez.GattManager1")
    adv_manager = dbus.Interface(bus.get_object(BLUEZ, adapter), "org.bluez.LEAdvertisingManager1")
    loop = GLib.MainLoop()
    trial = Trial(loop)
    app = Application(bus, trial)
    advert = Advertisement(bus)
    registered_app = registered_adv = False
    start_error = []
    registration_timeout = None

    def fail(error):
        start_error.append(str(error))
        loop.quit()

    def advertisement_ready():
        nonlocal registered_adv, registration_timeout
        registered_adv = True
        if registration_timeout is not None:
            GLib.source_remove(registration_timeout)
            registration_timeout = None
        print("FW-WIFI attivo per 5 minuti. PIN di prova:", trial.pin, flush=True)
        print("nRF Connect: scrivi SSID, password e poi PIN nelle tre caratteristiche.", flush=True)
        GLib.timeout_add_seconds(300, lambda: (loop.quit(), False)[1])

    def application_ready():
        nonlocal registered_app
        registered_app = True
        adv_manager.RegisterAdvertisement(
            advert.path, {}, reply_handler=advertisement_ready, error_handler=fail)

    def registration_expired():
        nonlocal registration_timeout
        registration_timeout = None
        fail("Timeout registrazione BlueZ")
        return False

    try:
        signal.signal(signal.SIGINT, lambda *_: loop.quit())
        signal.signal(signal.SIGTERM, lambda *_: loop.quit())
        registration_timeout = GLib.timeout_add_seconds(15, registration_expired)
        gatt.RegisterApplication(
            app.path, {}, reply_handler=application_ready, error_handler=fail)
        loop.run()
        if start_error:
            raise RuntimeError("Registrazione BLE non riuscita: " + start_error[0])
    finally:
        if registration_timeout is not None:
            GLib.source_remove(registration_timeout)
        if registered_adv:
            adv_manager.UnregisterAdvertisement(advert.path)
        if registered_app:
            gatt.UnregisterApplication(app.path)
        if not was_powered:
            props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(False))
        print("BLE spento. Nessun servizio persistente installato.", flush=True)


if __name__ == "__main__":
    main()
