##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Comlab AG
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
This protocol decodes sliced data from vector_slicer and generates
annotations for an enumerated type.

The mapping from the slice value to the enumeration is given by a
json file. The following example is for a one hot coded state of an fsm:
{
"S1":  1,
"S2":  2,
"S3":  4,
"S4":  8,
"S5": 16
}
'''

from .pd import Decoder
