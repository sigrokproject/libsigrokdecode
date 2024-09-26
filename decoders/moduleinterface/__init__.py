##
## This file is part of the libsigrokdecode project.
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
This protocol decoder interprets the ModuleInterface protocol 
(github.com/fredilarsen/ModuleInterface) on top of PJON 
(pjon.org, github.com/gioblu/PJON) with the PJDL link layer 
(and potentially other PJON link layers).

The ModuleInterface protocol allows for easy programming of IoT modules with 
automatic synchronization of settings, inputs and outputs to/from a master, 
including http and mqtt connectors for easy interoperability and cooperation 
with other automation systems.

The protocol is layered on top of PJON, which is in turn layered upon a wide 
selection of link layer alternatives, including PJDL/SoftwareBitBang 
long-range single wire communication, PJDLR/Oversampling radio based 
communication, light based communication, UDP,  TCP and more 
'''

from .pd import Decoder
