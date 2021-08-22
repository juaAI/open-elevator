'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

import os
import sys
import json
import requests
import numpy as np
import time
from multiprocessing import Pool

def make_single_requests(coords):
    lat,lon = coords[1], coords[0]
    url = f"http://code.predly.com:8080/v1/data?lat={lat}&lon={lon}&interpolation=cubic"
    resp = requests.get(url)
    if resp.status_code == 200:
        sys.stderr.write("OK\n")
    else:
        sys.stderr.write("ERROR\n")

def make_big_request(coords):
    url = f"http://code.predly.com:8080/v1/data"
    data = {
        "locations": coords,
        "interpolation": "none"
        }
    resp = requests.post(url,data=json.dumps(data))
    if resp.status_code == 200:
        sys.stderr.write("OK\n")
        print(resp.text)
    else:
        sys.stderr.write("ERROR\n")

def generate_coords():
    lats = list(np.arange(49,50,0.0001))
    lons = list(np.arange(7,8,0.0001))
    coords = []
    for i in range(len(lats)):
        coords.append([lons[i],lats[i]])
    return coords

def make_load_test_single():
    processes = os.cpu_count()   
    coords = generate_coords()
    p = Pool(processes=processes)

    start = time.time()
    p.map(make_single_requests, coords)
    print("Took", (time.time() - start)*1000, "milliseconds for", len(coords), "requests")
    p.close()

def make_load_test_multi():

    coords = generate_coords()
    start = time.time()
    make_big_request(coords)
    print("Took", (time.time() - start)*1000, "milliseconds")


make_load_test_single()