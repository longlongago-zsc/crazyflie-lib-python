#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2011-2013 Bitcraze AB
#
#  Crazyflie Nano Quadcopter Client
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA  02110-1301, USA.
""" CRTP UDP Driver. Work either with the UDP server or with an UDP device
See udpserver.py for the protocol"""

import re
import binascii
import threading
import time
from socket import *
import traceback
import os.path

import queue

keep_live_queue = queue.Queue()
is_connected = False

from .crtpdriver import CRTPDriver
from .crtpstack import CRTPPacket
from .exceptions import WrongUriType
from cflib.utils.callbacks import Caller

__author__ = 'Bitcraze AB'
__all__ = ['UdpDriver']

import logging
import datetime

# 1、创建一个logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 2、创建一个handler，用于写入日志文件
try:
    if not os.path.isdir('../logs') and not os.path.exists('../logs'):
        os.makedirs('../logs')
    fh = logging.FileHandler(
        '../logs/mechConsole_espDrone_' + datetime.datetime.now().strftime('%Y%m%d') + '_00000.log',
        mode='a')
    fh.setLevel(logging.WARNING)
    # 3、定义handler的输出格式（formatter）
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')

    # 4、给handler添加formatter
    fh.setFormatter(formatter)
    logger.addHandler(fh)
except:
    pass

# 再创建一个handler，用于输出到控制台
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# 3、定义handler的输出格式（formatter）
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')
# 4、给handler添加formatter
ch.setFormatter(formatter)
# 5、给logger添加handler
logger.addHandler(ch)


def _send_packet(send_socket, addr):
    global keep_live_queue
    global is_connected
    while is_connected:
        try:
            msg = keep_live_queue.get(timeout=0.1)
        except queue.Empty:
            msg = b'\xFF\x01\x01\x01'
        # logger.debug("send: {}".format(binascii.hexlify(raw)))
        try:
            send_socket.sendto(msg, addr)
        except OSError:
            logger.warning("_send_packet: Socket error")


class UdpDriver(CRTPDriver):

    def __init__(self):
        super().__init__()
        self._thread = None
        self.addr = None
        self.socket = None
        self.debug = False
        self.link_error_callback = Caller()
        self.link_quality_callback = Caller()
        self.needs_resending = True

    def connect(self, uri, linkQualityCallback, linkErrorCallback):
        global is_connected
        # check if the URI is a radio URI
        if not re.search('^udp://', uri):
            raise WrongUriType('Not an UDP URI')

        self.link_error_callback = linkErrorCallback
        self.link_quality_callback = linkQualityCallback
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.addr = (uri.split('udp://')[1], 2390)  # The destination IP and port '192.168.43.42'
        self.socket.bind(('', 2399))
        self.socket.connect(self.addr)
        is_connected = True
        self._thread = threading.Thread(target=_send_packet, args=(self.socket, self.addr))
        self._thread.start()
        if self.debug:
            logger.debug("Connected to UDP server")

    def receive_packet(self, time=0):
        global is_connected
        try:
            data, addr = self.socket.recvfrom(1024)
        except BaseException as e:
            is_connected = False
            try:
                self.link_error_callback(
                    'Error communicating with the Crazyflie. Socket error: socket might be closed.')
            except BaseException:
                pass
            if self.debug:
                logger.debug("Socket error: socket might be closed.")
            return None

        if data:
            # take the final byte as the checksum
            cksum_recv = data[len(data) - 1]
            # remove the checksum from the data
            data = data[0:(len(data) - 1)]
            # calculate checksum and check it with the last byte
            cksum = 0
            for i in data[0:]:
                cksum += i
            cksum %= 256
            # if self.debug:
            # raw = bytearray(data)
            # logger.debug("recv: {}".format(binascii.hexlify(bytearray(raw))))
            # pass
            if cksum != cksum_recv:
                if self.debug:
                    logger.debug("Checksum error {} != {}".format(cksum, cksum_recv))
                return None

            pk = CRTPPacket(data[0], list(data[1:]))

            # print the raw date
            #if self.debug:
            # logger.debug("recv: {}".format(binascii.hexlify(bytearray(data))))
            #    pass
            return pk
        else:
            return None

    def send_packet(self, pk):
        global keep_live_queue
        raw = (pk.header,) + pk.datat
        # logger.debug("send: {}".format(binascii.hexlify(bytearray(raw))))
        cksum = 0
        for i in raw:
            cksum += i
        cksum %= 256
        # print('cksum={}'.format(cksum))
        raw = raw + (cksum,)
        # change the tuple to bytes
        raw = bytearray(raw)
        # self.socket.sendto(raw, self.addr)
        keep_live_queue.put_nowait(raw)

    def close(self):
        global is_connected
        #  global keep_live_queue
        #  msg = b'\xFF\x01\x02\x02'
        #  keep_live_queue.put_nowait(msg)
        is_connected = False
        # Remove this from the server clients list
        self._thread.join(1)
        self.socket.close()

    def get_name(self):
        return 'udp'

    def scan_interface(self, address):
        address1 = 'udp://192.168.43.42'
        return [[address1, ""]]
