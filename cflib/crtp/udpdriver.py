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
import time
from socket import *

from .crtpdriver import CRTPDriver
from .crtpstack import CRTPPacket
from .exceptions import WrongUriType

__author__ = 'Bitcraze AB'
__all__ = ['UdpDriver']

import logging

# 1、创建一个logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 2、创建一个handler，用于写入日志文件
# fh = logging.FileHandler(__name__ + '_Debug.log')
# fh.setLevel(logging.DEBUG)

# 再创建一个handler，用于输出到控制台
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# 3、定义handler的输出格式（formatter）
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')

# 4、给handler添加formatter
# fh.setFormatter(formatter)
ch.setFormatter(formatter)

# 5、给logger添加handler
# logger.addHandler(fh)
logger.addHandler(ch)


class UdpDriver(CRTPDriver):

    def __init__(self):
        self.debug = True
        self.link_error_callback = None
        self.link_quality_callback = None
        self.needs_resending = True
        self.link_keep_alive = 0  # keep alive when no input device
        None

    def connect(self, uri, linkQualityCallback, linkErrorCallback):
        # check if the URI is a radio URI
        if not re.search('^udp://', uri):
            raise WrongUriType('Not an UDP URI')

        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.addr = ('192.168.43.42', 2390)  #  The destination IP and port
        self.socket.bind(('', 2399))
        self.socket.connect(self.addr)
        str1 = b'\xFF\x01\x01\x01'
        # Add this to the server clients list
        self.socket.sendto(str1, self.addr)
        if self.debug:
            logger.debug("Connected to UDP server")
            logger.debug("send: {}".format(binascii.hexlify(bytearray(str1))))

    def receive_packet(self, time=0):
        try:
            data, addr = self.socket.recvfrom(1024)
        except OSError:
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
            if self.debug:
                #raw = bytearray(data)
                #logger.debug("recv: {}".format(binascii.hexlify(bytearray(raw))))
                pass
            if cksum != cksum_recv:
                if self.debug:
                    logger.debug("Checksum error {} != {}".format(cksum, cksum_recv))
                return None

            pk = CRTPPacket(data[0], list(data[1:]))

            self.link_keep_alive += 1
            if self.link_keep_alive > 10:
                str1 = b'\xFF\x01\x01\x01'
                try:
                    self.socket.sendto(str1, self.addr)
                except OSError:
                    logger.warning("Socket error")
                self.link_keep_alive = 0

            # print the raw date
            if self.debug:
                # logger.debug("recv: {}".format(binascii.hexlify(bytearray(data))))
                pass
            return pk
        else:
            return None

    def send_packet(self, pk):
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
        # logger.debug("send: {}".format(binascii.hexlify(raw)))
        try:
            self.socket.sendto(raw, self.addr)
        except OSError:
            logger.warning("Socket error")
        self.link_keep_alive = 0
        # print the raw date
        if self.debug:
            # logger.debug("send: {}".format(binascii.hexlify(raw)))
            pass

    def close(self):
        str1 = b'\xFF\x01\x01\x01'
        # Remove this from the server clients list
        try:
            self.socket.sendto(str1, self.addr)
        except OSError:
            logger.warning("Socket error")
        if self.debug:
            logger.debug("Disconnected from UDP server")
            logger.debug("send: {}".format(binascii.hexlify(bytearray(str1))))
        time.sleep(1)
        self.socket.close()

    def get_name(self):
        return 'udp'

    def scan_interface(self, address):
        address1 = 'udp://192.168.43.42'
        return [[address1, ""]]
