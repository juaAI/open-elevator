'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from starlette.responses import StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from openelevator import OpenElevator
from sys import argv
import uvicorn

from api import schemas, util

app = FastAPI(
    title="Open Elevator API",
    description='This API gives access to elevation above sea level in 30 meter resolution.\
        More information about the dataset: <a href="https://registry.opendata.aws/terrain-tiles/">S3 Elevation Repo</a>',
    version=1.0
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

elevator = OpenElevator(initialized=True, cache=True)

# index entrypoint
@app.get("/")
def index():
    ''' Redirects to the docs
    '''
    resp = RedirectResponse(url='/docs')
    return resp

@app.get("/v1/data")
def get_elevation_single(
    lat:float,
    lon:float,
    interpolation:str="cubic"
    ):
    '''
    Returns elevation for given lat, lon, interpolation method
    Interpolation methods available: none, linear, nearest, cubic

    Not found value: -32768

    More information: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html
    '''
    if interpolation in elevator.interpolation_methods:
        check = util.check_lat_lon(lat, lon)
        if check == True:
            return {"elevation":elevator.get_elevation(lat, lon, interpolation=interpolation)}
        else:   
            return check    
    else:
        return {"error":f"interpolation must be in {elevator.interpolation_methods}"}

@app.post("/v1/data")
def get_elevation_list(locations:schemas.Locations):
    '''
    Returns elevations for given location array of [[lon,lat], [lon,lat], ...] and interpolation method
    Max 100 locations per request

    Interpolation methods available: none, linear, nearest, cubic

    More information: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html
    '''

    interpolation = locations.interpolation
    locations = locations.locations

    if interpolation in elevator.interpolation_methods:
        if len(locations) > 100:
            return {"error":"max 100 locations allowed per request"}
        else:
            all_elevations = []
            for i in locations:
                if len(i) != 2:
                    return {"error":f"'{i}': every location array must contain exactly 2 values"}
                else:                    
                    check = util.check_lat_lon(i[1],i[0])
                    if check == True:
                        all_elevations.append(
                            elevator.get_elevation(
                                i[1], 
                                i[0], 
                                interpolation=interpolation
                                )
                            )
                    else:   
                        return check
            return {"elevations":all_elevations}
    else:
        return {"error":f"interpolation must be in {elevator.interpolation_methods}"}

@app.get("/v1/viz")
def get_elevation_viz(
    lat:float,
    lon:float,
    colormap:str="terrain"
    ):
    '''
    Returns elevation png image of area arround given location

    Available colormaps:
            "terrain",
            "gist_earth",
            "ocean",
            "jet",
            "rainbow",
            "viridis",
            "cividis",
            "plasma",
            "inferno"
    '''
    check = util.check_lat_lon(lat, lon)
    if check == True:
        if colormap in elevator.colormaps:
            image = elevator.plot_elevation(lat, lon, colormap=colormap)
            return StreamingResponse(image, media_type="image/png")
        else:
            return {"error":f"colormap must be in {elevator.colormaps}"}
    else:
        return check

# allow cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uvicorn.run(app, host="0.0.0.0", port=8080)