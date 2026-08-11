##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Gerhard Sittig <gerhard.sittig@gmx.net>
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

"""
OUTPUT_PYTHON format:

Packet:
(<ptype>, <pdata>)

This is the list of <ptype> codes and their respective <pdata> values:
 - 'HEADER': The data is the header byte's value.
 - 'PROPORTIONAL': The data is a tuple of the channel number (1-based)
   and the channel's value.
 - 'DIGITAL': The data is a tuple of the channel number (1-based)
   and the channel's value.
 - 'FLAG': The data is a tuple of the flag's name, and the flag's value.
 - 'FOOTER': The data is the footer byte's value.
 - 'TELEM_SLOT': The data is the telemetry slot byte.
 - 'TELEMETRY': The data is a tuple of (slot_nr, value_16bit).
 - 'TELEMETRY_VOLTAGE': The data is a tuple of (slot_nr, voltage_volts, type_flag).
 - 'TELEMETRY_CURRENT': The data is a tuple of (slot_nr, current_ma, type_flag).
"""

import sigrokdecode as srd

class Ann:
    """Annotation class enumerations for sigrokdecode output."""
    HEADER, PROPORTIONAL, DIGITAL, FRAME_LOST, FAILSAFE, FOOTER, \
    TELEM_SLOT, TELEM_DATA, WARN = range(9)
    FLAG_LSB = FRAME_LOST

class State:
    """Decoder state machine integer definitions."""
    FRAME = 0
    TELEM = 1

