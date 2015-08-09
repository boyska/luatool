#!/usr/bin/env python2
#
# ESP8266 luatool
# Author e-mail: 4ref0nt@gmail.com
# Site: http://esp8266.ru
# Contributions from: https://github.com/sej7278
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
from time import sleep
import argparse
from os.path import basename
import logging
import re


version = "0.6.3"

def get_file_list():
    filedesc = re.compile(r'^name:([^, ]*), size:([0-9]+)$')
    data = writeln("local l = file.list();for k,v in pairs(l) do "
            "  print('name:'..k..', size:'..v)end\n", True)
    found = {}
    for l in data.split('\n'):
        line = l.strip()
        m = filedesc.match(line)
        if not m:
            logging.debug("Undesired line: '{}'".format(line))
            continue
        found[m.group(1)] = {'size': int(m.group(2)), 'name': m.group(1)}
    return found



def serial_writer(data, check=True):
    if s.inWaiting() > 0:
        s.flushInput()
    if len(data) > 0:
        sys.stdout.write("\r\n->")
        sys.stdout.write(data.split("\r")[0])
    s.write(data)
    sleep(0.3)
    if check:
        line = ''
        char = ''
        alldata = ''
        while char != chr(62):  # '>'
            alldata += char
            char = s.read(1)
            if char == '':
                raise Exception('No proper answer from MCU')
            if char == chr(13) or char == chr(10):  # LF or CR
                if line != '':
                    line = line.strip()
                    if line.strip() == data.strip():
                        sys.stdout.write(" -> ok")
                    elif line[:4] == "lua:":
                        sys.stdout.write("\r\n\r\nLua ERROR: %s" % line)
                        raise Exception('ERROR from Lua interpreter\r\n\r\n')
                    else:
                        data = data.split("\r")[0]
                        sys.stdout.write("\n\nERROR")
                        sys.stdout.write("\n send string    : '%s'" % data)
                        sys.stdout.write("\n expected echo  : '%s'" % data)
                        sys.stdout.write("\n but got answer : '%s'" % line)
                        sys.stdout.write("\n\n")
                        raise Exception('Error sending data to MCU\n\n')
                    line = ''
            else:
                line += char
        return alldata
    else:
        sys.stdout.write(" -> send without check")
        return None
writeln = serial_writer

def telnet_writer(data, check=True):
    kind_of_newlines = re.compile(r'\n|\r')
    logging.debug("Sent [[ {} ]]".format(data))
    s.write(data)
    sleep(0.3)
    if not check:
        sys.stdout.write(" -> send without check")

    response = s.read_until('>')
    logging.debug("Received [[ {} ]]".format(response))
    if not '>' in response:
        raise Exception('> not found')
    response = response[:response.index('>')]
    lines = kind_of_newlines.split(response)

    if any((line.strip().startswith('lua:') for line in lines)):
        logging.error("Received lua errors\n%s" % '\n'.join((line for line in
            lines if line.strip().startswith('lua:'))))
        raise Exception('ERROR from Lua interpreter\r\n\r\n')
    return response



def writer(data):
    writeln("file.writeline([==[" + data + "]==])\r")


def openserial(args):
    if args.telnet:
        import telnetlib
        s = telnetlib.Telnet(args.telnet, args.telnet_port, timeout=20)
        return s
    else:
        import serial
        # Open the selected serial port
        try:
            s = serial.Serial(args.port, args.baud)
        except:
            sys.stderr.write("Could not open port %s\n" % (args.port))
            sys.exit(1)
        if args.verbose:
            sys.stderr.write("Set timeout %s\r\n" % s.timeout)
        s.timeout = 3
        if args.verbose:
            sys.stderr.write("Set interCharTimeout %s\r\n" % s.interCharTimeout)
        s.interCharTimeout = 3
        return s


