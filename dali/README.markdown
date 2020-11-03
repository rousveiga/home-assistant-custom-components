# DALI Light

This is a **light** platform that will setup your DALI lights. The platform relies on [python-dali](https://github.com/sde1000/python-dali) and has only been tested with the [hasseb DALI master](http://hasseb.fi/shop2/index.php?route=product/product&product_id=50) (therefore no configuration available for other controllers). The platform will discover all your DALI lights and create entities for each ballast. For a faster discovery, declare `max_gears` with the total number of DALI lights in your setup.

## Example configuration
```yaml
- platform: dali
  name: Living Room
  max_gears: 4
```

## Dependencies

[pyhidapi](https://github.com/awelkie/pyhidapi), which is a dependency of this integration, relies on the [hidapi](https://github.com/libusb/hidapi/) library. On a venv installation, you may build it or install it through your preferred package manager.

On a HASS OS installation, I found that the quickest way to get it to work was to install the library through `apk` (`apk add hidapi`). This installs it in `/usr/lib`, which isn't persistent between container restarts, so it has to be moved to a directory that is (e.g. `/config/deps/`).

You will then have to fork pyhidapi and modify the `__load_hidapi` function to indicate the correct library path, and edit `manifest.conf` to replace awelkie's repo with your own. [If you choose `/config/deps/`, you can use my fork.](https://github.com/rousveiga/pyhidapi)

## dali2mqtt

[Here](https://github.com/dgomes/dali2mqtt) you can find dgomes' dali2mqtt daemon, for use if you'd rather have Home Assistant installed in a platform that cannot be connected to a DALI master.