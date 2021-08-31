'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''
import os
import yaml

def check_lat_lon(lat:float,lon:float):
    '''
    Checks if given lat, lon are formatted right

    In this API, lats between -90 and 90 are beingt used, 
    lons between -180 and 180 are being used (european).

    Args:
        lat:float >> latitude, number between -90 and 90
        lon:float >> longitude, number between -180 and 180

    Returns:
        True:bool  >> book True, if check successfull
        error:dict >> object with error code, if check failed
    '''
    if not ((90>=lat>=-90) or (180>=lon>=-180)):
        return {"error":"lat must be between -90 and 90, lon must be between -180 and 180"}
    else:
        return True

# load config and provide global vars that 
# are imported by server and routes
dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(dir_path,"config.yml")) as yaml_file:
    config_content = dict(yaml.load(
                        yaml_file, 
                        Loader=yaml.FullLoader
                        ))

server_host = config_content["server"]["host"]
server_port = config_content["server"]["port"]
rate_limit  = config_content["server"]["ratelimit"]
rate_reset  = config_content["server"]["ratereset"]
viz_active  = config_content["server"]["vizactive"]

if config_content["ssl"]["ssl"] == True:
    ssl_key  = config_content["ssl"]["certkey"]
    ssl_cert = config_content["ssl"]["cert"]
else:
    ssl_key  = None
    ssl_cert = None