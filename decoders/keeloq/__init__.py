##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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
KeeLoq is a block-cypher which is widely used as an industry standards in
in secure wireless Keyless Entry (RKE) systems such as anti-theft, gates and car immobilizers.
Transmitter or encoder sends commands to the receiver using a sequence of PWM bits organized 
in structured known as 'Code Word'. This decoder inteprets the bits and shows the 'Code Word' in
a human readable form. 

A typical KeeLoq implementation is for IC HCS300 :
https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/21137G.pdf
'''

from .pd import Decoder
