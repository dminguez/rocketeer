#!/usr/bin/python
#
# Copyright 2011 PaperCut Software Int. Pty. Ltd. http://www.papercut.com/
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
# 

############################################################################
#
#  Requirements:
#   * A Dream Cheeky Thunder USB Missile Launcher
#   * Python 2.6+
#   * Python PyUSB Support and its dependencies 
#      http://sourceforge.net/apps/trac/pyusb/
#      (on Mac use brew to "brew install libusb")
#   * Should work on Windows, Mac and Linux
#
#  Author:  Chris Dance <chris.dance@papercut.com>
#  Version: 1.0 : 2011-08-15
#  Modified by: Diego Mínguez Pastor <dminguezpastor@gmail.com>
#
############################################################################

import sys
import platform
import time
import socket
import re
import json
import urllib2
import base64

import usb.core
import usb.util

##########################  CONFIG   #########################

#
# Define a dictionary of "command sets" that map usernames to a sequence 
# of commands to target the user (e.g their desk/workstation).  It's 
# suggested that each set start and end with a "zero" command so it's
# always parked in a known reference location. The timing on move commands
# is milli-seconds. The number after "fire" denotes the number of rockets
# to shoot.
#
CURRENT_COORDINATE_X = 0
CURRENT_COORDINATE_Y = 0

COMMAND_SETS = {
    "paco" : (
        ("coordinates", "0, 0"),
    ),
    "moises" : (
        ("coordinates", "85, 15"),
    ),
    "fran" : (
        ("coordinates", "90, 15"),
    ),
    "pedro" : (
        ("coordinates", "22, 9"),
    ),
    "roberto" : (
        ("coordinates", "40, 5"),
    ),
    "franco" : (
        ("coordinates", "85, 10"),
    ),
    "pablo" : (
        ("coordinates", "102, 15"),
    ),
    "sequence" : (
        ("coordinates", "85, 10"),
        ("fire", 1),
        ("coordinates", "85, 15"),
        ("fire", 1),
        ("coordinates", "90, 15"),
        ("fire", 1),
    ),
}

##########################  ENG CONFIG  #########################

# The code...

# Protocol command bytes
DOWN    = 0x01
UP      = 0x02
LEFT    = 0x04
RIGHT   = 0x08
FIRE    = 0x10
STOP    = 0x20

DEVICE = None
DEVICE_TYPE = None

def usage():
    print "Usage: retaliation.py [command] [value]"
    print ""
    print "   commands:"
    print "     stalk - sit around waiting for a Jenkins CI failed build"
    print "             notification, then attack the perpetrator!"
    print ""
    print "     up    - move up <value> milliseconds"
    print "     down  - move down <value> milliseconds"
    print "     right - move right <value> milliseconds"
    print "     left  - move left <value> milliseconds"
    print "     fire  - fire <value> times (between 1-4)"
    print "     zero  - park at zero position (bottom-left)"
    print "     pause - pause <value> milliseconds"
    print "     led   - turn the led on or of (1 or 0)"
    print ""
    print "     <command_set_name> - run/test a defined COMMAND_SET"
    print "             e.g. run:"
    print "                  retaliation.py 'chris'"
    print "             to test targeting of chris as defined in your command set."
    print ""


def setup_usb():
    # Tested only with the Cheeky Dream Thunder
    # and original USB Launcher
    global DEVICE 
    global DEVICE_TYPE

    DEVICE = usb.core.find(idVendor=0x2123, idProduct=0x1010)

    if DEVICE is None:
        DEVICE = usb.core.find(idVendor=0x0a81, idProduct=0x0701)
        if DEVICE is None:
            raise ValueError('Missile device not found')
        else:
            DEVICE_TYPE = "Original"
    else:
        DEVICE_TYPE = "Thunder"

    

    # On Linux we need to detach usb HID first
    if "Linux" == platform.system():
        try:
            DEVICE.detach_kernel_driver(0)
        except Exception, e:
            pass # already unregistered    

    DEVICE.set_configuration()


def send_cmd(cmd):
    if "Thunder" == DEVICE_TYPE:
        DEVICE.ctrl_transfer(0x21, 0x09, 0, 0, [0x02, cmd, 0x00,0x00,0x00,0x00,0x00,0x00])
    elif "Original" == DEVICE_TYPE:
        DEVICE.ctrl_transfer(0x21, 0x09, 0x0200, 0, [cmd])

