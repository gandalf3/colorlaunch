#!/usr/bin/env python3

import json
import time
import math
import array
import os
import logging as log
import paho.mqtt.client as mqtt
from colorutil import Color

log.basicConfig(level=log.DEBUG,
                format='%(levelname)-8s %(module)s.%(funcName)s() +%(lineno)s: %(message)s'
                )


def read_config():

    config_path = 'config.json'
    if 'COLORLAUNCH_CONFIG' in os.environ:
        config_path = os.environ['COLORLAUNCH_CONFIG']

    if not os.path.isfile(config_path):
        log.error("Failed to find configuration file '%s'", config_path)
        exit(1)

    with open(config_path) as config_file:
        try:
            config = json.load(config_file)
        except json.decoder.JSONDecodeError as err:
            log.error("Invalid json in configuration file '%s': %s", config_path, err)
            exit(1)

    log.debug("Reading configuration from '%s'", config_path)
    return config


class Game:
    def __init__(self):
        self.version = None
        self.name = None

    def get_topic_handlers(self):
        raise NotImplementedError

    def set_led_adapter(self):
        raise NotImplementedError

class TopicHandler():
    def __init__(self, topic, func):
        self.topic = topic
        self.func = func
        self.except_handler = func

    def __repr__(self):
        return "TopicHandler('{}')".format(self.topic)

    def __call__(self, *args, exception_handler=None):
        try:
            self.func(*args)
        except:
            if exception_handler:
                exception_handler()

            raise

class ColorLaunch(Game):
    def __init__(self):
        super().__init__()
        self.name = "spectrum"
        self.version = (0, 1, 0)
        self.devmode = True
        self.animator = PulseAnimator()
        self.led_adapter = None

    def get_game_topic(self):
        topic = "{}-{}.{}.{}".format(self.name, *self.version)
        if (self.devmode):
            topic += '-dev'

        return topic

    def get_topic_handlers(self):
        return [
            TopicHandler(self.get_game_topic() + '/colors', self.handle_color)
        ]

    def set_led_adapter(self, led_adapter):
        self.led_adapter = led_adapter

    def handle_color(self, msg):
        color1 = msg['north_color']
        color2 = msg['south_color']
        color3 = msg['result_color']

        # TODO break led adapter out of animator
        # data = self.animator.pulse(color1, color2, color3)

        if self.led_adapter:
            self.animator.pulse(color1, color2, color3, self.led_adapter.send)


# class SimpleAnimator(Animator):

class PulseAnimator:
    def __init__(self):
        self.array = array.array('B')

    def idle():
        pass

    def pulse(self, color1, color2, color3, send):

        def _pulse(distance, radius):
            if distance >= radius:
                return 0
            value = math.cos((math.pi*distance)/radius)+1
            return value

        nc = Color(
            color1[0],
            color1[1],
            color1[2],
        )
        sc = Color(
            color2[0],
            color2[1],
            color2[2],
        )
        new_color = Color(
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


class MQTTAdapter:
    def __init__(self, address, port, heartbeat_interval=15):
        self.address = address
        self.port = port
        self.heartbeat_interval = heartbeat_interval

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        #self.client.enable_logger()

        self._topic_handlers    = {}

        self._is_fine = True
            

    # takes a list of TopicHandler objects, which wrap 
    def register_handlers(self, topic_handler_list):
        log.debug("registering topic handlers: %s", topic_handler_list)

        for handler in topic_handler_list:
            self._topic_handlers[handler.topic] = handler

    def _on_connect(self, client, userdata, flags, rc):
        for topic in self._topic_handlers.keys():
            self.client.subscribe(topic)


    def _on_message(self, client, userdata, msg):

        if msg.topic not in self._topic_handlers.keys():
            log.warning("ignored message for unknown topic '%s'" % msg.topic)
            return

        try:
            payload = json.loads(msg.payload)
        except json.decoder.JSONDecodeError as err:
            log.warning("invalid json in mqtt message on topic '%s': %s", msg.topic, err)
            return

        def set_exception_flag():
            self._is_fine = False
            log.exception("Encountered an unhandled exception in handler for topic '%s', payload was: '%s'", msg.topic, payload)

        self._topic_handlers[msg.topic](payload, exception_handler=set_exception_flag)


    def connect(self):
        log.debug("connecting to {} {}".format(self.address, self.port))
        self.client.connect(self.address, self.port, keepalive=60)

    def run(self):
        self.client.loop_start()
        while True:
            self.heartbeat()
            time.sleep(self.heartbeat_interval)


    def heartbeat(self):
        heartbeat = {
            'code':       200,
            'message':    "The pi is fine",
            'timestamp':  int(time.time()*1000),
        }

        if (not self._is_fine):
            heartbeat['code'] = 500
            heartbeat['message'] = "The pi is not fine"

        log.debug("sending heartbeat %s", heartbeat);

        self.client.publish('spectrum-0.1.0-dev/heartbeat', payload=json.dumps(heartbeat), qos=0, retain=True)


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


class Controller:
    def __init__(self):
        self.config = read_config()

        from urllib.parse import urlparse

        url = urlparse(self.config['MQTT_BROKER_URL'])
        self.control_adapter = MQTTAdapter(url.hostname, url.port)
        self.led_adapter = DMXAdapter()
        self.game = ColorLaunch()

        self.control_adapter.register_handlers(
            self.game.get_topic_handlers()
        )

        self.game.set_led_adapter(self.led_adapter)

    def start(self):
        self.control_adapter.connect()
        self.control_adapter.run();



if __name__ == '__main__':
    cont = Controller()
    cont.start()
