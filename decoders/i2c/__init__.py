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
I2C protocol decoder.

The Inter-Integrated Circuit (I2C) bus is a bidirectional, multi-master
bus using two signals (SCL = serial clock line, SDA = serial data line).

There can be many devices on the same bus. Each device can potentially be
master or slave (and that can change during runtime). Both slave and master
can potentially play the transmitter or receiver role (this can also
change at runtime).

Possible maximum data rates:
 - Standard mode: 100 kbit/s
 - Fast mode: 400 kbit/s
 - Fast-mode Plus: 1 Mbit/s
 - High-speed mode: 3.4 Mbit/s

START condition (S): SDA = falling, SCL = high
Repeated START condition (Sr): same as S
Data bit sampling: SCL = rising
STOP condition (P): SDA = rising, SCL = high

All data bytes on SDA are exactly 8 bits long (transmitted MSB-first).
Each byte has to be followed by a 9th ACK/NACK bit. If that bit is low,
that indicates an ACK, if it's high that indicates a NACK.

After the first START condition, a master sends the device address of the
slave it wants to talk to. Slave addresses are 7 bits long (MSB-first).
After those 7 bits, a data direction bit is sent. If the bit is low that
indicates a WRITE operation, if it's high that indicates a READ operation.

Later an optional 10bit slave addressing scheme was added.

Documentation:
http://www.nxp.com/acrobat/literature/9398/39340011.pdf (v2.1 spec)
http://www.nxp.com/acrobat/usermanuals/UM10204_3.pdf (v3 spec)
http://en.wikipedia.org/wiki/I2C

Protocol output format:

I2C packet:
[<i2c_command>, <data>, <ack_bit>]

<i2c_command> is one of:
  - 'START' (START condition)
  - 'START REPEAT' (Repeated START)
  - 'ADDRESS READ' (Address, read)
  - 'ADDRESS WRITE' (Address, write)
  - 'DATA READ' (Data, read)
  - 'DATA WRITE' (Data, write)
  - 'STOP' (STOP condition)

<data> is the data or address byte associated with the 'ADDRESS*' and 'DATA*'
command. For 'START', 'START REPEAT' and 'STOP', this is None.

<ack_bit> is either 'ACK' or 'NACK', but may also be None.
'''

from .i2c import *