def led(cmd):
    if "Thunder" == DEVICE_TYPE:
        DEVICE.ctrl_transfer(0x21, 0x09, 0, 0, [0x03, cmd, 0x00,0x00,0x00,0x00,0x00,0x00])
    elif "Original" == DEVICE_TYPE:
        print("There is no LED on this device")

def send_move(cmd, duration_ms):
    send_cmd(cmd)
    time.sleep(duration_ms / 1000.0)
    send_cmd(STOP)


def run_command(command, value, value2):
    command = command.lower()
    if command == "right":
        send_move(RIGHT, value)
    elif command == "left":
        send_move(LEFT, value)
    elif command == "up":
        send_move(UP, value)
    elif command == "down":
        send_move(DOWN, value)
    elif command == "zero" or command == "park" or command == "reset":
        # Move to bottom-left
        print "Moving to 0,0 - Resetting coordinates..."
        
        send_move(DOWN, 2000)
        send_move(LEFT, 8000)
        
        updateCoordinates(0,0)
    elif command == "pause" or command == "sleep":
        time.sleep(value / 1000.0)
    elif command == "led":
        if value == 0:
            led(0x00)
        else:
            led(0x01)
    elif command == "fire" or command == "shoot":
        if value < 1 or value > 4:
            value = 1
        # Stabilize prior to the shot, then allow for reload time after.
        time.sleep(0.5)
        for i in range(value):
            send_cmd(FIRE)
            time.sleep(4.5)
    elif command == "coordinates":
        global CURRENT_COORDINATE_X
        CURRENT_COORDINATE_X = int(CURRENT_COORDINATE_X)
        global CURRENT_COORDINATE_Y
        CURRENT_COORDINATE_Y = int(CURRENT_COORDINATE_Y)
        
        # tell the script two coordinates
        deltaX = 0
        deltaY = 0
        changeX = False
        changeY = False
        
        
        deltaX = CURRENT_COORDINATE_X - int(value)
        deltaY = CURRENT_COORDINATE_Y - int(value2)
	
        print "Moving to coordinates " + str(value) + "," + str(value2)
    
        if deltaX < 0:
            send_move(RIGHT, abs(deltaX) * 50)
            changeX = True
        elif deltaX > 0:
            send_move(LEFT, abs(deltaX) * 50)
            changeX = True
        if deltaY < 0:
            send_move(UP, abs(deltaY) * 50)
            changeY = True
        elif deltaY > 0:
            send_move(DOWN, abs(deltaY) * 50)
            changeY = True

        newCoordinateX = str(CURRENT_COORDINATE_X)
        newCoordinateY = str(CURRENT_COORDINATE_Y)
        
        if changeX or changeY:
            if changeX:
                newCoordinateX = value
            if changeY:
                newCoordinateY = value2

        updateCoordinates(newCoordinateX, newCoordinateY)
    else:
        print "Error: Unknown command: '%s'" % command


def run_command_set(commands):
    for cmd, value in commands:
        values = str(value).split(',')
        if(len(values) == 1):
            run_command(cmd, values[0], 0)
        elif(len(values) == 2):
            run_command(cmd, values[0], values[1])

def initCoordinates():
    f = open('rocket_coordinates', 'r')
    
    global CURRENT_COORDINATE_X
    CURRENT_COORDINATE_X = f.readline()
    global CURRENT_COORDINATE_Y
    CURRENT_COORDINATE_Y = f.readline()

    print "Welcome, Commander. Your current coordinates are: " + str(int(CURRENT_COORDINATE_X)) + "," + str(int(CURRENT_COORDINATE_Y))

def updateCoordinates(x, y):
    global CURRENT_COORDINATE_X
    CURRENT_COORDINATE_X = x
    global CURRENT_COORDINATE_Y
    CURRENT_COORDINATE_Y = y

    f = open('rocket_coordinates', 'w')
    f.write(str(x)+'\n')
    f.write(str(y)+'\n')

def main(args):

    if len(args) < 2:
        usage()
        sys.exit(1)

    setup_usb()

    initCoordinates()

    # Process any passed commands or command_sets
    command = args[1]
    value = 0
    value2 = 0
    if len(args) == 3:
        value = int(args[2])
    elif len(args) == 4:
        value = int(args[2])
        value2 = int(args[3])

    if command in COMMAND_SETS:
        run_command_set(COMMAND_SETS[command])
    else:
        run_command(command, value, value2)


if __name__ == '__main__':
    main(sys.argv)
