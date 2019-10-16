#!/usr/bin/env python3

import json
import paho.mqtt.client as mqtt
import time
import logging as log
import array
import os

log.basicConfig(level=log.DEBUG,
                format='%(levelname)-8s %(module)s.%(funcName)s() +%(lineno)s: %(message)s'
                )

def read_config():

    config_path = 'config.json'
    if 'COLORLAUNCH_CONFIG' in os.environ:
        config_path = os.environ['COLORLAUNCH_CONFIG']

    # TODO exceptions instead of exit side-effect
    if not os.path.isfile(config_path):
        log.error("Failed to find configuration file '%s'", config_path)
        exit(1)

    with open(config_path) as config_file:
        try:
            config = json.load(config_file)
        except json.decoder.JSONDecodeError as err:
            log.error("Invalid json in configuration file '%s': %s", config_path, err)
            exit(1)

    log.info("Loaded configuration from '%s'", config_path)
    return config


class MQTTAdapter:
    def __init__(self, address, port):
        self.address = address
        self.port = port

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.enable_logger()

        self._msg_handler    = None

    def _on_connect(self, client, userdata, flags, rc):
        self.client.subscribe("/spectrum/colors")


    def _on_message(self, client, userdata, msg):

        try:
            if (msg.topic == "/spectrum/colors"):
                
                try:
                    payload = json.loads(msg.payload)
                except json.decoder.JSONDecodeError as err:
                    log.error("invalid json in mqtt message %s" % err)
                    return

                if self._msg_handler:
                    self._msg_handler(payload)
                else:
                    log.warning("no handler defined, message ignored")

                # missing_keys = [key for key in ['end', 'color'] if key not in payload]
                # if any(missing_keys):
                #     log.error("mqtt message missing required key(s) %s" % missing_keys)
                #     return


                # elif (payload['type'] == 'colorcollide'):
                #     if self._handle_color_collide:
                #         self._handle_color_collide(payload['position'], payload['color1'], payload['color2'])


                # else:
                #     log.warning("unknown message type")

            else:
                log.info("ignored message from topic '%s'" % msg.topic)

        except:
            import traceback
            traceback.print_exc()


    def connect(self):
        log.debug("connecting to {} {}".format(self.address, self.port))
        self.client.connect(self.address, self.port, keepalive=60)
        self.client.loop_forever()


    def set_handler(self, func):
        self._msg_handler = func


class DMXAdapter:
    def __init__(self):
        from ola.ClientWrapper import ClientWrapper
        self.wrapper = ClientWrapper()

    def _sent_callback(self, status):
        if (not status.Succeeded()):
            log.error("Failed to send DMX: %s" % status.message)
        self.wrapper.Stop()

    def send(self, data):
        self.wrapper.Client().SendDmx(0, data, self._sent_callback)
        self.wrapper.Run()


class Animator:
    def __init__(self):
        self.array = array.array('B')

    def pulse(self, color1, color2, color3, send):
        import time
        import math

        def _pulse(distance, radius):
            if distance >= radius:
                return 0
            value = math.cos((math.pi*distance)/radius)+1
            return value

        from Color import Vector
        nc = Vector(
            color1[0],
            color1[1],
            color1[2],
        )
        sc = Vector(
            color2[0],
            color2[1],
            color2[2],
        )
        new_color = Vector(
            color3[0],
            color3[1],
            color3[2],
        )

        tick = 0
        np = 128
        sp = 0
        done = False
        collision_position = 64

        while True:
            lightstate = array.array('B')

            if (np <= sp):
                for i in range(128):
                    distance = int(abs(i-collision_position))
                    pixel_color = new_color * _pulse(distance, tick)
                    print(distance, tick, pixel_color)
                    lightstate.extend((int(min(pixel_color[0], 255)), int(min(pixel_color[1], 255)), int(min(pixel_color[2], 255)), 0))

                if tick >= 128:
                    lightstate = array.array('B')
                    for i in range(128):
                        lightstate.extend((0,0,0,0))
                    send(lightstate)
                    return

            else:
                for i in range(128):
                    if i == np:
                        lightstate.extend((color1[0], color1[1], color1[2], 0))
                    elif i == sp:
                        lightstate.extend((color2[0], color2[1], color2[2], 0))
                    else:
                        lightstate.extend((0,0,0,0))

                if (np-1 <= sp+1):
                    tick = 0

            send(lightstate)
            np -= 1
            sp += 1
            tick += 1
            time.sleep(.01)




    # def collide(self, position, color1, color2):
    #     log.debug("collision %s" % (position, color1, color2))

class Controller:
    def __init__(self):
        self.config = read_config()

        from urllib.parse import urlparse

        url = urlparse(self.config['MQTT_BROKER_URL'])
        self.input_adapter = MQTTAdapter(url.hostname, url.port)
        self.output_adapter = DMXAdapter()
        self.animator = Animator()

        self.input_adapter.set_handler(self.handle_message)

    def handle_message(self, msg):
        color1 = msg['colorValues'][0]
        color2 = msg['colorValues'][1]
        color3 = msg['colorValues'][2]
        data = self.animator.pulse(color1, color2, color3, self.output_adapter.send)
        # self.output_adapter.send(data)

    def start(self):
        self.input_adapter.connect()


class ColorLaunchController(Controller):
    def __init__(self):
        super().__init__()

    # def handle_message(self, msg):
    #     print("handling message", msg)


if __name__ == '__main__':
    clc = ColorLaunchController()
    clc.start()
