##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2025 Jorge Marques <jorge.marques@analog.com>
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
I3C (Improved Inter-Integrated Circuit) is a bidirectional, multi-master
bus using two signals (SCL = serial clock line, SDA = serial data line).
Supports higher data rates through push-pull drive, adds In-Band Interrupts
(IBI), Dynamic Address Assignment (DAA), and is is backward compatible with I²C.
'''

from .pd import Decoder
