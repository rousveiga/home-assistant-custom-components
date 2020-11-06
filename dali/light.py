"""
Support for DALI lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.dali/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ID, CONF_DEVICES)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, LightEntity, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-dali']

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

SUPPORT_DALI = SUPPORT_BRIGHTNESS

CONF_MAX_GEARS = "max_gears"
CONF_DRIVERS = "drivers"
CONF_MAX_BUSES = "max_buses"

MAX_RANGE = 64
MAX_BUSES = 4

DRIVER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MAX_GEARS, default=MAX_RANGE): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAX_BUSES, default=MAX_BUSES): cv.positive_int,
    vol.Required(CONF_DRIVERS, default=[]): vol.All(cv.ensure_list, [DRIVER_SCHEMA]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the DALI Light platform."""

    from dali.address import Short
    from dali.command import YesNoResponse, Response
    import dali.gear.general as gear
    import dali.driver.hasseb as hasseb_driver
    from dali.driver.hasseb import SyncHassebDALIUSBDriver 
    import threading

    dali_drivers = hasseb_driver.SyncHassebDALIUSBDriverFactory() 

    for idx, dali_driver in enumerate(dali_drivers):
        _LOGGER.debug("Found DALI driver")
        lock = threading.RLock()

        driver_config = config[CONF_DRIVERS][idx]

        lamps = []
        for lamp in range(0, driver_config[CONF_MAX_GEARS]):
            try:
                _LOGGER.debug("Searching for Gear on address <{}>".format(lamp))
                r = dali_driver.send(gear.QueryControlGearPresent(Short(lamp)))

                if isinstance(r, YesNoResponse) and r.value:
                    _LOGGER.debug("Found lamp")
                    lamps.append(Short(lamp))

            except Exception as e:
                #Not present
                _LOGGER.error("Error while QueryControlGearPresent: {}".format(e))
                _LOGGER.error("Hasseb DALI master not found")
                break

        add_devices([DALILight(dali_driver, lock, driver_config[CONF_NAME], l, idx) for l in lamps])
        add_devices([DALIBus(dali_driver, lock, driver_config[CONF_NAME], lamps, config[CONF_MAX_BUSES], idx)])

class DALILight(LightEntity):
    """Representation of an DALI Light."""

    def __init__(self, driver, driver_lock, controller_name, ballast, bus_index):
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        """Initialize a DALI Light."""
        self._brightness = 0
        self._state = False
        self._name = "{}_{}".format(controller_name, ballast.address)
        self.attributes = {"short_address": ballast.address}
        
        self.driver = driver
        self.driver_lock = driver_lock
        self.addr = ballast

        self._unique_id = (MAX_RANGE * bus_index) + self.addr.address

        try:
            with self.driver_lock:
                cmd = QueryActualLevel(self.addr)
                r = self.driver.send(cmd)
                if r.value != None and r.value < 255:
                    self._brightness = r.value
                    if r.value > 0:
                        r.state = True

        except ResponseError as e:
            _LOGGER.error("Response error on __init__")
        except MissingResponse as e:
            self._brightness = None
            self._state = None

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """The unique ID is calculated based on its bus index and its short address,
        so that conflicts don't arise from having lamps with the same short address in
        different buses. """
        return self._unique_id

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_DALI

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        from dali.gear.general import DAPC
 
        with self.driver_lock:
            try:
                self._brightness = kwargs.get(ATTR_BRIGHTNESS, 254)
                _LOGGER.debug("turn on {}".format(self._brightness))
                cmd = DAPC(self.addr, 254 if self._brightness==255 else self._brightness)
                r = self.driver.send(cmd)
                if self._brightness > 0:
                    self._state = True
            except usb.core.USBError as e:
                _LOGGER.error("Can't turn_on {}: {}".format(self._name, e))
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        from dali.gear.general import Off 

        with self.driver_lock:
            try:
                cmd = Off(self.addr)
                r = self.driver.send(cmd)
                self._state = False 
            except usb.core.USBError as e:
                _LOGGER.error("Can't turn_on {}: {}".format(self._name, e))
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """Doesn't make much sense to poll, commands have acks"""
        return True

    def update(self):
        """Fetch update state."""
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        import usb

        with self.driver_lock:
            try:
                r = self.driver.send(QueryActualLevel(self.addr))
                _LOGGER.debug("DALI Light update: new brightness is {}".format(r))
                if r:
                    self._brightness = r.value
                    if 0 < int(self._brightness) < 255:
                        self._state = True
                    else:
                        self._state = False
                else:
                    _LOGGER.error("return value = {}", r)
            except usb.core.USBError as e:
                _LOGGER.error("Can't update {}: {}".format(self._name, e))
            except ResponseError as e:
                _LOGGER.error("ResponseError QueryActualLevel")
            except MissingResponse as e:
                self._brightness = None

