#!/usr/bin/env python3

import json
import time
import math
import threading
import array
import queue
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
    def __init__(self, config):
        super().__init__()
        self.name = "spectrum"
        self.version = (0, 1, 0)
        self.devmode = True
        self.animator = SpringAnimator(config)
        # self.led_adapter = None

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

        self.animator.pulse(color1, color2, color3)


class Animator:
    def __init__(self, config):
        self._light_count = config['LIGHT_COUNT']
        self._light_format = config['LIGHT_FORMAT']
        # TODO use DMX constants and configuration
        self.lightstate = array.array('B', [0] * 512)
        self.lock = threading.Lock()

    def step(self, dt):
        raise NotImplementedError

    def clampf(self, value, _min=0.0, _max=1.0):
        return max(min(value, _max), _min)

    def clampb(self, value, _min=0, _max=255):
        return max(min(int(value), _max), _min)

class PulseAnimator(Animator):
    def __init__(self, config):
        super().__init__(config)

    def idle():
        pass

    def step(self, dt):


    def pulse(self, color1, color2, color3):
        pass


class SpringAnimator(Animator):
    def __init__(self, config):
        super().__init__(config)
        self.springs = array.array('f', [0.0] * self._light_count)
        self.velocities = array.array('f', [0.0] * self._light_count)
        self.spring_mass = 10
        # self.springs[0] = 1
        # self.springs[self._light_count-1] = 1
        self.springs[int((self._light_count-1)/2)] = 10
        self.speed = 60

    def idle():
        pass

    def step(self, dt):
        k = .8

        for i, x in enumerate(self.springs):
            # a very naive spring physics simulation
            force = k*(1/3)*(-x) + \
                    k*(1/3)*(self.springs[max(i-1, 0)]-x) + \
                    k*(1/3)*(self.springs[min(i+1, self._light_count-1)]-x)

            self.velocities[i] += force/self.spring_mass
            self.velocities[i] *= .9
            self.springs[i] += self.velocities[i]*dt*self.speed

            # self.springs[i] = self.clampf(self.springs[i], -1, 1)

        with self.lock:
            print(self.springs[50])
            for i in range(self._light_count):
                val = self.clampb(((self.springs[i]))*255)
                self.lightstate[4*i] = val
                self.lightstate[(4*i)+1] = val 
                self.lightstate[(4*i)+2] = val 

    def pulse(self, color1, color2, color3):
        self.springs[0] = 1.0
        self.springs[self._light_count-1] = 1.0


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


class LightAdapter:
    def __init__(self):
        self.animator = None

    def send(self, data):
        raise NotImplementedError

    def set_animator(self, animator):
        self.animator = animator

class DMXAdapter(LightAdapter):
    def __init__(self):
        pass

    def start(self):
        from ola.ClientWrapper import ClientWrapper
        from ola.DMXConstants import DMX_MIN_SLOT_VALUE, DMX_MAX_SLOT_VALUE, DMX_UNIVERSE_SIZE
        self._universe = 0
        self._wrapper = ClientWrapper()
        self._client = self._wrapper.Client()

        self.run()


    # TODO We could use OLA's internal event scheduling system, but currently
    # I'm not aware of any obvious reason to do so. Nevertheless it bears
    # further investigation.

    def _sent_callback(self, status):
        if (not status.Succeeded()):
            # TODO catch this and report it in our heartbeat
            log.error("Failed to send DMX: %s" % status.message)
        # Always stop, as we call ourselves from a loop
        self._wrapper.Stop()

    def send(self, data):
        self._client.SendDmx(0, data, self._sent_callback)
        self._wrapper.Run()

    def run(self):
        dt_start = time.time_ns()

        # awkwardly wait around while we waight for an animator to be assigned
        while not self.animator:
            time.sleep(1)

        while True:
            dt = time.time_ns() - dt_start
            dt_start = time.time_ns()

            self.animator.step(dt/(10**9))

            with self.animator.lock:
                self.send(self.animator.lightstate)

            # TODO use configuration
            time.sleep(1/60)


class Controller:
    def __init__(self):
        self.config = read_config()

        from urllib.parse import urlparse
        url = urlparse(self.config['MQTT_BROKER_URL'])

        self.game = ColorLaunch(self.config)
        self.command_adapter = MQTTAdapter(url.hostname, url.port, heartbeat_interval=self.config['HEARTBEAT_SECONDS'])
        self.led_adapter = DMXAdapter()

        # self.game.set_led_adapter(self.led_adapter)
        self.command_adapter.register_handlers(
            self.game.get_topic_handlers()
        )
        self.led_adapter.set_animator(self.game.animator)


    def start(self):
        # self.command_adapter.connect()
        # self.command_thread = threading.Thread(target=self.command_adapter.run)
        self.led_thread = threading.Thread(target=self.led_adapter.start)
        self.led_thread.start()
        # self.led_thread.join()


if __name__ == '__main__':
    cont = Controller()
    cont.start()
