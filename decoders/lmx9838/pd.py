##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2026 BrLumen <igflocal@gmail.com>
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

import sigrokdecode as srd

STX, ETX = 0x02, 0x03
MAX_DATA_LEN = 333

PTYPES = {
    0x52: ('REQ', 'Request'),
    0x43: ('CFM', 'Confirm'),
    0x69: ('IND', 'Indication'),
    0x72: ('RES', 'Response'),
}

# AN-1699 (SNOA498B), Table 93 'Opcode Values'.
OPCODES = {
    0x00: 'GAP_INQUIRY',
    0x01: 'GAP_DEVICE_FOUND',
    0x02: 'GAP_REMOTE_DEVICE_NAME',
    0x03: 'GAP_READ_LOCAL_NAME',
    0x04: 'GAP_WRITE_LOCAL_NAME',
    0x05: 'GAP_READ_LOCAL_BDA',
    0x06: 'GAP_SET_SCANMODE',
    0x07: 'SPP_SET_PORT_CONFIG',
    0x08: 'SPP_GET_PORT_CONFIG',
    0x09: 'SPP_PORT_CONFIG_CHANGED',
    0x0A: 'SPP_ESTABLISH_LINK',
    0x0B: 'SPP_LINK_ESTABLISHED',
    0x0C: 'SPP_INCOMING_LINK_ESTABLISHED',
    0x0D: 'SPP_RELEASE_LINK',
    0x0E: 'SPP_LINK_RELEASED',
    0x0F: 'SPP_SEND_DATA',
    0x10: 'SPP_INCOMING_DATA',
    0x11: 'SPP_TRANSPARENT_MODE',
    0x12: 'SPP_CONNECT_DEFAULT_CON',
    0x13: 'SPP_STORE_DEFAULT_CON',
    0x14: 'SPP_GET_LIST_DEFAULT_CON',
    0x15: 'SPP_DELETE_DEFAULT_CON',
    0x16: 'GAP_GET_FIXED_PIN',
    0x17: 'GAP_SET_FIXED_PIN',
    0x18: 'GAP_GET_SECURITY_MODE',
    0x19: 'GAP_SET_SECURITY_MODE',
    0x1A: 'RESTORE_FACTORY_SETTINGS',
    0x1B: 'GAP_REMOVE_PAIRING',
    0x1C: 'GAP_LIST_PAIRED_DEVICES',
    0x1D: 'FORCE_MASTER_ROLE',
    0x1E: 'SDAP_SERVICE_REQUEST',
    0x1F: 'GET_PORTS_TO_OPEN',
    0x20: 'READ_RSSI',
    0x21: 'GAP_ENTER_SNIFF_MODE',
    0x22: 'SET_PORTS_TO_OPEN',
    0x23: 'CHANGE_NVS_UART_SPEED',
    0x24: 'TEST_MODE',
    0x25: 'LMX9838_READY',
    0x26: 'RESET',
    0x27: 'CHANGE_LOCAL_BDADDRESS',
    0x28: 'STORE_CLASS_OF_DEVICE',
    0x29: 'ENABLE_SDP_RECORD',
    0x2A: 'DELETE_SDP_RECORDS',
    0x31: 'STORE_SDP_RECORD',
    0x32: 'SDAP_CONNECT',
    0x33: 'SDAP_DISCONNECT',
    0x34: 'SDAP_CONNECTION_LOST',
    0x35: 'SDAP_SERVICE_BROWSE',
    0x36: 'SDAP_SERVICE_SEARCH',
    0x37: 'GAP_EXIT_SNIFF_MODE',
    0x38: 'GAP_ENTER_PARK_MODE',
    0x39: 'GAP_EXIT_PARK_MODE',
    0x3A: 'GAP_ENTER_HOLD_MODE',
    0x3B: 'GAP_SET_LINK_POLICY',
    0x3C: 'GAP_GET_LINK_POLICY',
    0x3D: 'GAP_POWER_SAVE_MODE_CHANGED',
    0x3E: 'SPP_PORT_STATUS_CHANGED',
    0x3F: 'SDAP_ATTRIBUTE_REQUEST',
    0x40: 'SPP_GET_PORT_STATUS',
    0x41: 'SPP_PORT_SET_DTR',
    0x42: 'SPP_PORT_SET_RTS',
    0x43: 'SPP_PORT_BREAK',
    0x44: 'SPP_PORT_OVERRUN_ERROR',
    0x45: 'SPP_PORT_PARITY_ERROR',
    0x46: 'SPP_PORT_FRAMING_ERROR',
    0x47: 'WRITE_ROM_PATCH',
    0x48: 'CHANGE_UART_SETTINGS',
    0x49: 'READ_OPERATION_MODE',
    0x4A: 'WRITE_OPERATION_MODE',
    0x4B: 'RF_TEST_MODE',
    0x4C: 'SET_DEFAULT_LINK_POLICY',
    0x4D: 'GET_DEFAULT_LINK_POLICY',
    0x4E: 'SET_EVENT_FILTER',
    0x4F: 'GET_EVENT_FILTER',
    0x50: 'GAP_ACL_ESTABLISHED',
    0x51: 'GAP_ACL_TERMINATED',
    0x52: 'DISABLE_TL',
    0x53: 'TL_ENABLED',
    0x55: 'SET_DEFAULT_LINK_TIMEOUT',
    0x56: 'GET_DEFAULT_LINK_TIMEOUT',
    0x57: 'SPP_SET_LINK_TIMEOUT',
    0x58: 'SPP_GET_LINK_TIMEOUT',
    0x59: 'GAP_SET_AUDIO_CONFIG',
    0x5A: 'GAP_GET_AUDIO_CONFIG',
    0x5B: 'SET_DEFAULT_AUDIO_CONFIG',
    0x5C: 'GET_DEFAULT_AUDIO_CONFIG',
    0x5D: 'GAP_ESTABLISH_SCO_LINK',
    0x5E: 'GAP_RELEASE_SCO_LINK',
    0x5F: 'GAP_MUTE_MIC',
    0x60: 'GAP_SET_VOLUME',
    0x61: 'GAP_GET_VOLUME',
    0x62: 'GAP_CHANGE_SCO_PACKET_TYPE',
    0x63: 'SET_DEFAULT_LINK_LATENCY',
    0x64: 'GET_DEFAULT_LINK_LATENCY',
    0x65: 'HCI_COMMAND',
    0x66: 'AWAIT_INITIALIZATION_EVENT',
    0x67: 'SET_CLOCK_FREQUENCY',
    0x68: 'GET_CLOCK_FREQUENCY',
    0x69: 'SET_CLOCK_AND_BAUDRATE',
    0x6B: 'SET_GPIO_WPU',
    0x6C: 'GET_GPIO_STATE',
    0x6D: 'SET_GPIO_DIRECTION',
    0x6E: 'SET_GPIO_OUTPUT_HIGH',
    0x6F: 'SET_GPIO_OUTPUT_LOW',
    0x72: 'READ_NVS',
    0x73: 'WRITE_NVS',
    0x74: 'SET_PCM_SLAVE_CONFIG',
    0x75: 'GAP_GET_PIN',
}

