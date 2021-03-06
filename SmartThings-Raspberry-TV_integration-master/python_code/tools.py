import requests
import psutil
import os
import nmap
from netifaces import interfaces, ifaddresses, AF_INET
import ipaddress
import json
import time
from urlparse import urlparse
import xml.etree.ElementTree as ET
import ssdp
from conf import configuration
import re


def get_send_rpi_stats():
    cpu = psutil.cpu_percent()
    temp = float(os.popen('vcgencmd measure_temp').readline().replace("temp=", "").replace("'C\n", ""))
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    evt = {
        "type": "rpi_status",
        "body": {
            "temperature": temp,
            "cpuPercentage": cpu,
            "memory": memory.percent,
            "diskUsage": disk.percent,
            #"hubInfo": "online"
        }
    }
    return evt


def send_event_to_st(event, st_ip):
    i = 0
    resend_flag = True
    #print "event: ", event

    while resend_flag and i < 5:
        resend_flag = __send_evt__(event, st_ip)
        if resend_flag:
            i += 1
            print "{} send".format(i)


def __send_evt__(event, st_ip):
    tx_error = False
    url = "http://{}:39500".format(st_ip)
    headers = {
        'content-type': "application/json",
    }
    try:
        r = requests.post(url, data=event, headers=headers)
    except requests.exceptions.RequestException as e:
        print e
        tx_error = True
    else:
        if r.status_code != 202:
            print "Post Error Code: {}, Post Error Message: {}".format(r.status_code, r.text)
            tx_error = True
    return tx_error


def check_status(ip):
    return json.dumps({'device': ip, 'status': 'off'}) \
        if os.system("{} {} {}".format("ping -W 1 -w 3 -c 3 -q", ip, "> /dev/null 2>&1")) \
        else json.dumps({'device': ip, 'status': 'on'})


def get_smartthing_ip():
    st_ip = __get_st_ip__()
    st_ip_conf = configuration["ST_IP"]
    ip_match = None
    
    if st_ip_conf:
        ip_match = re.match(r'^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$', st_ip_conf)
        
    if not st_ip and not ip_match:
        print "Smartthings Hub is DOWN"
        exit(1)

    if st_ip and st_ip_conf != st_ip:
        configuration["ST_IP"] = st_ip
        path = os.path.dirname(os.path.realpath(__file__))
        with open('{}/conf.py'.format(path), 'w') as f:
            f.write("configuration = {}".format(configuration))
        time.sleep(1)


def __get_st_ip__():
    ST_IP = None
    #get my own IP address, mask and network
    for ifaceName in interfaces():
        if ifaceName != 'lo':
            interface_info = ifaddresses(ifaceName).setdefault(AF_INET)
            if interface_info:
                ip = interface_info[0]
        
    
    interface = ipaddress.IPv4Interface(u"{}/{}".format(ip.get('addr'), ip.get('netmask')))
    
    nm = nmap.PortScanner()
    nm.scan(hosts=str(interface.network), arguments='-p39500 --open')
    if nm.all_hosts():
        ST_IP = nm.all_hosts()[0]
    return ST_IP


def get_tv_ip():
    ip_match = None
    tv_ip = None
   
    tv_ip_conf = configuration["TV_IP"]
    
    if tv_ip_conf:
        ip_match = re.match(r'^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$', tv_ip_conf)
        
    tv_search_query = "ssdp:all"
    for device in ssdp.discover(tv_search_query):
        location = device.location
        device = ET.fromstring(requests.get(location).text)[1]

        if len(device) >= 10:
            if device[4].text == 'LG Digital Media Renderer TV' and \
                            device[7].text == 'LG Electronics' and \
                            device[10].text == 'LG TV':
                tv_ip = urlparse(location).netloc.split(":")[0]
                break

    if not tv_ip and not ip_match:
        print "TV is OFF, please turn on your LG TV"
        exit(1)

    if tv_ip and configuration["TV_IP"] != tv_ip:
        configuration["TV_IP"] = tv_ip
        path = os.path.dirname(os.path.realpath(__file__))
        with open('{}/conf.py'.format(path), 'w') as f:
            f.write("configuration = {}".format(configuration))
        time.sleep(1)
