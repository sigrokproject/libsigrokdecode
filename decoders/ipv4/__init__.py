'''
The principal communications protocol in the Internet protocol suite for relaying datagrams across network boundaries.

Its routing function enables internetworking, and essentially establishes the Internet.

This decoder stacks on top of the 'Ethernet' PD and decodes Ethernet payloads into IPv4 frames.
'''

from .pd import Decoder
