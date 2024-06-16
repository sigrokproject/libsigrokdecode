'''
The Address Resolution Protocol (ARP) is used for discovering the link layer address, such as a MAC address, associated with a given internet layer address, typically an IPv4 address.

This mapping is a critical function in the Internet protocol suite.

This decoder stacks on top of the 'Ethernet' PD and decodes Ethernet payloads into ARP packets.
'''

from .pd import Decoder
