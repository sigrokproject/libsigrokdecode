##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2026 BrLumen <igflocal@gmail.com>
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
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

'''
This decoder stacks on top of the 'uart' PD and decodes the command
interface of the Texas Instruments (formerly National Semiconductor)
LMX9838 "SimplyBlue" Bluetooth serial port module, as described in
AN-1699 "LMX9838 Software User's Guide" (SNOA498B).

Every packet in either direction is framed as:

  STX (0x02), packet type, opcode, data length (16 bit LE), checksum,
  <data>, ETX (0x03)

where the checksum is the low byte of the sum of packet type, opcode and
data length. Packet types are request (0x52 'R'), confirm (0x43 'C'),
indication (0x69 'i') and response (0x72 'r'). Every request is answered
by exactly one confirm with the same opcode.

The decoder annotates the frame bytes, the decoded data fields of the
most common commands, the whole packet, and pairs each request with its
confirm on a separate 'Transactions' row (including the response time).
Indications and responses are shown on the 'Events' row.

The module's UART speed is configurable (2400 to 921600 baud, factory
default 9600 baud, 8N1); set the 'uart' baudrate option accordingly.
Data exchanged in transparent mode is not decoded.
'''

from .pd import Decoder
