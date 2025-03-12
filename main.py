import time
from machine import I2C, Pin, Timer, ADC, reset
from I2C_LCD import I2CLcd
import json
import math


min_time = 1
max_time = 180
min_alt_time = 0
max_alt_time = 30
min_adc = 250
max_adc = 65535
TICK_PERIOD = 1000

potentiometer = ADC(26)
button = Pin(13, Pin.IN, Pin.PULL_UP)
button2 = Pin(17, Pin.IN, Pin.PULL_UP)

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
devices = i2c.scan()
if devices != []:
    lcd = I2CLcd(i2c, devices[0], 2, 16)
lcd.clear()

# store a list of all_timers purely to make sure they're all 'deinit'ed
all_timers: list[Timer] = []

text_buffer = [[" " for _ in range(16)], [" " for _ in range(16)]]


def write_to_text_buffer(text: str, col_n: int, row_n: int):
    # writes text to the text buffer starting at position (col_n, row_n)
    # does not wrap
    assert 0 <= row_n <= 1
    assert 0 <= col_n <= 15
    for i, ch in enumerate(text):
        x = col_n + i
        if x > 15:
            break
        text_buffer[row_n][x] = ch


time_control = {}
time_control_file_path = "time_control.txt"
try:
    with open(time_control_file_path, "r") as f:
        time_control = json.load(f)
except Exception as _exception:
    # file doesn't exist or is corrupted - write default_time_control to it and set time_control to default
    default_time_control = {
        "type": "bonus",
        "p1_initial_time": 10,
        "p2_initial_time": 10,
        "p1_alt_time": 5,
        "p2_alt_time": 5,
    }
    with open(time_control_file_path, "w") as f:
        json.dump(default_time_control, f)
    time_control = default_time_control.copy()
print("time_control: ", time_control)


def update_display():
    """Write the text buffer to the lcd screen."""
    for row_n in range(0, len(text_buffer)):
        lcd.move_to(0, row_n)
        for col_n in range(0, len(text_buffer[0])):
            lcd.putchar(text_buffer[row_n][col_n])


def blink_position(row_n: int, col_n: int):
    def revert_char():
        lcd.move_to(
            row_n,
            col_n,
        )
        lcd.putchar(text_buffer[col_n][row_n])

    lcd.move_to(row_n, col_n)
    lcd.putchar(chr(0))

    Timer(period=250, mode=Timer.ONE_SHOT, callback=lambda t: revert_char())


blink_timers: list[Timer] = []


def get_blink_timer(positions: list[tuple[int, int]]):
    global blink_timers

    def blink_positions():
        for [row_n, col_n] in positions:
            blink_position(row_n, col_n)

    blink_positions()
    timer = Timer(period=800, mode=Timer.PERIODIC, callback=lambda t: blink_positions())
    blink_timers.append(timer)
    all_timers.append(timer)
    return timer


FULL_CHAR = [
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
]
lcd.custom_char(0, FULL_CHAR)
CLOCK_CHAR = [
    0b00000,
    0b01110,
    0b10101,
    0b10111,
    0b10001,
    0b01110,
    0b00000,
    0b00000,
]
lcd.custom_char(1, CLOCK_CHAR)
PAWN_CHAR = [
    0b00100,
    0b01110,
    0b11111,
    0b01110,
    0b00100,
    0b00100,
    0b01110,
    0b11111,
]
lcd.custom_char(2, PAWN_CHAR)
TROPHY_CHAR = [
    0b11111,
    0b11111,
    0b01110,
    0b01110,
    0b00100,
    0b00100,
    0b01110,
    0b11111,
]
lcd.custom_char(3, TROPHY_CHAR)


initialisation_stages = [
    "type",
    "both-main-times",
    "both-alt-times",
    "second-main-time",
    "second-alt-time",
]
current_initialisation_stage = 0


def debounced(handler, interval_ms):
    previous_time = 0

    def wrapper(*args, **kwargs):
        nonlocal previous_time
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, previous_time) > interval_ms:
            previous_time = current_time
            return handler(*args, **kwargs)

    return wrapper


