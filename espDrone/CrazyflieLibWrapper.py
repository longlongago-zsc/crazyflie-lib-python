import logging
import time
from enum import Enum

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
import os.path
import datetime

send_queue = queue.Queue()
recv_queue = queue.Queue()
is_quit = False

__author__ = 'HighGreat'
__all__ = ['CrazyflieLibWrapper']

# 1、创建一个logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 2、创建一个handler，用于写入日志文件
if not os.path.isdir('../logs') and not os.path.exists('../logs'):
    os.makedirs('../logs')
fh = logging.FileHandler('../logs/mechConsole_espDrone_' + datetime.datetime.now().strftime('%Y%m%d') + '_00000.log',
                         mode='a')
fh.setLevel(logging.DEBUG)

# 再创建一个handler，用于输出到控制台
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# 3、定义handler的输出格式（formatter）
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')

# 4、给handler添加formatter
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# 5、给logger添加handler
logger.addHandler(fh)
logger.addHandler(ch)


class UIState:
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    SCANNING = 3


class CmdEnum:
    UNKNOWN = 0
    CONNECT = 1
    DISCONNECT = 2
    QUIT = 3
    ESTIMATE = 4
    MOTORS = 5
    BATTERY = 6
    BAROMETER = 7
    MAGNETOMETER = 8
    ACC = 9


class ConnectionState:
    NO_CONNECT = 0  # 没有建立连接
    CONNECT_SUCCESS = 1  # 连接成功
    SOCKET_BLOCK = 2  # 连接过程中阻塞或长时间没有收到传感器数据，上位机需要自动重连
    CONNECT_ERROR = 3  # 小飞机已关机或没有连接wifi
    MANU_DISCONNECT = 4  # 上位机主动断开


CmdDict = {
    CmdEnum.UNKNOWN: 'Unknown',
    CmdEnum.DISCONNECT: 'disconnect',
    CmdEnum.CONNECT: 'connect',
    CmdEnum.ESTIMATE: 'estimate',
    CmdEnum.MOTORS: 'motor',
    CmdEnum.BATTERY: 'battery',
    CmdEnum.QUIT: 'quit'
}


class BatteryStates:
    BATTERY, CHARGING, CHARGED, LOW_POWER = list(range(4))


