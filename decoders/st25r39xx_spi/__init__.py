##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019-2020 Benjamin Vernoux <bvernoux@gmail.com>
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
This decoder stacks on top of the 'spi' PD and decodes st25r3916 High performance NFC universal device and EMVCo reader
(SPI mode) protocol.

Details:
https://www.st.com/resource/en/datasheet/st25r3916.pdf
'''

from .pd import Decoder
