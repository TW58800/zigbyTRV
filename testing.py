import time
import ZHA_comms


class MotorTest:

    def __init__(self, motor):
        self.motor = motor

    def cycle(self):
        self.motor.forwards()
        print('forwards')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.stop_hard()
        print('stop hard')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.reverse()
        print('reverse')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.stop_hard()
        print('stop hard')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.forwards()
        print('forwards')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.stop_soft()
        print('stop soft')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.reverse()
        print('reverse')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

        self.motor.stop_soft()
        print('stop soft')
        time.sleep_ms(2000)

        print('sleep')
        ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

    def cycle_pwm(self):
        while True:

            # 1
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # 2
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(2000)

            # 3
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # 4
            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # 5
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # 6
            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(2000)

            # 7
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(2000)

            # 8
            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(2000)

            # 9
            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # 10
            # Reverse
            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(6000)

            self.motor.motor_pin2.on()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(4000)

            # Soft stop
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(2000)

            # Forwards
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(1023)
            time.sleep_ms(2000)

            # Soft stop
            self.motor.motor_pin2.off()
            self.motor.motor_pin1.duty(0)
            time.sleep_ms(3000)
