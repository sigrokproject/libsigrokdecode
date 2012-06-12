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
Serial Peripheral Interface protocol decoder.

Details:
TODO

Protocol output format:

SPI packet:
[<cmd>, <data1>, <data2>]

Commands:
 - 'DATA': <data1> contains the MISO data, <data2> contains the MOSI data.
   The data is _usually_ 8 bits (but can also be fewer or more bits).
   Both data items are Python numbers, not strings.
 - 'CS CHANGE': <data1> is the old CS# pin value, <data2> is the new value.
   Both data items are Python numbers (0/1), not strings.

Examples:
 ['CS-CHANGE', 1, 0]
 ['DATA', 0xff, 0x3a]
 ['DATA', 0x65, 0x00]
 ['CS-CHANGE', 0, 1]

'''

from .spi import *

