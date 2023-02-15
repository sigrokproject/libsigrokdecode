##
## This file is part of the libsigrokdecode project.
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
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

'''
The SPI (Serial Peripheral Interface) protocol decoder supports synchronous
SPI(-like) protocols with a clock line, a MISO and MOSI line for data
transfer in two directions, and an optional CS# pin.

Either MISO or MOSI (but not both) can be optional.

If CS# is supplied, data is only decoded when CS# is asserted (clock
transitions where CS# is not asserted are ignored). If CS# is not supplied,
data is decoded on every clock transition (depending on SPI mode).

The SPI CLK phase is handled differently in Default Speed mode vs High Speed mode.
The SPI Phase is always Phase 0 (sample on rising).
In Default speed mode, the MISO behaviour is: Sample on rising, Change on falling
In High Speed mode (>25MHz), the SD MISO phase behaviour changes to:
(Sample on rising, Change 14ns after rising). At low clock rates this looks like
Phase 1 (sample on falling, change on rising) but it isn't.
This decoder may struggle to decode data received between changing the SD card mode
(CMD6) and actually changing the frequency if the sample rate is insufficiently high.
'''

from .pd import Decoder
