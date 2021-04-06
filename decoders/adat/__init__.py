##
## This file is part of the libsigrokdecode project.
##
## Copyright (C)  2020 Hans Baier <hansfbaier@gmail.com>
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
This is a decoder for the ADAT lightpipe protocol.
The ADAT lightpipe protocol is used to connect professional
digital audio equipment.

Those are, for example: Multi-channel AD- and
DA-converters, audio interfaces, digital mixers, recorders.
'''

from .pd import Decoder
