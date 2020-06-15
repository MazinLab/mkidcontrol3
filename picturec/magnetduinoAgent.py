"""
Author: Noah Swimmer 15 June 2020

Program to control ArduinoUNO that will measure the current through the ADR magnet by monitoring the
current-sensing resistor on the PIPER-designed HichCurrent Boost board (see picturec reference folder
for circuit drawing). Will log values to redis, will also act as a safeguard to tell the magnet current
control that the current is operating out of normal bounds.

TODO:
"""

import serial
from serial import SerialException
import sys
import time
import logging
from logging import getLogger
from datetime import datetime
from redis import RedisError
from redis import Redis
from redistimeseries.client import Client

CURRENTDUINO_VERSION = "0.1"
REDIS_DB = 0
QUERY_INTERVAL = 1

KEYS = ['device-settings:currentduino:highcurrentboard', 'device-settings:currentduino:heatswitch',
        'status:magnet:current', 'status:heatswitch', 'status:highcurrentboard:powered',
        'status:highcurrentboard:current']
STATUS_KEY = "status:device:currentduino:status"
FIRMWARE_KEY = "status:device:currentduino:firmware"

class Currentduino(object):
    def __init__(self, port, baudrate=115200, timeout=0.1):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connect(raise_errors=False)

    def connect(self, reconnect=False, raise_errors=True):
        if reconnect:
            self.disconnect()

        try:
            if self.ser.isOpen():
                return
        except Exception:
            pass

        getLogger(__name__).debug(f"Connecting to {self.port} at {self.baudrate}")
        try:
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)
            time.sleep(.2)
            getLogger(__name__).debug(f"port {self.port} connection established")
            return True
        except (SerialException, IOError) as e:
            self.ser = None
            getLogger(__name__).error(f"Connecting to port {self.port} failed: {e}", exc_info=True)
            if raise_errors:
                raise e
            else:
                return False

    def disconnect(self):
        try:
            self.ser.close()
            self.ser = None
        except Exception as e:
            getLogger(__name__).info(f"Exception durring disconnect: {e}")


def setup_redis(host='localhost', port=6379, db=0):
    redis = Redis(host=host, port=port, db=db)
    return redis


def setup_redis_ts(host='localhost', port=6379, db=0):
    redis_ts = Client(host=host, port=port, db=db)

    # Add the necessary timestream keys here!
    return redis_ts


def store_status(redis, status):
    redis.set(STATUS_KEY, status)


def store_firmware(redis):
    redis.set(FIRMWARE_KEY, CURRENTDUINO_VERSION)


if __name__ == "__main__":

    logging.basicConfig()
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    currentduino = Currentduino(port='/dev/curremtduino', baudrate=115200)
    currentduino.connect()