class CrazyflieLibWrapper:
    LOG_NAME_THRUST = 'stabilizer.thrust'
    LOG_NAME_MOTOR_1 = 'motor.m1'
    LOG_NAME_MOTOR_2 = 'motor.m2'
    LOG_NAME_MOTOR_3 = 'motor.m3'
    LOG_NAME_MOTOR_4 = 'motor.m4'
    LOG_NAME_CAN_FLY = 'sys.canfly'

    # barometer
    LOG_NAME_ASL = 'baro.asl'
    LOG_NAME_PRESSURE = 'baro.pressure'
    LOG_NAME_TEMP = 'baro.temp'

    # magnetometer
    LOG_NAME_MAG_X = 'mag.x'
    LOG_NAME_MAG_Y = 'mag.y'
    LOG_NAME_MAG_Z = 'mag.z'

    #acc
    LOG_NAME_ACC_X = 'acc.x'
    LOG_NAME_ACC_Y = 'acc.y'
    LOG_NAME_ACC_Z = 'acc.z'

    LINK_URL = "udp://192.168.43.42"

    def __init__(self):
        self.link_url = "udp://192.168.43.42"
        self.uiState = UIState.SCANNING
        self.connectState = ConnectionState.NO_CONNECT

        logger.debug("config path: %s", espDrone.config_path)
        self.cf = Crazyflie(ro_cache=None,
                            rw_cache=espDrone.config_path + "/cache")

        cflib.crtp.init_drivers()

        # Connect some callbacks from the Crazyflie API
        self.cf.connected.add_callback(self._connected)
        self.cf.fully_connected.add_callback(self._fully_connected)
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
                'cmd': CmdEnum.ESTIMATE,
                'data': [self.estimateX, self.estimateY, self.estimateZ,
                         self.estimateRoll, self.estimatePitch, self.estimateYaw],
                'status': 0
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
                      data[self.LOG_NAME_MOTOR_3], data[self.LOG_NAME_MOTOR_4],
                      data[self.LOG_NAME_THRUST], data[self.LOG_NAME_CAN_FLY]]
            msg = {'cmd': CmdEnum.MOTORS, 'data': motors, 'status': 0}
            send_queue.put(msg)

            '''self.estimateThrust.setText(
                "%.2f%%" % self.thrustToPercentage(data[self.LOG_NAME_THRUST]))'''

            '''if data[self.LOG_NAME_CAN_FLY] != self._can_fly_deprecated:
                self._can_fly_deprecated = data[self.LOG_NAME_CAN_FLY]
                self._update_flight_commander(True)'''

    def _connected(self, url):
        self.uiState = UIState.CONNECTED
        self.connectState = ConnectionState.CONNECT_SUCCESS

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

    def _acc_data_receviced(self, timestamp, data, logconf):
        global send_queue
        msg = {'cmd': CmdEnum.ACC,
               'data': [data[self.LOG_NAME_ACC_X], data[self.LOG_NAME_ACC_Y], data[self.LOG_NAME_ACC_Z]], 'status': 0}
        send_queue.put(msg)

    def _magnetometer_data_receviced(self, timestamp, data, logconf):
        global send_queue
        msg = {'cmd': CmdEnum.MAGNETOMETER,
               'data': [data[self.LOG_NAME_MAG_X], data[self.LOG_NAME_MAG_Y], data[self.LOG_NAME_MAG_Z]], 'status': 0}
        send_queue.put(msg)

    def _barometer_data_receviced(self, timestamp, data, logconf):
        global send_queue
        msg = {'cmd': CmdEnum.BAROMETER,
               'data': [data[self.LOG_NAME_ASL], data[self.LOG_NAME_PRESSURE], data[self.LOG_NAME_TEMP]], 'status': 0}
        send_queue.put(msg)

    def _update_battery(self, timestamp, data, logconf):
        global send_queue
        msg = {'cmd': CmdEnum.BATTERY, 'data': [data["pm.vbat"], data["pm.state"]], 'status': 0}
        send_queue.put(msg)

        # logger.debug('_update_battery:%d', (int(data["pm.vbat"] * 1000)))
        # self.batteryBar.setValue(int(data["pm.vbat"] * 1000))

        '''
        color = 'COLOR_BLUE'
        # TODO firmware reports fully-charged state as 'Battery',
        # rather than 'Charged'
        if data["pm.state"] in [BatteryStates.CHARGING, BatteryStates.CHARGED]:
            color = 'COLOR_GREEN'
        elif data["pm.state"] == BatteryStates.LOW_POWER:
            color = 'COLOR_RED'
        '''

        # self.batteryBar.setStyleSheet(UiUtils.progressbar_stylesheet(color))
        # logger.debug(("_update_battery:%.3f, color:%s" % (data["pm.vbat"], color)))

    def _disconnected(self, link_uri):
        self.uiState = UIState.DISCONNECTED
        global send_queue
        msg = {'cmd': CmdEnum.CONNECT, 'data': [self.uiState], 'status': self.connectState}
        send_queue.put(msg)

    def _connection_initiated(self, url):
        self.uiState = UIState.CONNECTING
        self.connectState = ConnectionState.NO_CONNECT
        logger.debug("_connection_initiated")

    def _connect(self):
        if self.uiState == UIState.DISCONNECTED or self.uiState == UIState.SCANNING:
            self.connectState = ConnectionState.NO_CONNECT
            self.cf.open_link(self.link_url)

    def _fully_connected(self, link_uri):
        global send_queue
        """This callback is called when the Crazyflie has been connected and all parameters have been
                downloaded. It is now OK to set and get parameters."""
        self.uiState = UIState.CONNECTED
        self.connectState = ConnectionState.CONNECT_SUCCESS

        msg = {'cmd': CmdEnum.CONNECT, 'data': [UIState.CONNECTED], 'status': self.connectState}
        send_queue.put(msg)
        logger.debug(f'Parameters downloaded to {link_uri}')

        # MOTOR & THRUST
        lg = LogConfig("Motors", 90)
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
        except Exception as e:
            logger.warning(str(e))

        # barometer
        lg = LogConfig("Barometer", 100)
        lg.add_variable(self.LOG_NAME_ASL, "float")
        lg.add_variable(self.LOG_NAME_PRESSURE, "float")
        lg.add_variable(self.LOG_NAME_TEMP, "float")
        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._barometer_data_receviced)
            lg.error_cb.add_callback(self._logging_error)
            lg.start()
        except Exception as e:
            logger.warning(str(e))

        # barometer
        lg = LogConfig("Magnetometer", 110)
        lg.add_variable(self.LOG_NAME_MAG_X, "float")
        lg.add_variable(self.LOG_NAME_MAG_Y, "float")
        lg.add_variable(self.LOG_NAME_MAG_Z, "float")
        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._magnetometer_data_receviced)
            lg.error_cb.add_callback(self._logging_error)
            lg.start()
        except Exception as e:
            logger.warning(str(e))

        # acc sensor
        lg = LogConfig("AccSensor", 120)
        lg.add_variable(self.LOG_NAME_ACC_X, "float")
        lg.add_variable(self.LOG_NAME_ACC_Y, "float")
        lg.add_variable(self.LOG_NAME_ACC_Z, "float")
        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._acc_data_receviced)
            lg.error_cb.add_callback(self._logging_error)
            lg.start()
        except Exception as e:
            logger.warning(str(e))

    def _connection_lost(self, linkURI, errMsg):
        self.uiState = UIState.DISCONNECTED
        self.connectState = ConnectionState.CONNECT_ERROR
        global send_queue
        msg = {'cmd': CmdEnum.CONNECT, 'data': [UIState.DISCONNECTED], 'status': self.connectState}
        send_queue.put(msg)
        logger.debug(f"_connection_lost{errMsg}")

    def _connection_failed(self, linkURI, errMsg):
        self.uiState = UIState.DISCONNECTED
        self.connectState = ConnectionState.CONNECT_ERROR
        global send_queue
        msg = {'cmd': CmdEnum.CONNECT, 'data': [UIState.DISCONNECTED], 'status': self.connectState}
        send_queue.put(msg)
        logger.debug(f"_connection_failed:{error}")

    def connect(self):
        global send_queue
        if self.uiState == UIState.CONNECTED or self.uiState == UIState.CONNECTING:
            msg = {'cmd': CmdEnum.CONNECT, 'data': [self.uiState], 'status': self.connectState}
            send_queue.put(msg)
        else:
            self._connect()
            logger.debug(("connect url:%s" % self.link_url))

    def disconnect(self):
        self.uiState = UIState.DISCONNECTED
        self.cf.close_link()
        logger.debug(("disconnect url:%s" % self.link_url))

    def set_param(self, name, value):
        global send_queue
        try:
            self.cf.param.set_value(name, value)
        except Exception as e:
            msg = {'cmd': CmdEnum.UNKNOWN, 'data': value, 'status': 1}
            send_queue.put(msg)
            logger.error('set_param error:{0}'.format(e))


