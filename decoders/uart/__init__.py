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
UART protocol decoder.

Universal Asynchronous Receiver Transmitter (UART) is a simple serial
communication protocol which allows two devices to talk to each other.

It uses just two data signals and a ground (GND) signal:
 - RX/RXD: Receive signal
 - TX/TXD: Transmit signal

The protocol is asynchronous, i.e., there is no dedicated clock signal.
Rather, both devices have to agree on a baudrate (number of bits to be
transmitted per second) beforehand. Baudrates can be arbitrary in theory,
but usually the choice is limited by the hardware UARTs that are used.
Common values are 9600 or 115200.

The protocol allows full-duplex transmission, i.e. both devices can send
data at the same time. However, unlike SPI (which is always full-duplex,
i.e., each send operation is automatically also a receive operation), UART
allows one-way communication, too. In such a case only one signal (and GND)
is required.

The data is sent over the TX line in so-called 'frames', which consist of:
 - Exactly one start bit (always 0/low).
 - Between 5 and 9 data bits.
 - An (optional) parity bit.
 - One or more stop bit(s).

The idle state of the RX/TX line is 1/high. As the start bit is 0/low, the
receiver can continually monitor its RX line for a falling edge, in order
to detect the start bit.

Once detected, it can (due to the agreed-upon baudrate and thus the known
width/duration of one UART bit) sample the state of the RX line "in the
middle" of each (start/data/parity/stop) bit it wants to analyze.

It is configurable whether there is a parity bit in a frame, and if yes,
which type of parity is used:
 - None: No parity bit is included.
 - Odd: The number of 1 bits in the data (and parity bit itself) is odd.
 - Even: The number of 1 bits in the data (and parity bit itself) is even.
 - Mark/one: The parity bit is always 1/high (also called 'mark state').
 - Space/zero: The parity bit is always 0/low (also called 'space state').

It is also configurable how many stop bits are to be used:
 - 1 stop bit (most common case)
 - 2 stop bits
 - 1.5 stop bits (i.e., one stop bit, but 1.5 times the UART bit width)
 - 0.5 stop bits (i.e., one stop bit, but 0.5 times the UART bit width)

The bit order of the 5-9 data bits is LSB-first.

Possible special cases:
 - One or both data lines could be inverted, which also means that the idle
   state of the signal line(s) is low instead of high.
 - Only the data bits on one or both data lines (and the parity bit) could
   be inverted (but the start/stop bits remain non-inverted).
 - The bit order could be MSB-first instead of LSB-first.
 - The baudrate could change in the middle of the communication. This only
   happens in very special cases, and can only work if both devices know
   to which baudrate they are to switch, and when.
 - Theoretically, the baudrate on RX and the one on TX could also be
   different, but that's a very obscure case and probably doesn't happen
   very often in practice.

Error conditions:
 - If there is a parity bit, but it doesn't match the expected parity,
   this is called a 'parity error'.
 - If there are no stop bit(s), that's called a 'frame error'.

More information:
TODO: URLs

Protocol output format:

UART packet:
[<packet-type>, <rxtx>, <packet-data>]

This is the list of <packet-type>s and their respective <packet-data>:
 - 'STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'DATA': The data is the (integer) value of the UART data. Valid values
   range from 0 to 512 (as the data can be up to 9 bits in size).
 - 'PARITYBIT': The data is the (integer) value of the parity bit (0/1).
 - 'STOPBIT': The data is the (integer) value of the stop bit (0 or 1).
 - 'INVALID STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'INVALID STOPBIT': The data is the (integer) value of the stop bit (0/1).
 - 'PARITY ERROR': The data is a tuple with two entries. The first one is
   the expected parity value, the second is the actual parity value.
 - TODO: Frame error?

The <rxtx> field is 0 for RX packets, 1 for TX packets.
'''

from .uart import *