def change_stage_handler():
    global current_initialisation_stage
    global blink_timers

    for timer in blink_timers:
        timer.deinit()
    current_initialisation_stage = (current_initialisation_stage + 1) % len(
        initialisation_stages
    )
    print("current_initialisation_stage: ", current_initialisation_stage)
    cur_stage = initialisation_stages[current_initialisation_stage]
    if cur_stage == "type":
        blink_timer = get_blink_timer([(6, 0), (7, 0), (8, 0), (9, 0), (10, 0)])
        blink_timers.append(blink_timer)
    elif cur_stage == "both-main-times":
        blink_timer = get_blink_timer([(0, 1), (1, 1), (2, 1), (7, 1), (8, 1), (9, 1)])
        blink_timers.append(blink_timer)
    elif cur_stage == "both-alt-times":
        blink_timer = get_blink_timer([(4, 1), (5, 1), (11, 1), (12, 1)])
        blink_timers.append(blink_timer)
    elif cur_stage == "second-main-time":
        blink_timer = get_blink_timer([(7, 1), (8, 1), (9, 1)])
        blink_timers.append(blink_timer)
    elif cur_stage == "second-alt-time":
        blink_timer = get_blink_timer([(11, 1), (12, 1)])
        blink_timers.append(blink_timer)


def update_text_buffer_initialisation_stage():
    write_to_text_buffer(f" P1   {time_control['type']}  P2 ", 0, 0)
    write_to_text_buffer(
        f"{time_control['p1_initial_time']:<3}+{time_control['p1_alt_time']:<2}", 0, 1
    )
    text_buffer[0][5] = "\x01"

    tmp_length = len(
        f"{time_control['p2_initial_time']:}+{time_control['p2_alt_time']}"
    )
    write_to_text_buffer(
        f"{time_control['p2_initial_time']:<3}+{time_control['p2_alt_time']:<2}",
        7,
        1,
    )


def update_text_buffer_game_stage(game_state):
    write_to_text_buffer(" P1: ", 0, 0)
    write_to_text_buffer(" P2: ", 0, 1)

    if game_state["p1s_turn"]:
        text_buffer[0][0] = "\x02"
    else:
        text_buffer[1][0] = "\x02"

    write_to_text_buffer(
        f"{game_state['p1_main_time']}+{game_state['p1_alt_time']}", 5, 0
    )
    write_to_text_buffer(
        f"{game_state['p2_main_time']}+{game_state['p2_alt_time']}", 5, 1
    )


# TODO: use rolling average to smooth the readings
# TODO: adjust time selection from simply linear across possible choices
def adjust_with_potentiometer():
    global current_initialisation_stage
    global potentiometer
    global time_control

    prev_time_control = time_control.copy()
    if initialisation_stages[current_initialisation_stage] == "type":
        if potentiometer.read_u16() >= 65536 / 2:
            time_control["type"] = "delay"
        else:
            time_control["type"] = "bonus"
    elif initialisation_stages[current_initialisation_stage] == "both-main-times":
        adc_value = max(min_adc, min(potentiometer.read_u16(), max_adc))
        new_time = min_time + (adc_value - min_adc) * (max_time - min_time) / (
            max_adc - min_adc
        )
        new_time = math.floor(new_time)
        time_control["p1_initial_time"] = new_time
        time_control["p2_initial_time"] = new_time
    elif initialisation_stages[current_initialisation_stage] == "both-alt-times":
        adc_value = max(min_adc, min(potentiometer.read_u16(), max_adc))
        new_time = min_alt_time + (adc_value - min_adc) * (
            max_alt_time - min_alt_time
        ) / (max_adc - min_adc)
        new_time = math.floor(new_time)
        time_control["p1_alt_time"] = new_time
        time_control["p2_alt_time"] = new_time
    elif initialisation_stages[current_initialisation_stage] == "second-main-time":
        pass
    elif initialisation_stages[current_initialisation_stage] == "second-alt-time":
        pass

    if prev_time_control != time_control:
        update_text_buffer_initialisation_stage()
        update_display()


def handle_tick_timer(game_state):
    time_delta = TICK_PERIOD / 1000
    if game_state["type"] == "delay":
        if game_state["p1s_turn"]:
            if game_state["p1_alt_time"] > 0:
                game_state["p1_alt_time"] -= time_delta
            elif game_state["p1_main_time"] > 0:
                game_state["p1_main_time"] -= time_delta
            else:
                game_state["game_over"] = True
        else:
            if game_state["p2_alt_time"] > 0:
                game_state["p2_alt_time"] -= time_delta
            elif game_state["p2_main_time"] > 0:
                game_state["p2_main_time"] -= time_delta
            else:
                game_state["game_over"] = True
    elif game_state["type"] == "bonus":
        if game_state["p1s_turn"]:
            if game_state["p1_main_time"] > 0:
                game_state["p1_main_time"] -= time_delta
            else:
                game_state["game_over"] = True
        else:
            if game_state["p2_main_time"] > 0:
                game_state["p2_main_time"] -= time_delta
            else:
                game_state["game_over"] = True


