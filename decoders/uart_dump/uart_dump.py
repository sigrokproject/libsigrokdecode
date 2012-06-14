##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

import sigrokdecode as srd
import os
import sys

RX = 0
TX = 1

class Decoder(srd.Decoder):
    api_version = 1
    id = 'uart_dump'
    name = 'UART dump'
    longname = 'UART dump'
    desc = 'Output decoded UART data to a file.'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = [] # TODO?
    probes = []
    optional_probes = []
    options = {
        'rx': ['Output RX data?', 'yes'],
        'tx': ['Output TX data?', 'yes'],
        'filename': ['File name for RX and TX data', '-'],
        'filename_rx': ['File name for RX data', 'none'],
        'filename_tx': ['File name for TX data', 'none'],
    }
    annotations = []

    def __init__(self, **kwargs):
        self.f = None
        self.f_rx = None
        self.f_tx = None

    def file_open(self, filename):
        if filename == 'none':
            return None
        elif filename == '-':
            return sys.stdout
        else:
            return open(filename, 'w')

    def start(self, metadata):
        # The user can specify 'filename' (gets both RX and TX data), and/or
        # 'filename_rx' (for RX data only), and/or 'filename_tx', respectively.

        # Default is to output RX and TX to 'filename', with 'filename_rx' and
        # 'filename_tx' being unused.

        # If multiple 'filename*' options are specified, the user must NOT
        # use the same file for any of them.

        # A filename of 'none' is not allowed (has special meaning). A filename
        # of '-' means 'stdout'.

        self.f = self.file_open(self.options['filename'])
        self.f_rx = self.file_open(self.options['filename_rx'])
        self.f_tx = self.file_open(self.options['filename_tx'])

    def report(self):
        pass

    def decode(self, ss, es, data):
        ptype, rxtx, pdata = data

        # Ignore all UART packets except the actual data packets (i.e., we
        # do not print start bits, parity bits, stop bits, errors, and so on).
        if ptype != 'DATA':
            return

        # TODO: Configurable format.
        c = chr(pdata)

        # TODO: Error handling.

        # Output RX and/or TX to 'filename'.
        if self.f != None:
            self.f.write(c)
            self.f.flush()

        # Output RX data to 'filename_rx'.
        if self.f_rx != None:
            if self.options['rx'] == 'yes' and rxtx == RX:
                self.f_rx.write(c)
                self.f_rx.flush()

        # Output TX data to 'filename_tx'.
        if self.f_tx != None:
            if self.options['tx'] == 'yes' and rxtx == TX:
                self.f_tx.write(c)
                self.f_tx.flush()

