import logging

import cflib.crtp
import espDrone
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
#  from cflib.crazyflie.mem import MemoryElement
from espDrone.pose_logger import PoseLogger
from espDrone.pluginhelper import PluginHelper
from espDrone.config import Config
from espDrone.logconfigreader import LogConfigReader

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

    def __init__(self):

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

        # Add things to helper so tabs can access it
        PluginHelper.cf = self.cf
        PluginHelper.pose_logger = PoseLogger(self.cf)
        PluginHelper.pose_logger.data_received_cb.add_callback(self._pose_data_received)

        self.estimateX = 0.0
        self.estimateY = 0.0
        self.estimateZ = 0.0
        self.estimateRoll = 0.0
        self.estimatePitch = 0.0
        self.estimateYaw = 0.0

        self.link_url = "udp://192.168.43.42"


    def _pose_data_received(self, pose_logger, pose):
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

            logger.debug('x={0:.2f}, y={1:.2f}, z={2:.2f}, roll={3:.2f}, pitch={4:.2f}, yaw={5:.2f}'
                         .format(self.estimateX, self.estimateY,  self.estimateZ,
                                 self.estimateRoll, self.estimatePitch,  self.estimateYaw))

            #  self.ai.setBaro(estimated_z, self.is_visible())
            #  self.ai.setRollPitch(-roll, pitch, self.is_visible())

    def _connected(self, url):
        self.uiState = UIState.CONNECTED

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

    def _update_battery(self, timestamp, data, logconf):
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
        logger.debug(("_update_battery:%.3f, color:%s" % (data["pm.vbat"], color)))

    def _disconnected(self, link_uri):
        self.uiState = UIState.DISCONNECTED

    def _connection_initiated(self, url):
        self.uiState = UIState.CONNECTING

    def connect(self):
        self._connect()
        logger.debug(("connect url:%s" % self.link_url))

    def disconnect(self):
        Config().save_file()
        self.cf.close_link()
        logger.debug(("disconnect url:%s" % self.link_url))

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

    def _connection_failed(self, linkURI, error):
        self.uiState = UIState.DISCONNECTED

    def _logging_error(self, log_conf, msg):
        logger.debug("_logging_error")


def main():
    crazyflie = CrazyflieLibWrapper()

    while True:
        try:
            if crazyflie.uiState == UIState.DISCONNECTED:
                crazyflie.connect()
            if crazyflie.uiState == UIState.CONNECTED:
                continue
            elif crazyflie.uiState == UIState.CONNECTING:
                continue
            else:
                pass
        except Exception as e:
            logger.error(e)
            break

    if crazyflie.uiState == UIState.DISCONNECTED or crazyflie.uiState == UIState.CONNECTING:
        crazyflie.disconnect()


if __name__ == "__main__":
    main()
