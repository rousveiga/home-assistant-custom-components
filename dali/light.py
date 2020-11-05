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

MAX_RANGE = 64

DRIVER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MAX_GEARS, default=MAX_RANGE): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
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

        add_devices([DALILight(dali_driver, lock, driver_config[CONF_NAME], l) for l in lamps])

class DALILight(LightEntity):
    """Representation of an DALI Light."""

    def __init__(self, driver, driver_lock, controller_name, ballast):
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
        """Return the Short Address of this light."""
        return self.addr.address

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
        return False 

    def update(self):
        """Fetch update state."""
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        import usb

        with self.driver_lock:
            try:
                r = self.driver.send(QueryActualLevel(self.addr))
                _LOGGER.debug(r)
                if r:
                    self._brightness = r.value.as_integer
                    if 0 < self._brightness < 255:
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

    def __init__(self, driver, driver_lock, controller_name):
        from dali.gear.general import QueryActualLevel
        from dali.command import ResponseError, MissingResponse
        """Initialize a DALI Light."""
        self._brightness = 0
        self._state = False
        self._name = "{} bus".format(controller_name)

        self.driver = driver
        self.driver_lock = driver_lock
        self.addr = Short(0xFF)

        # try:
        #     with self.driver_lock:
        #         cmd = QueryActualLevel(self.addr)
        #         r = self.driver.send(cmd)
        #         if r.value != None and r.value < 255:
        #             self._brightness = r.value
        #             if r.value > 0:
        #                 r.state = True

        except ResponseError as e:
            _LOGGER.error("Response error on __init__")
        except MissingResponse as e:
            self._brightness = None
            self._state = None

    # def calculate_bus_status(self):
    #     try:
    #         with self.driver_lock:
    #             last_brightness = None

    #             for lamp in range(0, MAX_RANGE):
    #                 # query brightness
    #                 result = self.driver.send(QueryActualLevel(Short(lamp))

    #                 # check if brightness is valid value
    #                 if result.value != None and result.value < 255:

    #                     # Check if brightness is the first one or not different
    #                     if last_brightness == -1 or last_brightness == result.value:
    #                         last_brightness = result.value # save brightness and keep checking

    #                     else:
    #                         last_brightness = None #if brightness differs, the bus has no unified status
    #                         break

    #         # update self.brightness handle exceptions etc.

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """Return the Short Address of this light."""
        return self.addr.address

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
        return False 

    # def update(self):
    #     """Fetch update state."""
    #     from dali.gear.general import QueryActualLevel
    #     from dali.command import ResponseError, MissingResponse
    #     import usb

    #     with self.driver_lock:
    #         try:
    #             r = self.driver.send(QueryActualLevel(self.addr))
    #             _LOGGER.debug(r)
    #             if r:
    #                 self._brightness = r.value.as_integer
    #                 if 0 < self._brightness < 255:
    #                     self._state = True
    #                 else:
    #                     self._state = False
    #             else:
    #                 _LOGGER.error("return value = {}", r)
    #         except usb.core.USBError as e:
    #             _LOGGER.error("Can't update {}: {}".format(self._name, e))
    #         except ResponseError as e:
    #             _LOGGER.error("ResponseError QueryActualLevel")
    #         except MissingResponse as e:
    #             self._brightness = None
