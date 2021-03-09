'''
The User Datagram Protocol (UDP) is one of the core members of the Internet protocol suite.
With UDP, computer applications can send messages, in this case referred to as datagrams, to other hosts on an Internet Protocol (IP) network.

Prior communications are not required in order to set up communication channels or data paths.
UDP uses a simple connectionless communication model with a minimum of protocol mechanisms.

This decoder stacks on top of the 'IPv4' PD and decodes IPv4 payloads into UDP datagrams.
'''

from .pd import Decoder
