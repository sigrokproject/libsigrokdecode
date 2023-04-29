##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Fred Larsen <fredilarsen+sigrok@hotmail.com>, 
## based on code from Gerhard Sittig <gerhard.sittig@gmx.net>
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

# See the https://www.github.com/fredilarsen/moduleinterface/ project page,
# and the https://www.pjon.org/ PJON project page and the
# https://www.pjon.org/PJON-protocol-specification-v3.2.php protocol
# specification, which can use different link layers.

import sigrokdecode as srd
import struct

ANN_RXTX_INFO, ANN_PAYLOAD, ANN_END_CRC, ANN_SYN_RSP, \
ANN_RELATION, \
ANN_WARN, \
    = range(6)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'moduleinterface'
    name = 'ModuleInterface'
    longname = 'ModuleInterface'
    desc = 'The ModuleInterface protocol'
    license = 'gplv2+'
    inputs = ['pjon']
    outputs = []
    tags = ['Embedded/industrial']
    annotations = (
        ('addresses', 'Addresses'),
        ('payload', 'Payload'),
        ('end_crc', 'End CRC'),
        ('syn_rsp', 'Sync response'),
        ('relation', 'Relation'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('fields', 'Fields', (
            ANN_RXTX_INFO, ANN_PAYLOAD, ANN_END_CRC, ANN_SYN_RSP,
        )),
        ('relations', 'Relations', (ANN_RELATION,)),
        ('warnings', 'Warnings', (ANN_WARN,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.reset_frame()

    # TODO: Update to clear only used and all used variables
    def reset_frame(self):
        self.frame_ss = None
        self.frame_es = None
        self.frame_rx_id = None
        self.frame_tx_id = None
        self.frame_payload_text = None
        self.frame_bytes = None
        self.frame_has_ack = None
        self.ack_bytes = None
        self.ann_ss = None
        self.ann_es = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putg(self, ss, es, ann, data):
        self.put(ss, es, self.out_ann, [ann, data])

    def get_hex_string(self, bytes):
        s = ""
        for c in bytes:
            s += " {:02x}".format(c)
        return s

    def get_int_from_bytes(self, b):
        value = 0
        mult = 1
        for v in b:
            value += v*mult
            mult *= 256
        return value    

    def get_packet_type(self, t, extra_text):
        arr = []
        if t is 1:
            arr = ["REQUEST SETTINGS CONTRACT", "REQ_SET_CNTR", "RSC"]
        elif t is 2:
            arr = ["REQUEST INPUTS CONTRACT", "REQ_INP_CNTR", "RIC"]
        elif t is 3:
            arr = ["REQUEST OUTPUTS CONTRACT", "REQ_OUT_CNTR", "ROC"]
        elif t is 4:
            arr = ["SETTINGS CONTRACT", "SETTINGS CONTRACT", "SET_CNTR", "SC"]
        elif t is 5:
            arr = ["INPUTS CONTRACT", "INPUTS CONTRACT", "INP_CNTR", "IC"]
        elif t is 6:
            arr = ["OUTPUTS CONTRACT", "OUTPUTS CONTRACT", "OUT_CNTR", "OC"]
        elif t is 7:
            arr = ["REQUEST SETTINGS", "REQUEST SETTINGS", "REQ_SET", "RS"]
        elif t is 8:
            arr = ["REQUEST STATUS", "REQUEST STATUS", "REQ_STA", "RST"]
        elif t is 9:
            arr = ["SETTINGS", "SETTINGS", "SETTINGS", "S"]
        elif t is 10:
            arr = ["INPUTS", "INPUTS", "INPUTS", "I"]
        elif t is 11:
            arr = ["OUTPUTS", "OUTPUTS", "OUTPUTS", "O"]
        elif t is 12:
            arr = ["STATUS", "STATUS", "S"]
        elif t is 13:
            arr = ["TIMESYNC", "TIMESYNC", "TIME", "T"]
        else:
            arr = ["UNKNOWN", "U"]
        if extra_text is not None:
            arr[0] += extra_text
        return arr

    def get_valuetype_text(self, var_type):
        if var_type == 1: # mvtBoolean:
            return "b1"
        if var_type == 2: # mvtUint8:
            return "u1"
        if var_type == 3: # mvtUint16:
            return "u2"
        if var_type == 4: # mvtUint32:
            return "u4"
        if var_type == 5: # mvtInt8:
            return "i1"
        if var_type == 6: # mvtInt16:
            return "i2"
        if var_type == 7: # mvtInt32:
            return "i4"
        if var_type == 8: # mvtFloat32:
            return "f4"
        return "err"

    def get_statusbits_text(self, bits):
        s = ""
        if bits & 1: # CONTRACT_MISMATCH_SETTINGS
            s += "set_con,"
        if bits & 2: # CONTRACT_MISMATCH_INPUTS
            s += "inp_con,"
        if bits & 4: # MISSING_SETTINGS
            s += "set,"
        if bits & 8: # MISSING_INPUTS
            s += "inp,"
        if bits & 16: # MODIFIED_SETTINGS
            s += "set_mod,"
        if bits & 32: # MISSING_TIME
            s += "time,"
        if s.endswith(','):
            k = s.rfind(',')
            s = s[:k]
        if len(s) == 0:
            s = 'normal'        
        return s   

    def get_contract_text(self, payload):
        s = ""
        var_cnt = payload[0]
        if var_cnt == 0:
            return None
        pos = 1
        for i in range(0, var_cnt):
            if i != 0:
                s += " "
            type = payload[pos]
            pos += 1
            name_len = payload[pos]
            pos += 1
            name = payload[pos:pos+name_len]
            s += "".join(map(chr, name))
            s += ":" + self.get_valuetype_text(type)
            pos += name_len
        return s

    def get_status_text(self, p):
        pbits = p[0]
        pmem_err = p[1]
        ptime = p[2:6]
        #ttime = self.get_hex_string(ptime)
        ttime = self.get_int_from_bytes(ptime)
        bits_txt = self.get_statusbits_text(pbits)
        mem_txt = ""
        if pmem_err != 0:
            mem_txt = ", OUT_OF_MEM"
        text = "bits {:02x}({}){}, uptime {}s"\
            .format(pbits, bits_txt, mem_txt, ttime)
        return text

    def decode(self, ss, es, data):
        ptype, pdata = data
        
        # Accumulate data bytes as they arrive. Put them in the bucket
        # which corresponds to its most recently seen leader.
        if ptype == 'FRAME':
            b = pdata
 
            if b is None or b[0][0] != 'HEADER' or b[1][0] != 'PAYLOAD_BYTES':
                return
 
            header_start_pos = b[0][1]
            payload_start_pos = b[1][1]
            crc_start_pos = b[2][1]
            ack_pos = None
            if b[3][0] == "ACK":
                ack_pos = b[3][1], b[3][2]

            # Emit annotation for PJON header
            rxtx = 'RX ' + b[0][3] + ' - TX ' + b[0][4]
            full_text = rxtx
            self.putg(header_start_pos, payload_start_pos, ANN_RXTX_INFO, \
                [rxtx])
            
            # Emit annotations for payload
            p = b[1][3]
            if p is None:
                return    
            ptype = p[0]
            text = None
            payload = None
            payload_text = None
            parsed_payload_text = None
            status_text = None
            details = None
            #if ptype == 1 or ptype == 2 or ptype == 3:
                # Contract request, no additional data
            if ptype == 4 or ptype == 5 or ptype == 6:
                # Contract
                pcontract = p[1:5]
                pvarcnt = p[5]
                payload = p[5:]
                ctxt = self.get_int_from_bytes(pcontract)
                payload_text = self.get_hex_string(payload)
                text = self.get_packet_type(ptype, " - CNT {} - CID{}"\
                    .format(pvarcnt, ctxt))
                pay_txt = self.get_contract_text(payload)
                if pay_txt is not None:
                    parsed_payload_text = "VAR " + pay_txt
            elif ptype == 9 or ptype == 10 or ptype == 11:
                # Variable value packet
                pcontract = p[1:5]
                pvarcnt = p[5]
                pevent = True if pvarcnt > 127 else False
                if pevent:
                    pvarcnt -= 128
                payload = p[5:]
                ctxt = self.get_int_from_bytes(pcontract)
                details = " - CNT {:d} - EVENT {} - CID{}"\
                    .format(pvarcnt, pevent, ctxt)
                text = self.get_packet_type(ptype, details)
                # Extract status part of outputs packet
                if ptype == 11:
                    status_text = self.get_status_text(payload[-6:])
                    # Separate status part from payload to be shown
                    payload_text = self.get_hex_string(payload[:-6])
                else:
                    payload_text = self.get_hex_string(payload)                
            elif ptype == 12:
                # Status packet
                payload = p[1:]
                payload_text = self.get_hex_string(payload)
                status_text = self.get_status_text(payload[1:])
                text = self.get_packet_type(ptype, "(" + status_text + ")")
            elif ptype == 13:
                # Time sync packet
                payload = p[1:]
                ptime = p[1:5]
                ttime = self.get_int_from_bytes(ptime)
                text = self.get_packet_type(ptype, " UTC {}".format(ttime))
            else:
                text = self.get_packet_type(ptype, None)
            full_text += ' - ' + text[0]
            if details is not None:
                text[1] += details
            if payload_text is not None:
                text[0] += " - DATA" + payload_text
            if status_text is not None:
                text[0] += " - STATUS " + status_text
                text[1] += " - STATUS " + status_text
            self.putg(payload_start_pos, crc_start_pos, ANN_PAYLOAD, text)

            # Show ACK
            if ack_pos is not None:
                self.putg(ack_pos[0], ack_pos[1], ANN_PAYLOAD, ['ACK']) 

            # Emit annotation for Relations
            short4 = rxtx + " - " + text[2]
            short3 = rxtx + " - " + text[1]
            short2 = full_text
            if status_text is not None:
                full_text += " - STATUS " + status_text
            short1 = full_text
            if parsed_payload_text is not None:
                full_text += " - " + parsed_payload_text
            self.putg(ss, es, ANN_RELATION, \
                [full_text, short4, short3, short2, short1])

            self.putg(crc_start_pos, b[2][2], ANN_END_CRC, \
                ['Packet CRC','CRC'])
            return

        # Unknown or unhandled kind of PJON layer output.
        return