# AN-1699, Table 298 'Generic Error Codes'.
ERRORS = {
    0x00: 'OK',
    0x01: 'INVALID_NO_OF_PARAMETERS',
    0x02: 'DURATION_OUT_OF_RANGE',
    0x03: 'INVALID_MODE',
    0x04: 'TIMEOUT',
    0x05: 'UNKNOWN_ERROR',
    0x06: 'NAME_TOO_LONG',
    0x07: 'INVALID_DISCOVERABILITY_PARAMETER',
    0x08: 'INVALID_CONNECTABILITY_PARAMETER',
    0x09: 'INVALID_SECURITY_MODE',
    0x0A: 'LINKKEY_DOES_NOT_EXISTS',
    0x0B: 'CONNECTION_FAILED',
    0x0C: 'TRUNCATED_ANSWER',
    0x0D: 'RESULT_TOO_LARGE',
    0x0E: 'NOT_POSSIBLE_TO_ENTER_TESTMODE',
    0x0F: 'ILLEGAL_TESTMODE',
    0x10: 'RESET_TO_TI_BDADDRESS',
    0x11: 'UART_SPEED_OUT_OF_RANGE',
    0x12: 'INVALID_PORT',
    0x13: 'ILLEGAL_STATE_VALUE',
    0x14: 'IDENTIFIER_OUT_OF_RANGE',
    0x15: 'RECORD_ALREADY_IN_SELECTED_STATE',
    0x16: 'INVALID_AUTHENTICATION_VALUE',
    0x17: 'INVALID_ENCRYPTION_VALUE',
    0x18: 'MAXIMUM_NO_OF_SERVICE_RECORDS_REACHED',
    0x19: 'WRITING_TO_NVS',
    0x1A: 'INVALID_ROLE',
    0x1B: 'LIMIT',
    0x1C: 'UNEXPECTED',
    0x1D: 'UNABLE_TO_SEND',
    0x1E: 'CURRENTLY_NO_BUFFER',
    0x1F: 'NO_CONNECTION',
    0x20: 'SPP_INVALID_PORT',
    0x21: 'SPP_PORT_NOT_OPEN',
    0x22: 'SPP_PORT_BUSY',
    0x23: 'SPP_MULTIPLE_CONNECTIONS',
    0x24: 'SPP_MULTIPLE_TRANSPARENT',
    0x25: 'SPP_DEFAULT_CONNECTION_NOT_STORED',
    0x26: 'SPP_AUTOMATIC_CONNECTIONS_PROGRESSING',
    0x27: 'UNSPECIFIED_ERROR',
    0x28: 'IDENTIFIER_NOT_IN_USE',
    0x29: 'INVALID_SUPPORTED_FAXCLASS_VALUE',
    0x2A: 'TOO_MANY_SUPPORTED_FORMATS',
    0x2B: 'TOO_MANY_DATASTORES',
    0x2C: 'ATTEMPT_FAILED',
    0x2D: 'ILLEGAL_LINK_POLICY',
    0x2E: 'PINCODE_TOO_LONG',
    0x2F: 'PARITY_BIT_OUT_OF_RANGE',
    0x30: 'STOP_BITS_OUT_OF_RANGE',
    0x31: 'ILLEGAL_LINK_TIMEOUT',
    0x32: 'COMMAND_DISALLOWED',
    0x33: 'ILLEGAL_AUDIO_CODEC_TYPE',
    0x34: 'ILLEGAL_AUDIO_AIR_FORMAT',
    0x35: 'SDP_RECORD_TOO_LONG',
    0x36: 'SDP_FAILED_TO_CREATE_RECORD',
    0x37: 'SET_VOLUME_FAILED',
    0x38: 'ILLEGAL_PACKET_TYPE',
    0x39: 'INVALID_CODEC_SETTING',
}

