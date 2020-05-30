##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Tomas Mudrunka <harvie@github>
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
This decodes digital output of cheap generic calipers (usualy made in china)
Decoder will show measured value in milimeters or inches.

Please note that these devices often communicate on low voltage level,
which might not be possible to capture with 3.3V logic analyzers.
So additional circuitry might be needed to capture the signal.

This is NOT for calipers using Digimatic protocol (eg. Mitutoyo and similar brands)

More info:

http://www.shumatech.com/support/chinese_scales.htm
https://www.instructables.com/id/Reading-Digital-Callipers-with-an-Arduino-USB/
'''

from .pd import Decoder
