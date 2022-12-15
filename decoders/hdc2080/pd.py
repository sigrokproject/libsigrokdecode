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

regToLong = {
    0x00: "Temperature LSB",
    0x01: "Temperature MSB",
    0x02: "Humidity LSB",
    0x03: "Humidity MSB",
    0x04: "DataReady and interrupt configuration",
    0x05: "Maximum measured temperature",
    0x06: "Maximum measured humidity",
    0x07: "Interrupt enable",
    0x08: "Temperature offset adjustment",
    0x09: "Humidity offset adjustment",
    0x0A: "Temperature threshold LSB",
    0x0B: "Temperature threshold MSB",
    0x0C: "Humidity threshold low",
    0x0D: "Humidity threshold high",
    0x0E: "Soft reset and interrupt configuration",
    0x0F: "Measurement configuration",
    0xFC: "Manufacturer ID low",
    0xFD: "Manufacturer ID high",
    0xFE: "Device ID low",
    0xFF: "Device ID high",
}

regToShort = {
    0x00: "T LSB",
    0x01: "T MSB",
    0x02: "H LSB",
    0x03: "H MSB",
    0x04: "Interrupt/drdy",
    0x05: "T max",
    0x06: "H max",
    0x07: "Interrupt enable",
    0x08: "Temp offset adjust",
    0x09: "Hum offset adjust",
    0x0A: "Temp THR LSB",
    0x0B: "Temp THR MSB",
    0x0C: "RH THR LSB",
    0x0D: "RH THR MSB",
    0x0E: "Reset and DRDY/Int conf",
    0x0F: "Measurement conf",
    0xFC: "Man ID low",
    0xFD: "Man ID high",
    0xFE: "Dev ID low",
    0xFF: "Dev ID high",
}

STATE_IDLE = 1
STATE_GET_SLAVE_ADDR = 2
STATE_WAIT_WRITE_ADDR = 3
STATE_READ_ADDR = 4
STATE_WRITE_ADDR = 5

ROW_TEMP = 0
ROW_HUMID = 1
ROW_WARN = 2
ROW_READ_PTR = 3

class Decoder(srd.Decoder):
    api_version = 3
    id = 'hdc2080'
    name = 'HDC2080'
    longname = 'TI HDC2080'
    desc = 'HDC2080 Low-Power Humidity and Temperature Digital Sensor'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = []
    tags = ['IC', 'Sensor']
    annotations = (
        ('temperature', 'Temperature / °C'),
        ('humidity', 'Humidity / RH%'),
        ('warning', 'Warning'),
        ('rptr', 'Read Pointer'),
    )
    annotation_rows = (
        ('temp', 'Temperature', (0,)),
        ('humidity', 'Humitidy', (1,)),
        ('warning', 'Warnings', (2,)),
        ('readptrs', 'Read Pointers', (3,)),
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

    def getRegisterNameLong(self, reg):
        try:
            return regToLong[reg]
        except:
            return "Unknown"

    def getRegisterNameShort(self, reg):
        try:
            return regToShort[reg]
        except:
            return "Unk"

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
                self.handle_data_write_reg_label()
        elif self.state in (STATE_READ_ADDR, STATE_WRITE_ADDR):
            if "ADDRESS READ" in cmd:
                self.ss_addr = self.ss
            elif cmd == 'DATA READ':
                self.handle_read_reg_label(databyte)
                self.handle_reading(databyte)

                # increment the reg by one, as next time
                # (unless the reg has changed), we will
                # be at another register
                self.reg += 1

                self.bytes_num += 1
            # saved for potential future use
            elif cmd == 'DATA WRITE':
                # code here

                # self.handle_writing(databyte)
                # increment the reg by one, as next time
                # (unless the reg has changed), we will
                # be at another register
                self.reg += 1

                self.bytes_num += 1
            elif cmd == 'BITS':
                self.handle_bits(databyte)
            elif cmd == 'STOP':
                self.bytes_num = 0
                self.state = STATE_IDLE

    def handle_bits(self, bits):
        if not self.reg == 0x0f:
            return

        bits.reverse()

        tres_bits = bits[0][0] << 1 | bits[1][0]
        hres_bits = bits[2][0] << 1 | bits[3][0]
        # res      = bits[4][0] # unused
        meas_conf_bits = bits[5][0] << 1 | bits[6][0]
        meas_trig_bits = bits[7][0]

        ss_tres = bits[0][1]
        se_tres = bits[1][2]
        ss_hres = bits[2][1]
        se_hres = bits[3][2]
        ss_res = bits[4][1]
        se_res = bits[4][2]
        ss_meas_conf = bits[5][1]
        se_meas_conf = bits[6][2]
        ss_meas_trig = bits[7][1]
        se_meas_trig = bits[7][2]

        # tres
        tres_text = "Temperature resolution "
        if tres_bits & 0b00 == 0:
            tres_text += "14 bit (0b00)"
        elif tres_bits & 0b01:
            tres_text += "11 bit (0b01)"
        elif tres_bits & 0b10:
            tres_text += "9 bit (0b10)"
        self.put(ss_tres, se_tres, self.out_ann, [ROW_READ_PTR, [tres_text]])

        # hres
        hres_text = "Humidity resolution "
        if hres_bits & 0b00 == 0:
            hres_text += "14 bit (0b00)"
        elif hres_bits & 0b01:
            hres_text += "11 bit (0b01)"
        elif hres_bits & 0b10:
            hres_text += "9 bit (0b10)"
        self.put(ss_hres, se_hres, self.out_ann, [ROW_READ_PTR, [hres_text]])

        # res
        self.put(ss_res, se_res, self.out_ann, [ROW_READ_PTR, ["reserved"]])

        # measurement conf
        meas_conf_text = "Measurement configuration "
        if meas_conf_bits & 0b00 == 0:
            meas_conf_text += "humidity + temperature (0b00)"
        elif meas_conf_bits & 0b01:
            meas_conf_text += "temperature only (0b01)"
        self.put(ss_meas_conf, se_meas_conf, self.out_ann, [ROW_READ_PTR, [meas_conf_text]])

        # meas trig
        meas_trig_text = "Measurement trigger "
        if meas_trig_bits & 0b0:
            meas_trig_text += "no action (0b0)"
        elif meas_trig_bits & 0b1:
            meas_trig_text += "start measurement (0b1)"
        self.put(ss_meas_trig, se_meas_trig, self.out_ann, [ROW_READ_PTR, [meas_trig_text]])

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

    def handle_data_write_reg_label(self):
        if self.reg not in regToLong:
            return

        ss = self.ss_addr
        if self.bytes_num > 0:
            ss = self.ss

        slong = "Set read pointer: 0x{:02x} ({})".format(self.reg, self.getRegisterNameLong(self.reg))
        sshort = "RP 0x{:02x} ({})".format(self.reg, self.getRegisterNameShort(self.reg))
        self.put(ss, self.es, self.out_ann, [ROW_READ_PTR, [slong, sshort]])

    def handle_read_reg_label(self, databyte):
        if self.reg not in regToLong:
            return

        slong = "0x{:02x} ({})".format(self.reg, self.getRegisterNameLong(self.reg))
        sshort = "0x{:02x} ({})".format(self.reg, self.getRegisterNameShort(self.reg))

        ss = self.ss_addr
        if self.bytes_num > 0:
            ss = self.ss

        self.put(ss, self.es, self.out_ann, [ROW_READ_PTR, [slong, sshort]])
