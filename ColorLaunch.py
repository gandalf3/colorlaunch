#!/usr/bin/env python3

import json
import paho.mqtt.client as mqtt
import time
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

def read_config():
    config_path = 'config.json'

    with open(config_path) as config_file:
        try:
            config = json.load(config_file)
        except json.decoder.JSONDecodeError as err:
            log.error("invalid json in config: %s" % err)
            exit(1)

    return config


class MQTTAdapter:
    def __init__(self, address, port):
        self.address = address
        self.port = port

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.enable_logger()

        self._handle_color_send    = None
        self._handle_color_collide = None


    def _on_connect(self, client, userdata, flags, rc):
        self.client.subscribe("playanimation")


    def _on_message(self, client, userdata, msg):

        if (msg.topic == "playanimation"):
            
            try:
                payload = json.loads(msg.payload)
            except json.decoder.JSONDecodeError as err:
                log.error("invalid json in mqtt message %s" % err)
                return

            if (payload['type'] == 'colorsend'):

                missing_keys = [key for key in ['end', 'color'] if key not in payload]
                if any(missing_keys):
                    log.error("mqtt message missing required key(s) %s" % missing_keys)
                    return

                if self._handle_color_send:
                    self.handle_color_send()

            # elif (payload['type'] == 'colorcollide'):
            #     if self._handle_color_collide:
            #         self._handle_color_collide(payload['position'], payload['color1'], payload['color2'])


            else:
                log.warning("unknown message type")



    def connect(self):
        self.client.connect(self.address, self.port, keepalive=60)
        self.client.loop_forever()


    def set_color_send_handler(self, func):
        self._handle_color_send = func

    def set_color_collide_handler(self, func):
        self._handle_color_collide = func


class DMXAdapter:
    def __init__(self):
        pass


class Animator:
    def __init__(self):
        self.array = []

    def pulse(self, color):
        pass

    # def collide(self, position, color1, color2):
    #     log.debug("collision %s" % (position, color1, color2))



class ColorLaunchController:
    def __init__(self):
        self.config = read_config()

        from urllib.parse import urlparse

        url = urlparse(self.config['MQTT_BROKER_URL'])
        self.input_adapter = MQTTAdapter(url.hostname, url.port)
        self.output_adapter = DMXAdapter()
        self.animator = Animator()

        self.input_adapter.set_color_send_handler(self.animator.pulse)


    def start(self):
        self.input_adapter.connect()


if __name__ == '__main__':
    clc = ColorLaunchController()
    clc.start()
