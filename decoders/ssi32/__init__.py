##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Robert Bosch Car Multimedia GmbH
## Authors: Oleksij Rempel
##              <fixed-term.Oleksij.Rempel@de.bosch.com>
##              <linux@rempel-privat.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##

'''
This decoder stacks on top of the 'spi' PD and decodes Bosch SSI32
protocol.
'''

from .pd import Decoder
