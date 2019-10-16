
The part of colorlaunch which runs on the "pi" or some other computer attached to the light array.
It connects to a remote server via mosquitto and listens for colorsend events, and drives annimations on the light array accordingly

Usage:

    ./ColorLaunch.py

Configuration is loaded from a file located in the same directory (`config.json`) or a path specified with the `COLORLAUNCH_CONFIG` environment variable.
