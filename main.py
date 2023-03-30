import ZHA_comms
import valve
import time

print(" +--------------------------------------------+")
print(" | XBee MicroPython Radiator Valve Controller |")
print(" +--------------------------------------------+\n")

trv = ZHA_comms.TRV()
valve = valve.Valve(trv)
trv.valve = valve
trv.setup_xbee()
trv.valve.stop_valve()
trv.get_network_address()

while trv.process_msg() is not None:
    time.sleep_ms(500)  # to avoid starting homing before HA configuration has finished

# TRV.home_valve()
counter = time.ticks_ms()

while True:
    if ZHA_comms.xbee.atcmd("AI") != 0:
        print('not connected to network')
        ZHA_comms.xbee.atcmd("CB", 1)
        time.sleep_ms(10000)
    trv.process_msg()
    # TRV.demand()
    # print("On/Off attribute: %s" % ZHA_comms.on_off_attributes['OnOff'])
    # print('revs: %03i\n' % valve.revs)
    # time.sleep_ms(1000)
    now = time.ticks_ms()
    if time.ticks_diff(now, counter) > 30000:  # 120000:
        counter = time.ticks_ms()
        print('reporting attributes\n')
        # print('voltage: %03i\n' % ZHA_comms.get_voltage())
        trv.report_attributes(0x000d)
        # ZHA_comms.report_attributes(0x0006)
        # ZHA_comms.report_attributes(0x0002)
        # ZHA_comms.report_attributes(0x0001)
        # print("sleeping for 60 seconds\n")
        # ZHA_comms.awake_flag = 0
        # ZHA_comms.report_attributes(0x000f)
        # ZHA_comms.xbee.XBee().sleep_now(60000, pin_wake=True)
        # ZHA_comms.awake_flag = 1
        # ZHA_comms.report_attributes(0x000f)




