# DALI Light

This is a **light** platform that will setup your DALI lights and buses. The platform relies on [python-dali](https://github.com/sde1000/python-dali) and has only been tested with the [hasseb DALI master](http://hasseb.fi/shop2/index.php?route=product/product&product_id=50) (therefore no configuration available for other controllers). The platform will discover all your DALI lights and create entities for each ballast and bus.

A DALI Light is represented as a classic dimmable light entity. A DALI bus is also represented as a dimmable light entity whose address is the broadcast address. The state of a bus is computed based on the states of its lights: if all of its lights have the same state, the bus will show that state. If any lights differ, or any are unavailable, the bus will be off.

## Example configuration
```yaml
- platform: dali
  max_buses: 4
  drivers:
    - name: Living Room
      max_gears: 4
```

- `max_buses`: maximum number of DALI buses (or DALI drivers) you expect to have. Default is 4 (as the Raspberry Pi 4 has 4 USB ports). This is used in unique ID calculations, so DALI entity names may be switched around if you change this after the first run. If that happens, just go into the "Entities" section in the UI and rename everything.
- `drivers`: list of DALI drivers (or DALI masters - I've seen both terms in use. I'm referring to the Hasseb device linked above) you'd like to use. The entries under this section will be read sequentially and applied to the USB devices in enumeration order, which, as long as you do not switch which USB port they are connected to, should be consistent even between host reboots. Again, if anything happens, just rename the entities.
    - `name`: friendly name for this bus. The bus entity will have this as its friendly name, and `<friendly name with underscores>_bus` as its entity ID. Lights hanging from this bus will have `<friendly name with underscores>_<short address>` as their entity IDs.
    - `max_gears`: maximum number of lights hanging from this bus. Be careful with this parameter, as the setup iterates through short addresses in the range [0, `max_gears`) to discover ballasts. If you have two buses with one ballast each, but one of them has short address 0 and the other has short address 1, and you've configured `max_gears` to be 1 in both cases, it will never find the ballast with short address 1 despite being technically correct. This will hopefully be fixed in upcoming releases. 

## Dependencies

[pyhidapi](https://github.com/awelkie/pyhidapi), which is a dependency of this integration, relies on the [hidapi](https://github.com/libusb/hidapi/) library. On a venv installation, you may build it or install it through your preferred package manager.

On a HASS OS installation, I found that the quickest way to get it to work was to install the library through `apk` (`apk add hidapi`). This installs it in `/usr/lib`, which isn't persistent between container restarts, so it has to be moved to a directory that is (e.g. `/config/deps/`).

You will then have to fork pyhidapi and modify the `__load_hidapi` function to indicate the correct library path, and edit `manifest.conf` to replace awelkie's repo with your own. [If you choose `/config/deps/`, you can use my fork.](https://github.com/rousveiga/pyhidapi)

## dali2mqtt

[Here](https://github.com/dgomes/dali2mqtt) you can find dgomes' dali2mqtt daemon, for use if you'd rather have Home Assistant installed in a platform that cannot be connected to a DALI master.