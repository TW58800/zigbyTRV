from machine import ADC
import struct
import xbee
import time
from sys import stdout


def log(info):
    with open('trvlog.txt', 'w') as f:
        print(info + '\n', file=f)


class TRV:
    xbee = xbee
    valve = None
    data = [0]
    on_off_attributes = {
        'OnOff': True}
    msg = {'sender': "", 'payload': bytearray(), 'cluster': 0, 'source_ep': 0, 'dest_ep': 0, 'profile': 0,
           'address_low': 0,
           'address_high': 0}
    address = 0
    voltage_monitor = ADC('D2')
    awake_flag = 1
    connected_to_HA = True

    def run(self):
        counter = time.ticks_ms()
        while True:
            if self.xbee.atcmd("AI") != 0:
                print('not connected to network')
                self.xbee.atcmd("CB", 1)
                time.sleep_ms(10000)
            self.process_msg()
            if time.ticks_diff(time.ticks_ms(), counter) > 180000:
                counter = time.ticks_ms()
                self.report_attributes()

    def initialise(self):
        self.setup_xbee()
        self.valve.stop_valve()
        self.get_network_address()
        self.valve.home_valve()
        self.report_attributes()

    def setup_xbee(self):
        self.xbee.atcmd("SM", 6)
        # self.xbee.atcmd("AP", 4)  # leave commented out for now as XCTU cannot receive frames in REPL mode
        # self.xbee.atcmd("DH", 0x0013A200)
        # self.xbee.atcmd("DL", 0x41F2DE9F)
        # self.xbee.atcmd("AV", 1)  # analogue voltage reference 2.5V
        self.xbee.atcmd("AV", 2)  # analogue voltage reference VDD

    def report_attributes(self):
        self.report_attribute(0x0000, 0x55)
        self.report_attribute(0x0001, 0x55)
        self.report_attribute(0x0002, 0x55)
        self.report_attribute(0x0006, 0x55)
        self.report_attribute(0x000d, 0x55)
        self.report_attribute(0x000d, 0x01)
        self.report_attribute(0x000d, 0x02)
        # print("sleeping for 60 seconds\n")
        # self.awake_flag = 0
        self.report_attribute(0x000f, 0x55)
        # self.xbee.XBee().sleep_now(60000, pin_wake=True)
        # self.awake_flag = 1
        # self.report_attributes(0x000f)

    def send(self):
        try:
            xbee.transmit(xbee.ADDR_COORDINATOR, self.msg['payload'], source_ep=self.msg['source_ep'],
                          dest_ep=self.msg['dest_ep'],
                          cluster=self.msg['cluster'], profile=self.msg['profile'], bcast_radius=0, tx_options=0)
            print('Transmit to coordinator: %s\n' % self.msg['payload'])
        except OSError:
            print('OSError - could not send to coordinator')

    def send_broadcast_digi_data(self, string):
        try:
            time.sleep_ms(200)
            xbee.transmit(xbee.ADDR_BROADCAST, string)
        except OSError:
            print('OSError - could not send digi data')

    def send_for_printing(self, info):
        self.msg['source_ep'] = 0xf0
        self.msg['profile'] = 0x0104
        self.msg['dest_ep'] = 0xf0
        self.msg['payload'] = info
        try:
            xbee.transmit(xbee.ADDR_BROADCAST, self.msg['payload'], source_ep=self.msg['source_ep'],
                          dest_ep=self.msg['dest_ep'],
                          cluster=self.msg['cluster'], profile=self.msg['profile'], bcast_radius=0, tx_options=0)
            print('Transmit for printing: %s\n' % self.msg['payload'])
        except OSError:
            print('OSError - could not send for printing')

    def reference_voltage(self):
        av = self.xbee.atcmd("AV")
        if av == 0:
            return 1250
        elif av == 1:
            return 2500
        else:
            return self.xbee.atcmd(
                "%V")  # using a Voltage step-up 2.4V to 3.3V and measuring the AA battery voltage on D2
            # return 3300  # using the line Voltage as reference, as a fully charged AA battery starts at 1.5V, so a 2.5 ref would be to low with two AA batteries

    def battery_voltage_mV(self):
        # print(valve.voltage_monitor.read())
        if not self.xbee.atcmd("AV") == 2:
            batt_voltage = int(self.voltage_monitor.read() * (self.reference_voltage() / 4096))
            return batt_voltage
        else:
            # batt_voltage = self.xbee.atcmd("%V")  # using a Voltage step-up 2.4V to 3.3V and measuring the battery Vltage on D2
            batt_voltage = int(self.voltage_monitor.read() * (self.reference_voltage() / 4096))
            return batt_voltage

    def battery_voltage(self):
        return self.battery_voltage_mV() // 100  # power configuration cluster measures in 100mV increments

    def battery_percentage_remaining(self):
        voltage_as_percentage = int(
            (
                        self.battery_voltage_mV() - 2000) * 0.3)  # 2.4 volts is 63%  HA expects a value between 0 and 200 (0.5% resolution)
        if voltage_as_percentage > 255:
            voltage_as_percentage = 255
        if voltage_as_percentage < 0:
            voltage_as_percentage = 0
        # print('voltage: {:04.1f}%'.format(voltage_as_percentage / 2))
        return voltage_as_percentage

    def get_temperature(self):
        tp = self.xbee.atcmd('TP')
        if tp > 0x7FFF:
            tp = tp - 0x10000
        return tp * 100  # HA measures temperature in 100ths of a degree

    def get_network_address(self):
        # wait for a connection to be established
        print('\nconnecting...\n')
        if self.xbee.atcmd("AI") != 0:
            self.connected_to_HA = False
        while self.xbee.atcmd("AI") != 0:
            time.sleep(5)
            print('waiting for a join window...')
        # Get the XBee's 16-bit network address
        print('connected...\n')
        self.address = self.xbee.atcmd("MY")
        print('address: %04x' % self.address)
        log('%04i: address: %04x' % (time.ticks_ms(), self.address))
        self.send_broadcast_digi_data('address: %04x\n' % self.address)
        self.msg['address_high'] = self.address >> 8
        self.msg['address_low'] = self.address & 0xff
        print("device ready...\n")
        if not self.connected_to_HA:
            print('connecting to HA, wait one minute')
            timer = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), timer) < 60000:
                self.process_msg()
            self.connected_to_HA = True

    def process_msg(self):
        # Check if the XBee has any message in the queue.
        received_msg = self.xbee.receive()
        if received_msg is not None:
            self.msg['cluster'] = received_msg['cluster']
            self.msg['dest_ep'] = received_msg['source_ep']
            self.msg['source_ep'] = received_msg['dest_ep']
            self.msg['profile'] = received_msg['profile']
            print("\ndata received from %s >> \npayload: %s \ncluster: %04x \nsource ep: %02x \ndestination ep: %02x"
                  "\nprofile: %04x\n" % (
                      ''.join('{:02x}'.format(x).upper() for x in received_msg['sender_eui64']),
                      received_msg['payload'], received_msg['cluster'],
                      received_msg['source_ep'], received_msg['dest_ep'], received_msg['profile']))
            self.data = list(received_msg['payload'])
            print('sequence number: %02x' % self.data[1])

            # ---------------------------------------------------------------------------------------------------------------------
            # ZDO endpoint
            if received_msg['dest_ep'] == 0x0000:
                # active endpoints request
                if self.msg['cluster'] == 0x0005:
                    self.msg['payload'] = bytearray(
                        '{:c}\x00{:c}{:c}\x03\x01\x02\x55'.format(self.data[0], self.msg['address_low'],
                                                                  self.msg['address_high']))
                    self.msg['cluster'] = 0x8005
                    self.send()
                # simple descriptor request
                elif self.msg['cluster'] == 0x0004:
                    if self.data[3] == 0x55:
                        self.msg['payload'] = bytearray(
                            '{:c}\x00{:c}{:c}\x16'  # length of simple descriptor (last byte)
                            '\x55\x04\x01\x00\x00\x00'  # endpoint, profile id, device description identifier, version+reserved  
                            '\x06'  # input cluster count
                            '\x00\x00'  # basic
                            '\x01\x00'  # power configuration
                            '\x02\x00'  # device temperature configuration
                            '\x06\x00'  # on/off
                            '\x0d\x00'  # analogue output
                            '\x0f\x00'  # binary input
                            '\x01'  # output cluster count
                            '\x10\x00'  # binary output (not recognised by Home Assistant)
                            .format(self.data[0], self.msg['address_low'], self.msg['address_high']))
                    elif self.data[3] == 0x01:
                        self.msg['payload'] = bytearray(
                            '{:c}\x00{:c}{:c}\x08'  # length of simple descriptor (last byte)
                            '\x01\x04\x01\x00\x00\x00'  # endpoint, profile id, device description identifier, version+reserved  
                            '\x01'  # input cluster count 
                            '\x0d\x00'  # analogue input
                            # '\x0f\x00'  # binary input
                            '\x00'  # output cluster count
                            .format(self.data[0], self.msg['address_low'], self.msg['address_high']))
                    elif self.data[3] == 0x02:
                        self.msg['payload'] = bytearray(
                            '{:c}\x00{:c}{:c}\x08'  # length of simple descriptor (last byte)
                            '\x02\x04\x01\x00\x00\x00'  # endpoint, profile id, device description identifier, version+reserved  
                            '\x01'  # input cluster count 
                            '\x0d\x00'  # analogue input
                            # '\x0f\x00'  # binary input
                            '\x00'  # output cluster count
                            .format(self.data[0], self.msg['address_low'], self.msg['address_high']))
                    self.msg['cluster'] = 0x8004
                    self.send()
                # management leave request
                elif self.msg['cluster'] == 0x0034:
                    # restore device configuration to default and leave the network
                    xbee.atcmd("CB", 0x04)
                    self.msg['payload'] = bytearray('{:c}\x00'.format(self.data[0]))
                    self.msg['cluster'] = 0x8034
                    self.send()
                # management permit join request
                elif self.msg['cluster'] == 0x0036:
                    # if disassociated: join network
                    # if associated: wake device for 30 seconds if sleeping / send node identification broadcast
                    xbee.atcmd("CB", 0x01)
                    self.msg['payload'] = bytearray('{:c}\x00'.format(self.data[0]))
                    self.msg['cluster'] = 0x8036
                    self.send()
                else:
                    print('ZDO cluster %04x not supported' % self.msg['cluster'])
                print('Sequence number: %02x\n\n' % self.data[0])
            # ---------------------------------------------------------------------------------------------------------------------
            # endpoint for Tim's radiator valve controller device
            elif received_msg['dest_ep'] == 0x55:
                # 'basic' cluster
                if self.msg['cluster'] == 0x0000:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01' Zigpy asks for attributes 4 (manf name) and 5 (model identifier)
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header global/cluster-specific (2 bits) manufacturer specific (1 bit) direction (1 bit [1 = server to client]) disable default response (1 bit [0 = default response returned, e.g. 1 used when response frame is a direct effect of a previously recieved frame])
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                # '\x00\x00\x00\x20\x02'  # zigby stack version: 02
                                '\x04\x00\x00\x42\x09TW-Design'
                                '\x05\x00\x00\x42\x08MW-Valve'
                                # '\x07\x00\x00\x30\x03'  # power source - 03 = battery
                                .format(self.data[1]))
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'power configuration' cluster
                elif self.msg['cluster'] == 0x0001:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            batt_voltage = bytearray(struct.pack("B", self.battery_voltage()))
                            batt_percentage_remaining = bytearray(struct.pack("B", self.battery_percentage_remaining()))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x20\x00\x00\x20'.format(self.data[1])) + batt_voltage + bytearray(
                                # battery voltage (1 byte - uint8)
                                '\x21\x00\x00\x20') + batt_percentage_remaining + bytearray(
                                '\x31\x00\x00\x30\x03')  # battery size: AA
                            if self.data[3] == 0x21:  # attribute identifier: battery percentage
                                self.msg['payload'] = bytearray(
                                    '\x18{:c}\x01'  # header, sequence number, command identifier
                                    # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                    '\x21\x00\x00\x20'.format(self.data[1])) + self.battery_percentage_remaining()
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'temperature configuration' cluster
                elif self.msg['cluster'] == 0x0002:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            device_temperature = bytearray(struct.pack("h", self.get_temperature()))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x00\x00\x00\x29'.format(self.data[1])) + device_temperature
                            print(device_temperature)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'On/Off' cluster
                elif self.msg['cluster'] == 0x0006:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                '\x00\x00\x00\x10{:c}'  # attribute identifier (2 bytes), status (1 byte) data type (1 byte), value (1 byte)
                                .format(self.data[1], self.on_off_attributes['OnOff']))
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                                .format(self.data[1]))
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                    # cluster specific commands
                    elif self.data[0] & 0b11 == 0b01:
                        # off command
                        if self.data[2] == 0x00:
                            self.on_off_attributes['OnOff'] = False
                        # on command
                        elif self.data[2] == 0x01:
                            self.on_off_attributes['OnOff'] = True
                        # toggle command
                        elif self.data[2] == 0x02:
                            self.on_off_attributes['OnOff'] = not self.on_off_attributes['OnOff']
                        # after acting on a cluster specific command send a 'report attributes' '0x0a' message
                        self.msg['payload'] = bytearray(
                            '\x18{:c}\x0a'  # header, sequence number, command identifier
                            '\x00\x00\x10{:c}'.format(self.data[1], self.on_off_attributes[
                                'OnOff']))  # attribute identifier (2 bytes), data type (1 byte), value (1 byte)
                        self.send()
                        self.valve.demand()
                # 'analogue output' cluster
                elif self.msg['cluster'] == 0x000d:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = bytearray(struct.pack("f", self.valve.valve_sensor.rev_counter))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x11valve_revolutions'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x39'.format(self.data[1])) + present_value + bytearray(
                                # PresentValue (4 bytes)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'binary input' cluster
                elif self.msg['cluster'] == 0x000f:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = b'\x00'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x05awake'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x10'.format(self.data[1])) + present_value + bytearray(
                                # PresentValue (1 byte)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                else:
                    print('cluster: %04x not supported' % self.msg['cluster'])

            # ---------------------------------------------------------------------------------------------------------------------
            # xbee digi data endpoint
            elif received_msg['dest_ep'] == 0xe8:
                if (len(self.data) >= 3) and (self.data[0] & 0b11 == 0b00):
                    cmd = chr(self.data[1]) + chr(self.data[2])
                    print(cmd)
                    if len(self.data) == 3:
                        rsp = xbee.atcmd(cmd)
                        print(rsp)
                    else:
                        rsp = xbee.atcmd(cmd, self.data[3])
                        print(rsp)
                elif (len(self.data) >= 2) and (self.data[0] & 0b11 == 0b01):
                    print('TRV command')
                    if chr(self.data[1]) == 'P':
                        if len(self.data) > 3:
                            position = (self.data[2] << 8) + self.data[3]
                            print('goto revs {0}'.format(position))
                            self.valve.position = position
                            self.valve.goto_revs()
                    if chr(self.data[1]) == 'H':
                        print('home')
                        self.valve.home_valve()
                    if chr(self.data[1]) == 'F':
                        print('forwards')
                        self.valve.motor.forwards()
                    if chr(self.data[1]) == 'O':
                        print('open')
                        self.valve.goto_revs(0)
                    if chr(self.data[1]) == 'C':
                        print('close')
                        self.valve.goto_revs(self.valve.closed_position)
                    if chr(self.data[1]) == 'S':
                        print('stop')
                        self.valve.motor.stop_soft()
                    if chr(self.data[1]) == 'G':
                        print('revs :{0}'.format(self.valve.valve_sensor.rev_counter))
                        self.send_for_printing(bytearray(struct.pack("f", self.valve.valve_sensor.rev_counter)))
                    if chr(self.data[1]) == 'I':
                        print('interupt')
                        self.valve.interupt = True
                    if chr(self.data[1]) == 'T':
                        if len(self.data) > 3:
                            self.valve.valve_sensor.set_threshold((self.data[2] << 8) + self.data[3])
                    if chr(self.data[1]) == 'L':
                        print('L')
                    if chr(self.data[1]) == 'D':
                        print('D')
                else:
                    print('invalid command')

            # ---------------------------------------------------------------------------------------------------------------------
            # endpoint for printing
            elif received_msg['dest_ep'] == 0xf0:  # decimal 240 (last endpoint)
                print("%s" % received_msg[
                    'payload'])  # this does not go to the serial terminal it goes to the MicroPython REPL, XCTU has to be set to REPL mode [4] to display the output
                stdout.write("[serial out] %s" % received_msg['payload'])  # nothing appears on the serial port

            # ---------------------------------------------------------------------------------------------------------------------
            # endpoint for diagnostics
            elif received_msg['dest_ep'] == 0x01:
                # 'analogue output' cluster
                if self.msg['cluster'] == 0x000d:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            batt_voltage = bytearray(struct.pack("f", self.battery_voltage_mV()))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x0fbattery_voltage'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x39'.format(self.data[1])) + batt_voltage + bytearray(
                                # PresentValue (4 bytes)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'binary input' cluster
                elif self.msg['cluster'] == 0x000f:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = b'\x00'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x05awake'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x10'.format(self.data[1])) + present_value + bytearray(
                                # PresentValue (1 byte)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                elif self.msg['cluster'] == 0x0000:
                    print("%s\n" % self.msg['payload'])
                else:
                    print('cluster: %04x not supported' % self.msg['cluster'])

            # ---------------------------------------------------------------------------------------------------------------------
            # endpoint for valve period
            elif received_msg['dest_ep'] == 0x02:
                # 'analogue output' cluster
                if self.msg['cluster'] == 0x000d:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            period = bytearray(struct.pack("f", self.valve.valve_sensor.period_filtered))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x0cvalve_period'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x39'.format(self.data[1])) + period + bytearray(  # PresentValue (4 bytes)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                # 'binary input' cluster
                elif self.msg['cluster'] == 0x000f:
                    # global cluster commands
                    if self.data[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if self.data[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = b'\x00'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x05awake'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x10'.format(self.data[1])) + present_value + bytearray(
                                # PresentValue (1 byte)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif self.data[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(self.data[
                                                  1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % self.data[2])
                elif self.msg['cluster'] == 0x0000:
                    print("%s\n" % self.msg['payload'])
                else:
                    print('cluster: %04x not supported' % self.msg['cluster'])

    def report_attribute(self, cluster, ep):
        self.msg['source_ep'] = ep
        self.msg['dest_ep'] = 0x01
        self.msg['profile'] = 0x0104

        if ep == 0x55:
            # 'basic' cluster
            if cluster == 0x0000:
                self.msg['cluster'] = 0x0000
                self.msg['payload'] = bytearray(
                    '\x18\x01\x0a'  # header global/cluster-specific (2 bits) manufacturer specific (1 bit) direction (1 bit [1 = server to client]) disable default response (1 bit [0 = default response returned, e.g. 1 used when response frame is a direct effect of a previously recieved frame])
                    # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                    '\x00\x00\x20\x02'  # zigby stack version: 02
                    '\x04\x00\x42\x09TW-Design'
                    '\x05\x00\x42\x08MW-Valve'
                    '\x07\x00\x30\x03'  # power source: 03 = battery
                )
                self.send()

            if cluster == 0x0001:
                self.msg['cluster'] = 0x0001
                batt_voltage = bytearray(struct.pack("B", self.battery_voltage()))
                batt_percentage_remaining = bytearray(struct.pack("B", self.battery_percentage_remaining()))
                self.msg['payload'] = bytearray(
                    '\x18\x02\x0a'  # header, sequence number, command identifier
                    '\x20\x00\x20') + batt_voltage + bytearray(  # battery voltage (1 byte - uint8)
                    '\x21\x00\x20') + batt_percentage_remaining  # battery % remaining (1 byte - uint8)
                self.send()

            elif cluster == 0x0002:
                self.msg['cluster'] = 0x0002
                device_temperature = bytearray(struct.pack("h", self.get_temperature()))
                # print(["0x%02x" % b for b in device_temperature])
                # print(device_temperature)
                # print(get_temperature())
                self.msg['payload'] = bytearray(
                    '\x18\x03\x0a'
                    '\x00\x00'
                    '\x29'
                ) + device_temperature
                self.send()

            elif cluster == 0x0006:
                self.msg['cluster'] = 0x0006
                self.msg['payload'] = bytearray(
                    '\x18\x04\x0a'  # replaced the sequence number with \x04
                    # attribute ID (2 bytes), data type (1 byte), value (variable length)
                    '\x00\x00\x10{:c}'.format(self.on_off_attributes['OnOff']))
                self.send()

            elif cluster == 0x000d:
                self.msg['cluster'] = 0x000d
                present_value = bytearray(struct.pack("f", self.valve.valve_sensor.rev_counter))
                # print(["0x%02x" % b for b in present_value])
                self.msg['payload'] = bytearray(
                    '\x18\x05\x0a'  # replaced the sequence number with \x05
                    # attribute ID (2 bytes), data type (1 byte), value (variable length)
                    # '\x1c\x00\x42\x04revs'  # Description (variable bytes)
                    # '\x51\x00\x10\x00'  # OutOfService (1 byte)
                    '\x55\x00'  # attribute identifier
                    '\x39'  # data type
                    # '\x6f\x00\x18\x00'  # StatusFlags (1 byte)
                ) + present_value  # PresentValue (4 bytes)
                self.send()

            elif cluster == 0x000f:
                self.msg['cluster'] = 0x000f
                binary_sensor = bytearray(struct.pack("B", self.awake_flag))
                self.msg['payload'] = bytearray(
                    '\x18\x06\x0a'  # header, sequence number, command identifier
                    '\x55\x00'
                    '\x10'
                ) + binary_sensor
                self.send()

        elif ep == 0x01:
            if cluster == 0x000d:
                self.msg['cluster'] = 0x000d
                batt_voltage = bytearray(struct.pack("f", self.battery_voltage_mV()))
                # print(["0x%02x" % b for b in present_value])
                self.msg['payload'] = bytearray(
                    '\x18\x07\x0a'  # replaced the sequence number with \x07
                    # attribute ID (2 bytes), data type (1 byte), value (variable length)
                    # '\x1c\x00\x42\x04revs'  # Description (variable bytes)
                    # '\x51\x00\x10\x00'  # OutOfService (1 byte)
                    '\x55\x00'  # attribute identifier
                    '\x39'  # data type
                    # '\x6f\x00\x18\x00'  # StatusFlags (1 byte)
                ) + batt_voltage  # PresentValue (4 bytes)
                self.send()

        elif ep == 0x02:
            if cluster == 0x000d:
                self.msg['cluster'] = 0x000d
                period = bytearray(struct.pack("f", self.valve.valve_sensor.period_filtered))
                self.msg['payload'] = bytearray(
                    '\x18\x08\x0a'
                    # attribute ID (2 bytes), data type (1 byte), value (variable length)
                    # '\x1c\x00\x42\x04revs'  # Description (variable bytes)
                    # '\x51\x00\x10\x00'  # OutOfService (1 byte)
                    '\x55\x00'  # attribute identifier
                    '\x39'  # data type
                    # '\x6f\x00\x18\x00'  # StatusFlags (1 byte)
                ) + period  # PresentValue (4 bytes)
                self.send()
