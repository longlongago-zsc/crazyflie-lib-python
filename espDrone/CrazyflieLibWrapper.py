import logging
import time

import cflib.crtp
import espDrone
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.utils.callbacks import Caller
#  from cflib.crazyflie.mem import MemoryElement
from espDrone.pose_logger import PoseLogger
from espDrone.pluginhelper import PluginHelper
from espDrone.config import Config
from espDrone.logconfigreader import LogConfigReader

import threading
import queue
from socket import *
import json
send_queue = queue.Queue()
recv_queue = queue.Queue()
is_quit = False

__author__ = 'HighGreat'
__all__ = ['CrazyflieLibWrapper']

logger = logging.getLogger(__name__)


class UIState:
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    SCANNING = 3


class BatteryStates:
    BATTERY, CHARGING, CHARGED, LOW_POWER = list(range(4))


class CrazyflieLibWrapper:

    LOG_NAME_THRUST = 'stabilizer.thrust'
    LOG_NAME_MOTOR_1 = 'motor.m1'
    LOG_NAME_MOTOR_2 = 'motor.m2'
    LOG_NAME_MOTOR_3 = 'motor.m3'
    LOG_NAME_MOTOR_4 = 'motor.m4'
    LOG_NAME_CAN_FLY = 'sys.canfly'

    LINK_URL = "udp://192.168.43.42"

    def __init__(self):
        self.link_url = "udp://192.168.43.42"
        self.uiState = UIState.DISCONNECTED

        logger.debug("config path: %s", espDrone.config_path)
        self.cf = Crazyflie(ro_cache=None,
                            rw_cache=espDrone.config_path + "/cache")

        cflib.crtp.init_drivers()

        # Connection callbacks and signal wrappers for UI protection
        self.cf.connected.add_callback(self._connected)
        self.cf.disconnected.add_callback(self._disconnected)
        self.cf.connection_lost.add_callback(self._connection_lost)
        self.cf.connection_requested.add_callback(self._connection_initiated)

        # Parse the log configuration files
        self.logConfigReader = LogConfigReader(self.cf)

        self.estimateX = 0.0
        self.estimateY = 0.0
        self.estimateZ = 0.0
        self.estimateRoll = 0.0
        self.estimatePitch = 0.0
        self.estimateYaw = 0.0
        # Add things to helper so tabs can access it
        PluginHelper.cf = self.cf
        PluginHelper.pose_logger = PoseLogger(self.cf)
        PluginHelper.pose_logger.data_received_cb.add_callback(self._pose_data_received)

    def _pose_data_received(self, pose_logger, pose):
        global send_queue
        if self.uiState == UIState.CONNECTED:
            estimated_z = pose[2]
            roll = pose[3]
            pitch = pose[4]

            self.estimateX = pose[0]
            self.estimateY = pose[1]
            self.estimateZ = estimated_z
            self.estimateRoll = roll
            self.estimatePitch = pitch
            self.estimateYaw = pose[5]

            '''logger.debug('x={0:.2f}, y={1:.2f}, z={2:.2f}, roll={3:.2f}, pitch={4:.2f}, yaw={5:.2f}'
                         .format(self.estimateX, self.estimateY,  self.estimateZ,
                                 self.estimateRoll, self.estimatePitch,  self.estimateYaw))'''

            msg = {
                'cmd': 'estimate',
                'data': [self.estimateX, self.estimateY, self.estimateZ,
                        self.estimateRoll, self.estimatePitch, self.estimateYaw] ,
                'status':0
            }
            send_queue.put(msg)

            #  self.ai.setBaro(estimated_z, self.is_visible())
            #  self.ai.setRollPitch(-roll, pitch, self.is_visible())

    def _logging_error(self, log_conf, msg):
        logger.error(self, "Log error",
                          "Error when starting log config [%s]: %s" % (
                              log_conf.name, msg))

    def _log_data_received(self, timestamp, data, logconf):
        global send_queue

        if self.uiState == UIState.CONNECTED:
            motors = [data[self.LOG_NAME_MOTOR_1], data[self.LOG_NAME_MOTOR_2],
                      data[self.LOG_NAME_MOTOR_3], data[self.LOG_NAME_MOTOR_4]]
            msg = {'cmd': 'motor', 'data': motors, 'status': 0}
            send_queue.put(msg)

            msg1 = {'cmd': 'thrust', 'data': [data[self.LOG_NAME_THRUST]], 'status': 0}
            send_queue.put(msg1)

            msg2 = {'cmd': 'canfly', 'data': [data[self.LOG_NAME_CAN_FLY]], 'status': 0}
            send_queue.put(msg2)

            '''self.estimateThrust.setText(
                "%.2f%%" % self.thrustToPercentage(data[self.LOG_NAME_THRUST]))'''

            '''if data[self.LOG_NAME_CAN_FLY] != self._can_fly_deprecated:
                self._can_fly_deprecated = data[self.LOG_NAME_CAN_FLY]
                self._update_flight_commander(True)'''


    def _connected(self, url):
        self.uiState = UIState.CONNECTED

        global send_queue
        msg = {'cmd': 'connect', 'data': [self.uiState], 'status': 0}
        send_queue.put(msg)

        Config().set("link_uri", str(self.link_url))

        lg = LogConfig("Battery", 1000)
        lg.add_variable("pm.vbat", "float")
        lg.add_variable("pm.state", "int8_t")
        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._update_battery)
            lg.error_cb.add_callback(self._logging_error)
            lg.start()
        except KeyError as e:
            logger.warning(str(e))

        # MOTOR & THRUST
        lg = LogConfig("Motors", 100)
        lg.add_variable(self.LOG_NAME_THRUST, "uint16_t")
        lg.add_variable(self.LOG_NAME_MOTOR_1)
        lg.add_variable(self.LOG_NAME_MOTOR_2)
        lg.add_variable(self.LOG_NAME_MOTOR_3)
        lg.add_variable(self.LOG_NAME_MOTOR_4)
        lg.add_variable(self.LOG_NAME_CAN_FLY)

        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._log_data_received)
            lg.error_cb.add_callback(self._logging_error)
            lg.start()
        except KeyError as e:
            logger.warning(str(e))
        except AttributeError as e:
            logger.warning(str(e))

    def _update_battery(self, timestamp, data, logconf):
        global send_queue
        msg = {'cmd': 'pm', 'data': [data["pm.vbat"], data["pm.state"]], 'status': 0}
        send_queue.put(msg)

        # logger.debug('_update_battery:%d', (int(data["pm.vbat"] * 1000)))
        # self.batteryBar.setValue(int(data["pm.vbat"] * 1000))

        color = 'COLOR_BLUE'
        # TODO firmware reports fully-charged state as 'Battery',
        # rather than 'Charged'
        if data["pm.state"] in [BatteryStates.CHARGING, BatteryStates.CHARGED]:
            color = 'COLOR_GREEN'
        elif data["pm.state"] == BatteryStates.LOW_POWER:
            color = 'COLOR_RED'

        # self.batteryBar.setStyleSheet(UiUtils.progressbar_stylesheet(color))
        # logger.debug(("_update_battery:%.3f, color:%s" % (data["pm.vbat"], color)))

    def _disconnected(self, link_uri):
        self.uiState = UIState.DISCONNECTED
        global send_queue
        msg = {'cmd': 'connect', 'data': [self.uiState], 'status': 0}
        send_queue.put(msg)

    def _connection_initiated(self, url):
        self.uiState = UIState.CONNECTING
        global send_queue
        msg = {'cmd': 'connect', 'data': [self.uiState], 'status': 0}
        send_queue.put(msg)
        logger.debug("_connection_initiated")

    def _connect(self):
        if self.uiState == UIState.CONNECTED:
            self.cf.close_link()
        elif self.uiState == UIState.CONNECTING:
            self.cf.close_link()
            self.uiState = UIState.DISCONNECTED
        else:
            self.cf.open_link(self.link_url)

    def _connection_lost(self, linkURI, msg):
        self.uiState = UIState.DISCONNECTED
        global send_queue
        msg = {'cmd': 'connect', 'data': [self.uiState], 'status': 1}
        send_queue.put(msg)
        logger.debug("_connection_lost")

    def _connection_failed(self, linkURI, error):
        self.uiState = UIState.DISCONNECTED
        global send_queue
        msg = {'cmd': 'connect', 'data': [self.uiState], 'status': 1}
        send_queue.put(msg)
        logger.debug("_connection_failed")

    def connect(self):
        self._connect()
        logger.debug(("connect url:%s" % self.link_url))

    def disconnect(self):
        Config().save_file()
        self.cf.close_link()
        logger.debug(("disconnect url:%s" % self.link_url))

    def set_param(self, name, value):
        global send_queue
        try:
            self.cf.param.set_value(name, value)
        except Exception as e:
            msg = {'cmd': name, 'data': value, 'status': 1}
            send_queue.put(msg)
            logger.error('set_param error:{0}'.format(e))