if __name__ == '__main__':
    # parse arguments or use defaults
    parser = argparse.ArgumentParser(description='ESP8266 Lua script uploader.')
    parser.add_argument('-p', '--port',    default='/dev/ttyUSB0', help='Device name, default /dev/ttyUSB0')
    parser.add_argument('-b', '--baud',    default=9600,           help='Baudrate, default 9600')
    parser.add_argument('-T', '--telnet', metavar='HOST')
    parser.add_argument('-P', '--telnet-port', default=23, type=int, metavar='HOSTPORT')
    parser.add_argument('-f', '--src',     default='main.lua',     help='Source file on computer, default main.lua')
    parser.add_argument('-t', '--dest',    default=None,           help='Destination file on MCU, default to source file name')
    parser.add_argument('-c', '--compile', action='store_true',    help='Compile lua to lc after upload')
    parser.add_argument('-r', '--restart', action='store_true',    help='Restart MCU after upload')
    parser.add_argument('-d', '--dofile',  action='store_true',    help='Run the Lua script after upload')
    parser.add_argument('-v', '--verbose', action='store_true',    help="Show progress messages.")
    parser.add_argument('-a', '--append',  action='store_true',    help='Append source file to destination file.')
    parser.add_argument('-l', '--list',    action='store_true',    help='List files on device')
    parser.add_argument('-w', '--wipe',    action='store_true',    help='Delete all lua/lc files on device.')
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, filename='luatool.log')
    else:
        logging.basicConfig(level=logging.INFO, filename='luatool.log')

    if args.telnet:
        args.port = None
        args.baud = None
        writeln = telnet_writer
    else:
        args.telnet_port = None
        writeln = serial_writer

    if args.list:
        s = openserial(args)
        flist = get_file_list()
        for filename in flist:
            print '%(name)s\t(size=%(size)d)' % flist[filename]
        sys.exit(0)

    if args.wipe:
        s = openserial(args)
        out = writeln("local l = file.list();for k,v in pairs(l) do print(k)end\r",
                True)
        file_list = []
        fn = ""
        while True:
            char = s.read(1)
            if char == '' or char == chr(62):
                break
            if char not in ['\r', '\n']:
                fn += char
            else:
                if fn:
                    file_list.append(fn.strip())
                fn = ''
        for fn in file_list[1:]:  # first line is the list command sent to device
            if args.verbose:
                sys.stderr.write("Delete file {} from device.\r\n".format(fn))
            writeln("file.remove(\"" + fn + "\")\r")
        sys.exit(0)

    if args.dest is None:
        args.dest = basename(args.src)

    # open source file for reading
    try:
        f = open(args.src, "rt")
    except:
        sys.stderr.write("Could not open input file \"%s\"\n" % args.src)
        sys.exit(1)

    # Verify the selected file will not exceed the size of the serial buffer.
    # The size of the buffer is 256. This script does not accept files with
    # lines longer than 230 characters to have some room for command overhead.
    for ln in f:
        if len(ln) > 230:
            sys.stderr.write("File \"%s\" contains a line with more than 240 "
                             "characters. This exceeds the size of the serial buffer.\n"
                             % args.src)
            f.close()
            sys.exit(1)

    # Go back to the beginning of the file after verifying it has the correct
    # line length
    f.seek(0)

    # Open the selected serial port
    s = openserial(args)

    # set serial timeout
    if args.verbose:
        sys.stderr.write("Upload starting\r\n")

    # remove existing file on device
    if args.append==False:
        if args.verbose:
            sys.stderr.write("Stage 1. Deleting old file from flash memory")
        writeln("file.open(\"" + args.dest + "\", \"w\")\r")
        writeln("file.close()\r")
        writeln("file.remove(\"" + args.dest + "\")\r")
    else:
        if args.verbose:
            sys.stderr.write("[SKIPPED] Stage 1. Deleting old file from flash memory [SKIPPED]")


    # read source file line by line and write to device
    if args.verbose:
        sys.stderr.write("\r\nStage 2. Creating file in flash memory and write first line")
    if args.append: 
        writeln("file.open(\"" + args.dest + "\", \"a+\")\r")
    else:
        writeln("file.open(\"" + args.dest + "\", \"w+\")\r")
    line = f.readline()
    if args.verbose:
        sys.stderr.write("\r\nStage 3. Start writing data to flash memory...")
    while line != '':
        writer(line.strip())
        line = f.readline()

    # close both files
    f.close()
    if args.verbose:
        sys.stderr.write("\r\nStage 4. Flush data and closing file")
    writeln("file.flush()\r")
    writeln("file.close()\r")

    # compile?
    if args.compile:
        if args.verbose:
            sys.stderr.write("\r\nStage 5. Compiling")
        writeln("node.compile(\"" + args.dest + "\")\r")
        writeln("file.remove(\"" + args.dest + "\")\r")

    # restart or dofile
    if args.restart:
        writeln("node.restart()\r")
    if args.dofile:   # never exec if restart=1
        writeln("dofile(\"" + args.dest + "\")\r", 0)

    # close serial port
    s.flush()
    s.close()

    # flush screen
    sys.stdout.flush()
    sys.stderr.flush()
    sys.stderr.write("\r\n--->>> All done <<<---\r\n")
