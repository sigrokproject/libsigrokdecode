'''
Ethernet is a data link layer protocol found in Local/Wide Area Networks (LAN/WAN) typically carrying the Internet Protocol (IPv4 / IPv6).
It is considered one of the key technologies that make up the Internet.

Systems communicating over Ethernet divide a stream of data into shorter pieces called frames. Each frame contains source and destination addresses, and error-checking data so that damaged frames can be detected and discarded.

This decoder stacks on top of the '4B5B' PD and decodes bytes into Ethernet frames.
'''

from .pd import Decoder
