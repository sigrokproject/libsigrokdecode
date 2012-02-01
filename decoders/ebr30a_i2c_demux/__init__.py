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
TrekStor EBR30-a I2C demux protocol decoder.

Takes an I2C stream as input and outputs 3 different I2C streams, for the
3 different I2C devices on the TrekStor EBR30-a eBook reader (which are all
physically connected to the same SCL/SDA lines).

I2C slave addresses:

 - AXP199 battery management chip: 0x69/0x68 (8bit R/W), 0x34 (7bit)
 - H8563S RTC chip: 0xa3/0xa2 (8bit R/W), 0x51 (7bit)
 - Unknown accelerometer chip: 0x2b/0x2a (8bit R/W), 0x15 (7bit)
'''

from .ebr30a_i2c_demux import *