def udpSendhandle(udp_socket, crazyflie, pc_address):
    global send_queue
    global is_quit
    msg = ''
    while not is_quit:
        try:
            msg = send_queue.get(timeout = 10)
        except :
            if crazyflie.uiState == UIState.CONNECTED:
                msg = {'cmd': 'estimate', 'data': [0,0,0,0,0,0], 'status': 1}
        if msg:
            logger.debug('send msg:{0}'.format(msg))
            json_data = json.dumps(msg)
            bytes_data  = json_data.encode('utf-8')
            try:
                udp_socket.sendto(bytes_data , pc_address)
            except Exception as e:
                logger.debug("udpSendhandle Socket error: socket might be closed. because:{0}".format(e))
                time.sleep(0.01)
        else:
            time.sleep(0.01)

def udpReceivehandle(udp_socket, crazyflie):
    global recv_queue
    global send_queue
    global is_quit

    while not is_quit:
        try:
            data, addr = udp_socket.recvfrom(1024)
        except OSError:
                logger.debug("udpReceivehandle Socket error: socket might be closed.")
        cmd = ''

        try:
            if data:
                strs = ''
                logger.debug(type(data))
                if isinstance(data, bytes):
                    strs = data.decode('utf-8')
                elif isinstance(data, bytearray):
                    strs = str(data, 'utf-8')
                elif isinstance(data, str):
                    strs = data
                elif isinstance(data, list) or isinstance(data, tuple):
                    strs = [str(x) for x in data]
                else:
                    pass

                jsonObj = json.loads(strs)
                logger.debug('recv data:%s' % jsonObj)
                cmd = jsonObj.get('cmd')
        except Exception:
            logger.debug("recv data to json error")

        logger.debug('recv cmd: %s' % cmd)

        if cmd:
            if (cmd == 'quit'):
                crazyflie.disconnect()
                msg = {'cmd': cmd, 'data': [0], 'status': 0}
                send_queue.put(msg)
                time.sleep(0.01)
                is_quit = True
                send_queue.put(msg)
            elif cmd == 'disconnect':
                crazyflie.disconnect()
            elif cmd == 'connect':
                try:
                    crazyflie.connect()
                except Exception:
                    msg = {'cmd': 'connect', 'data': [crazyflie.uiState], 'status': 1}
                    send_queue.put(msg)
            else:
                msg = {'cmd': 'unknown', 'data': [0], 'status': 1}
                send_queue.put(msg)
        else:
            time.sleep(0.01)

    crazyflie.disconnect()


if __name__ == "__main__":

    logger.debug('-'*20 + "begin" + '-'*20)

    udp_address = ('127.0.0.1', 9494)
    pc_address = ('127.0.0.1', 9191)
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    udp_socket.bind(udp_address)

    crazyflie = CrazyflieLibWrapper()

    t1 = threading.Thread(target=udpReceivehandle, args=(udp_socket, crazyflie))
    t2 = threading.Thread(target=udpSendhandle, args=(udp_socket, crazyflie, pc_address))

    thread_list = []
    thread_list.append(t1)
    thread_list.append(t2)

    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()

    udp_socket.close()
    crazyflie.disconnect()

    logger.debug('-' * 20 + "end" + '-' * 20)


