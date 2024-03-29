#!/usr/bin/env python
######################################################################
# check_shelly.py
#
# A monitoring plugin to constantly monitor Shelly relay switch
# or power meter devices. Tested on 2nd Gen device.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (c) 2022 Claudio Kuenzler www.claudiokuenzler.com
# Copyright (c) 2023 Bernd Arnold
# Copyright (c) 2023 Fabian Ihle
#
# History:
# 20220214-16: Development on Shelly Pro 4 PM (2nd Gen device)
# 20220216 0.1: Code published in public repository
# 20230120 0.2: Check whether relay switch is turned on or off (--expect-powerstatus)
# 20230718 0.3: Support for generation 1 shelly devices (Fabian Ihle)
######################################################################
# version
version='0.3'

# imports
import argparse
import json
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import sys

# defaults
auth=False
ignore_restart=False
shelly_model="Pro4PM"
shelly_switch=0
exit_status=0
expect_powerstatus=None

# Input parameters
description = "check_shelly v%s - Monitoring Plugin for Shelly 2nd gen power devices" % version
parser = argparse.ArgumentParser(description=description)
parser.add_argument('-H', '--host', dest='host', required=True, help='IP address of Shelly device')
parser.add_argument('-a', '--auth', dest='auth', action='store_true', help='Enable authentication')
parser.add_argument('-u', '--user', dest='user', help='Username for authentication (actually always admin)')
parser.add_argument('-p', '--password', dest='password', help='Password for authentication')
parser.add_argument('-t', '--type', dest='checktype', required=True, choices=['info', 'system', 'meter'], help='Type of check to do: info, system, meter')
parser.add_argument('-v', '--shelly-version', dest='shelly_version', required=False, choices=['1', '2'], help='V1 or V2 shelly', default=2)
parser.add_argument('-m', '--model', dest='shelly_model', help='Hardware model of Shelly device (defaults to Pro4PM)')
parser.add_argument('-s', '--switch', dest='shelly_switch', type=int, help='Select the switch id of this Shelly device (e.g. switch_0 would be 0, defaults to 0)')
parser.add_argument('--ignore-restart', dest='ignore_restart', action='store_true', help='Ignore the fact that the device requires a restart')
parser.add_argument('--expect-powerstatus', dest='expect_powerstatus', choices=['0','1','off','on'], help='Check for powerstatus of the switch, raises a warning state if different, requires --type=meter')
args = parser.parse_args()

# Handle inputs, overwrite defaults
if (args.host):
    host=args.host

if (args.auth):
    auth=args.auth
    args.user ="admin"
    if not args.password:
        print("SHELLY CRITICAL: Need to give password when authentication is enabled")
        sys.exit(2)

if (args.shelly_model):
    shelly_model=args.shelly_model

if (args.shelly_switch):
    shelly_switch=args.shelly_switch

if (args.shelly_version):
    shelly_version=args.shelly_version

if (args.ignore_restart):
    ignore_restart=args.ignore_restart

if (args.checktype):
    checktype=args.checktype

if (args.expect_powerstatus):
    expect_powerstatus=True if args.expect_powerstatus == "1" or args.expect_powerstatus == "on" else False
    if checktype != "meter":
        print("SHELLY UNKNOWN: expect-powerstatus requires check type 'meter'")
        sys.exit(3)

if shelly_version == '1':
    apiurl="http://%s/settings" % host
    infourl="http://%s/shelly" % host
    statusurl="http://%s/status" % host
    meterurl=f"http://%s/meter/{shelly_switch}" % host
    relayurl=f"http://%s/relay/{shelly_switch}" % host
    AuthenticationMethod = HTTPBasicAuth
else: 
    apiurl="http://%s/rpc" % host
    infourl="http://%s/shelly" % host
    AuthenticationMethod = HTTPDigestAuth


# Handle different Shelly device models (shelly_model) or device generations
# todo: maybe this can be used in the future

#################################################################################
# Functions
def responsehandler(response):
    if (response.status_code == 401):
        print("SHELLY WARNING: unable to authenticate (Shelly requires authentication)")
        sys.exit(1)
    elif (response.status_code != 200):
        print("SHELLY CRITICAL: Not able to communicate with Shelly device - HTTP response was %i" % response.status_code)
        sys.exit(2)

def systemexit(exit_status, output, perfdata):
    print("%s %s" % (output, perfdata))
    sys.exit(exit_status)
#################################################################################
# Do the checks
if checktype == "info":
    try:
        r = requests.get(infourl)
    except OSError as err:
        systemexit(2, "SHELLY CRITICAL: {0}".format(err), "")
    responsehandler(r)
    data = r.json()
    if shelly_version == '1':
        deviceid = data['mac'] if data['longid'] == 1 else data['mac'][-3:]
        fwversion = data['fw']
        model = data['type']
        gen = 1
        devicename = ""
        auth_en = data['auth']
        if auth_en:
            authinfo="Authentication is enabled"
        else:
            authinfo="Authentication is disabled"
    else: 
        deviceid = data['id']
        model = data['model']
        gen = data['gen']
        fwversion = data['ver']
        devicename = data['app']
        auth_en = data['auth_en']
        if auth_en:
            authinfo="Authentication is enabled"
        else:
            authinfo="Authentication is disabled"

    output= "SHELLY OK: Device %s (Model: %s, Generation: %s, Firmware: %s) is running - %s" % (devicename, model, gen, fwversion, authinfo)
    perfdata = ""
    exit_status=0
    systemexit(exit_status, output, perfdata)


