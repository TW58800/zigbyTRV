# 27/11/2022 playing around with the header frames to see if the direction or default response bits make a difference in HA

import struct
import xbee
import time
import valve


# on/off cluster attributes
on_off_attributes = {
    'OnOff': True
}

msg = {'sender': "", 'payload': "", 'cluster': 0, 'source_ep': 0, 'dest_ep': 0, 'profile': 0, 'address_low': 0,
       'address_high': 0}

rev_counter = 2.0  # temporary, while checking attribute reporting

awake_flag = 0


def send():
    try:
        xbee.transmit(xbee.ADDR_COORDINATOR, msg['payload'], source_ep=msg['dest_ep'], dest_ep=msg['source_ep'],
                  cluster=msg['cluster'],
                  profile=msg['profile'], bcast_radius=0, tx_options=0)
        print('Transmit: %s\n' % msg['payload'])
    except OSError:
        print('OSError - could not send')


def setup_xbee():
    xbee.atcmd("SM", 6)


def get_voltage():
    voltage = xbee.atcmd("%V")
    battery_voltage = int(valve.voltage_monitor.read() * (voltage / 1024))
    return battery_voltage // 100  # power configuration cluster measures in 100mV increments


def get_battery_charge():
    voltage = xbee.atcmd("%V")
    battery_voltage = int(valve.voltage_monitor.read() * (voltage / 1024))
    voltage_as_percentage = int(
        (battery_voltage - 2000) * 0.3)  # 2.4 volts is 63%  HA expects a value between 0 and 200 (0.5% resolution)
    if voltage_as_percentage > 255:
        voltage_as_percentage = 255
    if voltage_as_percentage < 0:
        voltage_as_percentage = 0
    # print('voltage %i%%: ' % voltage_as_percentage)
    return bytearray(struct.pack("B", voltage_as_percentage))


def get_temperature():
    tp = xbee.atcmd('TP')
    if tp > 0x7FFF:
        tp = tp - 0x10000
    return tp*100  # HA measures temperature in 100ths of a degree


def get_network_address():
    # wait for a connection to be established
    print('\nConnecting...\n')
    while xbee.atcmd("AI") != 0:
        time.sleep(2)
        print('Waiting for a join window...')

    # Get the XBee's 16-bit network address
    print('Connected...\n')
    address = xbee.atcmd("MY")
    print('Address: %04x' % address)
    msg['address_high'] = address >> 8
    msg['address_low'] = address & 0xff
    print('Address High: %02x' % msg['address_high'])
    print('Address Low: %02x' % msg['address_low'])
    print("\nWaiting for data...\n")
    time.sleep_ms(10000)


def process_msg():
    # Check if the XBee has any message in the queue.
    received_msg = xbee.receive()
    # while received_msg:
    if received_msg is not None:
        # Get the sender's 64-bit address and payload from the received message.
        msg['sender'] = received_msg['sender_eui64']
        msg['payload'] = received_msg['payload']
        msg['cluster'] = received_msg['cluster']
        msg['source_ep'] = received_msg['source_ep']
        msg['dest_ep'] = received_msg['dest_ep']
        msg['profile'] = received_msg['profile']
        print("Data received from %s >> \nPayload: %s \nCluster: %04x \nSource ep: %02x \nDestination ep: %02x"
              "\nProfile: %04x\n" % (
                  ''.join('{:02x}'.format(x).upper() for x in msg['sender']), msg['payload'], msg['cluster'],
                  msg['source_ep'], msg['dest_ep'], msg['profile']))
        a = list(msg['payload'])


        # ZDO endpoint
        if msg['dest_ep'] == 0x0000:
            # active endpoints request
            if msg['cluster'] == 0x0005:
                msg['payload'] = bytearray(
                    '{:c}\x00{:c}{:c}\x01\x55'.format(a[0], msg['address_low'], msg['address_high']))
                msg['cluster'] = 0x8005
                send()
            # simple descriptor request
            elif msg['cluster'] == 0x0004:
                msg['payload'] = bytearray(
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
                    .format(a[0], msg['address_low'], msg['address_high']))
                msg['cluster'] = 0x8004
                send()
            # management leave request
            elif msg['cluster'] == 0x0034:
                # restore device configuration to default and leave the network
                xbee.atcmd("CB", 0x04)
                msg['payload'] = bytearray('{:c}\x00'.format(a[0]))
                msg['cluster'] = 0x8034
                send()
            # management permit join request
            elif msg['cluster'] == 0x0036:
                # if disassociated: join network
                # if associated: wake device for 30 seconds if sleeping / send node identification broadcast
                xbee.atcmd("CB", 0x01)
                msg['payload'] = bytearray('{:c}\x00'.format(a[0]))
                msg['cluster'] = 0x8036
                send()
            else:
                print('ZDO cluster %04x not supported' % msg['cluster'])
            print('Sequence number: %02x\n\n' % a[0])

