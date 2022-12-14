##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Jean Gressmann <jean@0x42.de>
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included in all
## copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.
##

import sigrokdecode as srd

STATE_IDLE = 1
STATE_GET_SLAVE_ADDR = 2
STATE_WAIT_WRITE_ADDR = 3
STATE_READ_ADDR = 4
STATE_WRITE_ADDR = 5

ROW_TEMP = 0
ROW_HUMID = 1
ROW_WARN = 4
ROW_READ_PTR = 5

regToLong = {
    0: "Temperature LSB",
    1: "Temperature MSB",
    2: "Humidity LSB",
    3: "Humidity MSB",
}

regToShort = {
    0: "T LSB",
    1: "T MSB",
    2: "H LSB",
    3: "H MSB",
}

regToRow = {
    0: 0,
    1: 0,
    2: 1,
    3: 1,
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'hdc2080'
    name = 'HDC2080'
    longname = 'TI HDC2080'
    desc = 'National LM75 (and compatibles) temperature sensor.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = []
    tags = ['IC', 'Sensor']
    annotations = (
        ('temperature', 'Temperature / °C'),
        ('humidity', 'Humidity / RH%'),
        ('text-verbose', 'Text (verbose)'),
        ('text', 'Text'),
        ('warning', 'Warning'),
        ('rptr', 'Read Pointer'),
    )
    annotation_rows = (
        ('temp', 'Temperature', (0,)),
        ('humidity', 'Humitidy', (1,)),
        ('readptrs', 'Read Pointers', (5,)),
        ('warning', 'Warnings', (4,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = STATE_IDLE
        self.reg = 0x00

        self.ss_addr = None

        # how many consecutive bytes
        # we have read or written in a row
        self.bytes_num = 0

        self.resetTemp()
        self.resetHumid()

    def resetTemp(self):
        self.ss_temp_lsb = None
        self.ss_temp_msb = None

        self.temp_lsb = None
        self.temp_msb = None

    def resetHumid(self):
        self.ss_humid_lsb = None
        self.ss_humid_msb = None

        self.humid_lsb = None
        self.humid_msb = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def warn_upon_invalid_slave(self, addr):
        # HDC2080 devices have a 7-bit I2C slave address, where the 6 MSBs are
        # fixed to 100000, and the 1 LSBs can be configured.
        # Thus, valid slave addresses (100000x) range from 0x40 to 0x41
        if addr not in [0x40, 0x41]:
            s = 'Warning: I²C slave 0x%02x not an HDC2080 sensor.'
            self.putx([4, [s % addr]])

    def decode(self, ss, es, data):
        cmd, databyte = data

        # Store the start/end samples of this I²C packet.
        self.ss, self.es = ss, es

        if self.state == STATE_IDLE:
            # Wait for an I²C START condition.
            if cmd != 'START':
                return
            self.state = STATE_GET_SLAVE_ADDR
        elif self.state == STATE_GET_SLAVE_ADDR:
            # Wait for an address read/write operation.
            if cmd in ('ADDRESS READ', 'ADDRESS WRITE'):
                self.warn_upon_invalid_slave(databyte)

                self.ss_addr = self.ss
                self.state = STATE_READ_ADDR
                if 'WRITE' in cmd:
                    self.state = STATE_WAIT_WRITE_ADDR
        elif self.state == STATE_WAIT_WRITE_ADDR:
            if 'DATA WRITE' in cmd:
                self.reg = databyte
                self.state = STATE_WRITE_ADDR
                self.handle_data_write_reg()
        elif self.state in (STATE_READ_ADDR, STATE_WRITE_ADDR):
            if "ADDRESS READ" in cmd:
                self.ss_addr = self.ss
            elif cmd == 'DATA READ':
                self.handle_reading_label(databyte)
                self.handle_reading(databyte)

                # increment the reg by one, as next time
                # (unless the reg has changed), we will
                # be at another register
                self.reg += 1

                self.bytes_num += 1
            elif cmd == 'DATA WRITE':
                self.handle_writing(databyte)
                # increment the reg by one, as next time
                # (unless the reg has changed), we will
                # be at another register
                self.reg += 1
            elif cmd == 'STOP':
                self.bytes_num = 0
                self.state = STATE_IDLE

    def handle_writing(self, databyte):
        if not self.reg == 0x0f:
            return

        # configuration
        conf = databyte

        label = ""

        print("test", conf & 0b1)

        # meas trig
        if conf & 0b0:
            label += "no meas trig"
        elif conf & 0b1:
            label += "start meas"
        label += ", "
        conf = conf >> 1

        # measurement conf
        if conf & 0b00 == 0:
            label += "mes humid+temp"
        elif conf & 0b01:
            label += "mes temp"
        label += ", "
        conf = conf >> 2

        # humid resolution
        if conf & 0b00 == 0:
            label += "HRES 14 bit"
        elif conf & 0b01:
            label += "HRES 11 bit"
        elif conf & 0b10:
            label += "HRES 9 bit"
        label += ", "
        conf = conf >> 2

        # temp resolution
        if conf & 0b00 == 0:
            label += "TRES 14 bit"
        elif conf & 0b01:
            label += "TRES 11 bit"
        elif conf & 0b10:
            label += "TRES 9 bit"
        label += ", "
            
        print("final conf:", label)

        print("handle_writing reg: 0x{:02x} data: 0b{:08b}".format(self.reg, databyte))

    def handle_reading(self, databyte):
        if self.reg not in range(0x00, 0x04):
            return

        if self.reg == 0x00:
            self.ss_temp_lsb = self.ss_addr
            self.temp_lsb = databyte
        elif self.reg == 0x01:
            self.ss_temp_msb = self.es
            self.temp_msb = databyte
        elif self.reg == 0x02:
            self.ss_humid_lsb = self.ss_addr
            self.humid_lsb = databyte
        elif self.reg == 0x03:
            self.ss_humid_msb = self.es
            self.humid_msb = databyte

        # process any events that need it
        self.handle_temp()
        self.handle_humid()

    def handle_temp(self):
        if not self.temp_lsb or not self.temp_msb:
            return

        temp = (self.temp_msb << 8) | self.temp_lsb
        temp = ((temp*165)/65536) - 40.5
        s = "Temperature {:.2f}°C".format(temp)

        self.put(self.ss_temp_lsb, self.ss_temp_msb, self.out_ann, [ROW_TEMP, [s]])
        self.resetTemp()

    def handle_humid(self):
        if not self.humid_lsb or not self.humid_msb:
            return

        humid = (self.humid_msb << 8) | self.humid_lsb
        humid = (humid*100)/65536
        s = "Humidity {:.2f} RH%".format(humid)

        self.put(self.ss_humid_lsb, self.ss_humid_msb, self.out_ann, [ROW_HUMID, [s]])
        self.resetHumid()

    def handle_data_write_reg(self):
        if self.reg not in range(0x00, 0x04):
            return

        slong = "Set read pointer: 0x{:02x} ({})".format(self.reg, regToLong[self.reg])
        sshort = "RP 0x{:02x} ({})".format(self.reg, regToShort[self.reg])
        self.put(self.ss_addr, self.es, self.out_ann, [ROW_READ_PTR, [slong, sshort]])

    def handle_reading_label(self, databyte):
        if self.reg not in range(0x00, 0x04):
            return

        slong = "0x{:02x} ({})".format(self.reg, regToLong[self.reg])
        sshort = "0x{:02x} ({})".format(self.reg, regToShort[self.reg])

        ss = self.ss_addr
        if self.bytes_num > 0:
            ss = self.ss

        self.put(ss, self.es, self.out_ann, [ROW_READ_PTR, [slong, sshort]])