def change_turn(p1s_turn: bool):
    global time_control
    global game_state
    if game_state["p1s_turn"] == p1s_turn:
        return
    if p1s_turn:
        game_state["p1s_turn"] = True
        if time_control["type"] == "delay":
            game_state["p2_alt_time"] = time_control["p2_alt_time"]
        elif time_control["type"] == "bonus":
            game_state["p2_main_time"] += game_state["p2_alt_time"]
    else:
        game_state["p1s_turn"] = False
        if time_control["type"] == "delay":
            game_state["p1_alt_time"] = time_control["p1_alt_time"]
        elif time_control["type"] == "bonus":
            game_state["p1_main_time"] += game_state["p1_alt_time"]
    print("now game state is:\n", game_state)


try:
    while True:
        ## set up the time control!

        text_buffer = [[" " for _ in range(16)], [" " for _ in range(16)]]
        update_display()
        current_initialisation_stage = 0
        setting_up_time_control = True

        def set_setting_up_time_control_to_false():
            # ... lambda can't have expression?? xdd
            global setting_up_time_control
            setting_up_time_control = False

        update_text_buffer_initialisation_stage()
        update_display()
        blink_timer = get_blink_timer([(6, 0), (7, 0), (8, 0), (9, 0), (10, 0)])
        tmp = debounced(change_stage_handler, 500)
        button.irq(
            handler=lambda _pin: (blink_timer.deinit(), tmp()),
            trigger=Pin.IRQ_FALLING,
        )
        button2.irq(
            handler=lambda _pin: debounced(set_setting_up_time_control_to_false(), 500),
            trigger=Pin.IRQ_FALLING,
        )
        while setting_up_time_control:
            print("setting_up_time_control: ", setting_up_time_control)
            previous_initialisation_stage = current_initialisation_stage
            while (
                previous_initialisation_stage == current_initialisation_stage
                and setting_up_time_control
            ):
                adjust_with_potentiometer()
                time.sleep_ms(500)

        ## now start the game!

        game_state = {
            "game_over": False,
            "p1s_turn": True,
            "p1_main_time": time_control["p1_initial_time"] * 60.0,
            "p2_main_time": time_control["p2_initial_time"] * 60.0,
            "p1_alt_time": time_control["p1_alt_time"],
            "p2_alt_time": time_control["p2_alt_time"],
            "type": time_control["type"],
        }
        for timer in all_timers:
            print("deiniting timer")
            timer.deinit()

        button.irq(handler=lambda pin: debounced(change_turn(False), 500))
        button2.irq(handler=lambda pin: debounced(change_turn(True), 500))

        time_timer = Timer(
            mode=Timer.PERIODIC,
            period=TICK_PERIOD,
            callback=lambda t: handle_tick_timer(game_state),
        )
        all_timers.append(time_timer)
        write_to_text_buffer(" " * 16, 0, 0)
        write_to_text_buffer(" " * 16, 0, 1)
        (potentiometer_reached_min, potentiometer_reached_max) = (False, False)
        while not game_state["game_over"]:
            update_text_buffer_game_stage(game_state)
            update_display()
            if potentiometer_reached_min and potentiometer_reached_max:
                # RESET THE GAME!
                for timer in all_timers:
                    timer.deinit()
                lcd.clear()
                break
            if potentiometer.read_u16() < 300:
                potentiometer_reached_min = True
            if potentiometer.read_u16() > 65000:
                potentiometer_reached_max = True
            time.sleep_ms(100)
        if game_state["game_over"]:
            if game_state["p1_main_time"] <= 0:
                text_buffer[0][0] = " "
                text_buffer[1][0] = "\x03"
                text_buffer[1][15] = "\x03"
                update_display()
            else:
                text_buffer[1][0] = " "
                text_buffer[0][0] = "\x03"
                text_buffer[0][15] = "\x03"
                update_display()

            display_endgame_screen = True

            def endgame_handler(pin):
                global display_endgame_screen
                display_endgame_screen = False

            button.irq(handler=endgame_handler, trigger=Pin.IRQ_FALLING)
            button2.irq(handler=endgame_handler, trigger=Pin.IRQ_FALLING)

            while display_endgame_screen:
                time.sleep_ms(100)
            time.sleep_ms(300)

except Exception as exception:
    print(f"caught exception {exception}")
finally:
    text_buffer = [[" " for _ in range(16)], [" " for _ in range(16)]]
    for timer in all_timers:
        timer.deinit()
    lcd.clear()
    print("finally...")
