import screen_brightness_control as sbc
import time
import atexit

DDCUTIL = 'ddcutil'

#monitors = sbc.list_monitors_info(DDCUTIL)

from pprint import pprint

bb = sbc.get_brightness(method=DDCUTIL)

def darken():
    for i, b in enumerate(bb):
        if bb is None:
            continue
        sbc.set_brightness(0, i, method=DDCUTIL)


def reset():
    for i, b in enumerate(bb):
        if b is None:
            continue
        sbc.set_brightness(b, i, method=DDCUTIL)

def main():
    atexit.register(reset)

    darken()
    time.sleep(5)
    reset()
    time.sleep(60)
    darken()
    time.sleep(120)
    #reset() # atexit does it for us.
