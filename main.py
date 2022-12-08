import ZHA_comms
import valve
import time

print(" +--------------------------------------------+")
print(" | XBee MicroPython Radiator Valve Controller |")
print(" +--------------------------------------------+\n")


# ZHA_comms.setup_xbee()
valve.stop_valve()
ZHA_comms.get_network_address()
ZHA_comms.process_msg()
# valve.home_valve()
counter = time.ticks_ms()

while True:
    ZHA_comms.process_msg()
    now = time.ticks_ms()
    if time.ticks_diff(now, counter) > 20000:
        print('reporting attributes')
        print(ZHA_comms.get_voltage())
        ZHA_comms.report_attributes(0x000d)
        ZHA_comms.report_attributes(0x0006)
        counter = time.ticks_ms()
    '''
    time.sleep_ms(1000)
    if ZHA_comms.on_off_attributes['OnOff']:  # on
        valve.actuate_valve('open')
    else:  # off
        valve.actuate_valve('close')
    print("On/Off attribute: %s" % ZHA_comms.on_off_attributes['OnOff'])
    print('revs: %03i\n' % valve.revs)
    # xbee.XBee().sleep_now(10000, False)  # need to tell HA this is a sleeping end device before using this
    
    '''