UART_SPEEDS = ['2400', '4800', '7200', '9600', '19200', '38400', '57600',
               '115200', '230400', '460800', '921600']

# Data layouts, keyed by (opcode, packet type). Each entry is a list of
# (label, kind); kinds are handled by Decoder.parse_field(). Whatever is not
# listed here is shown as a raw hex dump (CFM packets get a Status byte first).
STATUS = ('Status', 'status')
BDA = ('BdAddr', 'bda')
PORT = ('LocalPort', 'u8')
LAYOUTS = {
    (0x00, 'REQ'): [('Duration', 'u8'), ('NumResponses', 'u8'),
                    ('Mode', 'u8')],
    (0x01, 'IND'): [BDA, ('DeviceClass', 'u24')],
    (0x02, 'REQ'): [BDA],
    (0x02, 'CFM'): [STATUS, BDA, ('Name', 'lstr')],
    (0x03, 'CFM'): [STATUS, ('Name', 'lstr')],
    (0x04, 'REQ'): [('Name', 'lstr')],
    (0x05, 'CFM'): [STATUS, BDA],
    (0x06, 'REQ'): [('Connectable', 'u8'), ('Discoverable', 'u8')],
    (0x0A, 'REQ'): [PORT, BDA, ('RemotePort', 'u8')],
    (0x0A, 'CFM'): [STATUS, PORT],
    (0x0B, 'IND'): [STATUS, BDA, PORT, ('RemotePort', 'u8')],
    (0x0C, 'IND'): [BDA, PORT],
    (0x0D, 'REQ'): [PORT],
    (0x0D, 'CFM'): [STATUS, PORT],
    (0x0E, 'IND'): [('Reason', 'u8'), PORT],
    (0x0F, 'REQ'): [PORT, ('Payload', 'lpayload')],
    (0x0F, 'CFM'): [STATUS, PORT],
    (0x10, 'IND'): [PORT, ('Payload', 'lpayload')],
    (0x11, 'REQ'): [PORT],
    (0x11, 'CFM'): [STATUS, PORT],
    (0x11, 'IND'): [PORT, ('Mode', 'u8')],
    (0x17, 'REQ'): [('PIN', 'lstr')],
    (0x19, 'REQ'): [('Mode', 'u8')],
    (0x22, 'REQ'): [('Ports', 'u32')],
    (0x23, 'REQ'): [('UartSpeed', 'baud')],
    (0x25, 'IND'): [('Version', 'lstr')],
    (0x27, 'REQ'): [BDA],
    (0x49, 'CFM'): [STATUS, ('Mode', 'u8')],
    (0x4A, 'REQ'): [('Mode', 'u8')],
    (0x50, 'IND'): [BDA],
    (0x51, 'IND'): [BDA, ('Reason', 'u8')],
    (0x75, 'IND'): [BDA],
    (0x75, 'REQ'): [BDA, ('PIN', 'lstr')],
}

