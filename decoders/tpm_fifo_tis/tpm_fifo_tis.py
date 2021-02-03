#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2020-2021 Tobias Peter <tobias.peter@infineon.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

import binascii
import enum

from collections import defaultdict

from .tpm_tis_registers import decode_register, is_power_of_two, xfer_annotations

TPM_STS_X = 0x0018
TPM_STS_stsValid = 0x80
TPM_STS_commandReady = 0x40
TPM_STS_tpmGo = 0x20
TPM_STS_dataAvail = 0x10
TPM_STS_Expect = 0x08
TPM_STS_selfTestDone = 0x04
TPM_STS_responseRetry = 0x02

TPM_STS_read_mask = TPM_STS_commandReady | TPM_STS_dataAvail | TPM_STS_Expect
TPM_STS_write_mask = TPM_STS_commandReady | TPM_STS_tpmGo | TPM_STS_responseRetry

TPM_DATA_FIFO_X = 0x0024

ANNOTATIONS = (
    ('register-read', 'Register Read'),
    ('register-write', 'Register Write'),
    ('tpm-command', 'TPM Command'),
    ('tpm-response', 'TPM Response'),
    ('warning', 'Warning'),
    ('state', 'State'),
)
# sigrokdecoder annotation indices
ANN_REG_READ = 0
ANN_REG_WRITE = 1
ANN_TPM_CMD = 2
ANN_TPM_RSP = 3
ANN_WARN = 4
ANN_STATE = 5

TIMEOUT_B = 0  # TODO

