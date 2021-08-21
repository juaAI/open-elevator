'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

def check_lat_lon(lat,lon):
    if not ((90>=lat>=-90) or (180>=lon>=-180)):
        return {"error":"lat must be between -90 and 90, lon must be between -180 and 180"}
    else:
        return True