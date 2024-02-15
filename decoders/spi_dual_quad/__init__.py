##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2023 Marc Font Freixa <mfont@bz17.dev>
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
The SPI Dual/Quad (Serial Peripheral Interface) protocol decoder supports synchronous
SPI(-like) protocols with a clock line, a SIO0, SIO1, SIO2, SIO3 lines for data
transfer in two directions, and an optional CS# pin.

If CS# is supplied, data is only decoded when CS# is asserted (clock
transitions where CS# is not asserted are ignored). If CS# is not supplied,
data is decoded on every clock transition (depending on SPI mode).
'''

from .pd import Decoder