TPM_COMMAND_CODE_NAMES = defaultdict(lambda: "Unknown", {
    0x0000011f: "NV_UndefineSpaceSpecial",
    0x00000120: "EvictControl",
    0x00000121: "HierarchyControl",
    0x00000122: "NV_UndefineSpace",
    0x00000124: "ChangeEPS",
    0x00000125: "ChangePPS",
    0x00000126: "Clear",
    0x00000127: "ClearControl",
    0x00000128: "ClockSet",
    0x00000129: "HierarchyChangeAuth",
    0x0000012a: "NV_DefineSpace",
    0x0000012b: "PCR_Allocate",
    0x0000012c: "PCR_SetAuthPolicy",
    0x0000012d: "PP_Commands",
    0x0000012e: "SetPrimaryPolicy",
    0x0000012f: "FieldUpgradeStart",
    0x00000130: "ClockRateAdjust",
    0x00000131: "CreatePrimary",
    0x00000132: "NV_GlobalWriteLock",
    0x00000133: "GetCommandAuditDigest",
    0x00000134: "NV_Increment",
    0x00000135: "NV_SetBits",
    0x00000136: "NV_Extend",
    0x00000137: "NV_Write",
    0x00000138: "NV_WriteLock",
    0x00000139: "DictionaryAttackLockReset",
    0x0000013a: "DictionaryAttackParameters",
    0x0000013b: "NV_ChangeAuth",
    0x0000013c: "PCR_Event",
    0x0000013d: "PCR_Reset",
    0x0000013e: "SequenceComplete",
    0x0000013f: "SetAlgorithmSet",
    0x00000140: "SetCommandCodeAuditStatus",
    0x00000141: "FieldUpgradeData",
    0x00000142: "IncrementalSelfTest",
    0x00000143: "SelfTest",
    0x00000144: "Startup",
    0x00000145: "Shutdown",
    0x00000146: "StirRandom",
    0x00000147: "ActivateCredential",
    0x00000148: "Certify",
    0x00000149: "PolicyNV",
    0x0000014a: "CertifyCreation",
    0x0000014b: "Duplicate",
    0x0000014c: "GetTime",
    0x0000014d: "GetSessionAuditDigest",
    0x0000014e: "NV_Read",
    0x0000014f: "NV_ReadLock",
    0x00000150: "ObjectChangeAuth",
    0x00000151: "PolicySecret",
    0x00000152: "Rewrap",
    0x00000153: "Create",
    0x00000154: "ECDH_ZGen",
    0x00000155: "HMAC",
    0x00000156: "Import",
    0x00000157: "Load",
    0x00000158: "Quote",
    0x00000159: "RSA_Decrypt",
    0x0000015b: "HMAC_Start",
    0x0000015c: "SequenceUpdate",
    0x0000015d: "Sign",
    0x0000015e: "Unseal",
    0x00000160: "PolicySigned",
    0x00000161: "ContextLoad",
    0x00000162: "ContextSave",
    0x00000163: "ECDH_KeyGen",
    0x00000164: "EncryptDecrypt",
    0x00000165: "FlushContext",
    0x00000167: "LoadExternal",
    0x00000168: "MakeCredential",
    0x00000169: "NV_ReadPublic",
    0x0000016a: "PolicyAuthorize",
    0x0000016b: "PolicyAuthValue",
    0x0000016c: "PolicyCommandCode",
    0x0000016d: "PolicyCounterTimer",
    0x0000016e: "PolicyCpHash",
    0x0000016f: "PolicyLocality",
    0x00000170: "PolicyNameHash",
    0x00000171: "PolicyOR",
    0x00000172: "PolicyTicket",
    0x00000173: "ReadPublic",
    0x00000174: "RSA_Encrypt",
    0x00000176: "StartAuthSession",
    0x00000177: "VerifySignature",
    0x00000178: "ECC_Parameters",
    0x00000179: "FirmwareRead",
    0x0000017a: "GetCapability",
    0x0000017b: "GetRandom",
    0x0000017c: "GetTestResult",
    0x0000017d: "Hash",
    0x0000017e: "PCR_Read",
    0x0000017f: "PolicyPCR",
    0x00000180: "PolicyRestart",
    0x00000181: "ReadClock",
    0x00000182: "PCR_Extend",
    0x00000183: "PCR_SetAuthValue",
    0x00000184: "NV_Certify",
    0x00000185: "EventSequenceComplete",
    0x00000186: "HashSequenceStart",
    0x00000187: "PolicyPhysicalPresence",
    0x00000188: "PolicyDuplicationSelect",
    0x00000189: "PolicyGetDigest",
    0x0000018a: "TestParms",
    0x0000018b: "Commit",
    0x0000018c: "PolicyPassword",
    0x0000018d: "ZGen_2Phase",
    0x0000018e: "EC_Ephemeral",
    0x0000018f: "PolicyNvWritten",
    0x00000190: "PolicyTemplate",
    0x00000191: "CreateLoaded",
    0x00000192: "PolicyAuthorizeNV",
    0x00000193: "EncryptDecrypt2",
    0x00000194: "AC_GetCapability",
    0x00000195: "AC_Send",
    0x00000196: "Policy_AC_SendSelect",
    0x00000197: "CertifyX509",
    0x00000198: "ACT_SetTimeout",
    0x20000000: "Vendor_TCG_Test",
})
TPM_RESPONSE_CODE_NAMES = defaultdict(lambda: "Error: Unknown", {
    0x0000: "Success",
    0x001E: "Error: Bad Tag",
    0x0100: "Error: Initialize",
    0x0101: "Error: Failure",
    0x0103: "Error: Sequence",
    0x010B: "Error: Private",
    0x0119: "Error: Hmac",
    0x0120: "Error: Disabled",
    0x0121: "Error: Exclusive",
    0x0124: "Error: Auth Type",
    0x0125: "Error: Auth Missing",
    0x0126: "Error: Policy",
    0x0127: "Error: PCR",
    0x0128: "Error: Pcr Changed",
    0x012D: "Error: Upgrade",
    0x012E: "Error: Too Many Contexts",
    0x012F: "Error: Auth Unavailable",
    0x0130: "Error: Reboot",
    0x0131: "Error: Unbalanced",
    0x0142: "Error: Command Size",
    0x0143: "Error: Command Code",
    0x0144: "Error: Authsize",
    0x0145: "Error: Auth Context",
    0x0146: "Error: NV Range",
    0x0147: "Error: NV Size",
    0x0148: "Error: NV Locked",
    0x0149: "Error: NV Authorization",
    0x014A: "Error: NV Uninitialized",
    0x014B: "Error: NV Space",
    0x014C: "Error: NV Defined",
    0x0150: "Error: Bad Context",
    0x0151: "Error: Cphash",
    0x0152: "Error: Parent",
    0x0153: "Error: Needs Test",
    0x0154: "Error: No Result",
    0x0155: "Error: Sensitive",
    0x017F: "Error: Max Fm0",
    0x0081: "Error: Asymmetric",
    0x0082: "Error: Attributes",
    0x0083: "Error: Hash",
    0x0084: "Error: Value",
    0x0085: "Error: Hierarchy",
    0x0087: "Error: Key Size",
    0x0088: "Error: Mgf",
    0x0089: "Error: Mode",
    0x008A: "Error: Type",
    0x008B: "Error: Handle",
    0x008C: "Error: Kdf",
    0x008D: "Error: Range",
    0x008E: "Error: Auth Fail",
    0x008F: "Error: Nonce",
    0x0090: "Error: Pp",
    0x0092: "Error: Scheme",
    0x0095: "Error: Size",
    0x0096: "Error: Symmetric",
    0x0097: "Error: Tag",
    0x0098: "Error: Selector",
    0x009A: "Error: Insufficient",
    0x009B: "Error: Signature",
    0x009C: "Error: Key",
    0x009D: "Error: Policy Fail",
    0x009F: "Error: Integrity",
    0x00A0: "Error: Ticket",
    0x00A1: "Error: Reserved Bits",
    0x00A2: "Error: Bad Auth",
    0x00A3: "Error: Expired",
    0x00A4: "Error: Policy Cc",
    0x00A5: "Error: Binding",
    0x00A6: "Error: Curve",
    0x00A7: "Error: Ecc Point",
    0x0901: "Error: Context Gap",
    0x0902: "Error: Object Memory",
    0x0903: "Error: Session Memory",
    0x0904: "Error: Memory",
    0x0905: "Error: Session Handles",
    0x0906: "Error: Object Handles",
    0x0907: "Error: Locality",
    0x0908: "Error: Yielded",
    0x0909: "Error: Canceled",
    0x090A: "Error: Testing",
    0x0910: "Error: Reference H0",
    0x0911: "Error: Reference H1",
    0x0912: "Error: Reference H2",
    0x0913: "Error: Reference H3",
    0x0914: "Error: Reference H4",
    0x0915: "Error: Reference H5",
    0x0916: "Error: Reference H6",
    0x0918: "Error: Reference S0",
    0x0919: "Error: Reference S1",
    0x091A: "Error: Reference S2",
    0x091B: "Error: Reference S3",
    0x091C: "Error: Reference S4",
    0x091D: "Error: Reference S5",
    0x091E: "Error: Reference S6",
    0x0920: "Error: NV Rate",
    0x0921: "Error: Lockout",
    0x0922: "Error: Retry",
    0x0923: "Error: NV Unavailable",
    0x097F: "Error: Not Used",
})

