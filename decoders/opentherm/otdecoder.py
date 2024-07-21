#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# see https://www.gnu.org/licenses/ for license terms
#
# OpenTherm detailed decoder
# taken from https://github.com/sthamster/notexplorer
# Copyright (C) 2024 MaxWolf b8e06912cff61c7fc1f5df01ba2f43de51b04ce33fd4d351ce86a40c0cbf9abb
#
import sys
import time
import collections
import re

######
#
# Opentherm defines
#
######
# Message types according to Opentherm specs
OT_READ_DATA=0
OT_WRITE_DATA=1
OT_INVALID_DATA=2
OT_RESERVED=3
OT_READ_ACK=4
OT_WRITE_ACK=5
OT_DATA_INVALID=6
OT_UNKNOWN_DATA_ID=7

######
#
# Decode/comment Opentherm data
#
######
class OTData:
    def __init__(self, data_id, t_dir, pos, fmt, min, max, units, descr):
        self.data_id = data_id  # OT data-id
        self.t_dir = t_dir      # transfer direction ('R' - from slave, 'W' - to slave, 'RW' - both, 
                                # 'I' - from slave special mode (with simulaneous write), O - to slave special mode (with simultaneous read))
        self.pos = pos          # bit position, if exists (HB0 - bit 0 of high byte; LB1 - bit 1 of low byte etc; 0-7 - bits of the whole 16-bit word)
        self.fmt = fmt          # data format: BF - bitfield, U8, U16, S8, S16, F8.8
        self.min = min          # min value
        self.max = max          # max value
        self.units = units      # value units
        self.descr = descr      # data description (could contains conditional (==/>=/<=) descriptions

