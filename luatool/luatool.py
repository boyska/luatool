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
                   "print('name:'..k..', size:'..v) end\n", True)
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


def telnet_writer(data, ignored=True):
    if ignored is not True:
        import warnings
        warnings.warn("check attribute for telnet_writer is ignored",
                      warnings.DeprecationWarning)
    kind_of_newlines = re.compile(r'\n|\r')
    logging.debug("Sent [[ {} ]]".format(data))
    s.write(data)
    # we need to wait for ">", but "read_until" seems not reliable enough
    # so we just do some attemps, sleeping always a bit more
    for i in xrange(7):
        sleep(i * 0.1)  # at every attempt, we sleep something more
        response = s.read_until('>', 4)
        logging.debug("Received [[ {} ]]".format(response))
        if '>' in response:
            # ok, we have reached it
            break
    else:
        raise Exception('Error in response: > not found')
    response = response[:response.index('>')]
    lines = kind_of_newlines.split(response)

    if any((line.strip().startswith('lua:') for line in lines)):
        logging.error("Received lua errors\n%s" %
                      '\n'.join((line for line in lines if
                                 line.strip().startswith('lua:'))))
        raise Exception('ERROR from Lua interpreter\r\n\r\n')
    return response


def writer(data):
    writeln("file.writeline([==[" + data + "]==])\r")


def openserial(args):
    if args.telnet:
        import telnetlib
        logging.debug("connecting")
        s = telnetlib.Telnet(args.telnet, args.telnet_port, timeout=10)
        logging.debug("waiting for prompt")
        sleep(1)
        banner = s.read_very_eager()
        logging.debug("Banner '%s'" % banner)
        logging.info("connection ready")
        return s
    else:
        import serial
        # Open the selected serial port
        try:
            s = serial.Serial(args.port, args.baud)
        except:
            raise Exception("Could not open port %s\n" % (args.port))
        s.timeout = 3
        s.interCharTimeout = 3
        return s


def get_parser():
    # parse arguments or use defaults
    parser = argparse.ArgumentParser(description='ESP8266 Lua script uploader.')
    parser.add_argument('-p', '--port',    default='/dev/ttyUSB0', help='Device name, default /dev/ttyUSB0')
    parser.add_argument('-b', '--baud',    default=9600,           help='Baudrate, default 9600')
    parser.add_argument('-T', '--telnet', metavar='HOST')
    parser.add_argument('-P', '--telnet-port', default=23, type=int, metavar='HOSTPORT')
    parser.add_argument('-v', '--verbose', action='store_true',    help="Show progress messages.")
    sub = parser.add_subparsers()
    cmd_list = sub.add_parser('list')
    cmd_list.set_defaults(func=main_list)
    cmd_wipe = sub.add_parser('wipe')
    cmd_wipe.set_defaults(func=main_wipe)
    cmd_remove = sub.add_parser('remove')
    cmd_remove.set_defaults(func=main_remove)
    cmd_remove.add_argument('fname', metavar='FILENAME')
    cmd_upload = sub.add_parser('upload')
    cmd_upload.set_defaults(func=main_upload)
    cmd_upload.add_argument('src', metavar='FILENAME',
                            type=argparse.FileType('r'))
    cmd_upload.add_argument('-t', '--dest')
    cmd_upload.add_argument('-c', '--compile', action='store_true',    help='Compile lua to lc after upload')
    cmd_upload.add_argument('-a', '--append',  action='store_true',    help='Append source file to destination file.')
    cmd_upload.add_argument('-r', '--restart', action='store_true',    help='Restart MCU after upload')
    cmd_upload.add_argument('-d', '--dofile',  action='store_true',    help='Run the Lua script after upload')
    return parser


def main_list(args):
    flist = get_file_list()
    for filename in flist:
        print '%(name)s\t(size=%(size)d)' % flist[filename]


def main_wipe(args):
    for fn in get_file_list():
        logging.debug("Delete file {} from device.\r\n".format(fn))
        writeln("file.remove(\"" + fn + "\")\r")


def main_remove(args):
    writeln("file.remove(\"" + args.fname + "\")\r")


def main_upload(args):
    if args.dest is None:
        args.dest = basename(args.src.name)

    # Verify the selected file will not exceed the size of the serial buffer.
    # The size of the buffer is 256. This script does not accept files with
    # lines longer than 230 characters to have some room for command overhead.
    for ln in args.src:
        if len(ln) > 230:
            sys.stderr.write("File \"%s\" contains a line with more than 240 "
                             "characters. This exceeds the size of the serial buffer.\n"
                             % args.src)
            args.src.close()
            return 1

    # Go back to the beginning of the file after verifying it has the correct
    # line length
    args.src.seek(0)

    # set serial timeout
    if args.verbose:
        sys.stderr.write("Upload starting\r\n")

    # remove existing file on device
    if args.append is not True:
        logging.info("Stage 1. Deleting old file from flash memory")
        writeln("file.open(\"" + args.dest + "\", \"w\")\r")
        writeln("file.close()\r")
        writeln("file.remove(\"" + args.dest + "\")\r")
    else:
        logging.info("[SKIPPED] Stage 1. Deleting old file from flash memory [SKIPPED]")

    # read source file line by line and write to device
    logging.info("\r\nStage 2. Creating file in flash memory and write first line")
    if args.append:
        writeln("file.open(\"" + args.dest + "\", \"a+\")\r")
    else:
        writeln("file.open(\"" + args.dest + "\", \"w+\")\r")
    logging.info("\r\nStage 3. Start writing data to flash memory...")
    for line in args.src:
        writer(line.strip())

    # close both files
    args.src.close()
    logging.info("\r\nStage 4. Flush data and closing file")
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
    if not args.telnet:
        s.flush()
    s.close()

    sys.stderr.write("\r\n--->>> All done <<<---\r\n")


if __name__ == '__main__':
    args = get_parser().parse_args()
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

    global s
    s = openserial(args)
    ret = args.func(args)
    sys.exit(0 if ret is None else ret)