def _annotate_tpm_command(data):
    tag = data[0:2]
    size = data[2:6]
    cmd_code = int.from_bytes(data[6:10], byteorder='big')
    data = binascii.hexlify(data).upper().decode()
    return [
        "{cmd_code_name} ({cmd_code:04X}): {data}".format(cmd_code_name=TPM_COMMAND_CODE_NAMES[cmd_code], cmd_code=cmd_code, data=data),
        "{cmd_code_name} ({cmd_code:04X})".format(cmd_code_name=TPM_COMMAND_CODE_NAMES[cmd_code], cmd_code=cmd_code),
        '[{data_len} bytes]'.format(data_len=len(data))
    ]

def _annotate_tpm_response(data):
    tag = data[0:2]
    size = data[2:6]
    rsp_code = int.from_bytes(data[6:10], byteorder='big')
    data = binascii.hexlify(data).upper().decode()
    return [
        "{cmd_code_name} ({cmd_code:04X}): {data}".format(cmd_code_name=TPM_RESPONSE_CODE_NAMES[rsp_code], cmd_code=rsp_code, data=data),
        "{cmd_code_name} ({cmd_code:04X})".format(cmd_code_name=TPM_RESPONSE_CODE_NAMES[rsp_code], cmd_code=rsp_code),
        '[{data_len} bytes]'.format(data_len=len(data))
    ]

