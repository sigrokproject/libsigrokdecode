##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021 Karl Palsson <karlp@etactica.com>
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
This decoder stacks on top of the 'spi' PD and decodes Microchip/Ateml
ATM90E3x command/responses.

The ATM90E32/ATM90E36 are poly phase energy metering ICs

This PD has been tested with an ATM90E36 and an ATM90E32.
ATM90E2x are explicitly excluded at this point, as they use 
24 bit spi transfers instead of 32bit.
'''

from .pd import Decoder
