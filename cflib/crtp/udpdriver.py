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


class UdpDriver(CRTPDriver):

    def __init__(self):
        self.debug = False
        self.link_error_callback = None
        self.link_quality_callback = None
        self.needs_resending = True
        None

    def connect(self, uri, linkQualityCallback, linkErrorCallback):
        # check if the URI is a radio URI
        if not re.search('^udp://', uri):
            raise WrongUriType('Not an UDP URI')

        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.addr = ('192.168.43.42', 2390) #The destination IP and port
        self.socket.bind(('', 2399))
        self.socket.connect(self.addr)
        str1=b'\xFF\x01\x01\x01'
        # Add this to the server clients list
        self.socket.sendto(str1,self.addr)
        if self.debug:
            print("Connected to UDP server")
            print("send: {}".format(binascii.hexlify(bytearray(str1))))

    def receive_packet(self, time=0):
        try:
            data, addr = self.socket.recvfrom(1024)
        except OSError:
            if self.debug:
                print("Socket error: socket might be closed.")
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
            if cksum != cksum_recv:
                if self.debug:
                    print("Checksum error {} != {}".format(cksum, cksum_recv))
                return None

            pk = CRTPPacket(data[0], list(data[1:]))
            # print the raw date
            if self.debug:
                print("recv: {}".format(binascii.hexlify(bytearray(data))))
            return pk
        else:
            return None

    def send_packet(self, pk):
        raw = (pk.header,) + pk.datat
        cksum = 0
        for i in raw:
            cksum += i
        cksum %= 256
        raw = raw + (cksum,)
        # change the tuple to bytes
        raw = bytearray(raw)
        self.socket.sendto(raw, self.addr)
        # print the raw date
        if self.debug:
            print("send: {}".format(binascii.hexlify(raw)))

    def close(self):
        str1=b'\xFF\x01\x01\x01'
        # Remove this from the server clients list
        self.socket.sendto(str1, self.addr)
        if self.debug:
            print("Disconnected from UDP server")
            print("send: {}".format(binascii.hexlify(bytearray(str1))))
        time.sleep(1)
        self.socket.close()

    def get_name(self):
        return 'udp'

    def scan_interface(self, address):
        address1 = 'udp://192.168.43.42'
        return [[address1,""]]
