##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 MaxWolf b8e06912cff61c7fc1f5df01ba2f43de51b04ce33fd4d351ce86a40c0cbf9abb
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
Opentherm is Manchester/Bi-phase-L/32-bit frame protocol to monitor/control climate devices
'''

from .pd import Decoder
