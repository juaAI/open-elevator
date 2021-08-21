'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

from pydantic import BaseModel
from typing import Optional

class Locations(BaseModel):
    locations: list
    interpolation: str = "linear"