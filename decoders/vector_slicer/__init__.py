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
This protocol decoder can decode multiple bits from a logic analyzer
into a slice. A slice is a value which can further be decoded.

As input it takes the data from a logic analyzer.
It is required to use the lowest data channels, and use consecutive ones.
For example, for a 4 bit analyzer probe, channels D0/D1/D2/D3 should be
used. Using combinations like D7/D12/D3/D15 is not supported.
For an 8 bit analyzer probe you should use D0-D7, for a 16 bit analyzer
probe use D0-D15 and so on.

One can configure the base in the input vector and the length of the slice.

Currently the following decoders are available to annotate slices:
    - unsigned slice: annotate slice as unsigned integer
    - signed slice: annotate slice as signed integer
    - fixedpoint slice: annotate slice as fixedpoint number
    - enum slice: annotate slice as enumerated type
'''

from .pd import Decoder