def udpSendhandle(udp_socket, crazyflie, pc_address):
    global send_queue
    global is_quit
    msg = None
    while not is_quit:
        try:
            msg = send_queue.get(block=True, timeout=10)
        except BaseException as e:
            msg = None
            if crazyflie.uiState == UIState.CONNECTED or crazyflie.uiState == UIState.CONNECTING:
                logger.debug('disconnect:{0}'.format(e))
                crazyflie.connectState = ConnectionState.SOCKET_BLOCK
                crazyflie.disconnect()

        if msg:
            # if msg['cmd'] == CmdEnum.DISCONNECT or msg['cmd'] == CmdEnum.CONNECT:
            #    logger.debug('send msg:{0}'.format(msg))
            json_data = json.dumps(msg)
            bytes_data = json_data.encode('utf-8')
            try:
                udp_socket.sendto(bytes_data, pc_address)
            except BaseException as e:
                logger.debug('udpSendhandle Socket error: socket might be closed. because:{0}'.format(e))


def udpReceivehandle(udp_socket, crazyflie):
    global recv_queue
    global send_queue
    global is_quit

    while not is_quit:
        try:
            data, addr = udp_socket.recvfrom(1024)
        except OSError:
            logger.debug("udpReceivehandle Socket error: socket might be closed.")
            continue

        cmd = CmdEnum.UNKNOWN

        try:
            if data:
                strs = ''
                # logger.debug(type(data))
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
                cmd = jsonObj.get('cmd', CmdEnum.UNKNOWN)
        except Exception:
            logger.debug("recv data to json error")
            continue

        # logger.debug('recv cmd: %d<--->%s' % (cmd, CmdDict.get(cmd, 'UNKNOWN')))

        if cmd == CmdEnum.QUIT:
            crazyflie.connectState = ConnectionState.MANU_DISCONNECT
            crazyflie.disconnect()
            msg = {'cmd': CmdEnum.QUIT, 'data': [0], 'status': 0}
            send_queue.put(msg)
            time.sleep(0.01)
            is_quit = True
            send_queue.put(msg)
        elif cmd == CmdEnum.DISCONNECT:
            crazyflie.connectState = ConnectionState.MANU_DISCONNECT
            crazyflie.disconnect()
        elif cmd == CmdEnum.CONNECT:
            try:
                crazyflie.connect()
            except Exception:
                crazyflie.connectState = ConnectionState.CONNECT_ERROR
                msg = {'cmd': CmdEnum.CONNECT, 'data': [UIState.DISCONNECTED], 'status': crazyflie.connectState}
                send_queue.put(msg)
        else:
            msg = {'cmd': CmdEnum.UNKNOWN, 'data': [0], 'status': 1}
            send_queue.put(msg)

    Config().save_file()
    crazyflie.disconnect()


if __name__ == "__main__":

    logger.debug('-' * 20 + "begin" + '-' * 20)

    udp_address = ('127.0.0.1', 59494)
    pc_address = ('127.0.0.1', 59191)
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
