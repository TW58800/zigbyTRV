from machine import Pin, ADC, PWM
import time
import ZHA_comms


output_pin = Pin('D1', Pin.OUT)  # , Pin.PULL_UP)
apin = ADC('D3')  # create an analog pin on D3
motorPin = PWM(Pin('P1'))
output_pin.off()
motorPin.duty(0)
voltage_monitor = ADC('D2')

last_ticks = 0  # time.ticks_ms()
above_threshold = True
revs = -1
max_revs = 0
motor_direction = 0


def demand():
    if ZHA_comms.on_off_attributes['OnOff']:  # on
        actuate_valve('open')
    else:  # off
        actuate_valve('close')


def open_valve():
    # output_pin.on()
    # motorPin.duty(0)  # 880 is the slowest before the motor won't turn
    Pin('D1', Pin.IN, Pin.PULL_UP)
    Pin('D11', Pin.IN, Pin.PULL_DOWN)
    global motor_direction
    motor_direction = 1
    # print('opening')
    return 1


def close_valve():
    # output_pin.off()
    # motorPin.duty(1023)
    Pin('D1', Pin.IN, Pin.PULL_DOWN)
    Pin('D11', Pin.IN, Pin.PULL_UP)
    global motor_direction
    motor_direction = -1
    # print('closing')
    return -1


def stop_valve():
    # output_pin.on()
    # motorPin.duty(1023)
    Pin('D1', Pin.IN, Pin.PULL_UP)
    Pin('D11', Pin.IN, Pin.PULL_UP)
    global motor_direction
    motor_direction = 0
    # print('stopped')
    return 0


def actuate_valve(direction):
    global last_ticks
    if (direction == 'open') & (revs < max_revs):
        print('opening')
        open_valve()
        last_ticks = time.ticks_ms()
        while (revs < max_revs) & ZHA_comms.on_off_attributes['OnOff']:
            motor_moving()
            ZHA_comms.process_msg()
            # time.sleep_ms(1)
            # print('opening: %i' % revs)
            open_valve()
        stop_valve()
    elif (direction == 'close') & (revs > 0):
        print('closing')
        close_valve()
        last_ticks = time.ticks_ms()
        while (revs > 0) & (not ZHA_comms.on_off_attributes['OnOff']):
            motor_moving()
            ZHA_comms.process_msg()
            # time.sleep_ms(1)
            # print('closing: %i' % revs)
            close_valve()
        stop_valve()
    else:
        stop_valve()
        # print('revs: %i' % revs)


def home_valve():
    # goes to the closed position
    # time.sleep_ms(500)
    global last_ticks, revs, max_revs
    print('homing')
    close_valve()
    last_ticks = time.ticks_ms()
    while motor_moving() != 'stopped':
        ...
        # time.sleep_ms(1)
        # print(revs)
    print('reached end of travel')
    stop_valve()
    revs = 0
    # goes to the open position
    time.sleep_ms(500)
    print('moving to opposite end of travel')
    # time.sleep_ms(500)
    open_valve()
    last_ticks = time.ticks_ms()
    while motor_moving() != 'stopped':
        ...
        # counting revs
        # time.sleep_ms(2)
        # print(revs)
    # stop motor
    stop_valve()
    max_revs = revs - 300
    revs -= 150
    print('max revs: %s' % max_revs)
    ZHA_comms.report_attributes(0x000d)


def motor_moving():
    global motor_direction, last_ticks, revs, above_threshold
    sensor_now = apin.read()  # set xbee ref voltage (AT command 'AV') to VDD
    # print(sensor_now)
    # if printing, baud rate needs to be above 9600 to capture readings a fast as they are being created
    now = time.ticks_ms()
    period = time.ticks_diff(now, last_ticks)
    if (sensor_now < 1500) & above_threshold:
        above_threshold = False
        last_ticks = now
        revs = revs + motor_direction
        # print('high trigger: %s' % period)
    elif (sensor_now >= 1500) & (not above_threshold):
        # print('low trigger: %s' % period)
        above_threshold = True
    else:
        if period > 500:
            # print('stopped: %s' % period)
            return 'stopped'
        else:
            # print('waiting: %s' % period)
            return 'waiting'
    if period < 500:
        return 'moving'
    else:
        return 'stopped'


def test2():
    Pin('D1', Pin.IN, Pin.PULL_UP)
    Pin('D11', Pin.IN, Pin.PULL_UP)
    time.sleep_ms(2000)

    Pin('D1', Pin.IN, Pin.PULL_DOWN)
    Pin('D11', Pin.IN, Pin.PULL_UP)
    time.sleep_ms(2000)

    ZHA_comms.xbee.XBee().sleep_now(3000, pin_wake=True)

    Pin('D1', Pin.IN, Pin.PULL_UP)
    Pin('D11', Pin.IN, Pin.PULL_UP)
    time.sleep_ms(2000)

    ZHA_comms.xbee.XBee().sleep_now(2000, pin_wake=True)


def test():
    while True:
        # val = apin.read()  # read an analog value
        # print("- Analogue input value:", val)  # display analog value

        # 1
        output_pin.off()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # 2
        output_pin.off()
        motorPin.duty(0)
        time.sleep_ms(2000)

        # 3
        output_pin.off()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # 4
        output_pin.on()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # 5
        output_pin.off()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # 6
        output_pin.on()
        motorPin.duty(0)
        time.sleep_ms(2000)

        # 7
        output_pin.off()
        motorPin.duty(0)
        time.sleep_ms(2000)

        # 8
        output_pin.on()
        motorPin.duty(0)
        time.sleep_ms(2000)

        # 9
        output_pin.on()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # 10
        # Reverse
        output_pin.on()
        motorPin.duty(0)
        time.sleep_ms(6000)

        output_pin.on()
        motorPin.duty(1023)
        time.sleep_ms(4000)

        # Soft stop
        output_pin.off()
        motorPin.duty(0)
        time.sleep_ms(2000)

        # Forwards
        output_pin.off()
        motorPin.duty(1023)
        time.sleep_ms(2000)

        # Soft stop
        output_pin.off()
        motorPin.duty(0)
        time.sleep_ms(3000)

