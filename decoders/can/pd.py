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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

# CAN protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'can'
    name = 'CAN'
    longname = 'Controller Area Network'
    desc = 'Field bus protocol for distributed realtime control.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['can']
    probes = [
        {'id': 'can_rx', 'name': 'CAN RX', 'desc': 'CAN bus line'},
    ]
    optional_probes = []
    options = {
        'bitrate': ['Bitrate', 1000000], # 1Mbit/s
        'sample_point': ['Sample point', 70], # 70%
    }
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.reset_variables()

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'can')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'can')

        self.samplerate = metadata['samplerate']
        self.bit_width = float(self.samplerate) / float(self.options['bitrate'])
        self.bitpos = (self.bit_width / 100.0) * self.options['sample_point']

    def report(self):
        pass

    def reset_variables(self):
        self.state = 'IDLE'
        self.sof = self.frame_type = self.dlc = None
        self.rawbits = [] # All bits, including stuff bits
        self.bits = [] # Only actual CAN frame bits (no stuff bits)
        self.curbit = 0 # Current bit of CAN frame (bit 0 == SOF)
        self.last_databit = 999 # Positive value that bitnum+x will never match

    # Return True if we reached the desired bit position, False otherwise.
    def reached_bit(self, bitnum):
        bitpos = int(self.sof + (self.bit_width * bitnum) + self.bitpos)
        if self.samplenum >= bitpos:
            return True
        return False

    def is_stuff_bit(self):
        # CAN uses NRZ encoding and bit stuffing.
        # After 5 identical bits, a stuff bit of opposite value is added.
        last_6_bits = self.rawbits[-6:]
        if last_6_bits not in ([0, 0, 0, 0, 0, 1], [1, 1, 1, 1, 1, 0]):
            return False

        # Stuff bit. Keep it in self.rawbits, but drop it from self.bits.
        self.put(0, 0, self.out_ann, [0, ['Stuff bit: %d' % self.rawbits[-1]]])
        self.bits.pop() # Drop last bit.
        return True

    def is_valid_crc(self, crc_bits):
        return True # TODO

    def decode_error_frame(self, bits):
        pass # TODO

    def decode_overload_frame(self, bits):
        pass # TODO

    # Both standard and extended frames end with CRC, CRC delimiter, ACK,
    # ACK delimiter, and EOF fields. Handle them in a common function.
    # Returns True if the frame ended (EOF), False otherwise.
    def decode_frame_end(self, can_rx, bitnum):

        # CRC sequence (15 bits)
        if bitnum == (self.last_databit + 15):
            x = self.last_databit + 1
            crc_bits = self.bits[x:x + 15 + 1]
            self.crc = int(''.join(str(d) for d in crc_bits), 2)
            self.put(0, 0, self.out_ann, [0, ['CRC: 0x%04x' % self.crc]])

            if not self.is_valid_crc(crc_bits):
                self.put(0, 0, self.out_ann, [0, ['CRC is invalid']])

        # CRC delimiter bit (recessive)
        elif bitnum == (self.last_databit + 16):
            self.put(0, 0, self.out_ann, [0, ['CRC delimiter: %d' % can_rx]])

        # ACK slot bit (dominant: ACK, recessive: NACK)
        elif bitnum == (self.last_databit + 17):
            ack = 'ACK' if can_rx == 0 else 'NACK'
            self.put(0, 0, self.out_ann, [0, ['ACK slot: %s' % ack]])

        # ACK delimiter bit (recessive)
        elif bitnum == (self.last_databit + 18):
            self.put(0, 0, self.out_ann, [0, ['ACK delimiter: %d' % can_rx]])

        # End of frame (EOF), 7 recessive bits
        elif bitnum == (self.last_databit + 25):
            self.put(0, 0, self.out_ann, [0, ['End of frame', 'EOF']])
            self.reset_variables()
            return True

        return False

    # Returns True if the frame ended (EOF), False otherwise.
    def decode_standard_frame(self, can_rx, bitnum):

        # Bit 14: RB0 (reserved bit)
        # Has to be sent dominant, but receivers should accept recessive too.
        if bitnum == 14:
            self.put(0, 0, self.out_ann, [0, ['RB0: %d' % can_rx]])

            # Bit 12: Remote transmission request (RTR) bit
            # Data frame: dominant, remote frame: recessive
            # Remote frames do not contain a data field.
            rtr = 'remote' if self.bits[12] == 1 else 'data'
            self.put(0, 0, self.out_ann, [0, ['RTR: %s frame' % rtr]])

        # Bits 15-18: Data length code (DLC), in number of bytes (0-8).
        elif bitnum == 18:
            self.dlc = int(''.join(str(d) for d in self.bits[15:18 + 1]), 2)
            self.put(0, 0, self.out_ann, [0, ['DLC: %d' % self.dlc]])
            self.last_databit = 18 + (self.dlc * 8)

        # Bits 19-X: Data field (0-8 bytes, depending on DLC)
        # The bits within a data byte are transferred MSB-first.
        elif bitnum == self.last_databit:
            for i in range(self.dlc):
                x = 18 + (8 * i) + 1
                b = int(''.join(str(d) for d in self.bits[x:x + 8]), 2)
                self.put(0, 0, self.out_ann,
                         [0, ['Data byte %d: 0x%02x' % (i, b)]])

        elif bitnum > self.last_databit:
            return self.decode_frame_end(can_rx, bitnum)

        return False

    # Returns True if the frame ended (EOF), False otherwise.
    def decode_extended_frame(self, can_rx, bitnum):

        # Bits 14-31: Extended identifier (EID[17..0])
        if bitnum == 31:
            self.eid = int(''.join(str(d) for d in self.bits[14:]), 2)
            self.put(0, 0, self.out_ann,
                     [0, ['Extended ID: %d (0x%x)' % (self.eid, self.eid)]])

            self.fullid = self.id << 18 | self.eid
            self.put(0, 0, self.out_ann,
                     [0, ['Full ID: %d (0x%x)' % (self.fullid, self.fullid)]])

            # Bit 12: Substitute remote request (SRR) bit
            self.put(0, 0, self.out_ann, [0, ['SRR: %d' % self.bits[12]]])

        # Bit 32: Remote transmission request (RTR) bit
        # Data frame: dominant, remote frame: recessive
        # Remote frames do not contain a data field.
        if bitnum == 32:
            rtr = 'remote' if can_rx == 1 else 'data'
            self.put(0, 0, self.out_ann, [0, ['RTR: %s frame' % rtr]])

        # Bit 33: RB1 (reserved bit)
        elif bitnum == 33:
            self.put(0, 0, self.out_ann, [0, ['RB1: %d' % can_rx]])

        # Bit 34: RB0 (reserved bit)
        elif bitnum == 34:
            self.put(0, 0, self.out_ann, [0, ['RB0: %d' % can_rx]])

        # Bits 35-38: Data length code (DLC), in number of bytes (0-8).
        elif bitnum == 38:
            self.dlc = int(''.join(str(d) for d in self.bits[35:38 + 1]), 2)
            self.put(0, 0, self.out_ann, [0, ['DLC: %d' % self.dlc]])
            self.last_databit = 38 + (self.dlc * 8)

        # Bits 39-X: Data field (0-8 bytes, depending on DLC)
        # The bits within a data byte are transferred MSB-first.
        elif bitnum == self.last_databit:
            for i in range(self.dlc):
                x = 38 + (8 * i) + 1
                b = int(''.join(str(d) for d in self.bits[x:x + 8]), 2)
                self.put(0, 0, self.out_ann,
                         [0, ['Data byte %d: 0x%02x' % (i, b)]])

        elif bitnum > self.last_databit:
            return self.decode_frame_end(can_rx, bitnum)

        return False

    def handle_bit(self, can_rx):
        self.rawbits.append(can_rx)
        self.bits.append(can_rx)

        # Get the index of the current CAN frame bit (without stuff bits).
        bitnum = len(self.bits) - 1

        # For debugging.
        # self.put(0, 0, self.out_ann, [0, ['Bit %d (CAN bit %d): %d' % \
        #          (self.curbit, bitnum, can_rx)]])

        # If this is a stuff bit, remove it from self.bits and ignore it.
        if self.is_stuff_bit():
            self.curbit += 1 # Increase self.curbit (bitnum is not affected).
            return

        # Bit 0: Start of frame (SOF) bit
        if bitnum == 0:
            if can_rx == 0:
                self.put(0, 0, self.out_ann, [0, ['Start of frame', 'SOF']])
            else:
                self.put(0, 0, self.out_ann,
                         [1, ['Start of frame (SOF) must be a dominant bit']])

        # Bits 1-11: Identifier (ID[10..0])
        # The bits ID[10..4] must NOT be all recessive.
        elif bitnum == 11:
            self.id = int(''.join(str(d) for d in self.bits[1:]), 2)
            self.put(0, 0, self.out_ann,
                     [0, ['ID: %d (0x%x)' % (self.id, self.id)]])

        # RTR or SRR bit, depending on frame type (gets handled later).
        elif bitnum == 12:
            # self.put(0, 0, self.out_ann, [0, ['RTR/SRR: %d' % can_rx]])
            pass

        # Bit 13: Identifier extension (IDE) bit
        # Standard frame: dominant, extended frame: recessive
        elif bitnum == 13:
            ide = self.frame_type = 'standard' if can_rx == 0 else 'extended'
            self.put(0, 0, self.out_ann, [0, ['IDE: %s frame' % ide]])

        # Bits 14-X: Frame-type dependent, passed to the resp. handlers.
        elif bitnum >= 14:
            if self.frame_type == 'standard':
                done = self.decode_standard_frame(can_rx, bitnum)
            else:
                done = self.decode_extended_frame(can_rx, bitnum)

            # The handlers return True if a frame ended (EOF).
            if done:
                return

        # After a frame there are 3 intermission bits (recessive).
        # After these bits, the bus is considered free.

        self.curbit += 1

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            (can_rx,) = pins

            # State machine.
            if self.state == 'IDLE':
                # Wait for a dominant state (logic 0) on the bus.
                if can_rx == 1:
                    continue
                self.sof = self.samplenum
                # self.put(self.sof, self.sof, self.out_ann, [0, ['SOF']])
                self.state = 'GET BITS'
            elif self.state == 'GET BITS':
                # Wait until we're in the correct bit/sampling position.
                if not self.reached_bit(self.curbit):
                    continue
                self.handle_bit(can_rx)
            else:
                raise Exception("Invalid state: %s" % self.state)

