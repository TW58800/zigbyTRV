from machine import Pin, ADC, PWM
import time
import ZHA_comms


class Motor:
    motor_pin1 = Pin('D11', Pin.OUT)  # PWM(Pin('P1'))
    motor_pin2 = Pin('D1', Pin.OUT)  # , Pin.PULL_UP)

    @classmethod
    def forwards(cls):
        cls.motor_pin1.on()  # duty(1023)
        cls.motor_pin2.off()
        # Pin('D1', Pin.IN, Pin.PULL_UP)
        # Pin('D11', Pin.IN, Pin.PULL_DOWN)

    @classmethod
    def reverse(cls):
        cls.motor_pin1.off()  # duty(0)  # 880 is the slowest before the motor won't turn
        cls.motor_pin2.on()
        # Pin('D1', Pin.IN, Pin.PULL_DOWN)
        # Pin('D11', Pin.IN, Pin.PULL_UP)

    @classmethod
    def stop_hard(cls):
        cls.motor_pin1.on()  # duty(1023)
        cls.motor_pin2.on()
        # Pin('D1', Pin.IN, Pin.PULL_UP)
        # Pin('D11', Pin.IN, Pin.PULL_UP)

    @classmethod
    def stop_soft(cls):
        cls.motor_pin1.off()  # duty(0)
        cls.motor_pin2.off()
        # Pin('D1', Pin.IN, Pin.PULL_DOWN)
        # Pin('D11', Pin.IN, Pin.PULL_DOWN)


class Valve:
    STALL_TIME = 2000
    sensor = ADC('D3')  # create an analog pin on D3
    last_ticks = 0  # time.ticks_ms()
    above_threshold = True
    revs = -1
    max_revs = 0
    motor_direction = 0
    
    def demand(self):
        if ZHA_comms.on_off_attributes['OnOff']:  # on
            self.actuate_valve('open')
        else:  # off
            self.actuate_valve('close')

    def open_valve(self):
        Motor.forwards()
        self.motor_direction = 1
        # print('opening')
        return 1

    def close_valve(self):
        Motor.reverse()
        self.motor_direction = -1
        # print('closing')
        return -1

    def stop_valve(self):
        Motor.stop_hard()
        self.motor_direction = 0
        # print('stopped')
        return 0

    def actuate_valve(self, direction):
        if (direction == 'open') & (self.revs < self.max_revs):
            print('opening')
            self.open_valve()
            self.last_ticks = time.ticks_ms()
            while (self.revs < self.max_revs) & ZHA_comms.on_off_attributes['OnOff']:
                self.valve_moving()
                ZHA_comms.process_msg()
                # time.sleep_ms(1)
                # print('opening: %i' % revs)
                # self.open_valve()
            self.stop_valve()
        elif (direction == 'close') & (self.revs > 0):
            print('closing')
            self.close_valve()
            self.last_ticks = time.ticks_ms()
            while (self.revs > 0) & (not ZHA_comms.on_off_attributes['OnOff']):
                self.valve_moving()
                ZHA_comms.process_msg()
                # time.sleep_ms(1)
                # print('closing: %i' % revs)
                # self.close_valve()
            self.stop_valve()
        else:
            self.stop_valve()
            # print('revs: %i' % revs)

    def home_valve(self):
        # goes to the closed position
        print('homing')
        self.close_valve()
        self.last_ticks = time.ticks_ms()
        while self.valve_moving():
            ...
            # print(self.revs)
        print('reached end of travel')
        self.stop_valve()
        self.revs = 0
        time.sleep_ms(500)
        # goes to the open position
        print('moving to opposite end of travel')
        self.open_valve()
        self.last_ticks = time.ticks_ms()
        while self.valve_moving():
            ...
            # print(revs)
        self.stop_valve()
        if self.revs > 0:
            self.max_revs = self.revs - 300
            self.revs -= 150
            ZHA_comms.rev_counter = self.revs
            print('max revs: %s\n' % self.max_revs)
        else:
            print('motor did not move\n')

    def valve_sensor(self):
        sensor_value = self.sensor.read()  # set xbee ref voltage (AT command 'AV') to VDD
        if (sensor_value >= 1500) & (not self.above_threshold):
            self.above_threshold = True
        elif (sensor_value < 1500) & self.above_threshold:
            self.above_threshold = False
            self.last_ticks = time.ticks_ms()
            self.revs += self.motor_direction
            ZHA_comms.rev_counter = self.revs

    def valve_moving(self):
        # print(sensor_now)
        # if printing, baud rate needs to be above 9600 to capture readings a fast as they are being created
        period = time.ticks_diff(time.ticks_ms(), self.last_ticks)
        self.valve_sensor()
        if period < self.STALL_TIME:
            return True
        else:
            return False
