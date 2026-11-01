"""Decoder fixture for synchronous EOF output and exception reporting."""
import time
import sigrokdecode as srd


class Decoder(srd.Decoder):
    api_version = 3
    id = 'eof_test'
    name = 'EOF test'
    longname = 'EOF test fixture'
    desc = 'Test-only decoder, not installed with the protocol decoders.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['eof_test']
    tags = ['Util']
    channels = ({'id': 'd0', 'name': 'D0', 'desc': 'Input'},)
    options = ({'id': 'mode', 'desc': 'Test case', 'default': 'tail',
                'values': ('tail', 'error', 'flush-error')},)
    binary = (('binary', 'Binary'),)

    def __init__(self):
        self.reset()

    def reset(self):
        self.ended = False

    def start(self):
        self.out = self.register(srd.OUTPUT_BINARY)

    def decode(self):
        try:
            while True:
                self.wait()
        except EOFError:
            self.ended = True
        # A decoder may release the GIL while producing its final output.
        time.sleep(0.05)
        if self.options['mode'] == 'error':
            raise RuntimeError('EOF test decode failure')
        if self.options['mode'] == 'tail':
            self.put(0, self.samplenum, self.out, [0, b'\x00\x0a\x0d\x1a\xffEND'])

    def flush(self):
        if self.ended and self.options['mode'] == 'flush-error':
            raise RuntimeError('EOF test flush failure')
