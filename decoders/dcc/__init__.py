##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2025 Vincent Hamp <hamp@zimo.at>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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
DCC is an acronym for Digital Command Control, a standardized protocol for
controlling digital model railways. This decoder handles DCC as well as it's
bidirectional extension RailCom.

Documentation available at:
https://www.railcommunity.org
https://www.nmra.org

RailCom@(Lenz Elektronik GmbH)
'''

from .pd import Decoder
