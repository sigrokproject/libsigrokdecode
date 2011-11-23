##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

import sigrok

lastsample = None
oldbit = None
transitions = None
rising = None
falling = None

def decode(sampledata):
    """Counts the low->high and high->low transitions in the specified
       channel(s) of the signal."""
    global lastsample
    global oldbit, transitions, rising, falling

    # TODO: Don't hardcode the number of channels.
    channels = 8

    # FIXME: Get the data in the correct format in the first place.
    inbuf = [ord(x) for x in sampledata['data']]

    if lastsample == None:
        oldbit = [0] * channels
        transitions = [0] * channels
        rising = [0] * channels
        falling = [0] * channels

        # Initial values.
        lastsample = inbuf[0]
        for i in range(channels):
            oldbit[i] = (lastsample & (1 << i)) >> i

    # TODO: Handle LAs with more/less than 8 channels.
    for s in inbuf:
        # Optimization: Skip identical bytes (no transitions).
        if lastsample != s:
            for i in range(channels):
                curbit = (s & (1 << i)) >> i
                # Optimization: Skip identical bits (no transitions).
                if oldbit[i] == curbit:
                    continue
                elif (oldbit[i] == 0 and curbit == 1):
                    rising[i] += 1
                elif (oldbit[i] == 1 and curbit == 0):
                    falling[i] += 1
                oldbit[i] = curbit

            # Total number of transitions is the sum of rising and falling edges.
            for i in range(channels):
                transitions[i] = rising[i] + falling[i]

            lastsample = s
            print(transitions)

    sigrok.put(sampledata)

register = {
    'id': 'transitioncounter',
    'name': 'Transition counter',
    'longname': '...',
    'desc': 'Counts rising/falling edges in the signal.',
    'longdesc': '...',
    'author': 'Uwe Hermann',
    'email': 'uwe@hermann-uwe.de',
    'license': 'gplv2+',
    'in': ['logic'],
    'out': ['transitioncounts'],
    'probes': [
        # All probes.
    ],
    'options': {
        # No options so far.
    },
    # 'start': start,
    # 'report': report,
}

# Use psyco (if available) as it results in huge performance improvements.
try:
    import psyco
    psyco.bind(decode)
except ImportError:
    pass

