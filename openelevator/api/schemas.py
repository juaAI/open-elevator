'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

from pydantic import BaseModel
from typing import Optional, List

class Locations(BaseModel):
    locations: List[List[float]] = [[12.423,52.1333],[8.22, 53.232]]
    interpolation: str = "linear"

class SingleElevationResponse(BaseModel):
    elevation: float = 112.435
    location: dict = {"lat":52.44, "lon":8.54}

class MultiElevationResponse(BaseModel):
    results: list = [{"elevation":112.435, "location":{"lat":52.44, "lon":8.54}},
                     {"elevation":112.435, "location":{"lat":52.44, "lon":8.54}}]