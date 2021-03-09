'''
4B5B is a form of data communications line code which maps groups of 4 data bits to 5-bit symbols for transmission.

These 5-bit symbols are pre-determined in a dictionary and they are chosen to ensure that there will be sufficient transitions in the line state to produce a self-clocking signal.

Some symbols are used as control characters to indicate the transmission medium is idle or to mark the start and end of a frame.

4B5B is used by Fiber Distributed Data Interface (FDDI), Multichannel Audio Digital Interface (MADI), Fast Ethernet (100BASE-X) and USB Power Delivery (USB-PD).

This decoder stacks on top of the 'NRZ-I' PD and decodes bits into 4B5B symbols.
'''

from .pd import Decoder