class Decoder(srd.Decoder):
    """
    Futaba SBUS and SBUS2 High-Performance Protocol Decoder for libsigrokdecode.

    Decodes 25-byte servo channel frames (channels 1-16 proportional, 17-18 digital,
    flags, failsafe) and 3-byte SBUS2 telemetry slots with sensor type flag decoding
    (0xC0 for Voltage in 0.1V steps, 0xC4 for Current in mA).
    """
    api_version = 3
    id = 'sbus_futaba'
    name = 'SBUS (Futaba)'
    longname = 'Futaba SBUS / SBUS2 (Serial bus)'
    desc = 'Serial bus for hobby remote control by Futaba (with SBUS2 telemetry support)'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = ['sbus_futaba']
    tags = ['Remote Control']
    options = (
        {'id': 'prop_val_min', 'desc': 'Proportional value lower boundary', 'default': 0},
        {'id': 'prop_val_max', 'desc': 'Proportional value upper boundary', 'default': 2047},
    )
    annotations = (
        ('header', 'Header'),
        ('proportional', 'Proportional'),
        ('digital', 'Digital'),
        ('framelost', 'Frame Lost'),
        ('failsafe', 'Failsafe'),
        ('footer', 'Footer'),
        ('telem-slot', 'Telemetry Slot'),
        ('telem-data', 'Telemetry Data'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('framing', 'Framing', (Ann.HEADER, Ann.FOOTER,
            Ann.FRAME_LOST, Ann.FAILSAFE)),
        ('channels', 'Channels', (Ann.PROPORTIONAL, Ann.DIGITAL)),
        ('telemetry', 'Telemetry', (Ann.TELEM_SLOT, Ann.TELEM_DATA)),
        ('warnings', 'Warnings', (Ann.WARN,)),
    )

    def __init__(self):
        """
        Brief: Initializes the decoder instance and byte buffer.
        Params: None
        Invariants: bytes_accum is empty list; state starts at State.FRAME.
        Output: None
        """
        self.bytes_accum = []
        self.msg_complete = None
        self.failed = None
        self.state = State.FRAME
        self.has_telem = False
        self.reset()

    def reset(self):
        """
        Brief: Resets state machine variables for a fresh frame sequence.
        Params: None
        Invariants: Clears bytes_accum; resets state to State.FRAME.
        Output: None
        """
        self.bytes_accum.clear()
        self.msg_complete = False
        self.failed = None
        self.state = State.FRAME
        self.has_telem = False

    def start(self):
        """
        Brief: Registers graphical and Python output channels with sigrokdecode framework.
        Params: None
        Invariants: Registers OUTPUT_ANN and OUTPUT_PYTHON streams.
        Output: None
        """
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

    def putg(self, ss, es, data):
        """
        Brief: Emits graphical annotations to the GUI for sample range [ss, es].
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            data (list): [annotation_class, text_list].
        Invariants: ss <= es.
        Output: None
        """
        self.put(ss, es, self.out_ann, data)

    def putpy(self, ss, es, data):
        """
        Brief: Emits Python output data structures to upper-layer decoders for [ss, es].
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            data (list/tuple): [packet_type, payload].
        Invariants: ss <= es.
        Output: None
        """
        self.put(ss, es, self.out_py, data)

    def _process_telem(self):
        """
        Brief: Decodes 3-byte SBUS2 telemetry slots (Slot ID + Data Byte 1 + Data Byte 2).
               Data Byte 1 acts as a sensor type indicator (0xC0 = Voltage, 0xC4 = Current).
               Data Byte 2 contains the corresponding measurement value.
        Params: None
        Invariants: Operates during State.TELEM. Switches to State.FRAME if 0x0F header is received.
        Output: None
        """
        while self.bytes_accum:
            if self.bytes_accum[0][0] == 0x0f:
                self.state = State.FRAME
                self.msg_complete = False
                self.has_telem = False
                self._process_frame()
                return

            if len(self.bytes_accum) < 3:
                return

            telem_bytes = self.bytes_accum[:3]
            del self.bytes_accum[:3]

            b_slot, ss_s, es_s = telem_bytes[0]
            b_lsb, ss_l, es_l = telem_bytes[1]
            b_msb, ss_m, es_m = telem_bytes[2]

            slot_nr = b_slot
            ss_data, es_data = ss_l, es_m

            if b_lsb == 0xc0:
                v_val = b_msb / 10.0
                text_slot = ['Slot {:d} (Voltage)'.format(slot_nr), 'Slot {:d}'.format(slot_nr), 'S{:d}'.format(slot_nr)]
                text_data = [
                    'Voltage: {:.1f}V (Flag: 0x{:02x})'.format(v_val, b_lsb),
                    'Voltage: {:.1f}V'.format(v_val),
                    '{:.1f}V'.format(v_val)
                ]
                self.putg(ss_s, es_s, [Ann.TELEM_SLOT, text_slot])
                self.putpy(ss_s, es_s, ['TELEM_SLOT', slot_nr])

                self.putg(ss_data, es_data, [Ann.TELEM_DATA, text_data])
                self.putpy(ss_data, es_data, ['TELEMETRY_VOLTAGE', (slot_nr, v_val, b_lsb)])

            elif b_lsb == 0xc4:
                c_val = float(b_msb)
                text_slot = ['Slot {:d} (Current)'.format(slot_nr), 'Slot {:d}'.format(slot_nr), 'S{:d}'.format(slot_nr)]
                text_data = [
                    'Current: {:.1f} mA (Flag: 0x{:02x})'.format(c_val, b_lsb),
                    'Current: {:.1f} mA'.format(c_val),
                    '{:.1f} mA'.format(c_val)
                ]
                self.putg(ss_s, es_s, [Ann.TELEM_SLOT, text_slot])
                self.putpy(ss_s, es_s, ['TELEM_SLOT', slot_nr])

                self.putg(ss_data, es_data, [Ann.TELEM_DATA, text_data])
                self.putpy(ss_data, es_data, ['TELEMETRY_CURRENT', (slot_nr, c_val, b_lsb)])

            else:
                val_16 = b_lsb | (b_msb << 8)
                text_slot = ['Slot {:d} (0x{:02x})'.format(slot_nr, slot_nr), 'Slot {:d}'.format(slot_nr), 'S{:d}'.format(slot_nr)]
                text_data = ['Val: {:d} (0x{:04x})'.format(val_16, val_16), '{:d}'.format(val_16)]
                self.putg(ss_s, es_s, [Ann.TELEM_SLOT, text_slot])
                self.putpy(ss_s, es_s, ['TELEM_SLOT', slot_nr])

                self.putg(ss_data, es_data, [Ann.TELEM_DATA, text_data])
                self.putpy(ss_data, es_data, ['TELEMETRY', (slot_nr, val_16)])

    def _process_frame(self):
        """
        Brief: Decodes 25-byte SBUS/SBUS2 servo channel frames directly from bytes_accum with bit-precise sample alignment.
        Params: None
        Invariants: Waits for 25 bytes starting with Header 0x0F. Syncs to 0x0F if misaligned.
        Output: None
        """
        while self.bytes_accum and self.bytes_accum[0][0] != 0x0f:
            val, ss, es = self.bytes_accum.pop(0)
            text = ['Unexpected byte 0x{:02x}'.format(val), 'Header']
            self.putg(ss, es, [Ann.WARN, text])

        if len(self.bytes_accum) < 25:
            return

        frame_bytes = self.bytes_accum[:25]
        del self.bytes_accum[:25]

        # 1. Header (Byte 0)
        val, ss, es = frame_bytes[0]
        self.putg(ss, es, [Ann.HEADER, ['0x{:02x}'.format(val)]])
        self.putpy(ss, es, ['HEADER', val])

        # 2. 16 Proportional channels (Bytes 1..22)
        payload = [b[0] for b in frame_bytes[1:23]]
        for i in range(16):
            bit_start = i * 11
            bit_end = bit_start + 11

            byte_idx = bit_start >> 3
            bit_shift = bit_start & 7

            b0 = payload[byte_idx]
            b1 = payload[byte_idx + 1]
            b2 = payload[byte_idx + 2] if (byte_idx + 2 < 22) else 0

            ch_val = ((b0 | (b1 << 8) | (b2 << 16)) >> bit_shift) & 0x7ff

            # Bit-precise sample boundary calculation (UART 8E2 = 12 bit periods per byte: 1 start + 8 data + 1 parity + 2 stop)
            b_start_idx = 1 + (bit_start >> 3)
            b_start_ss, b_start_es = frame_bytes[b_start_idx][1], frame_bytes[b_start_idx][2]
            dur_start = (b_start_es - b_start_ss) / 12.0
            ch_ss = b_start_ss + int((1 + (bit_start & 7)) * dur_start)

            b_end_idx = 1 + ((bit_end - 1) >> 3)
            b_end_ss, b_end_es = frame_bytes[b_end_idx][1], frame_bytes[b_end_idx][2]
            dur_end = (b_end_es - b_end_ss) / 12.0
            ch_es = b_end_ss + int((2 + ((bit_end - 1) & 7)) * dur_end)

            ch_nr = 1 + i
            text = ['{:d}'.format(ch_val)]
            self.putg(ch_ss, ch_es, [Ann.PROPORTIONAL, text])
            if ch_val < self.options['prop_val_min']:
                self.putg(ch_ss, ch_es, [Ann.WARN, ['Low proportional value', 'Low']])
            elif ch_val > self.options['prop_val_max']:
                self.putg(ch_ss, ch_es, [Ann.WARN, ['High proportional value', 'High']])
            self.putpy(ch_ss, ch_es, ['PROPORTIONAL', (ch_nr, ch_val)])

        # 3. Digital channels & Flags (Byte 23)
        flags_val, flags_ss, flags_es = frame_bytes[23]
        dur_flags = (flags_es - flags_ss) / 12.0

        d17 = (flags_val >> 0) & 1
        d18 = (flags_val >> 1) & 1
        flst = (flags_val >> 2) & 1
        fsafe = (flags_val >> 3) & 1
        msb_flg = (flags_val >> 4) & 0x0f

        # Bit 0: Digital Ch 17
        ss_d17 = flags_ss + int(1 * dur_flags)
        es_d17 = flags_ss + int(2 * dur_flags)
        self.putg(ss_d17, es_d17, [Ann.DIGITAL, ['{:d}'.format(d17)]])
        self.putpy(ss_d17, es_d17, ['DIGITAL', (17, d17)])

        # Bit 1: Digital Ch 18
        ss_d18 = flags_ss + int(2 * dur_flags)
        es_d18 = flags_ss + int(3 * dur_flags)
        self.putg(ss_d18, es_d18, [Ann.DIGITAL, ['{:d}'.format(d18)]])
        self.putpy(ss_d18, es_d18, ['DIGITAL', (18, d18)])

        # Bit 2: Frame Lost
        ss_flst = flags_ss + int(3 * dur_flags)
        es_flst = flags_ss + int(4 * dur_flags)
        self.putg(ss_flst, es_flst, [Ann.FRAME_LOST, ['{:d}'.format(flst)]])
        self.putpy(ss_flst, es_flst, ['FLAG', ('framelost', flst)])

        # Bit 3: Failsafe
        ss_fsafe = flags_ss + int(4 * dur_flags)
        es_fsafe = flags_ss + int(5 * dur_flags)
        self.putg(ss_fsafe, es_fsafe, [Ann.FAILSAFE, ['{:d}'.format(fsafe)]])
        self.putpy(ss_fsafe, es_fsafe, ['FLAG', ('failsafe', fsafe)])

        # Bits 4..7: MSB flags
        ss_msb = flags_ss + int(5 * dur_flags)
        es_msb = flags_ss + int(9 * dur_flags)
        if msb_flg != 0:
            self.putg(ss_msb, es_msb, [Ann.WARN, ['Unexpected MSB flags', 'Flags']])
        self.putpy(ss_msb, es_msb, ['FLAG', ('msb', msb_flg)])

        # 4. Footer (Byte 24)
        ftr_val, ftr_ss, ftr_es = frame_bytes[24]
        if ftr_val == 0x00:
            text = ['0x00 (Standard)', '0x00']
            self.has_telem = False
        elif (ftr_val & 0x0f) == 0x04:
            slot_base = (ftr_val >> 4) * 8
            text = ['0x{:02x} (Slots {}-{})'.format(ftr_val, slot_base, slot_base + 7), '0x{:02x}'.format(ftr_val)]
            self.has_telem = True
        else:
            text = ['Unexpected footer 0x{:02x}'.format(ftr_val), '0x{:02x}'.format(ftr_val)]
            self.putg(ftr_ss, ftr_es, [Ann.WARN, text])
            self.has_telem = False

        self.putg(ftr_ss, ftr_es, [Ann.FOOTER, text])
        self.putpy(ftr_ss, ftr_es, ['FOOTER', ftr_val])

        self.msg_complete = True
        if self.has_telem:
            self.state = State.TELEM
            if self.bytes_accum:
                self.process_bytes()

    def process_bytes(self):
        """
        Brief: Processes accumulated UART bytes according to current decoder state (FRAME or TELEM).
        Params: None
        Invariants: Dispatches to _process_frame or _process_telem based on self.state.
        Output: None
        """
        if self.failed:
            return

        if self.state == State.TELEM:
            self._process_telem()
        elif self.state == State.FRAME:
            self._process_frame()

    def handle_frame(self, ss, es, value, valid):
        """
        Brief: Receives a complete UART byte (value, valid, ss, es) and buffers it.
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            value (int): Byte value (0x00..0xFF).
            valid (bool): Framing/parity validity.
        Invariants: Accumulates byte tuples (val, ss, es) into self.bytes_accum.
        Output: None
        """
        if not valid:
            self.failed = ['Invalid data', 'Invalid']
            return

        self.bytes_accum.append((value, ss, es))
        self.process_bytes()

    def handle_idle(self, ss, es):
        """
        Brief: Handles UART IDLE gaps between frames/telemetry windows.
        Params:
            ss (int): Start sample index of IDLE period.
            es (int): End sample index of IDLE period.
        Invariants: Resets state in State.FRAME if incomplete; allows idle in State.TELEM.
        Output: None
        """
        if self.state == State.FRAME:
            if self.bytes_accum and not self.failed:
                self.putg(self.bytes_accum[0][1], self.bytes_accum[-1][2], [Ann.WARN, ['Unprocessed bytes', 'Unprocessed']])
            self.reset()
        elif self.state == State.TELEM:
            pass

    def handle_break(self, ss, es):
        """
        Brief: Handles UART BREAK condition on line, logs warning, and resets state.
        Params:
            ss (int): Start sample index of BREAK.
            es (int): End sample index of BREAK.
        Invariants: Marks self.failed and calls reset().
        Output: None
        """
        if not self.failed:
            self.failed = ['BREAK condition', 'Break']
        self.handle_idle(None, None)
        text = ['BREAK condition', 'Break']
        self.putg(ss, es, [Ann.WARN, text])
        self.reset()

    def decode(self, ss, es, data):
        """
        Brief: Main entry point called by sigrokdecode engine for incoming UART events.
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            data (tuple): (ptype, rxtx, pdata) event tuple from UART decoder.
        Invariants: Dispatches FRAME, IDLE, or BREAK events. Ignores raw bit stream DATA.
        Output: None
        """
        ptype, rxtx, pdata = data
        if ptype == 'FRAME':
            value, valid = pdata
            self.handle_frame(ss, es, value, valid)
        elif ptype == 'IDLE':
            self.handle_idle(ss, es)
        elif ptype == 'BREAK':
            self.handle_break(ss, es)
