import ZHA_comms
import valve
import time

print(" +--------------------------------------------+")
print(" | XBee MicroPython Radiator Valve Controller |")
print(" +--------------------------------------------+\n")


ZHA_comms.setup_xbee()
valve.stop_valve()
ZHA_comms.get_network_address()
while ZHA_comms.process_msg() is not None:
    ...
# valve.home_valve()
counter = time.ticks_ms()

while True:
    # valve.test2()
    ZHA_comms.process_msg()
    # valve.demand()
    print("On/Off attribute: %s" % ZHA_comms.on_off_attributes['OnOff'])
    print('revs: %03i\n' % valve.revs)
    time.sleep_ms(500)
    now = time.ticks_ms()
    if time.ticks_diff(now, counter) > 15000:
        print('reporting attributes\n')
        print('voltage: %03i\n' % ZHA_comms.get_voltage())
        ZHA_comms.report_attributes(0x000d)
        ZHA_comms.report_attributes(0x0006)
        ZHA_comms.report_attributes(0x0002)
        ZHA_comms.report_attributes(0x0001)
        counter = time.ticks_ms()
        print("sleeping for 5 seconds\n")
        ZHA_comms.xbee.XBee().sleep_now(5000, pin_wake=True)