class DALIBus(LightEntity):
    """Representation of a DALI bus."""

    def __init__(self, driver, driver_lock, controller_name, ballasts, max_buses, bus_index):
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        from dali.address import Broadcast

        """Initialize a DALI Light."""
        self._brightness = 0
        self._state = False
        self._name = "{} bus".format(controller_name)

        self.lamp_addresses = ballasts
        self.attributes = {"short_addresses": [ballast.address for ballast in ballasts] }

        self.driver = driver
        self.driver_lock = driver_lock
        self.addr = Broadcast()

        self._unique_id = max_buses * MAX_RANGE + bus_index

        self.calculate_bus_state()

    def calculate_bus_state(self):
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        import usb

        try:
            with self.driver_lock:
                last_brightness = None

                for lamp_address in self.lamp_addresses:
                    # query brightness
                    result = self.driver.send(QueryActualLevel(lamp_address))
                    _LOGGER.debug("DALI Bus update: lamp {} brightness is {}".format(lamp_address.address, result.value))

                    # check if brightness is valid value
                    if result.value != None and int(result.value) < 255 and (last_brightness == None or last_brightness == int(result.value)):
                        last_brightness = int(result.value) # save brightness and keep checking

                    else:
                        _LOGGER.debug("Lamp {} returned invalid or different value; bus status is not unified")
                        last_brightness = None #if brightness differs, the bus has no unified status
                        break

            _LOGGER.debug("DALI Bus update: new brightness is {}".format(last_brightness))

            self._brightness = last_brightness
            if self._brightness == None:
                self._state = None
            elif self._brightness > 0:
                self._state = True
            else:
                self._state = False

        except usb.core.USBError as e:
            _LOGGER.error("USB Error {}: {}".format(self._name, e))
            self._brightness = None
            self._state = None
        except ResponseError as e:
            _LOGGER.error("Response Error in QueryActualLevel: {}: {}".format(self._name, e))
            self._brightness = None
            self._state = None
        except MissingResponse as e:
            _LOGGER.error("Missing response: {}: {}".format(self._name, e))
            self._brightness = None
            self._state = None

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """The unique ID for a bus has to be outside the range of possible lamp 
        unique IDs. As lamp IDs span in the ranges 0..63 for bus 0, 64..127 for bus
        1, and so on, bus IDs begin *after* the last possible lamp ID, indicated by
        64 * max_buses."""
        return self._unique_id

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_DALI

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        from dali.gear.general import DAPC
 
        with self.driver_lock:
            try:
                self._brightness = kwargs.get(ATTR_BRIGHTNESS, 254)
                _LOGGER.debug("turn on {}".format(self._brightness))
                cmd = DAPC(self.addr, 254 if self._brightness==255 else self._brightness)
                r = self.driver.send(cmd)
                if self._brightness > 0:
                    self._state = True
            except usb.core.USBError as e:
                _LOGGER.error("Can't turn_on {}: {}".format(self._name, e))
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        from dali.gear.general import Off 

        with self.driver_lock:
            try:
                cmd = Off(self.addr)
                r = self.driver.send(cmd)
                self._state = False 
            except usb.core.USBError as e:
                _LOGGER.error("Can't turn_on {}: {}".format(self._name, e))
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """Doesn't make much sense to poll, commands have acks"""
        return True

    def update(self):
        """Fetch update state."""
        self.calculate_bus_state()
