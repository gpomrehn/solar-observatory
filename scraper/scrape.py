#!/usr/bin/env python -f

import os
import time
import json
import requests
import threading
from requests.auth import HTTPDigestAuth
from prometheus_client import start_http_server, Gauge


host = os.getenv('ENVOY_HOST')
password = os.getenv('ENVOY_PASS')

user = 'installer'
auth = HTTPDigestAuth(user, password)
marker = b'data: '


serials = {
    121726069304: 'west',
    121726070309: 'east',
    121726070418: 'east',
    121726070273: 'west',
    121726068492: 'south',
    121726070030: 'south',
    121726061656: 'south',
    121726069153: 'south',
    121726068232: 'south',
    121726068475: 'south',
    121727000382: 'south',
    121726070423: 'west',
    121726070470: 'east',
    121727000409: 'south',
    121726070319: 'east',
    121726070375: 'west',
    121727000255: 'south',
    121726070274: 'west',
    121726070045: 'east',
    121726069685: 'south',
    121726070431: 'south',
    121727000392: 'south',
    121726070213: 'south',
    121726069957: 'west',
    121726069138: 'south',
}


stream_gauges = {
    'p': Gauge('meter_active_power_watts', 'Active Power', ['type', 'phase']),
    'q': Gauge('meter_reactive_power_watts', 'Reactive Power', ['type', 'phase']),
    's': Gauge('meter_apparent_power_watts', 'Apparent Power', ['type', 'phase']),
    'v': Gauge('meter_voltage_volts', 'Voltage', ['type', 'phase']),
    'i': Gauge('meter_current_amps', 'Current', ['type', 'phase']),
    'f': Gauge('meter_frequency_hertz', 'Frequency', ['type', 'phase']),
    'pf': Gauge('meter_power_factor_ratio', 'Power Factor', ['type', 'phase']),
}

production_gauges = {
    'activeCount': Gauge('production_active_count', 'Active Count', ['type']),
    'wNow': Gauge('power_now_watts', 'Active Count', ['type']),
    'whToday': Gauge('production_today_watthours', 'Total production today', ['type']),
    'whLastSevenDays': Gauge('production_7days_watthours', 'Total production last seven days', ['type']),
    'whLifetime': Gauge('production_lifetime_watthours', 'Total production lifetime', ['type']),
}

consumption_gauges = {
    'wNow': Gauge('consumption_now_watts', 'Active Count', ['type']),
    'whToday': Gauge('consumption_today_watthours', 'Total consumption today', ['type']),
    'whLastSevenDays': Gauge('consumption_7days_watthours', 'Total consumption last seven days', ['type']),
    'whLifetime': Gauge('consumption_lifetime_watthours', 'Total consumption lifetime', ['type']),
}

inverter_gauges = {
    'last': Gauge('inverter_last_report_watts', 'Last reported watts', ['serial', 'location']),
    'max': Gauge('inverter_max_report_watts', 'Max reported watts', ['serial', 'location']),
}


def scrape_stream():
    while True:
        try:
            url = 'http://%s/stream/meter' % host
            stream = requests.get(url, auth=auth, stream=True, timeout=5)
            for line in stream.iter_lines():
                if line.startswith(marker):
                    data = json.loads(line.replace(marker, b''))
                    print(data)
                    for meter_type in ['production', 'net-consumption', 'total-consumption']:
                        for phase in ['ph-a', 'ph-b']:
                            for key, value in data.get(meter_type, {}).get(phase, {}).items():
                                if key in stream_gauges:
                                    stream_gauges[key].labels(type=meter_type, phase=phase).set(value)
        except requests.exceptions.RequestException as e:
            print('Exception fetching stream data: %s' % e)
            time.sleep(5)


def scrape_production_json():
    url = 'http://%s/production.json' % host
    data = requests.get(url).json()
    production = data['production']
    print(production)
    for each in production:
        mtype = each['type']
        for key in ['activeCount', 'wNow', 'whLifetime', 'whToday', 'whLastSevenDays']:
            value = each.get(key)
            if value is not None:
                production_gauges[key].labels(type=mtype).set(value)
    consumption = data['consumption']
    print(consumption)
    for each in consumption:
        mtype = each['measurementType']
        for key in ['wNow', 'whLifetime', 'whToday', 'whLastSevenDays']:
            value = each.get(key)
            if value is not None:
                consumption_gauges[key].labels(type=mtype).set(value)



def scrape_inverters():
    url = 'http://%s/api/v1/production/inverters' % host
    data = requests.get(url, auth=auth).json()
    print(data)
    for inverter in data:
        serial = int(inverter['serialNumber'])
        location = serials.get(serial, 'unknown')
        inverter_gauges['last'].labels(serial=serial, location=location).set(inverter['lastReportWatts'])
        inverter_gauges['max'].labels(serial=serial, location=location).set(inverter['maxReportWatts'])


def main():
    start_http_server(8000)
    stream_thread = threading.Thread(target=scrape_stream)
    stream_thread.setDaemon(True)
    stream_thread.start()
    while True:
        try:
            scrape_production_json()
            scrape_inverters()
        except Exception as e:
            print('Exception fetching scrape data: %s' % e)
        time.sleep(60)


if __name__ == '__main__':
    main()