# ----------------------------------------------------------------------------------------------------------------------
        # endpoint for Tim's radiator valve controller device
        elif msg['dest_ep'] == 0x55:

            # 'basic' cluster
            if msg['cluster'] == 0x0000:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01' Zigpy asks for attributes 4 (manf name) and 5 (model identifier)
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header global/cluster-specific (2 bits) manufacturer specific (1 bit) direction (1 bit [1 = server to client]) disable default response (1 bit [0 = default response returned, e.g. 1 used when response frame is a direct effect of a previously recieved frame])
                            # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                            '\x04\x00\x00\x42\x09TW-Design'
                            '\x05\x00\x00\x42\x08MW-Valve'
                            .format(a[1]))
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])

            # 'power configuration' cluster
            elif msg['cluster'] == 0x0001:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01'
                        battery_voltage = bytearray(struct.pack("B", get_voltage()))
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header, sequence number, command identifier
                            # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                            '\x20\x00\x00\x20'.format(a[1])) + battery_voltage + bytearray(  # battery voltage (1 byte - uint8)
                            '\x21\x00\x00\x20') + get_battery_charge()
                        if a[3] == 0x21:
                            msg['payload'] = bytearray(
                                '\x18{:c}\x01'  # header, sequence number, command identifier
                                # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                                '\x21\x00\x00\x20'.format(a[1])) + get_battery_charge()
                        send()
                    # configure reporting '0x06'
                    elif a[2] == 0x06:
                        # configure reporting response '0x07'
                        # just responds with success, even though I haven't set up any reporting mechanism!
                        msg['payload'] = bytearray(
                            '\x18{:c}\x07'  # header, sequence number, command identifier
                            '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])

            # 'temperature configuration' cluster
            elif msg['cluster'] == 0x0002:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01'
                        device_temperature = bytearray(struct.pack("h", get_temperature()))
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header, sequence number, command identifier
                            # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                            '\x00\x00\x00\x29'.format(a[1])) + device_temperature
                        print(device_temperature)
                        send()
                    # configure reporting '0x06'
                    elif a[2] == 0x06:
                        # configure reporting response '0x07'
                        # just responds with success, even though I haven't set up any reporting mechanism!
                        msg['payload'] = bytearray(
                            '\x18{:c}\x07'  # header, sequence number, command identifier
                            '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])

            # 'On/Off' cluster
            elif msg['cluster'] == 0x0006:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01'
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header, sequence number, command identifier
                            '\x00\x00\x00\x10{:c}'  # attribute identifier (2 bytes), status (1 byte) data type (1 byte), value (1 byte)
                            .format(a[1], on_off_attributes['OnOff']))
                        send()
                    # configure reporting '0x06'
                    elif a[2] == 0x06:
                        # configure reporting response '0x07'
                        # just responds with success, even though I haven't set up any reporting mechanism!
                        msg['payload'] = bytearray(
                            '\x18{:c}\x07'  # header, sequence number, command identifier
                            '\x00'  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                            .format(a[1]))
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])
                # cluster specific commands
                elif a[0] & 0b11 == 0b01:
                    # off command
                    if a[2] == 0x00:
                        on_off_attributes['OnOff'] = False
                    # on command
                    elif a[2] == 0x01:
                        on_off_attributes['OnOff'] = True
                    # toggle command
                    elif a[2] == 0x02:
                        on_off_attributes['OnOff'] = not on_off_attributes['OnOff']
                    # after acting on a cluster specific command send a 'report attributes' '0x0a' message
                    msg['payload'] = bytearray(
                        '\x18{:c}\x0a'  # header, sequence number, command identifier
                        '\x00\x00\x10{:c}'.format(a[1], on_off_attributes['OnOff']))  # attribute identifier (2 bytes), data type (1 byte), value (1 byte)
                    send()

            # 'analogue output' cluster
            elif msg['cluster'] == 0x000d:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01'
                        present_value = bytearray(struct.pack("f", valve.revs))
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header, sequence number, command identifier
                            # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                            '\x1c\x00\x00\x42\x11valve_revolutions'  # Description (variable bytes)
                            '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                            '\x55\x00\x00\x39'.format(a[1])) + present_value + bytearray(  # PresentValue (4 bytes)
                            '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                        send()
                    # configure reporting '0x06'
                    elif a[2] == 0x06:
                        # configure reporting response '0x07'
                        # just responds with success, even though I haven't set up any reporting mechanism!
                        msg['payload'] = bytearray(
                            '\x18{:c}\x07'  # header, sequence number, command identifier
                            '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])

            # 'binary input' cluster
            elif msg['cluster'] == 0x000f:
                # global cluster commands
                if a[0] & 0b11 == 0b00:
                    # read attributes '0x00'
                    if a[2] == 0x00:
                        # read attributes response '0x01'
                        present_value = b'\x00'
                        msg['payload'] = bytearray(
                            '\x18{:c}\x01'  # header, sequence number, command identifier
                            # attribute ID (2 bytes), status (1 byte), data type (1 byte), value (variable length)
                            '\x1c\x00\x00\x42\x05awake'  # Description (variable bytes)
                            '\x51\x00\x00\x10\x00'  # OutOfService (1 byte)
                            '\x55\x00\x00\x10'.format(a[1])) + present_value + bytearray(  # PresentValue (1 byte)
                            '\x6f\x00\x00\x18\x00')  # StatusFlags (1 byte)
                        send()
                    # configure reporting '0x06'
                    elif a[2] == 0x06:
                        # configure reporting response '0x07'
                        # just responds with success, even though I haven't set up any reporting mechanism!
                        msg['payload'] = bytearray(
                            '\x18{:c}\x07'  # header, sequence number, command identifier
                            '\x00'.format(a[1]))  # only sending a single ZCL payload byte (0x00) to indicate that all attributes were successfully configured
                        send()
                    else:
                        print('general command : %04x not supported' % a[2])

            else:
                print('cluster: %04x not supported' % msg['cluster'])
            print('sequence number: %02x\n' % a[1])
        # received_msg = xbee.receive()
    else:
        return None


def report_attributes(cluster):
    if cluster == 0x0006:
        msg['cluster'] = 0x0006
        msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
        msg['dest_ep'] = 0x55
        msg['profile'] = 0x0104
        msg['payload'] = bytearray(
            '\x18\x01\x0a'  # replaced the sequence number with \x01
            # attribute ID (2 bytes), data type (1 byte), value (variable length)
            '\x00\x00\x10{:c}'.format(on_off_attributes['OnOff']))
        send()
    elif cluster == 0x000d:
        global rev_counter
        rev_counter += 0.1
        present_value = bytearray(struct.pack("f", valve.revs))  # rev_counter))
        # print(["0x%02x" % b for b in present_value])
        msg['cluster'] = 0x000d
        msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
        msg['dest_ep'] = 0x55
        msg['profile'] = 0x0104
        msg['payload'] = bytearray(
            '\x18\x02\x0a'  # replaced the sequence number with \x02
            # attribute ID (2 bytes), data type (1 byte), value (variable length)
            # '\x1c\x00\x42\x04revs'  # Description (variable bytes)
            # '\x51\x00\x10\x00'  # OutOfService (1 byte)
            '\x55\x00'  # attribute identifier
            '\x39'  # data type
            # '\x6f\x00\x18\x00'  # StatusFlags (1 byte)
            ) + present_value  # PresentValue (4 bytes)
        send()

    elif cluster == 0x0002:
        device_temperature = bytearray(struct.pack("h", get_temperature()))
        # print(["0x%02x" % b for b in device_temperature])
        # print(device_temperature)
        # print(get_temperature())
        msg['payload'] = bytearray(
            '\x18\x03\x0a'
            '\x00\x00'
            '\x29'
            ) + device_temperature
        msg['cluster'] = 0x0002
        msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
        msg['dest_ep'] = 0x55
        msg['profile'] = 0x0104
        send()

    elif cluster == 0x0001:
        msg['payload'] = bytearray(
            '\x18\x04\x0a'  # header, sequence number, command identifier
            '\x21\x00'
            '\x20'
            ) + get_battery_charge()
        msg['cluster'] = 0x0001
        msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
        msg['dest_ep'] = 0x55
        msg['profile'] = 0x0104
        send()

    elif cluster == 0x000f:
        global awake_flag
        binary_sensor = bytearray(struct.pack("B", awake_flag))
        msg['payload'] = bytearray(
            '\x18\x05\x0a'  # header, sequence number, command identifier
            '\x55\x00'
            '\x10'
            ) + binary_sensor
        msg['cluster'] = 0x000f
        msg['source_ep'] = 0x01  # dest and source are swapped in the send function, should probably change this
        msg['dest_ep'] = 0x55
        msg['profile'] = 0x0104
        send()
