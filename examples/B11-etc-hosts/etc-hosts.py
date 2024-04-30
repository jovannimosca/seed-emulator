#!/usr/bin/env python3
# encoding: utf-8

from seedemu.compiler import Docker
from seedemu.layers import Base, EtcHosts
from seedemu.core import Emulator
import os, sys

# Add to example folder to the python path, and then import the mini internet
example_dir = "/".join(os.path.realpath(__file__).split("/")[0:-2])
sys.path.insert(1, example_dir)

from B00_mini_internet import mini_internet

mini_internet.run('base-internet.bin')

emu = Emulator()
emu.load('base-internet.bin')

etc_hosts = EtcHosts()

# Create a new host in AS-152 with custom host name
base: Base = emu.getLayer('Base')
as152 = base.getAutonomousSystem(152)
as152.createHost('database').joinNetwork('net0', address = '10.152.0.4').addHostName('database.com')

# Add the etc_hosts layer
emu.addLayer(etc_hosts)

# Render the emulation and further customization
emu.render()
emu.compile(Docker(), './output', override=True)
