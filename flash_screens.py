from collections import namedtuple
from contextlib import contextmanager
from email import contentmanager
import functools
import concurrent.futures
import screen_brightness_control as sbc
import time
import atexit
import subprocess
import dataclasses
from typing import *

DDCUTIL = "ddcutil"

import re


@dataclasses.dataclass(frozen=True)
class Display:
	name: str
	device: str
	manufacturer: str
	model: str
	serial: str

	_i2cpattern: ClassVar[re.Pattern] = re.compile(r"/dev/i2c-(\d+)")

	@property
	def i2cbus(self):
		match = self._i2cpattern.match(self.device)
		assert match is not None
		return match.group(1)


def detectBuses():
	detectOutput = subprocess.run(
		["ddcutil", "detect", "-t"], check=True, capture_output=True, encoding="utf-8"
	).stdout

	def parseDisplay(displayOutput: str) -> Optional[Display]:
		displayOutput = [
			line.strip() for line in displayOutput.strip().splitlines() if line != ""
		]
		if displayOutput == []:
			return None

		name = displayOutput[0]

		def getProps():
			for line in displayOutput[1:]:
				line = line.strip()
				k, v = line.split(":", maxsplit=1)
				yield k.strip(), v.strip()

		props = dict(getProps())
		device = props["I2C bus"]
		man, mod, ser = props["Monitor"].split(":", maxsplit=2)
		return Display(
			name=name, device=device, manufacturer=man, model=mod, serial=ser
		)

	displays = [
		d
		for section in detectOutput.split("\n\n")
		if (
			(d := parseDisplay(section)) is not None
			and not d.name.startswith("Phantom")
			and not d.name.startswith("Invalid")
		)
	]

	for d in displays:
		print(d)

	return displays


def getProp(propnum: int, display: Display) -> int:
	output = subprocess.run(
		[
			"ddcutil",
			"-b",
			display.i2cbus,
			"--terse",
			"--maxtries",
			"3,3,3",
			"getvcp",
			str(propnum),
		],
		check=True,
		capture_output=True,
		encoding="utf-8",
	).stdout
	[_vcp, _propnum, _dunno, valStr, maxValStr] = output.split(" ", maxsplit=4)
	assert _vcp == "VCP"
	assert int(_propnum) == propnum
	return int(valStr)


def setProp(propnum: int, display: Display, value: int) -> None:
	subprocess.run(
		[
			"ddcutil",
			"-b",
			display.i2cbus,
			"--terse",
			"--maxtries",
			"3,3,3",
			"setvcp",
			str(propnum),
			str(value),
		],
		check=True,
	)


getBrightness = functools.partial(getProp, 10)
setBrightness = functools.partial(setProp, 10)
getContrast = functools.partial(getProp, 12)
setContrast = functools.partial(setProp, 12)


class BrCn(NamedTuple):
	brightness: int
	contrast: int


from pprint import pprint

displays: List[Display]


def getInitial(d: Display):
	return BrCn(getBrightness(d), getContrast(d))


def darken(displays: List[Display]):
	with concurrent.futures.ThreadPoolExecutor() as threads:
		for d in displays:

			def _darken():
				setBrightness(d, 10)
				setContrast(d, 10)

			threads.submit(_darken)
	print("done")


def reset(displays: List[Tuple[Display, BrCn]]):
	with concurrent.futures.ThreadPoolExecutor() as threads:

		for d, initial in displays:

			def _reset():
				setBrightness(d, initial.brightness)
				setContrast(d, initial.contrast)

			threads.submit(_reset)
		print("done")


@contextmanager
def resetDisplays(displays: List[Display]):
	initial = [(d, getInitial(d)) for d in displays]
	_reset = lambda: reset(initial)
	try:
		yield _reset
	finally:
		_reset()


def flash():
	global displays

	displays = detectBuses()

	with resetDisplays(displays) as _reset:
		darken(displays)
		time.sleep(5)
		_reset()
		time.sleep(60)
		darken(displays)
		time.sleep(120)
		# _reset() # cm does it for us.


from enum import Enum


class EventType(Enum):
	Start = "SESSION_START"
	End = "SESSION_END"
	Interrupt = "SESSION_INTERRUPT"


class SessionType(Enum):
	Pomodoro = "POMODORO"
	LongBreak = "LONG_BREAK"
	ShortBreak = "SHORT_BREAK"


import sys


def main():
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("--event", choices=[x.value for x in EventType], nargs="?")
	parser.add_argument(
		"--session-type", choices=[x.value for x in SessionType], nargs="?"
	)
	args = parser.parse_args()

	if args.event is None and args.session_type is None:
		# no args, just flash
		return flash()

	if (args.event is None) ^ (args.session_type is None):
		raise argparse.ArgumentError(
			None, "You must path either neither or both of --event and --session-type."
		)

	if (
		EventType(args.event) is EventType.End
		and SessionType(args.session_type) is SessionType.Pomodoro
	):
		return flash()

	print(f"doing nothing for {args.event=}, {args.session_type=}")
