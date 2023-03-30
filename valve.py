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


class Sensor:
    ADC = ADC('D3')  # create an analog pin on D3
    # above_threshold = True
    period = 0
    last_reading = 0
    rev_counter = 0

    class Timer:
        set = False
        time = time.ticks_ms()
    timer = Timer()

    def read(self, direction):
        sensor_value = self.ADC.read()
        # print(sensor_value) # set xbee ref voltage (AT command 'AV') to VDD
        if (sensor_value >= 1500) & (self.last_reading < 1500):  # (not self.above_threshold):
            # self.above_threshold = True
            if self.timer.set:
                self.period = time.ticks_diff(time.ticks_ms(), self.timer.time)
            else:
                self.period = 0
            self.timer.time = time.ticks_ms()
            self.timer.set = True
            self.rev_counter += direction
            print(self.rev_counter)
        self.last_reading = sensor_value

    def reset_timer(self):
        self.timer.set = False


class Valve:
    valve_sensor = Sensor()
    STALL_TIME = 300  # milliseconds
    closed_position = 0
    motor_direction = 0
    interupt = False

    def __init__(self, trv):
        self.trv = trv
    
    def demand(self):
        if self.trv.on_off_attributes['OnOff']:  # on
            self.actuate_valve('open')
        else:  # off
            self.actuate_valve('close')

    def open_valve(self):
        Motor.forwards()
        self.motor_direction = -1
        # print('opening')
        return 1

    def close_valve(self):
        Motor.reverse()
        self.motor_direction = 1
        # print('closing')
        return -1

    def stop_valve(self):
        Motor.stop_hard()
        self.motor_direction = 0
        # print('stopped')
        return 0

    def actuate_valve(self, direction):
        if (direction == 'open') & self.trv.on_off_attributes['OnOff']:
            print('opening')
            self.goto_revs(self.closed_position)
        elif (direction == 'close') & (not self.trv.on_off_attributes['OnOff']):
            print('closing')
            self.goto_revs(0)
        else:
            self.stop_valve()
            # print('revs: %i' % revs)

    def home_valve(self):
        # goes to the closed position
        print('homing')
        self.open_valve()
        self.valve_moving(self.STALL_TIME)
        print('reached end of travel')
        self.valve_sensor.rev_counter = 0
        time.sleep_ms(500)
        # goes to the open position
        print('moving to opposite end of travel')
        self.close_valve()
        self.valve_moving(self.STALL_TIME)
        if self.valve_sensor.rev_counter > 150:
            self.closed_position = self.valve_sensor.rev_counter - 50
            self.valve_sensor.rev_counter -= 50
            self.trv.rev_counter = self.valve_sensor.rev_counter
            print('closed position: %s\n' % self.closed_position)
        else:
            print('insufficint valve travel, revs: %i\n' % self.valve_sensor.rev_counter)

    def valve_moving(self, max_period):
        while (self.valve_sensor.period < max_period) & (not self.interupt):
            self.valve_sensor.read(self.motor_direction)
            # if printing, baud rate needs to be above 9600 to capture readings a fast as they are being created
            self.trv.process_msg()
        self.stop_valve()
        self.valve_sensor.period = 0
        self.valve_sensor.reset_timer()
        self.interupt = False

    def get_period(self):
        return self.valve_sensor.period

    def goto_revs(self, position: int):
        if self.valve_sensor.rev_counter > position:
            self.open_valve()
            while (self.valve_sensor.rev_counter > position) & (self.valve_sensor.period < self.STALL_TIME):
                self.trv.process_msg()
                self.valve_sensor.read(self.motor_direction)
                if self.valve_sensor.period > self.STALL_TIME:
                    print('valve stalling, period (ms): %i' % self.valve_sensor.period)
            self.stop_valve()
            self.valve_sensor.reset_timer()
        elif self.valve_sensor.rev_counter < position:
            self.close_valve()
            while (self.valve_sensor.rev_counter < position) & (self.valve_sensor.period < self.STALL_TIME):
                self.trv.process_msg()
                self.valve_sensor.read(self.motor_direction)
            self.stop_valve()
            self.valve_sensor.reset_timer()
        else:
            print('valve already at desired position')

    def set_revs(self, rev_no):
        self.valve_sensor.rev_counter = rev_no
        