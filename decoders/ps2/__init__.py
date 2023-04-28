##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Daniel Schulte <trilader@schroedingers-bit.net>
## Copyright (C) 2023 Marshal Horn <kamocat@gmail.com>
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
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

'''
This protocol decoder can decode PS/2 device -> host communication \
and host -> device communication.

To interpret the data, please stack the appropriate keyboard or mouse \
decoder
'''

from .pd import Decoder