elif checktype == "system":
    postdata = {'id':1, 'method':'Sys.GetStatus'}
    if auth:
        try:
            r = requests.post(apiurl, json=postdata, auth=AuthenticationMethod(args.user, args.password))
            r_status = None
            if shelly_version == '1':
                r_status = requests.post(statusurl, auth=AuthenticationMethod(args.user, args.password))
        except OSError as err:
            systemexit(2, "SHELLY CRITICAL: {0}".format(err), "")
    else:
        try:
            r = requests.post(apiurl, json=postdata)
        except OSError as err:
            systemexit(2, "SHELLY CRITICAL: {0}".format(err), "")
    responsehandler(r)
    if r_status:
        responsehandler(r_status)
        data_status = r_status.json()
    #print(r.text) #debug
    data = r.json()
    #print(json.dumps(data)) #debug
    if shelly_version == '1':
        devicename = data['device']['hostname']
        systemtime = data['time']
        uptime = data_status['uptime'] 
        ram_size = data_status['ram_total']
        ram_free = data_status['ram_free']
        ram_used = ram_size - ram_free 
        fs_size = data_status['fs_size']
        fs_free = data_status['fs_free']
        fs_used = fs_size - fs_free
    else:
        devicename = data['src']
        restart_required = data['result']['restart_required']
        systemtime = data['result']['time']
        uptime = data['result']['uptime']
        ram_size = data['result']['ram_size']
        ram_free = data['result']['ram_free']
        ram_used = ram_size - ram_free
        fs_size = data['result']['fs_size']
        fs_free = data['result']['fs_free']
        fs_used = fs_size - fs_free

        if (restart_required == True and ignore_restart == False):
            output_warning="SHELLY WARNING: Device (%s) requires a restart" % (devicename)
            exit_status=1

    if (exit_status > 1):
        output=output_critical
    elif (exit_status > 0):
        output=output_warning
    else:
        output="SHELLY OK: Device (%s), uptime %i" % (devicename, uptime)

    perfdata="|uptime=%i memory=%iB;;;0;%i disk=%iB;;;0;%i" % (uptime, ram_used, ram_size, fs_used, fs_size)
    systemexit(exit_status, output, perfdata)

elif checktype == "meter":
    postdata = { "id": 1, "method": "Switch.GetStatus", "params": {"id": shelly_switch} }
    r_meter = None
    r_relay = None
    if auth:
        try:
            r = requests.post(apiurl, json=postdata, auth=AuthenticationMethod(args.user, args.password))
            if shelly_version == '1':
                r_meter = requests.post(meterurl, auth=AuthenticationMethod(args.user, args.password))
                r_relay = requests.post(relayurl, auth=AuthenticationMethod(args.user, args.password))
        except OSError as err:
            systemexit(2, "SHELLY CRITICAL: {0}".format(err), "")
    else:
        try:
            r = requests.post(apiurl, json=postdata)
        except OSError as err:
            systemexit(2, "SHELLY CRITICAL: {0}".format(err), "")
    responsehandler(r)
    if r_meter:
        responsehandler(r_meter)
        responsehandler(r_relay)
        data_meter = r_meter.json()
        data_relay = r_relay.json()
    data = r.json()

    if shelly_version == '1':
        devicename = data['device']['hostname']
        apower = data_meter['power']
        aenergy_total = data_meter['total']
        powerstatus = "on" if data_relay['ison'] else "off"

        if (exit_status == 0):
            state_text = "OK"
        elif (exit_status == 1):
            state_text = "WARNING"
        elif (exit_status == 2):
            state_text = "CRITICAL"
        else:
            state_text = "UNKNOWN"

        output=f"SHELLY {state_text}: Device ({devicename}) SWITCH_{shelly_switch} is {powerstatus}, currently using {apower} Watt"
        perfdata="|power=%i total_power=%.3f powerstatus=%i" % (apower, aenergy_total,  1 if powerstatus else 0)

    else:
        devicename = data['src']
        # apower: number, last measured instantaneous power (in Watts) delivered to the attached load
        apower = data['result']['apower']
        # current: number, last measured current in Amperes
        current = data['result']['current']
        # aenergy total: number, total energy consumed in Watt-hours
        aenergy_total = data['result']['aenergy']['total']
        # aenergy by minute: array of numbers, energy consumption by minute (in Milliwatt-hours) for the last three minutes (the lower the index of the element in the array, the closer to the current moment the minute)
        aenergy_by_minute = data['result']['aenergy']['by_minute']
        temp_celsius = data['result']['temperature']['tC']
        powerstatus = data['result']['output']

        # If actual powerstatus is not the expected powerstatus then raise warning
        if expect_powerstatus != None:
            if expect_powerstatus != powerstatus:
                exit_status=1

        # Set state text for monitoring ("SHELLY WARNING" etc.)
        if (exit_status == 0):
            state_text = "OK"
        elif (exit_status == 1):
            state_text = "WARNING"
        elif (exit_status == 2):
            state_text = "CRITICAL"
        else:
            state_text = "UNKNOWN"

        output="SHELLY %s: Device (%s) SWITCH_%i is %s, currently using %i Watt / %i Amp" % (state_text, devicename, shelly_switch, "on" if powerstatus else "off", apower, current)
        perfdata="|power=%i current=%i total_power=%.3f temp=%.1f powerstatus=%i" % (apower, current, aenergy_total, temp_celsius, 1 if powerstatus else 0)
    systemexit(exit_status, output, perfdata)

else:
    systemexit(3, "SHELLY UNKNOWN: Unknown check type. Try --help.", "")