class OTDecoder:
    def __init__(self):
        self.OT_MSGS = { 
            OT_READ_DATA: "READ-DATA",
            OT_WRITE_DATA: "WRITE-DATA",
            OT_INVALID_DATA: "INVALID-DATA",
            OT_RESERVED: "OT-RESERVED",
            OT_READ_ACK:"READ-ACK", 
            OT_WRITE_ACK:"WRITE-ACK", 
            OT_DATA_INVALID:"DATA-INVALID", 
            OT_UNKNOWN_DATA_ID:"UNKNOWN-DATAID" }
        # Opentherm DATA-ID descriptions collected from 
        #   Opentherm%20Protocol%20v2-2.pdf
        #   https://www.opentherm.eu/request-details
        #   http://otgw.tclcode.com/firmware.html
        #   +forums and other sources...
        self.otd = collections.OrderedDict()
        self.otd["000"]      = OTData("000", "RI", "",    "BF", 0, 1, "", "Master/slave status")
        self.otd["000I"]     = OTData("000", "R", "",    "BF", 0, 1, "", "Master/slave status")
        self.otd["000I:HB0"] = OTData("000", "R", "HB0", "BF", 0, 1, "", "MS: CH enable")
        self.otd["000I:HB1"] = OTData("000", "R", "HB1", "BF", 0, 1, "", "MS: DHW enable")
        self.otd["000I:HB2"] = OTData("000", "R", "HB2", "BF", 0, 1, "", "MS: Cooling enable")
        self.otd["000I:HB3"] = OTData("000", "R", "HB3", "BF", 0, 1, "", "MS: OTC active")
        self.otd["000I:HB4"] = OTData("000", "R", "HB4", "BF", 0, 1, "", "MS: CH2 enable")
        self.otd["000I:HB5"] = OTData("000", "R", "HB5", "BF", 0, 1, "", "MS: Summer mode")  # 0 - winter, 1 - summer
        self.otd["000I:HB6"] = OTData("000", "R", "HB6", "BF", 0, 1, "", "MS: DHW blocked")  # 0 - DHW unblocked, 1 - blocked
        self.otd["000I:HB7"] = OTData("000", "R", "HB7", "BF", 0, 1, "", "MS: reserved")
        self.otd["000:HB0"]  = OTData("000", "R", "HB0", "BF", 0, 1, "", "MS: CH enable")
        self.otd["000:HB1"]  = OTData("000", "R", "HB1", "BF", 0, 1, "", "MS: DHW enable")
        self.otd["000:HB2"]  = OTData("000", "R", "HB2", "BF", 0, 1, "", "MS: Cooling enable")
        self.otd["000:HB3"]  = OTData("000", "R", "HB3", "BF", 0, 1, "", "MS: OTC active")
        self.otd["000:HB4"]  = OTData("000", "R", "HB4", "BF", 0, 1, "", "MS: CH2 enable")
        self.otd["000:HB5"]  = OTData("000", "R", "HB5", "BF", 0, 1, "", "MS: Summer/winter mode")
        self.otd["000:HB6"]  = OTData("000", "R", "HB6", "BF", 0, 1, "", "MS: DHW blocking")
        self.otd["000:HB7"]  = OTData("000", "R", "HB7", "BF", 0, 1, "", "MS: reserved")
        self.otd["000:LB0"]  = OTData("000", "R", "LB0", "BF", 0, 1, "", "SS: Fault")
        self.otd["000:LB1"]  = OTData("000", "R", "LB1", "BF", 0, 1, "", "SS: CH mode")
        self.otd["000:LB2"]  = OTData("000", "R", "LB2", "BF", 0, 1, "", "SS: DHW mode")
        self.otd["000:LB3"]  = OTData("000", "R", "LB3", "BF", 0, 1, "", "SS: Flame on")
        self.otd["000:LB4"]  = OTData("000", "R", "LB4", "BF", 0, 1, "", "SS: Cooling on")
        self.otd["000:LB5"]  = OTData("000", "R", "LB5", "BF", 0, 1, "", "SS: CH2 active")
        self.otd["000:LB6"]  = OTData("000", "R", "LB6", "BF", 0, 1, "", "SS: Diagnostic/service indication")
        self.otd["000:LB7"]  = OTData("000", "R", "LB7", "BF", 0, 1, "", "SS: Electricity production")
        self.otd["001"]      = OTData("001", "RW", "",    "", 0, 100, "°C", "CH water temperature Setpoint")
        self.otd["001W"]     = OTData("001", "W", "",    "F8.8", 0, 100, "°C", "CH water temperature Setpoint")
        self.otd["001R"]     = OTData("001", "R", "",    "F8.8", 0, 100, "°C", "CH water temperature Setpoint")
        self.otd["002"]      = OTData("002", "W", "",    "BF", 0, 1, "", "Master configuration")
        self.otd["002:LB"]   = OTData("002", "W", "0-7", "U8", 0, 255, "", "Master configuration: MemberId code")
        self.otd["002:HB0"]  = OTData("002", "W", "HB0", "BF", 0, 1, "", "Master configuration: Smart power")
        self.otd["003"]      = OTData("003", "R", "",    "BF", 0, 1, "", "Slave configuration")
        self.otd["003:LB"]   = OTData("003", "R", "0-7", "U8", 0, 255, "", "Slave configuration: MemberId code")
        self.otd["003:HB0"]  = OTData("003", "R", "HB0", "BF", 0, 1, "", "DHW present")
        self.otd["003:HB1"]  = OTData("003", "R", "HB1", "BF", 0, 1, "", "On/Off control only")
        self.otd["003:HB2"]  = OTData("003", "R", "HB2", "BF", 0, 1, "", "Cooling supported")
        self.otd["003:HB3"]  = OTData("003", "R", "HB3", "BF", 0, 1, "", "DHW configuration")
        self.otd["003:HB4"]  = OTData("003", "R", "HB4", "BF", 0, 1, "", "Master low-off&pump control allowed")
        self.otd["003:HB5"]  = OTData("003", "R", "HB5", "BF", 0, 1, "", "CH2 present")
        self.otd["003:HB6"]  = OTData("003", "R", "HB6", "BF", 0, 1, "", "Remote water filling function")
        self.otd["003:HB7"]  = OTData("003", "R", "HB7", "BF", 0, 1, "", "Heat/cool mode control")
        self.otd["004"]      = OTData("004", "RW", "",   "",   0, 0, "", "Slave control")
        self.otd["004W"]     = OTData("004", "W", "8-15", "U8", 0, 255, "", "==1 Boiler Lockout-reset;==10 Service request reset;==2 Request Water filling")
        self.otd["004R"]     = OTData("004", "R", "0-7", "U8", 0, 255, "", ">127 response ok;<128 response error")
        self.otd["005"]      = OTData("005", "R", "",    "BF", 0, 1, "", "Boiler faults")
        self.otd["005:HB0"]  = OTData("005", "R", "HB0", "BF", 0, 1, "", "Service required")
        self.otd["005:HB1"]  = OTData("005", "R", "HB1", "BF", 0, 1, "", "Lockout-reset enabled")
        self.otd["005:HB2"]  = OTData("005", "R", "HB2", "BF", 0, 1, "", "Low water pressure")
        self.otd["005:HB3"]  = OTData("005", "R", "HB3", "BF", 0, 1, "", "Gas/flame fault")
        self.otd["005:HB4"]  = OTData("005", "R", "HB4", "BF", 0, 1, "", "Air pressure fault")
        self.otd["005:HB5"]  = OTData("005", "R", "HB5", "BF", 0, 1, "", "Water over-temperature")
        self.otd["005:LB"]   = OTData("005", "R", "0-7", "U8", 0, 255, "", "OEM fault code")
        self.otd["006"]      = OTData("006", "R", "",    "BF", 0, 1, "", "Remote boiler parameters")
        self.otd["006:HB0"]  = OTData("006", "R", "HB0", "BF", 0, 1, "", "transfer-enabled: DHW setpoint")
        self.otd["006:HB1"]  = OTData("006", "R", "HB1", "BF", 0, 1, "", "transfer-enabled: max. CH setpoint")
        self.otd["006:HB2"]  = OTData("006", "R", "HB2", "BF", 0, 1, "", "transfer-enabled: param 2 (OTC HC ratio)") # unsure
        self.otd["006:HB3"]  = OTData("006", "R", "HB3", "BF", 0, 1, "", "transfer-enabled: param 3")
        self.otd["006:HB4"]  = OTData("006", "R", "HB4", "BF", 0, 1, "", "transfer-enabled: param 4")
        self.otd["006:HB5"]  = OTData("006", "R", "HB5", "BF", 0, 1, "", "transfer-enabled: param 5")
        self.otd["006:HB6"]  = OTData("006", "R", "HB6", "BF", 0, 1, "", "transfer-enabled: param 6")
        self.otd["006:HB7"]  = OTData("006", "R", "HB7", "BF", 0, 1, "", "transfer-enabled: param 7")
        self.otd["006:LB0"]  = OTData("006", "R", "LB0", "BF", 0, 1, "", "read/write: DHW setpoint")
        self.otd["006:LB1"]  = OTData("006", "R", "LB1", "BF", 0, 1, "", "read/write: max. CH setpoint")
        self.otd["006:LB2"]  = OTData("006", "R", "LB2", "BF", 0, 1, "", "read/write: param 2 (OTC HC ratio)") # unsure
        self.otd["006:LB3"]  = OTData("006", "R", "LB3", "BF", 0, 1, "", "read/write: param 3")
        self.otd["006:LB4"]  = OTData("006", "R", "LB4", "BF", 0, 1, "", "read/write: param 4")
        self.otd["006:LB5"]  = OTData("006", "R", "LB5", "BF", 0, 1, "", "read/write: param 5")
        self.otd["006:LB6"]  = OTData("006", "R", "LB6", "BF", 0, 1, "", "read/write: param 6")
        self.otd["006:LB7"]  = OTData("006", "R", "LB7", "BF", 0, 1, "", "read/write: param 7")
        self.otd["007"]      = OTData("007", "W", "",    "F8.8", 0, 100, "%", "Cooling control signal")
        self.otd["008"]      = OTData("008", "W", "",    "F8.8", 0, 100, "°C", "Control Setpoint for 2nd CH circuit")
        self.otd["009"]      = OTData("009", "R", "",    "F8.8", 0, 30, "", "Remote override room Setpoint") # 0 - no override
        self.otd["010"]      = OTData("010", "R", "8-15", "U8", 0, 255, "", "Number of Transparent-Slave-Parameters supported by slave")
        self.otd["011"]      = OTData("011", "RW", "",   "",  0, 0,  "", "Index/Value of transparent slave parameter")
        self.otd["011R"]     = OTData("011", "R", "",    "BF", 0, 9, "", "Transparent slave parameter")
        self.otd["011R:HB"]  = OTData("011", "R", "8-15", "U8", 0, 255, "", "Index of read transparent slave parameter")
        self.otd["011R:LB"]  = OTData("011", "R", "0-7", "U8", 0, 255, "", "Value of read transparent slave parameter")
        self.otd["011W"]     = OTData("011", "W", "",    "BF", 0, 1, "", "Transparent slave parameter to write")
        self.otd["011W:HB"]  = OTData("011", "W", "8-15","U8", 0, 255, "", "Index of referred-to transparent slave parameter to write")
        self.otd["011W:LB"]  = OTData("011", "W", "0-7", "U8", 0, 255, "", "Value of referred-to transparent slave parameter to write")
        self.otd["012"]      = OTData("012", "R", "8-15", "U8"  , 0, 255, "", "Size of Fault-History-Buffer supported by slave")
        self.otd["013"]      = OTData("013", "R", ""   , "BF", 0, 1, "", "Fault-history buffer entry")
        self.otd["013:HB"]   = OTData("013", "R", "8-15", "U8", 0, 255, "", "Index number")
        self.otd["013:LB"]   = OTData("013", "R", "0-7", "U8", 0, 255, "", "Entry Value")
        self.otd["014"]      = OTData("014", "W", ""   , "F8.8", 0, 100, "", "Maximum relative modulation level setting (%)")
        self.otd["015"]      = OTData("015", "R", ""   , "BF", 0, 0, "", "Boiler capacities")
        self.otd["015:HB"]   = OTData("015", "R", "8-15", "U8" , 0, 255, "kW", "Maximum boiler capacity")
        self.otd["015:LB"]   = OTData("015", "R", "0-7", "U8", 0, 100, "%", "Minimum boiler modulation level")
        self.otd["016"]      = OTData("016", "W", ""   , "F8.8", -40, 127, "°C", "Room Setpoint")
        self.otd["017"]      = OTData("017", "R", ""   , "F8.8", 0, 100, "%", "Relative Modulation Level")
        self.otd["018"]      = OTData("018", "R", ""   , "F8.8", 0, 5, "bar", "Water pressure in CH circuit")
        self.otd["019"]      = OTData("019", "R", ""   , "F8.8", 0, 16, "l/min", "Water flow rate in DHW circuit")
        self.otd["020"]      = OTData("020", "RW", ""  , ""  , 0, 0, "", "Time and DoW")
        self.otd["020R"]     = OTData("020", "R", ""   , "BF"  , 0, 0, "", "")
        self.otd["020R:HB0"] = OTData("020", "R", "13-15", "U8", 0, 7, "", "Day of Week")
        self.otd["020R:HB1"] = OTData("020", "R", "8-12", "U8", 0, 23, "", "Hours")
        self.otd["020R:LB"]  = OTData("020", "R", "0-7", "U8", 0, 59, "", "Minutes")
        self.otd["020W"]     = OTData("020", "W", ""   , ""  , 0, 0, "", "Day of Week and Time of Day")
        self.otd["020W:HB0"] = OTData("020", "W", "13-15", "U8", 0, 7, "", "Day of Week")
        self.otd["020W:HB1"] = OTData("020", "W", "8-12", "U8", 0, 23, "", "Hours")
        self.otd["020W:LB"]  = OTData("020", "W", "0-7", "U8", 0, 59, "", "Minutes")
        self.otd["021"]      = OTData("021", "RW", ""   , ""  , 0, 0, "", "Calendar date")
        self.otd["021R"]     = OTData("021", "R", ""   , "BF", 0, 0, "", "Calendar date")
        self.otd["021R:HB"]  = OTData("021", "R", "8-15", "U8", 1, 12, "", "Month")
        self.otd["021R:LB"]  = OTData("021", "R", "0-7", "U8", 1, 31, "", "Day")
        self.otd["021W"]     = OTData("021", "W", ""   , "BF", 0, 0, "", "")
        self.otd["021W:HB"]  = OTData("021", "W", "8-15", "U8", 1, 12, "", "Month")
        self.otd["021W:LB"]  = OTData("021", "W", "0-7", "U8", 1, 31, "", "Day")
        self.otd["022"]      = OTData("022", "RW", ""  , ""  , 0, 0, "", "Calendar year")
        self.otd["022R"]     = OTData("022", "R", ""   , "U16", 0, 65535, "", "Year")
        self.otd["022W"]     = OTData("022", "W", ""   , "U16", 0, 65535, "", "Year")
        self.otd["023"]      = OTData("023", "W", ""   , "F8.8", -40, 127, "°C", "Room Setpoint for 2nd CH circuit")
        self.otd["024"]      = OTData("024", "W", ""   , "F8.8", -40, 127, "°C", "Room temperature (°C)")
        self.otd["025"]      = OTData("025", "R", ""   , "F8.8", -40, 127, "°C", "Boiler flow water temperature")
        self.otd["026"]      = OTData("026", "R", ""   , "F8.8", -40, 127, "°C", "DHW temperature")
        self.otd["027"]      = OTData("027", "R", ""   , "F8.8", -40, 127, "°C", "Outside temperature")
        self.otd["028"]      = OTData("028", "R", ""   , "F8.8", -40, 127, "°C", "Return water temperature")
        self.otd["029"]      = OTData("029", "R", ""   , "F8.8", -40, 127, "°C", "Solar storage temperature")
        self.otd["030"]      = OTData("030", "R", ""   , "S16", -40, 250, "°C", "Solar collector temperature")
        self.otd["031"]      = OTData("031", "R", ""   , "F8.8", -40, 127, "°C", "Flow water temperature CH2 circuit")
        self.otd["032"]      = OTData("032", "R", ""   , "F8.8", -40, 127, "°C", "Domestic hot water temperature 2")
        self.otd["033"]      = OTData("033", "R", ""   , "S16", -40, 500, "°C", "Boiler exhaust temperature")
        self.otd["034"]      = OTData("034", "R", ""   , "F8.8", -40, 127, "°C", "Boiler heat exchanger temperature") # unsure
        self.otd["035"]      = OTData("035", "R", ""   , "U16"  , 0, 0, "", "Boiler fan speed") # rpm/60? unsure
