from machine import ADC
import struct
import xbee
import time


class TRV:
    xbee = xbee
    valve = None

    on_off_attributes = {
        'OnOff': True
    }

    msg = {'sender': "", 'payload': "", 'cluster': 0, 'source_ep': 0, 'dest_ep': 0, 'profile': 0, 'address_low': 0,
           'address_high': 0}

    address = 0
    rev_counter = 0
    voltage_monitor = ADC('D2')
    awake_flag = 0

    def run(self):
        counter = time.ticks_ms()
        while True:
            if self.xbee.atcmd("AI") != 0:
                print('not connected to network')
                self.xbee.atcmd("CB", 1)
                time.sleep_ms(10000)
            self.process_msg()
            # print('revs: %03i\n' % valve.revs)
            # time.sleep_ms(1000)
            if time.ticks_diff(time.ticks_ms(), counter) > 10000:  # 180000:
                counter = time.ticks_ms()
                print("On/Off attribute: %s" % self.on_off_attributes['OnOff'])
                print("On/Off trv attribute: %s" % self.valve.trv.on_off_attributes['OnOff'])
                '''
                print('reporting attributes\n')
                self.report_attributes(0x000d)
                self.report_attributes(0x0006)
                self.report_attributes(0x0002)
                self.report_attributes(0x0001)
                # print("sleeping for 60 seconds\n")
                # self.awake_flag = 0
                self.report_attributes(0x000f)
                # self.xbee.XBee().sleep_now(60000, pin_wake=True)
                # self.awake_flag = 1
                # self.report_attributes(0x000f)
                '''

    def initialise(self):
        self.setup_xbee()
        self.valve.stop_valve()
        self.get_network_address()
        while self.process_msg() is not None:
            time.sleep_ms(500)  # to avoid starting homing before HA configuration has finished
        self.valve.home_valve()

    def setup_xbee(self):
        self.xbee.atcmd("SM", 6)
        # xbee.atcmd("AV", 1)  # analogue voltage reference 2.5V
        self.xbee.atcmd("AV", 2)  # analogue voltage reference VDD

    def send(self):
        try:
            xbee.transmit(xbee.ADDR_COORDINATOR, self.msg['payload'], source_ep=self.msg['dest_ep'], dest_ep=self.msg['source_ep'],
                          cluster=self.msg['cluster'], profile=self.msg['profile'], bcast_radius=0, tx_options=0)
            print('Transmit: %s\n' % self.msg['payload'])
            # send_broadcast_digi_data('Transmit: %s\n' % self.msg['payload'])
        except OSError:
            print('OSError - could not send')

    @staticmethod
    def send_broadcast_digi_data(string):
        try:
            xbee.transmit(xbee.ADDR_BROADCAST, string)
        except OSError:
            print('OSError - could not send')

    def reference_voltage(self):
        av = self.xbee.atcmd("AV")
        if av == 0:
            return 1250
        elif av == 1:
            return 2500
        else:
            return self.xbee.atcmd("%V")

    def battery_voltage_mV(self):
        # print(valve.voltage_monitor.read())
        if not self.xbee.atcmd("AV") == 2:
            batt_voltage = int(self.voltage_monitor.read() * (self.reference_voltage() / 4096))
            # self.send_broadcast_digi_data('battery voltage %imV: ' % batt_voltage)
            return batt_voltage
        else:
            batt_voltage = self.xbee.atcmd("%V")
            # self.send_broadcast_digi_data('battery voltage %i: ' % batt_voltage)
            return batt_voltage

    def battery_voltage(self):
        return self.battery_voltage_mV() // 100  # power configuration cluster measures in 100mV increments

    def battery_percentage_remaining(self):
        voltage_as_percentage = int(
            (self.battery_voltage_mV() - 2000) * 0.3)  # 2.4 volts is 63%  HA expects a value between 0 and 200 (0.5% resolution)
        if voltage_as_percentage > 255:
            voltage_as_percentage = 255
        if voltage_as_percentage < 0:
            voltage_as_percentage = 0
        print('voltage: {:04.1f}%'.format(voltage_as_percentage/2))
        return voltage_as_percentage

    def get_temperature(self):
        tp = self.xbee.atcmd('TP')
        if tp > 0x7FFF:
            tp = tp - 0x10000
        return tp*100  # HA measures temperature in 100ths of a degree

    def get_network_address(self):
        # wait for a connection to be established
        print('\nConnecting...\n')
        while self.xbee.atcmd("AI") != 0:
            time.sleep(2)
            print('Waiting for a join window...')

        # Get the XBee's 16-bit network address
        print('Connected...\n')
        self.address = self.xbee.atcmd("MY")
        print('Address: %04x' % self.address)
        self.msg['address_high'] = self.address >> 8
        self.msg['address_low'] = self.address & 0xff
        print('Address High: %02x' % self.msg['address_high'])
        print('Address Low: %02x' % self.msg['address_low'])
        print("\nWaiting for data...\n")
        self.send_broadcast_digi_data("\nRouter-1 waiting for data...\n")
        # time.sleep_ms(10000)

    def process_msg(self):
        # Check if the XBee has any message in the queue.
        received_msg = self.xbee.receive()
        # while received_self.msg:
        if received_msg is not None:
            # Get the sender's 64-bit address and payload from the received message.
            self.msg['sender'] = received_msg['sender_eui64']
            self.msg['payload'] = received_msg['payload']
            self.msg['cluster'] = received_msg['cluster']
            self.msg['source_ep'] = received_msg['source_ep']
            self.msg['dest_ep'] = received_msg['dest_ep']
            self.msg['profile'] = received_msg['profile']
            print("Data received from %s >> \nPayload: %s \nCluster: %04x \nSource ep: %02x \nDestination ep: %02x"
                  "\nProfile: %04x\n" % (
                      ''.join('{:02x}'.format(x).upper() for x in self.msg['sender']), self.msg['payload'], self.msg['cluster'],
                      self.msg['source_ep'], self.msg['dest_ep'], self.msg['profile']))
            a = list(self.msg['payload'])

            # ZDO endpoint
            if self.msg['dest_ep'] == 0x0000:
                # active endpoints request
                if self.msg['cluster'] == 0x0005:
                    self.msg['payload'] = bytearray(
                        '{:c}\x00{:c}{:c}\x01\x55'.format(a[0], self.msg['address_low'], self.msg['address_high']))
                    self.msg['cluster'] = 0x8005
                    self.send()
                # simple descriptor request
                elif self.msg['cluster'] == 0x0004:
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
                        .format(a[0], self.msg['address_low'], self.msg['address_high']))
                    self.msg['cluster'] = 0x8004
                    self.send()
                # management leave request
                elif self.msg['cluster'] == 0x0034:
                    # restore device configuration to default and leave the network
                    xbee.atcmd("CB", 0x04)
                    self.msg['payload'] = bytearray('{:c}\x00'.format(a[0]))
                    self.msg['cluster'] = 0x8034
                    self.send()
                # management permit join request
                elif self.msg['cluster'] == 0x0036:
                    # if disassociated: join network
                    # if associated: wake device for 30 seconds if sleeping / send node identification broadcast
                    xbee.atcmd("CB", 0x01)
                    self.msg['payload'] = bytearray('{:c}\x00'.format(a[0]))
                    self.msg['cluster'] = 0x8036
                    self.send()
                else:
                    print('ZDO cluster %04x not supported' % self.msg['cluster'])
                print('Sequence number: %02x\n\n' % a[0])

    # ----------------------------------------------------------------------------------------------------------------------
            # endpoint for Tim's radiator valve controller device
            elif self.msg['dest_ep'] == 0x55:

                # 'basic' cluster
                if self.msg['cluster'] == 0x0000:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01' Zigpy asks for attributes 4 (manf name) and 5 (model identifier)
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header global/cluster-specific (2 bits) manufacturer specific (1 bit) direction (1 bit [1 = server to client]) disable default response (1 bit [0 = default response returned, e.g. 1 used when response frame is a direct effect of a previously recieved frame])
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x04\x00\x00\x42\x09TW-Design'
                                '\x05\x00\x00\x42\x08MW-Valve'
                                .format(a[1]))
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])

                # 'power configuration' cluster
                elif self.msg['cluster'] == 0x0001:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01'
                            batt_voltage = bytearray(struct.pack("B", self.battery_voltage()))
                            batt_percentage_remaining = bytearray(struct.pack("B", self.battery_percentage_remaining()))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x20\x00\x00\x20'.format(a[1])) + batt_voltage + bytearray(  # battery voltage (1 byte - uint8)
                                '\x21\x00\x00\x20') + batt_percentage_remaining
                            if a[3] == 0x21:
                                self.msg['payload'] = bytearray(
                                    '\x18{:c}\x01'  # header, sequence number, command identifier
                                    # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                    '\x21\x00\x00\x20'.format(a[1])) + self.battery_percentage_remaining()
                            self.send()
                        # configure reporting '0x06'
                        elif a[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])

                # 'temperature configuration' cluster
                elif self.msg['cluster'] == 0x0002:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01'
                            device_temperature = bytearray(struct.pack("h", self.get_temperature()))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x00\x00\x00\x29'.format(a[1])) + device_temperature
                            print(device_temperature)
                            self.send()
                        # configure reporting '0x06'
                        elif a[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])

                # 'On/Off' cluster
                elif self.msg['cluster'] == 0x0006:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                '\x00\x00\x00\x10{:c}'  # attribute identifier (2 bytes), status (1 byte) data type (1 byte), value (1 byte)
                                .format(a[1], self.on_off_attributes['OnOff']))
                            self.send()
                        # configure reporting '0x06'
                        elif a[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                                .format(a[1]))
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])
                    # cluster specific commands
                    elif a[0] & 0b11 == 0b01:
                        # off command
                        if a[2] == 0x00:
                            self.on_off_attributes['OnOff'] = False
                        # on command
                        elif a[2] == 0x01:
                            self.on_off_attributes['OnOff'] = True
                        # toggle command
                        elif a[2] == 0x02:
                            self.on_off_attributes['OnOff'] = not self.on_off_attributes['OnOff']
                        # after acting on a cluster specific command send a 'report attributes' '0x0a' message
                        self.msg['payload'] = bytearray(
                            '\x18{:c}\x0a'  # header, sequence number, command identifier
                            '\x00\x00\x10{:c}'.format(a[1], self.on_off_attributes['OnOff']))  # attribute identifier (2 bytes), data type (1 byte), value (1 byte)
                        self.send()
                        self.valve.demand()

                # 'analogue output' cluster
                elif self.msg['cluster'] == 0x000d:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = bytearray(struct.pack("f", self.rev_counter))
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x11valve_revolutions'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x39'.format(a[1])) + present_value + bytearray(  # PresentValue (4 bytes)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif a[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])

                # 'binary input' cluster
                elif self.msg['cluster'] == 0x000f:
                    # global cluster commands
                    if a[0] & 0b11 == 0b00:
                        # read attributes '0x00'
                        if a[2] == 0x00:
                            # read attributes response '0x01'
                            present_value = b'\x00'
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x1c\x00\x00\x42\x05awake'  # Description (variable bytes)
                                '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                                '\x55\x00\x00\x10'.format(a[1])) + present_value + bytearray(  # PresentValue (1 byte)
                                '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                            self.send()
                        # configure reporting '0x06'
                        elif a[2] == 0x06:
                            # configure reporting response '0x07'
                            # just responds with success, even though I haven't set up any reporting mechanism!
                            self.msg['payload'] = bytearray(
                                '\x18{:c}\x07'  # header, sequence number, command identifier
                                '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            self.send()
                        else:
                            print('general command : %04x not supported' % a[2])

                else:
                    print('cluster: %04x not supported' % self.msg['cluster'])
                print('sequence number: %02x\n' % a[1])
            # received_self.msg = xbee.receive()

            elif self.msg['dest_ep'] == 0xe8:
                if (len(a) >= 3) and (a[0] & 0b11 == 0b00):
                    cmd = chr(a[1]) + chr(a[2])
                    print(cmd)
                    if len(a) == 3:
                        rsp = xbee.atcmd(cmd)
                        print(rsp)
                    else:
                        rsp = xbee.atcmd(cmd, a[3])
                        # rsp = xbee.atcmd(cmd)
                    self.send_broadcast_digi_data(bytearray(rsp.to_bytes(2, 'little')))
                elif (len(a) >= 2) and (a[0] & 0b11 == 0b01):
                    print('TRV command')
                    if chr(a[1]) == 'P':
                        if len(a) > 2:
                            print('goto revs {0}'.format(a[2]))
                            self.valve.goto_revs(a[2])
                    if chr(a[1]) == 'H':
                        print('home')
                        self.valve.home_valve()
                    if chr(a[1]) == 'F':
                        print('forwards')
                        self.valve.motor.forwards()
                    if chr(a[1]) == 'O':
                        print('open')
                        self.valve.goto_revs(0)
                    if chr(a[1]) == 'C':
                        print('close')
                        self.valve.goto_revs(self.valve.closed_position)
                    if chr(a[1]) == 'S':
                        print('stop')
                        self.valve.motor.stop_soft()
                    if chr(a[1]) == 'G':
                        print('revs :{0}'.format(self.valve.valve_sensor.rev_counter))
                        self.send_broadcast_digi_data(bytearray(self.valve.valve_sensor.rev_counter.to_bytes(2, 'little')))
                    if chr(a[1]) == 'I':
                        print('interupt')
                        self.valve.interupt = True
                else:
                    print('invalid command')
        else:
            # send_broadcast_digi_data(bytearray(b'what'))
            return None

    def report_attributes(self, cluster):

        if cluster == 0x0001:
            batt_voltage = bytearray(struct.pack("B", self.battery_voltage()))
            batt_percentage_remaining = bytearray(struct.pack("B", self.battery_percentage_remaining()))
            self.msg['payload'] = bytearray(
                '\x18\x04\x0a'  # header, sequence number, command identifier
                '\x20\x00\x20') + batt_voltage + bytearray(  # battery voltage (1 byte - uint8)
                '\x21\x00\x20') + batt_percentage_remaining  # battery % remaining (1 byte - uint8)
            self.msg['cluster'] = 0x0001
            self.msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
            self.msg['dest_ep'] = 0x55
            self.msg['profile'] = 0x0104
            self.send()

        elif cluster == 0x0002:
            device_temperature = bytearray(struct.pack("h", self.get_temperature()))
            # print(["0x%02x" % b for b in device_temperature])
            # print(device_temperature)
            # print(get_temperature())
            self.msg['payload'] = bytearray(
                '\x18\x03\x0a'
                '\x00\x00'
                '\x29'
                ) + device_temperature
            self.msg['cluster'] = 0x0002
            self.msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
            self.msg['dest_ep'] = 0x55
            self.msg['profile'] = 0x0104
            self.send()

        elif cluster == 0x0006:
            self.msg['cluster'] = 0x0006
            self.msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
            self.msg['dest_ep'] = 0x55
            self.msg['profile'] = 0x0104
            self.msg['payload'] = bytearray(
                '\x18\x01\x0a'  # replaced the sequence number with \x01
                # attribute ID (2 bytes), data type (1 byte), value (variable length)
                '\x00\x00\x10{:c}'.format(self.on_off_attributes['OnOff']))
            self.send()

        elif cluster == 0x000d:
            present_value = bytearray(struct.pack("f", self.rev_counter))
            # print(["0x%02x" % b for b in present_value])
            self.msg['cluster'] = 0x000d
            self.msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
            self.msg['dest_ep'] = 0x55
            self.msg['profile'] = 0x0104
            self.msg['payload'] = bytearray(
                '\x18\x02\x0a'  # replaced the sequence number with \x02
                # attribute ID (2 bytes), data type (1 byte), value (variable length)
                # '\x1c\x00\x42\x04revs'  # Description (variable bytes)
                # '\x51\x00\x10\x00'  # OutOfService (1 byte)
                '\x55\x00'  # attribute identifier
                '\x39'  # data type
                # '\x6f\x00\x18\x00'  # StatusFlags (1 byte)
                ) + present_value  # PresentValue (4 bytes)
            self.send()

        elif cluster == 0x000f:
            binary_sensor = bytearray(struct.pack("B", self.awake_flag))
            self.msg['payload'] = bytearray(
                '\x18\x05\x0a'  # header, sequence number, command identifier
                '\x55\x00'
                '\x10'
                ) + binary_sensor
            self.msg['cluster'] = 0x000f
            self.msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
            self.msg['dest_ep'] = 0x55
            self.msg['profile'] = 0x0104
            self.send()