# Annotation class indices, per direction (rxtx * NCLS + index).
(A_STX, A_PTYPE, A_OPCODE, A_LEN, A_CSUM, A_DATA, A_ETX, A_FIELD,
    A_PACKET) = range(9)
NCLS = 9
A_WARN, A_TXN, A_EVENT = 2 * NCLS, 2 * NCLS + 1, 2 * NCLS + 2

# Sizes of fixed-length data field kinds.
FIXED_SIZE = {'u8': 1, 'status': 1, 'baud': 1, 'u16': 2, 'u24': 3, 'u32': 4,
              'bda': 6}

def hexdump(d):
    return ' '.join('%02X' % b for b in d)

def asciidump(d):
    return ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in d)

def le_int(d):
    return int.from_bytes(bytes(d), 'little')

class Decoder(srd.Decoder):
    api_version = 3
    id = 'lmx9838'
    name = 'LMX9838'
    longname = 'Texas Instruments LMX9838 SimplyBlue'
    desc = 'Bluetooth SPP module command protocol (AN-1699).'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = []
    tags = ['Wireless/RF']
    annotations = (
        ('rx-stx', 'RX STX'),
        ('rx-ptype', 'RX packet type'),
        ('rx-opcode', 'RX opcode'),
        ('rx-len', 'RX data length'),
        ('rx-csum', 'RX checksum'),
        ('rx-data', 'RX data byte'),
        ('rx-etx', 'RX ETX'),
        ('rx-field', 'RX field'),
        ('rx-packet', 'RX packet'),
        ('tx-stx', 'TX STX'),
        ('tx-ptype', 'TX packet type'),
        ('tx-opcode', 'TX opcode'),
        ('tx-len', 'TX data length'),
        ('tx-csum', 'TX checksum'),
        ('tx-data', 'TX data byte'),
        ('tx-etx', 'TX ETX'),
        ('tx-field', 'TX field'),
        ('tx-packet', 'TX packet'),
        ('warning', 'Warning'),
        ('transaction', 'Request/confirm transaction'),
        ('event', 'Indication/response event'),
    )
    annotation_rows = (
        ('rx-frames', 'RX frames', tuple(range(A_STX, A_ETX + 1))),
        ('rx-packets', 'RX packets', (A_PACKET,)),
        ('rx-fields', 'RX fields', (A_FIELD,)),
        ('tx-frames', 'TX frames',
            tuple(range(NCLS + A_STX, NCLS + A_ETX + 1))),
        ('tx-packets', 'TX packets', (NCLS + A_PACKET,)),
        ('tx-fields', 'TX fields', (NCLS + A_FIELD,)),
        ('transactions', 'Transactions', (A_TXN,)),
        ('events', 'Events', (A_EVENT,)),
        ('warnings', 'Warnings', (A_WARN,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.pkt = [self.new_packet(), self.new_packet()]
        # Opcode -> (ss, request summary) of REQs still awaiting their CFM.
        self.pending = {}

    def new_packet(self):
        return {
            'state': 'STX',
            'ss': None,      # Start sample of the whole packet.
            'ptype': None,   # (short, long) name of the packet type.
            'opcode': None,
            'len': 0,
            'len_ss': None,
            'hdr_sum': 0,    # Running checksum of the header bytes.
            'data': [],      # Data bytes.
            'pos': [],       # (ss, es) per data byte.
        }

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putx(self, ss, es, rxtx, cls, texts):
        self.put(ss, es, self.out_ann, [rxtx * NCLS + cls, texts])

    def warn(self, ss, es, text):
        self.put(ss, es, self.out_ann, [A_WARN, [text]])

    def parse_field(self, kind, d, i):
        '''Returns (text, size) or None if the data is too short.'''
        n = len(d) - i
        size = FIXED_SIZE.get(kind)
        if kind == 'lstr':
            size = 1 + d[i] if n >= 1 else None
        elif kind == 'lpayload':
            size = 2 + le_int(d[i:i + 2]) if n >= 2 else None
        if size is None or n < size:
            return None
        v = d[i:i + size]
        if kind == 'status':
            text = ERRORS.get(v[0], '0x%02X' % v[0])
        elif kind == 'baud':
            text = UART_SPEEDS[v[0]] if v[0] < len(UART_SPEEDS) \
                else '0x%02X' % v[0]
        elif kind == 'bda':
            text = ':'.join('%02X' % b for b in reversed(v))
        elif kind == 'lstr':
            text = '"%s"' % asciidump(v[1:]).rstrip('.')
        elif kind == 'lpayload':
            text = '%d bytes: %s [%s]' % (size - 2, hexdump(v[2:]),
                                          asciidump(v[2:]))
        elif kind == 'u16':
            text = '%d' % le_int(v)
        else:
            text = '0x%0*X' % (2 * size, le_int(v))
        return text, size

    def emit_fields(self, rxtx, p):
        '''Annotates the data area and returns a summary string.'''
        d, pos = p['data'], p['pos']
        ptype = p['ptype'][0]
        layout = LAYOUTS.get((p['opcode'], ptype))
        if layout is None:
            layout = [STATUS] if ptype == 'CFM' else []
        parts, i = [], 0
        for label, kind in layout:
            r = self.parse_field(kind, d, i)
            if not r:
                self.warn(pos[i][0] if i < len(d) else p['ss'],
                          pos[-1][1] if pos else p['ss'],
                          'Data too short for field %s' % label)
                break
            text, size = r
            self.putx(pos[i][0], pos[i + size - 1][1], rxtx, A_FIELD,
                      ['%s: %s' % (label, text), text])
            parts.append('%s=%s' % (label, text))
            i += size
            if kind == 'status' and d[i - 1] != 0:
                break # On error the remaining fields are omitted.
        if i < len(d):
            rest = d[i:]
            self.putx(pos[i][0], pos[-1][1], rxtx, A_FIELD,
                      ['Data: %s [%s]' % (hexdump(rest), asciidump(rest)),
                       hexdump(rest)])
            parts.append(hexdump(rest))
        return ', '.join(parts)

    def emit_packet(self, rxtx, es):
        p = self.pkt[rxtx]
        ptype = p['ptype'][0]
        opname = OPCODES.get(p['opcode'], '0x%02X' % p['opcode'])
        summary = self.emit_fields(rxtx, p)
        full = '%s %s' % (ptype, opname)
        if summary:
            full += ': ' + summary
        self.putx(p['ss'], es, rxtx, A_PACKET,
                  [full, '%s %s' % (ptype, opname),
                   '%s %02X' % (ptype, p['opcode'])])
        self.track_transaction(p, ptype, opname, summary, es)

    def duration(self, ss, es):
        if not self.samplerate:
            return ''
        t = (es - ss) / self.samplerate
        if t >= 1e-3:
            return ' (%.1f ms)' % (t * 1e3)
        return ' (%.0f us)' % (t * 1e6)

    def track_transaction(self, p, ptype, opname, summary, es):
        op = p['opcode']
        if ptype == 'REQ':
            if op in self.pending:
                self.warn(self.pending[op][0], p['ss'],
                          'REQ %s without CFM' % opname)
            self.pending[op] = (p['ss'], summary)
        elif ptype == 'CFM':
            if op not in self.pending:
                self.warn(p['ss'], es, 'CFM %s without REQ' % opname)
                return
            req_ss, req_summary = self.pending.pop(op)
            result = summary.replace('Status=', '', 1) or 'OK'
            req = '(%s)' % req_summary if req_summary else ''
            self.put(req_ss, es, self.out_ann, [A_TXN, [
                '%s%s -> %s%s' % (opname, req, result,
                                  self.duration(req_ss, es)),
                '%s -> %s' % (opname, result.split(',')[0]),
                opname]])
        else:
            self.put(p['ss'], es, self.out_ann, [A_EVENT, [
                '%s %s%s' % (ptype, opname, ': ' + summary if summary else ''),
                '%s %s' % (ptype, opname), opname]])

    def decode(self, ss, es, data):
        ptype, rxtx, pdata = data
        if ptype != 'DATA':
            return
        b = pdata[0]
        p = self.pkt[rxtx]
        st = p['state']
        if st == 'STX':
            if b != STX:
                return
            self.pkt[rxtx] = p = self.new_packet()
            p['ss'] = ss
            self.putx(ss, es, rxtx, A_STX, ['STX', 'S'])
            p['state'] = 'PACKET TYPE'
        elif st == 'PACKET TYPE':
            p['ptype'] = PTYPES.get(b)
            p['hdr_sum'] = b
            if p['ptype'] is None:
                self.warn(ss, es, 'Unknown packet type 0x%02X' % b)
                p['state'] = 'STX'
                return
            self.putx(ss, es, rxtx, A_PTYPE, [p['ptype'][1], p['ptype'][0]])
            p['state'] = 'OPCODE'
        elif st == 'OPCODE':
            p['opcode'] = b
            p['hdr_sum'] += b
            name = OPCODES.get(b)
            if name:
                self.putx(ss, es, rxtx, A_OPCODE, [name, '%02X' % b])
            else:
                self.putx(ss, es, rxtx, A_OPCODE,
                          ['Opcode 0x%02X' % b, '%02X' % b])
                self.warn(ss, es, 'Unknown opcode 0x%02X' % b)
            p['state'] = 'LENGTH LO'
        elif st == 'LENGTH LO':
            p['len'] = b
            p['hdr_sum'] += b
            p['len_ss'] = ss
            p['state'] = 'LENGTH HI'
        elif st == 'LENGTH HI':
            p['len'] |= b << 8
            p['hdr_sum'] += b
            self.putx(p['len_ss'], es, rxtx, A_LEN,
                      ['Length: %d' % p['len'], '%d' % p['len']])
            p['state'] = 'CHECKSUM'
            if p['len'] > MAX_DATA_LEN:
                self.warn(p['len_ss'], es, 'Data length %d exceeds %d, '
                          'resync' % (p['len'], MAX_DATA_LEN))
                p['state'] = 'STX'
        elif st == 'CHECKSUM':
            exp = p['hdr_sum'] & 0xFF
            if b != exp:
                self.putx(ss, es, rxtx, A_CSUM,
                          ['Checksum BAD: 0x%02X (expected 0x%02X)' % (b, exp),
                           'CS BAD', 'CS'])
                self.warn(ss, es, 'Checksum mismatch: got 0x%02X, expected '
                          '0x%02X, resync' % (b, exp))
                p['state'] = 'STX'
                return
            self.putx(ss, es, rxtx, A_CSUM,
                      ['Checksum OK: 0x%02X' % b, 'CS OK', 'CS'])
            p['state'] = 'DATA' if p['len'] else 'ETX'
        elif st == 'DATA':
            p['data'].append(b)
            p['pos'].append((ss, es))
            self.putx(ss, es, rxtx, A_DATA, ['%02X' % b])
            if len(p['data']) == p['len']:
                p['state'] = 'ETX'
        elif st == 'ETX':
            if b == ETX:
                self.putx(ss, es, rxtx, A_ETX, ['ETX', 'E'])
                self.emit_packet(rxtx, es)
                p['state'] = 'STX'
            else:
                self.warn(ss, es, 'Expected ETX, got 0x%02X' % b)
                self.emit_packet(rxtx, ss)
                p['state'] = 'STX'
                if b == STX:
                    self.decode(ss, es, data)
