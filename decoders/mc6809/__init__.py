##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2026, fjkraan@electrickery.nl
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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
The Motorola MC6809 is an 8-bit microprocessor.

In addition to the 8-bit data bus, this decoder requires the input signals
E, Q, RD/WR (read-not-write) to do its work. An explicit
clock signal is not required. 

Details:
https://ia803103.us.archive.org/14/items/mc6809mc6809e8bitmicroprocessorprogrammingmanualmotorolainc.1981/MC6809-MC6809E%208-Bit%20Microprocessor%20Programming%20Manual%20%28Motorola%20Inc.%29%201981.pdf
https://github.com/M6809-Docs/m6809pm
'''

from .pd import Decoder
