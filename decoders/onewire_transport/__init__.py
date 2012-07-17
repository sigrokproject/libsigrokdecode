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
1-Wire protocol decoder.

The 1-Wire protocol enables bidirectional communication over a single wire (and
ground) between a single master and one or multiple slaves. The protocol is
layered.
- Link layer (reset, presence detection, reading/writing bits)
- Network layer (skip/search/match device ROM addresses)
- Transport layer (transfer data between 1-Wire master and device)

Transport layer

The transport layer is the largest and most complex part of the protocol, since
it is very device specific. The decoder is parsing only a small part of the
protocol.

Annotations:
The next link layer annotations are shown:
- RESET/PRESENCE True/False
  The event is marked from the signal negative edge to the end of the reset
  high period. It is also reported if there are any devices attached to the
  bus.
The next network layer annotations are shown:
- ROM val
  The 64bit value of the addressed device is displayed:
  family code (1B) + serial number (6B) + CRC (1B)
- FUNCTION COMMAND val name
  The requested FUNCTION command is displayed as an 8bit HEX value and by name.
- DATA val
  Data intended for the transport layer is displayed as an 8bit HEX value.

TODO:
- add CRC checks for transport layer
'''

from .onewire_transport import *