class TpmState(enum.Enum):
    Unknown = 0
    Idle = 1
    Ready = 2
    Reception = 3
    Execution = 4
    Completion = 5


def _annotate_bytes(data):
    return [
        binascii.hexlify(data).upper().decode(),
        '[{data_len} bytes]'.format(data_len=len(data))
    ]


class decoder:
    def __init__(self, out_ann, out_py):
        self.out_ann = out_ann
        self.out_py = out_py

        self.state = TpmState.Unknown
        self.state_finished = False  # Reception and Completion states use Expect/dataAvailable flags to say whether they expect/have more data. If not, they are finished
        self.state_start = None  # time stamp the current state started
        self.command_buffer = bytearray()
        self.command_start = None  # must be set when state is Completion
        self.response_buffer = bytearray()
        self.response_start = None  # bust be set when state is Reception

    def __iter__(self):
        '''Generator. Takes (ss, es, xfer) tuples via generator send(). Yields (ss, es, ann, labels) annotations.
        The general protocol is:
            - For a fresh generator, send(None).
            - Whenever this generator yields None, the next iteration should send((ss, es, xfer)).
            - Whenever this generator yields a tuple, that is an annotation that should be put(), and the next iteration should send(None).
        '''
        try:
            while True:
                ss, es, xfer = yield from self._transaction()
                if xfer.reading:
                    yield from self._on_read(xfer.addr, xfer.data, ss, es)
                else:
                    yield from self._on_write(xfer.addr, xfer.data, ss, es)
        except GeneratorExit:
            if self.state_start is not None:
                yield (self.state_start, es, self.out_ann, [ANN_STATE, [str(self.state)]])

    def _warn(self, ss, es, warning):
        if not isinstance(warning, list):
            warning = [warning]
        yield (ss, es, self.out_ann, [ANN_WARN, warning])

    def _transaction(self):
        '''Generator. Takes (ss, es, xfer) tuples via generator send(). Yields (ss, es, ann, labels) annotations. Returns an (ss, es, xfer) tuple.
        Use as follows to receive a new transaction:
            ss, es, xfer = yield from _transaction()
        '''
        ss, es, xfer = yield None

        if xfer.addr > 0xff and xfer.addr & 0xffff0000 != 0x00d40000:
            yield from self._warn(ss, es, 'Invalid FIFO Register address {xfer_addr:08X}'.format(xfer_addr=xfer.addr))
            return

        annotations = xfer_annotations(xfer)

        yield (ss, es, self.out_ann, [ANN_REG_READ if xfer.reading else ANN_REG_WRITE, annotations])
        return (ss, es, xfer)

    def _set_state(self, new_state, new_state_start):
        '''Generator. Yields (ss, es, ann, labels) annotations.
        Use this as follows when a state transition is detected:
            yield from _set_state(new_state, new_state_start)
        '''
        if new_state == self.state:
            return
        if self.state_start is not None:
            yield (self.state_start, new_state_start, self.out_ann, [ANN_STATE, [str(self.state)]])
        self.state = new_state
        self.state_start = new_state_start
        if new_state == TpmState.Reception or new_state == TpmState.Completion:
            self.state_finished = False

    def _reset_response(self, ss=None, data=None):
        self.response_buffer.clear()
        self.response_start = ss
        if data:
            self.response_buffer.extend(data)

    def _reset_command(self, ss=None, data=None):
        self.command_buffer.clear()
        self.command_start = ss
        if data:
            self.command_buffer.extend(data)

    def _on_read(self, reg, data, ss, es):
        if reg & 0xfff == TPM_STS_X:
            status = data[0]

            if self.state == TpmState.Unknown:
                if status & (TPM_STS_commandReady | TPM_STS_dataAvail) == TPM_STS_commandReady:
                    yield from self._set_state(TpmState.Ready, ss)
                elif status & TPM_STS_Expect:
                    yield from self._set_state(TpmState.Reception, ss)
                elif status & TPM_STS_dataAvail:
                    yield from self._set_state(TpmState.Completion, ss)
            if self.state == TpmState.Idle:
                if status & (TPM_STS_commandReady | TPM_STS_dataAvail) == TPM_STS_commandReady:
                    yield from self._set_state(TpmState.Ready, ss)
                elif status & TPM_STS_read_mask != 0:
                    yield from self._warn(ss, es, "Read status values that are unexpected in IDLE state")
                    yield from self._set_state(TpmState.Unknown, ss)
                    yield from self._on_read(reg, data, ss, es)  # now in Unknown state
            elif self.state == TpmState.Ready:
                if status & TPM_STS_read_mask == TPM_STS_Expect:
                    yield from self._set_state(TpmState.Reception, ss)
                elif status & (TPM_STS_commandReady | TPM_STS_dataAvail) != TPM_STS_commandReady:
                    yield from self._warn(ss, es, "Read status values that are unexpected in READY state: {}".format(status))
                    yield from self._set_state(TpmState.Unknown, ss)
                    yield from self._on_read(reg, data, ss, es)  # now in Unknown state
            elif self.state == TpmState.Reception:
                if status & TPM_STS_stsValid and not status & TPM_STS_Expect:
                    self.state_finished = True
            elif self.state == TpmState.Execution:
                if status & TPM_STS_read_mask == TPM_STS_dataAvail:
                    self._reset_response(ss)
                    yield from self._set_state(TpmState.Completion, ss)
                elif status & TPM_STS_read_mask != 0:
                    yield from self._warn(ss, es, "Read status values that are unexpected in IDLE state")
                    yield from self._set_state(TpmState.Unknown, ss)
                    yield from self._on_read(reg, data, ss, es)  # now in Unknown state
            elif self.state == TpmState.Completion:
                if status & TPM_STS_read_mask == 0:
                    yield (self.response_start, es, self.out_ann, [ANN_TPM_RSP, _annotate_tpm_response(self.response_buffer)])
                    yield (self.response_start, es, self.out_py, ['RESPONSE', bytes(self.response_buffer)])
                    self.state_finished = True
                    self._reset_response()
                    yield from self._set_state(TpmState.Idle, ss)
                elif status & TPM_STS_stsValid and status & TPM_STS_read_mask != TPM_STS_dataAvail:
                    yield from self._warn(ss, es, "Read status values that are unexpected in IDLE state")
                    yield from self._set_state(TpmState.Unknown, ss)
                    yield from self._on_read(reg, data, ss, es)  # now in Unknown state

        elif reg & 0xfff == TPM_DATA_FIFO_X:
            if self.state == TpmState.Completion:
                if self.state_finished:
                    yield from self._warn(ss, es, "The TPM does not report more data dataAvailable, so this will just be 0xFFs")
                else:
                    self.response_buffer.extend(data)
                # Note: if the client does not detect when the TPM clears dataAvail, it will read FFs into this buffer
            else:
                yield from self._warn(ss, es, "TPM does not have any data, and will return 0xFFs")

    def _on_write(self, reg, data, ss, es):
        if reg & 0xfff == TPM_STS_X:
            status = data[0]
            if not is_power_of_two(status):
                yield from self._warn(ss, es, "Only one field may be set at a time when writing to TPM_STS_X")
                yield from self._set_state(TpmState.Unknown, ss)
                return

            if self.state == TpmState.Idle:
                if status & TPM_STS_responseRetry:
                    yield from self._warn(ss, es, "There is no response to retry")
                elif status & TPM_STS_tpmGo:
                    yield from self._warn(ss, es, "There is no command to execute")
                elif status & TPM_STS_commandReady:
                    yield from self._set_state(TpmState.Ready, ss)
            elif self.state == TpmState.Ready:
                if status & TPM_STS_responseRetry:
                    yield from self._warn(ss, es, "commandReady indicates respose has already been successfully read")
                elif status & TPM_STS_tpmGo:
                    yield from self._warn(ss, es, "There is no command to execute")
                elif status & TPM_STS_commandReady:
                    yield from self._warn(ss, es, "TPM is already ready to receive commands")
            elif self.state == TpmState.Reception:
                if status & TPM_STS_responseRetry:
                    yield from self._warn(ss, es, "There is no response to retry")
                elif status & TPM_STS_commandReady:
                    yield from self._warn(ss, es, "Command aborted (while sending command)")
                    self._reset_command()
                    yield from self._set_state(TpmState.Idle, es)
                elif status & TPM_STS_tpmGo:
                    if not self.state_finished:
                        yield from self._warn(ss, es, "TPM is still expecting data, so this tpmGo signal is ignored")
                    else:  # assume everything is kosher, though this MAY be an invalid transition!  # TODO: transition to Unkown in the unknown case?
                        yield (self.command_start, ss, self.out_ann, [ANN_TPM_CMD, _annotate_tpm_command(self.command_buffer)])
                        yield (self.command_start, ss, self.out_py, ['COMMAND', bytes(self.command_buffer)])
                        self._reset_command()
                        yield from self._set_state(TpmState.Execution, ss)
            elif self.state == TpmState.Execution:
                if status & TPM_STS_responseRetry:
                    yield from self._warn(ss, es, "There is no response to retry")
                elif status & TPM_STS_tpmGo:
                    yield from self._warn(ss, es, "Command is already executing")
                elif status & TPM_STS_commandReady:
                    yield from self._warn(ss, es, "Command aborted (while executing command)")
                    yield from self._set_state(TpmState.Idle, es)
            elif self.state == TpmState.Completion:
                if status & TPM_STS_responseRetry:
                    yield from self._warn(self.response_start, ss, "TPM resets ReadFIFO pointers and starts sending the response from the first byte")
                    self._reset_response(ss)
                elif status & TPM_STS_tpmGo:
                    yield from self._warn(ss, es, "There is no command to execute")
                elif status & TPM_STS_commandReady:
                    yield from self._warn(self.response_start, ss, "Command aborted (while receiving response)")
                    self._reset_response()
                    yield from self._set_state(TpmState.Idle, es)

        if reg & 0xfff == TPM_DATA_FIFO_X:
            if self.state == TpmState.Ready or self.state == TpmState.Idle:  # the TPM is allowed to implicitly transition to idle; without reading the status register, we can't know this, so we just allow it here. Technically, starting to send data in the Idle state is just dropped. TODO: make this some sort of flag?
                self._reset_command(ss)
                self.command_buffer.extend(data)
                yield from self._set_state(TpmState.Reception, ss)
            elif self.state == TpmState.Reception:
                if self.state_finished:
                    yield from self._warn(ss, es, "The TPM is not expecting more data, so this will be dropped")
                else:
                    self.command_buffer.extend(data)
            else:
                yield from self._warn(ss, es, "TPM is not expecting data and will drop writes")
