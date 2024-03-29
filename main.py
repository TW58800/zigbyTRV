import ZHA_comms
import valve
import uos

print(" +--------------------------------------------+")
print(" | XBee MicroPython Radiator Valve Controller |")
print(" +--------------------------------------------+\n")

trv = ZHA_comms.TRV()
valve = valve.Valve(trv)
trv.valve = valve
trv.initialise()
trv.run()
