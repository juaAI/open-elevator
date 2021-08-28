'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

from fastapi import APIRouter, Depends
from fastapi_cache.decorator import cache
from fastapi_limiter.depends import RateLimiter

from starlette.responses import StreamingResponse, Response
from starlette.requests import Request

from openelevator import OpenElevator
from api import schemas, util

router = APIRouter()
elevator = OpenElevator(initialized=True, cache=True)

@router.get("/json", response_model=schemas.SingleElevationResponse,
                     dependencies=[Depends(RateLimiter(
                        times=util.rate_limit, 
                        seconds=util.rate_reset,
                        ))])
@cache()
async def get_elevation_single(
    request: Request,
    response: Response,
    lat:float,
    lon:float,
    interpolation:str="cubic"
    ):
    '''
    Returns elevation for given lat, lon, interpolation method
    Interpolation methods available: none, linear, nearest, cubic

    Not found value: -32768

    More information: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html
    
    Args:
        lat:float  >> Latitude (y axis), number between -90 and 90
        lon:float  >> Longitude(x axis), number between -180 and 180
        interpolation:str >> Interpolation method (none, linear, nearest, cubic)

    Returns:
        response:object >> json object with elevation data
    '''
    if interpolation not in elevator.INTERPOLATION_METHODS:
        return {"error":f"interpolation must be in {elevator.INTERPOLATION_METHODS}"}
    else:    
        check = util.check_lat_lon(lat, lon)
        if check == True:
            resp = {
                    "elevation":await elevator.get_elevation(
                                        lat, 
                                        lon, 
                                        interpolation=interpolation
                                        ),
                    "location":{
                        "lat":lat, 
                        "lon":lon
                        }
                    }
            return resp
        else:   
            return check    

@router.post("/json", response_model=schemas.MultiElevationResponse,
                      dependencies=[Depends(RateLimiter(
                        times=util.rate_limit, 
                        seconds=util.rate_reset
                        ))])
async def get_elevation_list(
    locations:schemas.Locations,
    request: Request,
    response: Response
    ):
    '''
    Returns elevations for given location array of [[lon,lat], [lon,lat], ...] and interpolation method
    Max 100 locations per request

    Interpolation methods available: none, linear, nearest, cubic

    More information: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html
    
    Post Args:
        locations:2D array/list of
            lat:float  >> Latitude (y axis), number between -90 and 90
            lon:float  >> Longitude(x axis), number between -180 and 180
        interpolation:str >> Interpolation method (none, linear, nearest, cubic)

    Returns:
        response:object >> json object with elevation data
    
    '''

    interpolation = locations.interpolation
    locations = locations.locations
    
    if interpolation not in elevator.INTERPOLATION_METHODS:
        return {"error":f"interpolation must be in {elevator.INTERPOLATION_METHODS}"}
    else:
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
                        all_elevations.append({
                            "elevation": await elevator.get_elevation(
                                i[1], 
                                i[0], 
                                interpolation=interpolation
                                ),
                            "location":{
                                "lat":i[0],
                                "lon":i[1]
                                }
                            }
                        )
                    else:   
                        return check
            
            resp = {"results":all_elevations}
            return resp

if util.viz_active:
    @router.get("/viz")
    async def get_elevation_viz(
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

        Args:
            lat:float  >> Latitude (y axis), number between -90 and 90
            lon:float  >> Longitude(x axis), number between -180 and 180
            interpolation:str >> Interpolation method (none, linear, nearest, cubic)

        Returns:
            response:image/png >> streamed response
        
        '''
        check = util.check_lat_lon(lat, lon)
        if check == True:
            if colormap in elevator.COLORMAPS:
                image = elevator.plot_elevation(lat, lon, colormap=colormap)
                return StreamingResponse(image, media_type="image/png")
            else:
                return {"error":f"colormap must be in {elevator.COLORMAPS}"}
        else:
            return check