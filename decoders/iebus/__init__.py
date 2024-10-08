##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2023 Maciej Grela <enki@fsck.pl>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <https://www.gnu.org/licenses/>.


'''
IEBus (Inter Equipment Bus) is a communication bus specification
"between equipments within a vehicle or a chassis". IEBus is mainly
used for car audio and car navigations as well some vending machines.
'''

from .pd import Decoder
