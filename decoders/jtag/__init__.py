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

'''
JTAG protocol decoder.

JTAG (Joint Test Action Group), a.k.a. "IEEE 1149.1: Standard Test Access Port
and Boundary-Scan Architecture", is a protocol used for testing, debugging,
and flashing various digital ICs.

TODO: Protocol details.

Protocol output format (WORK IN PROGRESS!):

JTAG packet:
[<packet-type>, <data>]

<packet-type> is one of:
 - 'NEW STATE': <data> is the new state of the JTAG state machine.
   Valid values: 'TEST-LOGIC-RESET', 'RUN-TEST/IDLE', 'SELECT-DR-SCAN',
   'CAPTURE-DR', 'SHIFT-DR', 'EXIT1-DR', 'PAUSE-DR', 'EXIT2-DR', 'UPDATE-DR',
   'SELECT-IR-SCAN', 'CAPTURE-IR', 'SHIFT-IR', 'EXIT1-IR', 'PAUSE-IR',
   'EXIT2-IR', 'UPDATE-IR'.
 - 'IR TDI': Bitstring that was clocked into the IR register.
 - 'IR TDO': Bitstring that was clocked out of the IR register.
 - 'DR TDI': Bitstring that was clocked into the DR register.
 - 'DR TDO': Bitstring that was clocked out of the DR register.
 - ...

All bitstrings are a sequence of '1' and '0' characters. The right-most
character in the bitstring is the LSB. Example: '01110001' (1 is LSB).

Details:
https://en.wikipedia.org/wiki/Joint_Test_Action_Group
http://focus.ti.com/lit/an/ssya002c/ssya002c.pdf
'''

from .jtag import *

