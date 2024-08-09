##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Theo Hussey <husseytg@gmail.com>
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
The Spacewire decoder supports decoding of Spacewire control characters,
control codes, and data characters.

SpaceWire has taken into consideration two existing standards, IEEE 1355-1995
and ANSI/TIA/EIA-644. SpaceWire is specifically provided for use onboard a
spacecraft.

See ECSS-E-50-12A for a complete description of the Spacewire protocol.
'''

from .pd import Decoder
