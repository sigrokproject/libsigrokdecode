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
1-Wire protocol decoder (link layer).

The 1-Wire protocol enables bidirectional communication over a single wire
(and ground) between a single master and one or multiple slaves. The protocol
is layered:

 - Link layer (reset, presence detection, reading/writing bits)
 - Network layer (skip/search/match device ROM addresses)
 - Transport layer (transport data between 1-Wire master and device)

Link layer protocol details:

Sample rate:
A sufficiently high samplerate is required to properly detect all the elements
of the protocol. A lower samplerate can be used if the master does not use
overdrive communication speed. The following minimal values should be used:

 - overdrive available: 2MHz minimum, 5MHz suggested
 - overdrive not available: 400kHz minimum, 1MHz suggested

Probes:
1-Wire requires a single signal, but some master implementations might have a
separate signal used to deliver power to the bus during temperature conversion
as an example. This power signal is currently not used.

 - owr (1-Wire signal line)
 - pwr (optional, dedicated power supply pin)

Options:
1-Wire is an asynchronous protocol, so the decoder must know the samplerate.
The timing for sampling bits, presence, and reset is calculated by the decoder,
but in case the user wishes to use different values, it is possible to
configure the following timing values (number of samplerate periods):

 - overdrive              (if active the decoder will be prepared for overdrive)
 - cnt_normal_bit         (time for normal mode sample bit)
 - cnt_normal_slot        (time for normal mode data slot)
 - cnt_normal_presence    (time for normal mode sample presence)
 - cnt_normal_reset       (time for normal mode reset)
 - cnt_overdrive_bit      (time for overdrive mode sample bit)
 - cnt_overdrive_slot     (time for overdrive mode data slot)
 - cnt_overdrive_presence (time for overdrive mode sample presence)
 - cnt_overdrive_reset    (time for overdrive mode reset)

These options should be configured only on very rare cases and the user should
read the decoder source code to understand them correctly.

Protocol output format:
TODO.

Annotations:

Link layer annotations show the following events:

 - NOTE/WARNING/ERROR
   Possible samplerate related timing issues are reported.
 - Reset/presence true/false
   The event is marked from the signal negative edge to the end of the reset
   high period. It's also reported if there are any devices attached to the bus.
 - Bit 0/1
   The event is marked from the signal negative edge to the end of the data
   slot. The value of each received bit is also provided.

TODO:
- Check for protocol correctness, if events are timed inside prescribed limits.
- Maybe add support for interrupts, check if this feature is deprecated.
'''

from .onewire_link import *

