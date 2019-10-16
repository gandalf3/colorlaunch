
The part of colorlaunch which runs on the pi (or some computer) attached to the light array.
It connects to a remote server via mosquitto and listens for colorsend events, and drives animations on the light array accordingly

It depends on [OLA](https://www.openlighting.org/) for handling lights via DMX. The `ola` python module needs to be installed and the OLA daemon (`olad`) needs to be configured and running before `ColorLaunch.py` is executed.

For mosquitto it uses the `paho-mqtt` library, [available on pypi](https://pypi.org/project/paho-mqtt/).

Usage:

    ./ColorLaunch.py

Configuration is loaded from a file located in the same directory (`config.json`) or a path specified with the `COLORLAUNCH_CONFIG` environment variable.
