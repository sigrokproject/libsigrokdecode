##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Nie Guangze <guangze.nie@outlook.com>
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
SENT (Single Edge Nibble Transmission) is used for 
high resoluiton communication from a sensor to ECU.

This decoder is based on SENT standard of SAE J2716-2016.
'''

from .pd import Decoder
