##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
## Copyright (C) 2019-2026 Stephan Thiele <stephan.thiele@mailbox.org>
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

from common.srdhelper import bitpack_msb
import sigrokdecode as srd

class SamplerateError(Exception):
    pass

def dlc2len(dlc):
    return [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64][dlc]

def gray2num(gray_code):
    num = gray_code
    mask = gray_code

    while mask:
        mask >>= 1
        num ^= mask

    return num

class Decoder(srd.Decoder):
    api_version = 3
    id = 'can'
    name = 'CAN'
    longname = 'Controller Area Network'
    desc = 'Field bus protocol for distributed realtime control.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['can']
    tags = ['Automotive']
    channels = (
        {'id': 'can_rx', 'name': 'CAN RX', 'desc': 'CAN bus line'},
    )
    options = (
        {'id': 'nominal_bitrate', 'desc': 'Nominal bitrate (bits/s)', 'default': 1000000},
        {'id': 'fd_bitrate', 'desc': 'FD bitrate (bits/s)', 'default': 2000000},
        {'id': 'xl_bitrate', 'desc': 'XL bitrate (bits/s)', 'default': 4000000},
        {'id': 'nominal_sample_point', 'desc': 'Nominal sample point (%)', 'default': 70.0},
        {'id': 'fd_sample_point', 'desc': 'FD sample point (%)', 'default': 70.0},
        {'id': 'xl_sample_point', 'desc': 'XL sample point (%)', 'default': 70.0},
    )
    annotations = (
        ('data', 'Payload data'),
        ('sof', 'Start of frame'),
        ('eof', 'End of frame'),
        ('id', 'Identifier'),
        ('ext-id', 'Extended identifier'),
        ('full-id', 'Full identifier'),
        ('ide', 'Identifier extension bit'),
        ('reserved-bit', 'Reserved bit 0 and 1'),
        ('rtr', 'Remote transmission request'),
        ('srr', 'Substitute remote request'),
        ('dlc', 'Data length count'),
        ('crc-sequence', 'CRC sequence'),
        ('crc-delimiter', 'CRC delimiter'),
        ('ack-slot', 'ACK slot'),
        ('ack-delimiter', 'ACK delimiter'),
        ('stuff-bit', 'Stuff bit'),
        ('warning', 'Warning'),
        ('bit', 'Bit'),
        ('sbc', 'Stuff bit count'),
        ('xlf', 'Extended data length format'),
        ('resXL', 'Reserved bit extended data field length format'),
        ('ADH', 'Arbitration to data high'),
        ('DH1', 'Data high bit 1'),
        ('DH2', 'Data high bit 2'),
        ('DL1', 'Data low bit 1'),
        ('SDT', 'Service data unit type'),
        ('SEC', 'Simple/extended content'),
        ('PCRC-13', 'Preface CRC-13'),
        ('VCID', 'Virtual CAN network channel identifier'),
        ('AF', 'Acceptance field'),
        ('FCP', 'Format check pattern'),
        ('DAH', 'Data arbitration high'),
        ('AH1', 'Arbitration high 1'),
        ('AL1', 'Arbitration low 1'),
        ('AH2', 'Arbitration high 2')
    )
    annotation_rows = (
        ('bits', 'Bits', (15, 17)),
        ('fields', 'Fields', tuple(range(15)) + (18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34)),
        ('warnings', 'Warnings', (16,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.reset_variables()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)

    def set_bit_rate(self, bitrate, sample_point):
        prev_bit_remaining_samples = self.bit_width - self.sample_point

        self.bit_width = float(self.samplerate) / float(bitrate)
        self.sample_point = (self.bit_width / 100.0) * sample_point

        if self.fd:
            # Set virtual dom edge after the bit where bitrate switch happened, to adjust sample grid to new bitrate
            if self.xl:
                self.dom_edge_bcount = self.curbit
                self.dom_edge_snum = self.samplenum + prev_bit_remaining_samples
            else:
                self.dom_edge_bcount = self.curbit + 1
                self.dom_edge_snum = self.samplenum + self.bit_width - self.sample_point

    def set_nominal_bitrate(self):
        self.set_bit_rate(self.options['nominal_bitrate'], self.options['nominal_sample_point'])

    def set_fd_bitrate(self):
        self.set_bit_rate(self.options['fd_bitrate'], self.options['fd_sample_point'])

    def set_xl_bitrate(self):
        self.set_bit_rate(self.options['xl_bitrate'], self.options['xl_sample_point'])

    def set_dlc_and_crc_len(self, dlc):
        self.dlc = dlc

        if self.xl:
            self.crc_len = 32
        elif self.fd:
            if dlc2len(self.dlc) < 16:
                self.crc_len = 17
            else:
                self.crc_len = 21
        else:
            self.crc_len = 15

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            self.bit_width = float(self.samplerate) / float(self.options['nominal_bitrate'])
            self.sample_point = (self.bit_width / 100.0) * self.options['nominal_sample_point']

    # Generic helper for CAN bit annotations.
    def putg(self, ss, es, data):
        left, right = int(self.sample_point), int(self.bit_width - self.sample_point)
        self.put(ss - left, es + right, self.out_ann, data)

    # Single-CAN-bit annotation for a bitrate switch bit using the current samplenum.
    def putx_brs(self, from_bitrate, from_spp, to_bitrate, to_spp, data):
        from_samples_per_bit = float(self.samplerate) / float(from_bitrate)
        from_spp_sample_no = (from_samples_per_bit / 100.0) * from_spp

        to_samples_per_bit = float(self.samplerate) / float(to_bitrate)
        to_spp_sample_no = (to_samples_per_bit / 100.0) * to_spp

        num_samples_brs_bit = from_spp_sample_no + to_samples_per_bit - to_spp_sample_no

        left, right = int(from_spp_sample_no), int(num_samples_brs_bit - from_spp_sample_no)
        self.put(self.samplenum - left, self.samplenum + right, self.out_ann, data)

    # Single-CAN-bit annotation using the current samplenum.
    def putx(self, data):
        self.putg(self.samplenum, self.samplenum, data)

    # Single-CAN-bit annotation using the samplenum of CAN bit 12.
    def put12(self, data):
        self.putg(self.ss_bit12, self.ss_bit12, data)

    # Single-CAN-bit annotation using the samplenum of CAN bit 32.
    def put32(self, data):
        self.putg(self.ss_bit32, self.ss_bit32, data)

    # Multi-CAN-bit annotation from self.ss_block to current samplenum.
    def putb(self, data):
        self.putg(self.ss_block, self.samplenum, data)

    def putpy(self, data):
        self.put(self.ss_packet, self.es_packet, self.out_python, data)

    def reset_variables(self):
        self.state = 'IDLE'
        self.sof = self.frame_type = self.dlc = None
        self.rawbits = [] # All bits, including stuff bits
        self.bits = [] # Only actual CAN frame bits (no stuff bits)
        self.curbit = 0 # Current bit of CAN frame (bit 0 == SOF)
        self.last_databit = 999 # Positive value that bitnum+x will never match
        self.crc_start = 999
        self.ss_block = None
        self.ss_bit12 = None
        self.ss_bit32 = None
        self.ss_databytebits = []
        self.frame_bytes = []
        self.rtr_type = None
        self.fd = False
        self.xl = False
        self.brs = False
        self.rtr = None
        self.last_bit_was_stuff_bit = False
        self.crc_len = 15
        self.dlc_field_len = 4

    # Poor man's clock synchronization. Use signal edges which change to
    # dominant state in rather simple ways. This naive approach is neither
    # aware of the SYNC phase's width nor the specific location of the edge,
    # but improves the decoder's reliability when the input signal's bitrate
    # does not exactly match the nominal rate.
    def dom_edge_seen(self, force = False):
        self.dom_edge_snum = self.samplenum
        self.dom_edge_bcount = self.curbit

    # Determine the position of the next desired bit's sample point.
    def get_sample_point(self, bitnum):
        samplenum = self.dom_edge_snum
        samplenum += self.bit_width * (bitnum - self.dom_edge_bcount)
        samplenum += self.sample_point
        return int(samplenum)

    def is_stuff_bit(self):
        # CAN uses NRZ encoding (dynamic bit stuffing).
        # After five consecutive bits of identical value, a stuff bit of the
        # opposite polarity is inserted.
        #
        # In CAN-FD frames, additional fixed bit stuffing is used for the CRC field.
        # This fixed stuffing begins one bit before the CRC field, regardless of
        # whether five identical bits have occurred.

        # If a dynamic stuff bit and a fixed stuff bit would be inserted at the
        # same position, only the fixed stuff bit is inserted. In this case,
        # only a single stuff bit is inserted:
        if self.last_bit_was_stuff_bit:
            self.last_bit_was_stuff_bit = False
            return False

        cur_bit = len(self.bits) - 1

        # Bit stuffing is not applied to the CRC delimiter, ACK field,
        # or End-of-Frame (EOF) field:
        if cur_bit > self.crc_start + self.crc_len - 1:
            self.last_bit_was_stuff_bit = False
            return False

        if self.xl and cur_bit > 21: # After DL1 bit
            # Within the CAN-XL Control field (starting from DL1 bit), data field and FCRC sequence, a fixed stuff bit
            # is inserted after every 10th bit:
            if (cur_bit - 20) % 10 != 0:
                self.last_bit_was_stuff_bit = False
                return False

        elif not self.xl and self.fd and cur_bit > self.last_databit:
            # Within the CAN-FD CRC field, a fixed stuff bit is inserted after every fourth bit:
            if (cur_bit - self.last_databit - 1) % 4 != 0:
                self.last_bit_was_stuff_bit = False
                return False
        else:
            # NRZ dynamic bit stuffing:
            last_6_bits = self.rawbits[-6:]
            if last_6_bits not in ([0, 0, 0, 0, 0, 1], [1, 1, 1, 1, 1, 0]):
                self.last_bit_was_stuff_bit = False
                return False

        # Stuff bit. Keep it in self.rawbits, but drop it from self.bits.
        self.bits.pop() # Drop last bit.
        self.last_bit_was_stuff_bit = True
        return True

    def is_valid_even_parity(self, num, given_parity_bit):
        calculated_parity_bit = 0

        while num:
            calculated_parity_bit ^= num & 1
            num >>= 1

        return calculated_parity_bit == given_parity_bit

    def is_valid_odd_parity(self, num, given_parity_bit):
        return not self.is_valid_even_parity(num, given_parity_bit)

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

        # Remember start of Non-FD CRC sequence, XL FCRC sequence or FD-SBC field (see below).
        if bitnum == (self.last_databit + 1):
            self.ss_block = self.samplenum
        elif self.fd and not self.xl and bitnum == (self.last_databit + 4):
            # SBC field
            x = self.last_databit + 1
            sbc_bits = self.bits[x:x + self.last_databit + 4]
            p_gray_sbc = bitpack_msb(sbc_bits)

            parity = p_gray_sbc & 1
            gray_sbc = p_gray_sbc >> 1

            if not self.is_valid_even_parity(gray_sbc, parity):
                self.putb([16, ['Parity is invalid']])

            sbc = gray2num(gray_sbc) # Number of stuff bits modulo 8

            self.putb([18, ['Stuff bit count: %d' % sbc,
                            'SBC: %d' % sbc, 'SBC']])

        # Remember start of FD-CRC sequence (see below).
        elif self.fd and not self.xl and bitnum == (self.last_databit + 4 + 1):
            self.ss_block = self.samplenum

        # CRC sequence (15 bits, 17 bits, 21 bits or 32 bits)
        elif bitnum == (self.crc_start - 1 + self.crc_len):
            x = self.crc_start
            crc_bits = self.bits[x:x + self.crc_len + 1]

            crc_type = ("F" if self.xl else "") + "CRC-%d" % self.crc_len
            self.crc = bitpack_msb(crc_bits)
            self.putb([11, ['%s sequence: 0x%04x' % (crc_type, self.crc),
                            '%s: 0x%04x' % (crc_type, self.crc), '%s' % crc_type]])
            if not self.is_valid_crc(crc_bits):
                self.putb([16, ['CRC is invalid']])

        elif self.xl and bitnum == self.crc_start + 32:
            # Remember start of FCP sequence (see below).
            self.ss_block = self.samplenum

        elif self.xl and bitnum == self.crc_start + 35:
            x = self.crc_start + 32
            fcp = bitpack_msb(self.bits[x:x + self.crc_start + 36])

            self.putb([30, ['Format check pattern: 0x%02X' % fcp,
                            'FCP: 0x%02X' % fcp, 'FCP']])

        # CRC delimiter bit (recessive)
        elif not self.xl and bitnum == (self.crc_start + self.crc_len):
            data = [12, ['CRC delimiter: %d' % can_rx,
                         'CRC d: %d' % can_rx, 'CRC d']]

            if self.fd and self.brs:
                from_bitrate = self.options['fd_bitrate']
                from_spp = self.options['fd_sample_point']
                to_bitrate = self.options['nominal_bitrate']
                to_spp = self.options['nominal_sample_point']

                self.putx_brs(from_bitrate, from_spp, to_bitrate, to_spp, data)
            else:
                self.putx(data)

            if can_rx != 1:
                self.putx([16, ['CRC delimiter must be a recessive bit']])

        elif self.xl and bitnum == self.crc_start + 36:
            self.putx([31, ['Data arbitration high: %d' % can_rx,
                            'DAH: %d' % can_rx, 'DAH']])

        elif self.xl and bitnum == self.crc_start + 37:
            self.putx([32, ['Arbitration high 1: %d' % can_rx,
                            'AH1: %d' % can_rx, 'AH1']])

        elif self.xl and bitnum == self.crc_start + 38:
            self.putx([33, ['Arbitration low 1: %d' % can_rx,
                            'AL1: %d' % can_rx, 'AL1']])

        elif self.xl and bitnum == self.crc_start + 39:
            self.putx([34, ['Arbitration high 2: %d' % can_rx,
                            'AH2: %d' % can_rx, 'AH2']])

        # ACK slot bit (dominant: ACK, recessive: NACK)
        elif self.xl and bitnum == self.crc_start + 40 or not self.xl and bitnum == (self.crc_start - 1 + self.crc_len + 2):
            ack = 'ACK' if can_rx == 0 else 'NACK'
            self.putx([13, ['ACK slot: %s' % ack, 'ACK s: %s' % ack, 'ACK s']])

        # ACK delimiter bit (recessive)
        elif self.xl and bitnum == self.crc_start + 41 or not self.xl and bitnum == (self.crc_start - 1 + self.crc_len + 3):
            self.putx([14, ['ACK delimiter: %d' % can_rx,
                            'ACK d: %d' % can_rx, 'ACK d']])
            if can_rx != 1:
                self.putx([16, ['ACK delimiter must be a recessive bit']])

        # Remember start of EOF (see below).
        elif self.xl and bitnum == self.crc_start + 42 or not self.xl and bitnum == (self.crc_start - 1 + self.crc_len + 4):
            self.ss_block = self.samplenum

        # End of frame (EOF), 7 recessive bits
        elif self.xl and bitnum == self.crc_start - 1 + 42 + 7 or not self.xl and bitnum == (self.crc_start - 1 + self.crc_len + 3 + 7):
            self.putb([2, ['End of frame', 'EOF', 'E']])
            if self.rawbits[-7:] != [1, 1, 1, 1, 1, 1, 1]:
                self.putb([16, ['End of frame (EOF) must be 7 recessive bits']])
            self.es_packet = self.samplenum
            py_data = tuple([self.frame_type, self.fullid, self.rtr_type,
                self.dlc, self.frame_bytes])
            self.putpy(py_data)
            self.reset_variables()
            return True

        return False

    # Returns True if the frame ended (EOF), False otherwise.
    def decode_standard_frame(self, can_rx, bitnum):

        # Bit 14: FDF (Flexible data format)
        # Has to be sent dominant when FD frame, has to be sent recessive
        # when classic CAN frame.
        if bitnum == 14:
            self.fd = True if can_rx else False
            if self.fd:
                self.putx([7, ['Flexible data format: %d' % can_rx,
                               'FDF: %d' % can_rx, 'FDF']])
            else:
                self.putx([7, ['Reserved bit 0: %d' % can_rx,
                               'RB0: %d' % can_rx, 'RB0']])

            if self.fd:
                # Bit 12: Substitute remote request (SRR) bit
                self.put12([8, ['Substitute remote request', 'SRR']])
                self.dlc_start = 18
            else:
                # Bit 12: Remote transmission request (RTR) bit
                # Data frame: dominant, remote frame: recessive
                # Remote frames do not contain a data field.
                rtr = 'remote' if self.bits[12] == 1 else 'data'
                self.put12([8, ['Remote transmission request: %s frame' % rtr,
                                'RTR: %s frame' % rtr, 'RTR']])
                self.rtr_type = rtr
                self.dlc_start = 15

        if bitnum == 15 and self.fd:
            self.xl = True if can_rx else False

            if self.xl:
                self.putx([19, ['Extended data length format: %d' % can_rx,
                                'XLF: %d' % can_rx, 'XLF']])
                self.dlc_start = 30
                self.dlc_field_len = 11
            else:
                self.putx([7, ['Reserved: %d' % can_rx, 'R0: %d' % can_rx, 'R0']])

        if bitnum == 16 and self.fd:
            if self.xl:
                self.putx([20, ['Reserved bit extended data field length format: %d' % can_rx,
                                'resXL: %d' % can_rx, 'resXL']])
            else:
                data = [7, ['Bit rate switch: %d' % can_rx,
                            'BRS: %d' % can_rx, 'BRS']]

                if self.brs:
                    from_bitrate = self.options['nominal_bitrate']
                    from_spp = self.options['nominal_sample_point']
                    to_bitrate = self.options['fd_bitrate']
                    to_spp = self.options['fd_sample_point']

                    self.putx_brs(from_bitrate, from_spp, to_bitrate, to_spp, data)
                else:
                    self.putx(data)

        if bitnum == 17 and self.fd:
            if self.xl:
                self.putx([21, ['Arbitration to data high: %d' % can_rx, 'ADH: %d' % can_rx, 'ADH']])
            else:
                self.putx([7, ['Error state indicator: %d' % can_rx, 'ESI: %d' % can_rx, 'ESI']])

        if self.xl:
            if bitnum == 18:
                self.putx([22, ['Data high bit 1: %d' % can_rx, 'DH1: %d' % can_rx, 'DH1']])

            elif bitnum == 19:
                self.putx([23, ['Data high bit 2: %d' % can_rx, 'DH2: %d' % can_rx, 'DH2']])

            elif bitnum == 20:
                self.putx([24, ['Data low bit 1: %d' % can_rx, 'DL1: %d' % can_rx, 'DL1']])

            # Remember start of SDT (see below).
            elif bitnum == 21:
                self.ss_block = self.samplenum

            elif bitnum == 28:
                sdt = bitpack_msb(self.bits[21:29])

                self.putb([25, ['Service data unit type: %d' % sdt,
                                'SDT: %d' % sdt, 'SDT']])

            elif bitnum == 29:
                self.putx([26, ['Simple/extended content: %d' % can_rx,
                                'SEC: %d' % can_rx, 'SEC']])

        # Remember start of DLC (see below).
        if bitnum == self.dlc_start:
            self.ss_block = self.samplenum

        # Data length code (DLC)
        # - Classic CAN: number of bytes (0-8)
        # - CAN-FD: 0=0, 1=1, 2=2, 3=3, 4=4, 5=5, 6=6, 7=7, 8=8, 9=12, 10=16, 11=20, 12=24, 13=32, 14=48, 15=64
        # - CAN-XL: Number of bytes minus one (0 - 2047) while 0 means 1 byte of data (0 bytes is not possible anymore)

        elif bitnum == self.dlc_start + self.dlc_field_len - 1:
            self.set_dlc_and_crc_len(bitpack_msb(self.bits[self.dlc_start:self.dlc_start + self.dlc_field_len]))
            self.putb([10, ['Data length code: %d' % self.dlc,
                            'DLC: %d' % self.dlc, 'DLC']])

            if self.xl:
                self.last_databit = 96 + (self.dlc + 1) * 8
            else:
              self.last_databit = self.dlc_start + self.dlc_field_len - 1 + (dlc2len(self.dlc) * 8)

            self.crc_start = self.last_databit + 1

            if self.fd and not self.xl:
                self.crc_start += 4 # Skip SBC field

            if self.dlc > 8 and not self.fd:
                self.putb([16, ['Data length code (DLC) > 8 is not allowed']])

        if self.xl:
            # Remember start of SBC (see below).
            if bitnum == 41:
                self.ss_block = self.samplenum

            # Stuff bit count (SBC)
            elif bitnum == 43:
                # SBC field
                sbc_bits = self.bits[41:44]
                p_gray_sbc = bitpack_msb(sbc_bits)

                parity = p_gray_sbc & 1
                gray_sbc = p_gray_sbc >> 1

                # in contrast to FD CRC, odd parity scheme is used:
                if not self.is_valid_odd_parity(gray_sbc, parity):
                    self.putb([16, ['Parity is invalid']])

                sbc = gray2num(gray_sbc) # Number of stuff bits modulo 8

                self.putb([18, ['Stuff bit count: %d' % sbc,
                                'SBC: %d' % sbc, 'SBC']])

            # Remember start of PCRC (see below).
            elif bitnum == 44:
                self.ss_block = self.samplenum

            #  Preface CRC (PCRC)
            elif bitnum == 56:
                pcrc = bitpack_msb(self.bits[45:58])

                self.putb([27, ['Preface CRC-13: 0x%04x' % pcrc,
                                'PCRC-13: 0x%04x' % pcrc, 'PCRC-13']])

            # Remember start of VCID (see below).
            elif bitnum == 57:
                self.ss_block = self.samplenum

            # Virtual CAN network channel identifier (VCID)
            elif bitnum == 64:
                vcid = bitpack_msb(self.bits[58:65])

                self.putb([28, ['Virtual CAN network channel identifier: 0x%02X (%d)' % (vcid, vcid),
                                'VCID: 0x%02X (%d)' % (vcid, vcid), 'VCID']])

            # Remember start of AF (see below).
            elif bitnum == 65:
                self.ss_block = self.samplenum

            # Acceptance field (AF)
            elif bitnum == 96:
                af = bitpack_msb(self.bits[65:97])

                self.putb([29, ['Acceptance field: 0x%02x (%d)' % (af, af),
                                'AF: 0x%02x (%d)' % (af, af), 'AF']])

        # Remember all databyte bits, except the very last one.
        if bitnum in range(97 if self.xl else self.dlc_start + 4, self.last_databit):
            self.ss_databytebits.append(self.samplenum)

        # Data field (0-2048 bytes, depending on DLC)
        # The bits within a data byte are transferred MSB-first.
        elif bitnum == self.last_databit:
            self.ss_databytebits.append(self.samplenum) # Last databyte bit.
            for i in range(self.dlc + 1 if self.xl else dlc2len(self.dlc)):
                x = (97 if self.xl else self.dlc_start + 4) + (8 * i)
                b = bitpack_msb(self.bits[x:x + 8])
                self.frame_bytes.append(b)
                ss = self.ss_databytebits[i * 8]
                es = self.ss_databytebits[((i + 1) * 8) - 1]
                self.putg(ss, es, [0, ['Data byte %d: 0x%02x' % (i, b),
                                       'DB %d: 0x%02x' % (i, b), 'DB']])
            self.ss_databytebits = []

        elif bitnum > self.last_databit:
            return self.decode_frame_end(can_rx, bitnum)

        return False

    # Returns True if the frame ended (EOF), False otherwise.
    def decode_extended_frame(self, can_rx, bitnum):

        # Remember start of EID (see below).
        if bitnum == 14:
            self.ss_block = self.samplenum
            self.fd = False
            self.dlc_start = 35

        # Bits 14-31: Extended identifier (EID[17..0])
        elif bitnum == 31:
            self.eid = bitpack_msb(self.bits[14:])
            s = '%d (0x%x)' % (self.eid, self.eid)
            self.putb([4, ['Extended Identifier: %s' % s,
                           'Extended ID: %s' % s, 'Extended ID', 'EID']])

            self.fullid = self.ident << 18 | self.eid
            s = '%d (0x%x)' % (self.fullid, self.fullid)
            self.putb([5, ['Full Identifier: %s' % s, 'Full ID: %s' % s,
                           'Full ID', 'FID']])

            # Bit 12: Substitute remote request (SRR) bit
            self.put12([9, ['Substitute remote request: %d' % self.bits[12],
                            'SRR: %d' % self.bits[12], 'SRR']])

        # Bit 32: Remote transmission request (RTR) bit
        # Data frame: dominant, remote frame: recessive
        # Remote frames do not contain a data field.

        # Remember start of RTR (see below).
        if bitnum == 32:
            self.ss_bit32 = self.samplenum
            self.rtr = can_rx

            if not self.fd:
                rtr = 'remote' if can_rx == 1 else 'data'
                self.putx([8, ['Remote transmission request: %s frame' % rtr,
                              'RTR: %s frame' % rtr, 'RTR']])
                self.rtr_type = rtr

        # Bit 33: RB1 (reserved bit)
        elif bitnum == 33:
            self.fd = True if can_rx else False
            if self.fd:
                self.dlc_start = 37
                self.putx([7, ['Flexible data format: %d' % can_rx,
                               'FDF: %d' % can_rx, 'FDF']])
                self.put32([7, ['Reserved bit 1: %d' % self.rtr,
                                'RB1: %d' % self.rtr, 'RB1']])
            else:
                self.putx([7, ['Reserved bit 1: %d' % can_rx,
                               'RB1: %d' % can_rx, 'RB1']])

        # Bit 34: RB0 (reserved bit)
        elif bitnum == 34:
            self.putx([7, ['Reserved bit 0: %d' % can_rx,
                           'RB0: %d' % can_rx, 'RB0']])

        elif bitnum == 35 and self.fd:
            data = [7, ['Bit rate switch: %d' % can_rx,
                        'BRS: %d' % can_rx, 'BRS']]

            if self.brs:
                from_bitrate = self.options['nominal_bitrate']
                from_spp = self.options['nominal_sample_point']
                to_bitrate = self.options['fd_bitrate']
                to_spp = self.options['fd_sample_point']

                self.putx_brs(from_bitrate, from_spp, to_bitrate, to_spp, data)
            else:
                self.putx(data)

        elif bitnum == 36 and self.fd:
            self.putx([7, ['Error state indicator: %d' % can_rx,
                           'ESI: %d' % can_rx, 'ESI']])

        # Remember start of DLC (see below).
        elif bitnum == self.dlc_start:
            self.ss_block = self.samplenum

        # Bits 35-38: Data length code (DLC), in number of bytes (0-8).
        elif bitnum == self.dlc_start + 3:
            self.set_dlc_and_crc_len(bitpack_msb(self.bits[self.dlc_start:self.dlc_start + 4]))
            self.putb([10, ['Data length code: %d' % self.dlc,
                            'DLC: %d' % self.dlc, 'DLC']])
            self.last_databit = self.dlc_start + 3 + (dlc2len(self.dlc) * 8)
            self.crc_start = self.last_databit + 1

            if self.fd:
                self.crc_start += 4 # Skip SBC field

        # Remember all databyte bits, except the very last one.
        elif bitnum in range(self.dlc_start + 4, self.last_databit):
            self.ss_databytebits.append(self.samplenum)

        # Bits 39-X: Data field (0-8 bytes, depending on DLC)
        # The bits within a data byte are transferred MSB-first.
        elif bitnum == self.last_databit:
            self.ss_databytebits.append(self.samplenum) # Last databyte bit.
            for i in range(dlc2len(self.dlc)):
                x = self.dlc_start + 4 + (8 * i)
                b = bitpack_msb(self.bits[x:x + 8])
                self.frame_bytes.append(b)
                ss = self.ss_databytebits[i * 8]
                es = self.ss_databytebits[((i + 1) * 8) - 1]
                self.putg(ss, es, [0, ['Data byte %d: 0x%02x' % (i, b),
                                       'DB %d: 0x%02x' % (i, b), 'DB']])
            self.ss_databytebits = []

        elif bitnum > self.last_databit:
            return self.decode_frame_end(can_rx, bitnum)

        return False

    def handle_bit(self, bitnum, can_rx):
        self.rawbits.append(can_rx)
        self.bits.append(can_rx)

        # If this is a stuff bit, remove it from self.bits and ignore it.
        if self.is_stuff_bit():
            self.putx([15, [str(can_rx)]])
            self.curbit += 1 # Increase self.curbit (bitnum is not affected).
            return
        else:
            if self.fd and can_rx and (bitnum == 16 and self.frame_type == 'standard'
                                    or bitnum == 35 and self.frame_type == 'extended'):
                from_bitrate = self.options['nominal_bitrate']
                from_spp = self.options['nominal_sample_point']
                to_bitrate = self.options['fd_bitrate']
                to_spp = self.options['fd_sample_point']

                self.putx_brs(from_bitrate, from_spp, to_bitrate, to_spp, [17, [str(can_rx)]])
            elif self.fd and self.brs and bitnum == (self.crc_start + self.crc_len):
                from_bitrate = self.options['fd_bitrate']
                from_spp = self.options['fd_sample_point']
                to_bitrate = self.options['nominal_bitrate']
                to_spp = self.options['nominal_sample_point']

                self.putx_brs(from_bitrate, from_spp, to_bitrate, to_spp, [17, [str(can_rx)]])
            else:
                self.putx([17, [str(can_rx)]])

        # Bit 0: Start of frame (SOF) bit
        if bitnum == 0:
            self.ss_packet = self.samplenum
            self.putx([1, ['Start of frame', 'SOF', 'S']])
            if can_rx != 0:
                self.putx([16, ['Start of frame (SOF) must be a dominant bit']])

        # Remember start of ID (see below).
        elif bitnum == 1:
            self.ss_block = self.samplenum

        # Bits 1-11: Identifier (ID[10..0])
        # The bits ID[10..4] must NOT be all recessive.
        elif bitnum == 11:
            # BEWARE! Don't clobber the decoder's .id field which is
            # part of its boiler plate!
            self.ident = bitpack_msb(self.bits[1:])
            self.fullid = self.ident
            s = '%d (0x%x)' % (self.ident, self.ident),
            self.putb([3, ['Identifier: %s' % s, 'ID: %s' % s, 'ID']])
            if (self.ident & 0x7f0) == 0x7f0:
                self.putb([16, ['Identifier bits 10..4 must not be all recessive']])

        # RTR or SRR bit, depending on frame type (gets handled later).
        elif bitnum == 12:
            # self.putx([0, ['RTR/SRR: %d' % can_rx]]) # Debug only.
            self.ss_bit12 = self.samplenum

        # Bit 13: Identifier extension (IDE) bit
        # Standard frame: dominant, extended frame: recessive
        elif bitnum == 13:
            ide = self.frame_type = 'standard' if can_rx == 0 else 'extended'
            self.putx([6, ['Identifier extension bit: %s frame' % ide,
                           'IDE: %s frame' % ide, 'IDE']])

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

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            # State machine.
            if self.state == 'IDLE':
                # Wait for a dominant state (logic 0) on the bus.
                (can_rx,) = self.wait({0: 'l'})
                self.sof = self.samplenum
                self.dom_edge_seen(force = True)
                self.state = 'GET BITS'
            elif self.state == 'GET BITS':
                bitnum = len(self.bits) # Get the index of the current CAN frame bit (without stuff bits).

                # Wait until we're in the correct bit/sampling position.
                pos = self.get_sample_point(self.curbit)
                (can_rx,) = self.wait([{'skip': pos - self.samplenum}, {0: 'f'}])

                if self.matched[1]:
                    self.dom_edge_seen()
                if self.matched[0]:
                    if self.fd:
                        # FD-BRS bit:
                        if can_rx and (bitnum == 16 and self.frame_type == 'standard'
                                    or bitnum == 35 and self.frame_type == 'extended'):
                            self.brs = True if can_rx else False

                            if self.brs:
                                self.set_fd_bitrate()

                        # FD-CRC delimiter
                        elif self.brs and bitnum == (self.crc_start + self.crc_len):
                            self.set_nominal_bitrate()

                    self.handle_bit(bitnum, can_rx)

                    if self.xl:
                        if bitnum == 17: # After ADH bit
                            self.set_xl_bitrate()
                        elif bitnum == self.crc_start + 35: # After last FCP bit
                            self.set_nominal_bitrate()