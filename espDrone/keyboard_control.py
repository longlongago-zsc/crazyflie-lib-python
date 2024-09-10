"""
This script contains a keyboard controller using the MotionCommander.

Info on API element used:
https://github.com/bitcraze/crazyflie-lib-python/blob/master/cflib/positioning/motion_commander.py
"""
import logging
from pynput import keyboard

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander

URI = "udp://192.168.43.42"  # ENSURE THIS MATCHES YOUR CRAZYFLIE CONFIGURATION

__author__ = 'HighGreat'
__all__ = ['keyboard_control']

# Only output errors from the logging framework
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s.%(module)s.%(funcName)s.%(lineno)d: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class KeyboardDrone:

    def __init__(self, mc):
        self.mc = mc

        self.velocity = 0.75 + 0.1
        self.ang_velocity = 120

        self.sleeptime = 0.5
        # self.max_hight = 0.8
        # self.hight = 0.0
        print('Press u for taking off!')

    def on_press(self, key):

        if key == keyboard.Key.space:
            logger.debug('start_up')
            self.mc.start_up(self.velocity)
        elif key.char == 'w':
            self.mc.start_forward(self.velocity)

        elif key.char == 'f':
            self.mc.move_distance(0.0, 0.0, 1.0, 0.5 / 1)
            logger.debug('up 0.5m')

        elif key.char == 'u':
            self.mc.take_off(0.5)

        elif key.char == 's':
            self.mc.start_back(self.velocity)

        elif key.char == 'a':
            self.mc.start_left(self.velocity)

        elif key.char == 'd':
            self.mc.start_right(self.velocity)

        elif key.char == 'c':
            self.mc.start_down(self.velocity)

        elif key.char == 'l':
            print('Kill engines')
            return False

        elif key.char == 'q':
            self.mc.start_turn_left(self.ang_velocity)

        elif key.char == 'e':
            self.mc.start_turn_right(self.ang_velocity)

    def on_release(self, key):
        self.mc.stop()


if __name__ == '__main__':

    cflib.crtp.init_drivers(enable_debug_driver=False)

    with SyncCrazyflie(URI,cf=Crazyflie(rw_cache='./cache')) as scf:
        # We take off when the commander is created
        mc = MotionCommander(scf)

        drone = KeyboardDrone(mc)

        with keyboard.Listener(on_press=drone.on_press, on_release=drone.on_release) as listener:
            listener.join()
