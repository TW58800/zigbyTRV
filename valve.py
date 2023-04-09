from machine import Pin, ADC, PWM
import time


class Motor:
    motor_pin1 = Pin('D11', Pin.OUT)  # PWM(Pin('P1'))
    motor_pin2 = Pin('D1', Pin.OUT)  # , Pin.PULL_UP)
    direction = 0
    moving = False

    def forwards(self):
        self.motor_pin1.on()  # duty(1023)
        self.motor_pin2.off()
        self.direction = -1
        self.moving = True
        # Pin('D1', Pin.IN, Pin.PULL_UP)
        # Pin('D11', Pin.IN, Pin.PULL_DOWN)

    def reverse(self):
        self.motor_pin1.off()  # duty(0) 880 is the slowest before the motor won't turn
        self.motor_pin2.on()
        self.direction = 1
        self.moving = True
        # Pin('D1', Pin.IN, Pin.PULL_DOWN)
        # Pin('D11', Pin.IN, Pin.PULL_UP)

    def stop_hard(self):
        self.motor_pin1.on()
        self.motor_pin2.on()
        self.direction = 0
        self.moving = False
        # Pin('D1', Pin.IN, Pin.PULL_UP)
        # Pin('D11', Pin.IN, Pin.PULL_UP)

    def stop_soft(self):
        self.motor_pin1.off()  # duty(0)
        self.motor_pin2.off()
        self.direction = 0
        self.moving = False
        # Pin('D1', Pin.IN, Pin.PULL_DOWN)
        # Pin('D11', Pin.IN, Pin.PULL_DOWN)


class Sensor:
    ADC = ADC('D3')  # create an analog pin on D3
    period = 0
    last_reading = 0
    rev_counter = 0

    class Timer:
        set = False
        time = time.ticks_ms()
    timer = Timer()

    def __init__(self, motor):
        self.motor = motor

    def read(self):
        sensor_value = self.ADC.read()  # set xbee ref voltage (AT command 'AV') to VDD
        if (sensor_value >= 1500) & (self.last_reading < 1500):
            # print(self.period)
            self.reset_period()
            self.timer.time = time.ticks_ms()
            self.timer.set = True
            self.rev_counter += self.motor.direction
            # print(self.rev_counter)
        self.last_reading = sensor_value
        if self.timer.set:
            self.period = time.ticks_diff(time.ticks_ms(), self.timer.time)
        else:
            self.period = 0

    def reset_timer(self):
        self.timer.set = False

    def reset_period(self):
        self.period = 0

    def reset(self):
        self.reset_period()
        self.reset_timer()


class Valve:
    motor = Motor()
    valve_sensor = Sensor(motor)
    STALL_TIME = 1000  # milliseconds
    closed_position = 0
    position = 0
    travelling = False
    interupt = False

    def __init__(self, trv):
        self.trv = trv

    def open_valve(self):
        if self.motor.moving & (self.motor.direction == -1):
            return
        else:
            self.stop_valve()
            time.sleep_ms(1000)
            self.motor.forwards()
            return -1

    def close_valve(self):
        if self.motor.moving & (self.motor.direction == 1):
            return
        else:
            self.stop_valve()
            time.sleep_ms(1000)
            self.motor.reverse()
            return 1

    def stop_valve(self):
        self.motor.stop_soft()
        self.valve_sensor.reset()
        return 0

    def demand(self):  # report attribute turned off for now
        if self.trv.on_off_attributes['OnOff']:
            print('open command')
            self.position = 0
            self.goto_revs()
        else:
            print('close command')
            self.position = self.closed_position
            self.goto_revs()

    def home_valve(self):
        print('homing')
        self.open_valve()
        self.valve_moving(self.STALL_TIME)
        print('reached end of travel')
        self.valve_sensor.rev_counter = 0
        time.sleep_ms(500)
        print('moving to opposite end of travel')
        print('rev counter: %s\n' % self.valve_sensor.rev_counter)
        self.close_valve()
        self.valve_moving(self.STALL_TIME)
        if self.valve_sensor.rev_counter > 200:
            self.closed_position = self.valve_sensor.rev_counter - 100
            self.valve_sensor.rev_counter -= 50
            self.trv.on_off_attributes['OnOff'] = False
            print('\nclosed position: %s' % self.closed_position)
            print('rev counter: %s\n' % self.valve_sensor.rev_counter)
            self.position = self.closed_position
            self.goto_revs()
            # print('rev counter: %s\n' % self.valve_sensor.rev_counter)
        else:
            print('insufficient valve travel, revs: %i\n' % self.valve_sensor.rev_counter)

    def valve_moving(self, max_period):
        while (self.valve_sensor.period < max_period) & (not self.interupt):
            self.valve_sensor.read()
            self.trv.process_msg()
            # if printing, baud rate needs to be above 9600 to capture readings a fast as they are being created
        self.stop_valve()
        self.interupt = False

    def goto_revs(self):
        if self.travelling:
            return
        if self.valve_sensor.rev_counter == self.position:
            print('valve already at desired position')
        else:
            self.travelling = True
            print('travelling')
            while (self.valve_sensor.rev_counter is not self.position) & (self.valve_sensor.period < self.STALL_TIME):
                if self.valve_sensor.rev_counter > self.position:
                    self.open_valve()
                else:
                    self.close_valve()
                self.valve_sensor.read()
                self.trv.process_msg()
            self.stop_valve()
            if self.valve_sensor.period > self.STALL_TIME:
                print('valve stalling, period (ms): %i' % self.valve_sensor.period)
            else:
                print('valve reached desired position')
            print('rev counter: %s\n' % self.valve_sensor.rev_counter)
        self.travelling = False

    def set_revs(self, rev_no):
        self.valve_sensor.rev_counter = rev_no

    def get_period(self):
        return self.valve_sensor.period
        