# could also be
#        self.otd["035:HB"]      = OTData("035", "R", ""   , "U8"  , 0, 255, "", "Boiler fan speed Setpoint")
#        self.otd["035:LB"]      = OTData("035", "R", ""   , "U8"  , 0, 255, "", "Boiler fan speed actual value")
        self.otd["036"]      = OTData("036", "R", ""   , "F8.8"  , -128, 127, "µA", "Electrical current through burner flame") # unsure
        self.otd["037"]      = OTData("037", "W", ""   , "F8.8"  , -40, 127, "°C", "Room temperature for 2nd CH circuit") # unsure
        self.otd["038"]      = OTData("038", "W", ""   , "F8.8"  , 0, 0, "%", "Relative Humidity") # unsure
        self.otd["048"]      = OTData("048", "R", ""   , "BF"  , 0, 0, "", "DHW Setpoint bounds for adjustment")
        self.otd["048:HB"]   = OTData("048", "R", "8-15", "S8" , 0, 127, "°C", "Upper bound")
        self.otd["048:LB"]   = OTData("048", "R", "0-7", "S8"  , 0, 127, "°C", "Lower bound")
        self.otd["049"]      = OTData("049", "R", ""   , "BF"  , 0, 0, "°C", "Max CH water Setpoint bounds for adjustment")
        self.otd["049:HB"]   = OTData("049", "R", "8-15", "S8" , 0, 127, "°C", "Upper bound")
        self.otd["049:LB"]   = OTData("049", "R", "0-7", "S8"  , 0, 127, "°C", "Lower bound")
        self.otd["050"]      = OTData("050", "R", ""   , "BF"  , 0, 0, "", "OTC HC-Ratio bounds") # unsure
        self.otd["050:HB"]   = OTData("050", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["050:LB"]   = OTData("050", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["051"]      = OTData("051", "R", ""   , "BF"  , 0, 0, "", "Remote param 3") # unsure
        self.otd["051:HB"]   = OTData("051", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["051:LB"]   = OTData("051", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["052"]      = OTData("052", "R", ""   , "BF"  , 0, 0, "", "Remote param 4") # unsure
        self.otd["052:HB"]   = OTData("052", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["052:LB"]   = OTData("052", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["053"]      = OTData("053", "R", ""   , "BF"  , 0, 0, "", "Remote param 5") # unsure
        self.otd["053:HB"]   = OTData("053", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["053:LB"]   = OTData("053", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["054"]      = OTData("054", "R", ""   , "BF"  , 0, 0, "", "Remote param 6") # unsure
        self.otd["054:HB"]   = OTData("054", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["054:LB"]   = OTData("054", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["055"]      = OTData("055", "R", ""   , "BF"  , 0, 0, "", "Remote param 7") # unsure
        self.otd["055:HB"]   = OTData("055", "R", "8-15", "S8" , -128, 127, "", "Upper bound")
        self.otd["055:LB"]   = OTData("055", "R", "0-7", "S8"  , -128, 127, "", "Lower bound")
        self.otd["056"]      = OTData("056", "RW", ""  , ""  , 0, 0, "°C", "DHW Setpoint (Remote param 0)")
        self.otd["056R"]     = OTData("056", "R", ""   , "F8.8", 0, 127, "°C", "Current DHW Setpoint (Remote param 0)")
        self.otd["056W"]     = OTData("056", "W", ""   , "F8.8", 0, 127, "°C", "DHW Setpoint to set(Remote param 0)")
        self.otd["057"]      = OTData("057", "RW", ""  , ""  , 0, 0, "°C", "Max CH water Setpoint (Remote param 1)")
        self.otd["057R"]     = OTData("057", "R", ""   , "F8.8", 0, 127, "°C", "Current Max CH water Setpoint (Remote param 1)")
        self.otd["057W"]     = OTData("057", "W", ""   , "F8.8", 0, 127, "°C", "Max CH water Setpoint to set (Remote param 1)")
        self.otd["058"]      = OTData("058", "RW", ""  , ""  , 0, 0, "°C", "OTC HC Ratio (Remote param 2)") # unsure
        self.otd["058R"]     = OTData("058", "R", ""   , "F8.8", 0, 127, "°C", "Current OTC HC Ratio (Remote param 2)") # unsure
        self.otd["058W"]     = OTData("058", "W", ""   , "F8.8", 0, 127, "°C", "OTC HC Ratio to set (Remote param 2)") # unsure
        self.otd["059"]      = OTData("059", "RW", ""  , ""  , 0, 0, "", "(Remote param 3)")
        self.otd["059R"]     = OTData("059", "R", ""   , "F8.8", 0, 127, "", "Current (Remote param 3)")
        self.otd["059W"]     = OTData("059", "W", ""   , "F8.8", 0, 127, "", "to set (Remote param 3)")
        self.otd["060"]      = OTData("060", "RW", ""  , ""  , 0, 0, "", "(Remote param 4)")
        self.otd["060R"]     = OTData("060", "R", ""   , "F8.8", 0, 127, "", "Current (Remote param 4)")
        self.otd["060W"]     = OTData("060", "W", ""   , "F8.8", 0, 127, "", "to set (Remote param 4)")
        self.otd["061"]      = OTData("061", "RW", ""  , ""  , 0, 0, "", "(Remote param 5)")
        self.otd["061R"]     = OTData("061", "R", ""   , "F8.8", 0, 127, "", "Current (Remote param 5)")
        self.otd["061W"]     = OTData("061", "W", ""   , "F8.8", 0, 127, "", "to set (Remote param 5)")
        self.otd["062"]      = OTData("062", "RW", ""  , ""  , 0, 0, "", "(Remote param 6)")
        self.otd["062R"]     = OTData("062", "R", ""   , "F8.8", 0, 127, "", "Current (Remote param 6)")
        self.otd["062W"]     = OTData("062", "W", ""   , "F8.8", 0, 127, "", "to set (Remote param 6)")
        self.otd["063"]      = OTData("063", "RW", ""  , ""  , 0, 0, "", "(Remote param 7)")
        self.otd["063R"]     = OTData("063", "R", ""   , "F8.8", 0, 127, "", "Current (Remote param 7)")
        self.otd["063W"]     = OTData("063", "W", ""   , "F8.8", 0, 127, "", "to set (Remote param 7)")
        self.otd["070"]      = OTData("070", "R", "",    "BF", 0, 0, "", "Status ventilation / heat-recovery") # unsure
        self.otd["070:HB0"]  = OTData("070", "R", "HB0", "BF", 0, 1, "", "Master status ventilation / heat-recovery: Ventilation enable") # unsure
        self.otd["070:HB1"]  = OTData("070", "R", "HB1", "BF", 0, 1, "", "Master status ventilation / heat-recovery: Bypass postion") # unsure
        self.otd["070:HB2"]  = OTData("070", "R", "HB2", "BF", 0, 1, "", "Master status ventilation / heat-recovery: Bypass mode") # unsure
        self.otd["070:HB3"]  = OTData("070", "R", "HB3", "BF", 0, 1, "", "Master status ventilation / heat-recovery: Free ventilation mode") # unsure
        self.otd["070:LB0"]  = OTData("070", "R", "LB0", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Fault indication") # unsure
        self.otd["070:LB1"]  = OTData("070", "R", "LB1", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Ventilation mode") # unsure
        self.otd["070:LB2"]  = OTData("070", "R", "LB2", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Bypass status") # unsure
        self.otd["070:LB3"]  = OTData("070", "R", "LB3", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Bypass automatic status") # unsure
        self.otd["070:LB4"]  = OTData("070", "R", "LB4", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Free ventilation status") # unsure
        self.otd["070:LB6"]  = OTData("070", "R", "LB6", "BF", 0, 1, "", "Slave status ventilation / heat-recovery: Diagnostic indication") # unsure
        self.otd["071"]      = OTData("071", "R", ""   , ""  , 0, 0, "", "Relative ventilation position (0-100%). 0% is the minimum set ventilation and 100% is the maximum set ventilation") # unsure
        self.otd["072"]      = OTData("072", "R", ""   , ""  , 0, 0, "", "Application-specific fault flags and OEM fault code ventilation / heat-recovery") # unsure
        self.otd["073"]      = OTData("073", "R", ""   , ""  , 0, 0, "", "An OEM-specific diagnostic/service code for ventilation / heat-recovery system") # unsure
        self.otd["074"]      = OTData("074", "R", "",    "BF", 0, 1, "", "Slave Configuration ventilation / heat-recovery") # unsure
        self.otd["074:HB0"]  = OTData("074", "R", "HB0", "BF", 0, 1, "", "Ventilation enabled") # unsure
        self.otd["074:HB1"]  = OTData("074", "R", "HB1", "BF", 0, 1, "", "Bypass position") # unsure
        self.otd["074:HB2"]  = OTData("074", "R", "HB2", "BF", 0, 1, "", "Bypass mode") # unsure
        self.otd["074:HB3"]  = OTData("074", "R", "HB3", "BF", 0, 1, "", "Speed control") # unsure
        self.otd["074:LB"]   = OTData("074", "R", "0-7", "U8", 0, 255, "", "Slave MemberID Code ventilation / heat-recovery") # unsure
#!!! not properly checked from below
        self.otd["075"]      = OTData("075", "R", ""   , "U16", 0, 0, "", "The implemented version of the OpenTherm Protocol Specification in the ventilation / heat-recovery system")
        self.otd["076"]      = OTData("076", "R", ""   , "U16", 0, 0, "", "Ventilation / heat-recovery product version number and type")
        self.otd["077"]      = OTData("077", "R", ""   , "U16", 0, 100, "%", "Relative ventilation")
        self.otd["078"]      = OTData("078", "R", ""   , "U16", 0, 100, "%", "Relative humidity exhaust air")
        self.otd["079"]      = OTData("079", "R", ""   , "U16", 0, 2000, "ppm", "CO2 level exhaust air")
        self.otd["080"]      = OTData("080", "R", ""   , "U16", 0, 0, "°C", "Supply inlet temperature")
        self.otd["081"]      = OTData("081", "R", ""   , "U16", 0, 0, "°C", "Supply outlet temperature")
        self.otd["082"]      = OTData("082", "R", ""   , "U16", 0, 0, "°C", "mExhaust inlet temperature")
        self.otd["083"]      = OTData("083", "R", ""   , "U16", 0, 0, "°C", "Exhaust outlet temperature")
        self.otd["084"]      = OTData("084", "R", ""   , "U16", 0, 0, "rpm", "Exhaust fan speed")
        self.otd["085"]      = OTData("085", "R", ""   , "U16", 0, 0, "rpm", "Supply fan speed")
        self.otd["086"]      = OTData("086", "R", "",    "BF", 0, 0, "", "Remote ventilation / heat-recovery parameter:")
        self.otd["086:HB0"]  = OTData("086", "R", "HB0", "BF", 0, 0, "", "Transfer-enable: Nominal ventilation value")
        self.otd["086:LB0"]  = OTData("086", "R", "LB0", "BF", 0, 0, "", "Read/write : Nominal ventilation value")
        self.otd["087"]      = OTData("087", "R", ""   , "U16", 0, 100, "%", "Nominal relative value for ventilation")
        self.otd["088"]      = OTData("088", "R", ""   , "U16", 0, 255, "", "Number of Transparent-Slave-Parameters supported by TSP’s ventilation / heat-recovery")
        self.otd["089"]      = OTData("089", "R", ""   , "U16", 0, 255, "", "Index number / Value of referred-to transparent TSP’s ventilation / heat-recovery parameter")
        self.otd["090"]      = OTData("090", "R", ""   , "U16", 0, 255, "", "Size of Fault-History-Buffer supported by ventilation / heat-recovery")
        self.otd["091"]      = OTData("091", "R", ""   , "U16", 0, 255, "", "Index number / Value of referred-to fault-history buffer entry ventilation / heat-recovery")
# from https://www.opentherm.eu/request-details/?post_ids=3931
        self.otd["093"]      = OTData("093", "R", ""   , "U16", 0, 65535, "", "Brand Index / Slave Brand name")
        self.otd["094"]      = OTData("094", "R", ""   , "U16", 0, 65535, "", "Brand Version Index / Slave product type/version")
        self.otd["095"]      = OTData("095", "R", ""   , "U16", 0, 65535, "", "Brand Serial Number index / Slave product serialnumber")
        self.otd["098"]      = OTData("098", "R", ""   , "U16", 0, 255, "", "For a specific RF sensor the RF strength and battery level is written")
        self.otd["099"]      = OTData("099", "R", ""   , "U16", 0, 255, "", "Operating Mode HC1, HC2/ Operating Mode DHW")
# to check
        self.otd["100"]      = OTData("100", "R", ""   , "U16", 0, 255, "", "Function of manual and program changes in master and remote room Setpoint")
        self.otd["101"]      = OTData("101", "R", ""   , "BF", 0, 0, "", "Solar Storage:")
        self.otd["101:HB"]   = OTData("101", "R", "8-10", "U8", 0, 0, "", "Master Solar Storage: Solar mode")
        self.otd["101:LB0"]  = OTData("101", "R", "LB0", "BF", 0, 0, "", "Slave Solar Storage: Fault indication")
        self.otd["101:LB1"]  = OTData("101", "R", "1-3", "U8", 0, 7, "", "Slave Solar Storage: Solar mode status")
        self.otd["101:LB2"]  = OTData("101", "R", "4-5", "U8", 0, 3, "", "Slave Solar Storage: Solar status")
        self.otd["102"]      = OTData("102", "R", ""   , ""  , 0, 0, "", "Application-specific fault flags and OEM fault code Solar Storage")
        self.otd["103"]      = OTData("103", "R", "",    "BF", 0, 0, "", "Slave Configuration Solar Storage")
        self.otd["103:HB0"]  = OTData("103", "R", "HB0", "BF", 0, 0, "", "System type")
        self.otd["103:LB"]   = OTData("103", "R", "0-7", "U8", 0, 255, "", "Slave MemberID")
        self.otd["104"]      = OTData("104", "R", ""   , "U16", 0, 255, "", "Solar Storage product version number and type")
        self.otd["105"]      = OTData("105", "R", ""   , "U16", 0, 255, "", "Number of Transparent-Slave-Parameters supported by TSP’s Solar Storage")
        self.otd["106"]      = OTData("106", "R", ""   , "U16", 0, 255, "", "Index number / Value of referred-to transparent TSP’s Solar Storage parameter")
        self.otd["107"]      = OTData("107", "R", ""   , "U16", 0, 255, "", "Size of Fault-History-Buffer supported by Solar Storage")
        self.otd["108"]      = OTData("108", "R", ""   , "U16", 0, 255, "", "Index number / Value of referred-to fault-history buffer entry Solar Stor")
        self.otd["109"]      = OTData("109", "R", ""   , "U16", 0, 255, "", "Electricity producer starts")
        self.otd["110"]      = OTData("110", "R", ""   , "U16", 0, 255, "", "Electricity producer hours")
        self.otd["111"]      = OTData("111", "R", ""   , "U16", 0, 255, "", "Electricity production")
        self.otd["112"]      = OTData("112", "R", ""   , "U16", 0, 255, "", "Cumulativ Electricity production")
        self.otd["113"]      = OTData("113", "R", ""   , "U16", 0, 255, "", "Number of un-successful burner starts")
        self.otd["114"]      = OTData("114", "R", ""   , "U16", 0, 255, "", "Number of times flame signal was too low")
# below data-ids are checked up against specs
        self.otd["115"]      = OTData("115", "R", ""   , "U16", 0, 255, "", "OEM-specific diagnostic/service code")
        # below ids are RW (write 0 to reset)
        self.otd["116"]      = OTData("116", "R", ""   , "U16", 0, 65535, "", "Number of succesful starts burner")
        self.otd["117"]      = OTData("117", "R", ""   , "U16", 0, 65535, "", "Number of starts CH pump")
        self.otd["118"]      = OTData("118", "R", ""   , "U16", 0, 65535, "", "Number of starts DHW pump/valve")
        self.otd["119"]      = OTData("119", "R", ""   , "U16", 0, 65535, "", "Number of starts burner during DHW mode")
        self.otd["120"]      = OTData("120", "R", ""   , "U16", 0, 65535, "", "Number of hours that burner is in operation (i.e. flame on)")
        self.otd["121"]      = OTData("121", "R", ""   , "U16", 0, 65535, "", "Number of hours that CH pump has been running")
        self.otd["122"]      = OTData("122", "R", ""   , "U16", 0, 65535, "", "Number of hours that DHW pump has been running or DHW valve has been opened")
        self.otd["123"]      = OTData("123", "R", ""   , "U16", 0, 65535, "", "Number of hours that burner is in operation during DHW mode")
        # ^^^
        self.otd["124"]      = OTData("124", "W", ""   , "F8.8", 1, 127, "", "The implemented version of the OpenTherm Protocol Specification in the master")
        self.otd["125"]      = OTData("125", "R", ""   , "F8.8", 1, 127, "", "The implemented version of the OpenTherm Protocol Specification in the slave")
        self.otd["126"]      = OTData("126", "W", ""   , "BF"  , 0, 0, "", "Master product version number and type")
        self.otd["126:HB"]   = OTData("126", "W", "8-15", "U8"  , 0, 255, "", "Master product version number and type")
        self.otd["126:LB"]   = OTData("126", "W", "0-7", "U8"  , 0, 255, "", "Master product version number and type")
        self.otd["127"]      = OTData("127", "R", ""   , "BF"  , 0, 0, "", "Slave product version number and type")
        self.otd["127:HB"]   = OTData("127", "R", "8-15", "U8"  , 0, 255, "", "Slave product version number and type")
        self.otd["127:LB"]   = OTData("127", "R", "0-7", "U8"  , 0, 255, "", "Slave product version number and type")
# baxi ecofour unspecified regs
        self.otd["129"]      = OTData("129", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 129")
        self.otd["130"]      = OTData("130", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 130")
        self.otd["131"]      = OTData("131", "R", ""   , "BF", 0, 0, "", "Remeha codes:")
        self.otd["131:HB"]   = OTData("131", "R", "8-15", "U8", 0, 255, "", "dU")
        self.otd["131:LB"]   = OTData("131", "R", "0-7", "U8", 0, 255, "", "dF")
        self.otd["132"]      = OTData("132", "R", ""   , "BF", 0, 0, "", "Remeha Servicemessage:")
        self.otd["132:HB"]   = OTData("132", "R", "8-15", "U8", 0, 255, "", "Next service type")
        self.otd["132:LB"]   = OTData("132", "R", "0-7", "U8", 0, 255, "", "?")
        self.otd["133"]      = OTData("133", "W", ""   , "U16", 0, 511, "", "Remeha detection connected SCU’s")
        self.otd["149"]      = OTData("149", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 149")
        self.otd["150"]      = OTData("150", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 150")
        self.otd["151"]      = OTData("151", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 151")
        self.otd["173"]      = OTData("173", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 173")
        self.otd["198"]      = OTData("198", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 198")
        self.otd["199"]      = OTData("199", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 199")
        self.otd["200"]      = OTData("200", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 200")
        self.otd["202"]      = OTData("202", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 202")
        self.otd["203"]      = OTData("203", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 203")
        self.otd["204"]      = OTData("204", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 204")
        self.otd["209"]      = OTData("209", "R", ""   , "U16", 0, 65535, "", "BAXI data-id 209")


        # from https://otgw.tclcode.com/details.cgi
        self.OT_MEMBERS = { 
            0: "Unspecified",
            2: "AWB",
            4: "Multibrand", # Atag, Baxi Slim, Brötje, Elco
            5: "Itho Daalderop",
            6: "Daikin/Ideal",
            8: "Biasi/Buderus/Logamax", 
            9: "Ferroli/Agpo",
            11: "De Dietrich/Remeha/Baxi Prime", 
            13: "Cetetherm",
            16: "Unical",
            18: "Bosch",
            24: "Vaillant/AWB/Bulex", 
            27: "Baxi",
            29: "Daalderop/Itho",
            33: "Viessmann",
            41: "Radiant",
            56: "Baxi Luna",
            131: "Netfit/Bosch",
            173: "Intergas"
        }


    # return opentherm master-to-slave and slave-to-master message names by numeric id
    def msg_descr(self, resp):
        if resp < 0 or resp > 7:
            return "!LAME!"
        else:
            return self.OT_MSGS[resp]

    # extract response bits based on otd descriptions of data position
    def get_bits(self, value, pos):
        if pos[0:2] == "LB":
            return (value >> int(pos[2])) & 1
        elif pos[0:2] == "HB":
            return (value >> (8+int(pos[2]))) & 1
        else:
            iv = pos.split("-")
            mask = 0
            for i in range(0, int(iv[1]) - int(iv[0]) + 1):
                mask = (mask << 1) | 1
            return (value >> int(iv[0])) & mask
    
    # decode opentherm data-value based on it's pos and fmt; 
    # return: ( string representation, 1 if success else -1 )
    def decode_value(self, value, fmt, pos):
        if fmt == "U8" or fmt == "BF":
            if pos != "":
                v = self.get_bits(value, pos) & 0xff
            else:
                v  = (value & 0xff)
            return "%u" % v, 1
        elif fmt == "U16":
            return "%u" % (value & 0xffff), 1
        elif fmt == "S8":
            if pos != "":
                v = self.get_bits(value, pos) & 0xff
            else:
                v = value & 0xff
            if v > 127:
                return "-%u" % (256 - v), 1
            else:
                return "%u" % v, 1
        elif fmt == "S16":
            if value > 32767:
                return "-%u" % (65536 - (value & 0xffff)), 1
            else:
                return "%u" % (value & 0xffff), 1
        elif fmt == "F8.8": # # 1/256 gives 0.00390625 i.e. 8 fractional decimal digits but it useless in this certain practical case, let's limit output to 3 decimal digits to get something out of smallest possible number
            v = value & 0xffff
            if v > 32767:
                return ("-%.3f" % ((65536-v)/256)).rstrip('0').rstrip('.'), 1 # default %f formatting produces extra trailing zeroes
            else:
                return ("%.3f" % (v/256)).rstrip('0').rstrip('.'), 1
        else:
            # unknown format
            return "###", -1

    # decode description string (if it has conditional parts separated by ';')
    def decode_descr(self, descr, val):
        if ';' not in descr:
            return descr;
        ds = descr.split(';')
        for d in ds:
            c  = d.split(' ', 1)
            if eval(val + c[0]):
                return c[1]
        return "unknown value " + val

    # decode and describe opentherm data-value using direct otd[] lookup by dids
    def describe_dataid(self, dids, val):
        descr = ""
        if self.otd[dids].fmt == "BF":
            descr = self.otd[dids].descr
            for variant in ( "HB", "HB0", "HB1", "HB2", "HB3", "HB4", "HB5", "HB6", "HB7", "LB", "LB0", "LB1", "LB2", "LB3", "LB4", "LB5", "LB6", "LB7" ):
                varid = dids + ":" + variant
                if varid in self.otd:
                    vv, vc = self.decode_value(val, self.otd[varid].fmt, self.otd[varid].pos)
                    if vc > 0:
                        if '-' in self.otd[varid].pos: # multibit field
                            descr = descr + "; " + self.decode_descr(self.otd[varid].descr, vv) + " = " + vv + self.otd[varid].units
                            if float(vv) < self.otd[varid].min or float(vv) > self.otd[varid].max:
                                descr = descr + " - out of range!"
                        else:
                            descr = descr + "; " + ("+" if vv == "1" else "-") + self.otd[varid].descr
                        if varid == "003:LB" or varid == "002:LB" or varid == "074:LB" or varid == "103:LB":
                            descr = descr + " (" + self.describe_member(int(vv)) + ")"
                    else:
                        return "Unable to decode value \'" + val + "\' as per fmt " + self.otd[varid].fmt + " from pos " +  self.otd[varid].pos , -1
        else:
            v,c = self.decode_value(val, self.otd[dids].fmt, self.otd[dids].pos)
            if c < 0:
                return "Unable to decode value \'" + val + "\' as per fmt " + self.otd[dids].fmt + " from pos " +  self.otd[dids].pos , -1
            descr = self.decode_descr(self.otd[dids].descr, v) + "; " + v + self.otd[dids].units
            if float(v) < self.otd[dids].min or float(v) > self.otd[dids].max:
                descr = descr + " - out of range!"
        return descr, 1


    # describe either read or write opentherm request/response
    def describe_param_internal(self, dids, t_dir, val_sent, val_received, do_print):
        descr = ""
        if not dids in self.otd:
            if do_print:
                print("Data-id " + dids + " is unknown")
            return "Unknown data-id", -3
        if not t_dir in self.otd[dids].t_dir:
            if do_print:
                print("Data-id " + dids + "/" + t_dir + " is unknown")
            return "Unknown data-id direction", -3

        if t_dir == "R":
            if (val_sent >= 0) and ("I" in self.otd[dids].t_dir):
                descr = descr + " Read input value: "
                vv2, vc2 = self.describe_dataid(dids + "I", val_sent)
                if vc2 < 0:
                    return vv2, vc2
                descr = descr + vv2 + " "
            else:
                descr = self.otd[dids].descr
            if (val_received >= 0):
                vv, vc = self.describe_dataid(dids, val_received)
                if vc < 0:
                    return vv, vc
                descr = descr + " Response: " + vv
        else: # assume "W"
           if (val_sent >=0):
               vv, vc = self.describe_dataid(dids, val_sent)
               if vc < 0:
                    return vv, vc
               descr = descr + "Written: " + vv + " "
           if (val_received >=0) and ("O" in self.otd[dids].t_dir):
                descr = descr + " Write output value: "
                vv2, vc2 = self.describe_dataid(dids + "I", val_received)
                if vc2 < 0:
                    return vv2, vc2
                descr = descr + vv2
           else:
                descr = self.otd[dids].descr
        if do_print:
            print(descr)
        return descr, 1

    # most generic opentherm request/response decoder
    def describe_param(self, data_id, t_dir, value_sent, value_received, do_print=False):
        if value_sent is int:
            vsn = value_sent
        else:
            try:
                vsn = int(value_sent)
            except:
                if do_print:
                    print("Value \'" + value_sent + "\' is not a number")
                return "NaN", -2
        if value_received is int:
            vrn = value_received
        else:
            try:
                vrn = int(value_received)
            except:
                if do_print:
                    print("Value \'" + value_received + "\' is not a number")
                return "NaN", -2
        if type(data_id) is int:
            dids = "%03d" % data_id
        if type(data_id) is str:
            dids = ("00" + data_id)[-3:]
        if not dids in self.otd:
            if do_print:
                print("Data-id " + dids + " is unknown")
            return "Unknown data-id", -3
        if self.otd[dids].t_dir == "RW":
            r, c = self.describe_param_internal(dids + t_dir, t_dir, vsn, vrn, do_print)
            return self.otd[dids].descr + ": " + r, c
        return self.describe_param_internal(dids, t_dir, vsn, vrn, do_print)

    def describe_member(self, member_id):
        if member_id in self.OT_MEMBERS:
            return self.OT_MEMBERS[member_id]
        else:
            return "UNKNOWN"
         
    def parse_val(self, val):
        vn = ""
        if "+" in val:
            vals = val.split('+')
            sum = 0
            for v in vals:
                sum = sum + self.parse_val(v)
            return sum & 0xffff
        cv = "?" # for exception reporting
        try:
            if "%" in val:
                v = val.split('%')
                vn = v[0]
                if v[1] == "F8.8": # float %8.8f
                    cv = v[0]
                    if "~" == cv[0:1]:
                        nf = -float(cv[1:])
                    else: 
                        nf = float(cv)
                    nf = nf * 256
                    n = int(nf)
                    return n & 0xffff
                elif v[1][0:1] == "B": # 16bit word's bit %B<N> or bitrange %B<N>-<M>
                    cv = vn
                    n = int(cv)
                    if "-" in v[1]:
                        br = v[1][1:].split('-')
                        vn = br[0]
                        cv = vn
                        bl = int(cv)
                        vn = br[1]
                        cv = vn
                        bh = int(cv)
                        mask = 0
                        for i in range(0, (bh - bl) + 1):
                            mask = (mask << 1) | 1
                        return (n & mask) << bl
                    else:
                        n = n & 1
                        vn = v[1][1:]
                        cv = vn
                        b = int(cv)
                        return n << b
                elif v[1][0:2] == "HB": # 8bit high byte or numbered bit %HB<N>
                    if v[1][2:3].isdigit:
                        cv = v[1][2:3]
                        bn = int(cv)
                        cv = vn
                        return (int(cv) & 255) << (8 + bn)
                    cv = vn
                    return (int(cv) & 255) << 8
                elif v[1][0:2] == "LB": # 8bit low byte or numbered bit %LB<N>
                    if v[1][2:3].isdigit:
                        cv = v[1][2:3]
                        bn = int(cv)
                        cv = vn
                        return (int(cv) & 255) << (bn)
                    cv = vn
                    return (int(cv) & 255)
                else:
                    raise ValueError("Invalid opentherm number format \'" + v[1] + "\'")
            cv = val # pure number
            n = int(cv)
            return n
        except:
            logging.error("Invalid numeric value \'" + cv + "\'")
            raise

