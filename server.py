'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

import aioredis
import uvicorn

from starlette.responses import RedirectResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter

from api.routes import elevation
from util import server_host, server_port, ssl_cert, ssl_key

# init app
app = FastAPI(
    title="Open Elevator API",
    description='This API gives access to elevation above sea level in 30 meter resolution.\
        More information about the dataset: <a href="https://registry.opendata.aws/terrain-tiles/">S3 Elevation Repo</a>',
    version=1.0
    )
app.add_middleware(GZipMiddleware, minimum_size=1000)

# init cache
@app.on_event("startup")
async def startup():
    '''
    Initializes redis for caching of API requests
    and rate limiting
    '''
    redis = await aioredis.from_url(
        "redis://localhost", 
        encoding="iso-8859-1", 
        decode_responses=True
        )
    FastAPICache.init(
        RedisBackend(redis), 
        prefix="fastapi-cache"
        )
    await FastAPILimiter.init(redis)

# index entrypoint
@app.get("/")
async def index():
    ''' Redirects to the docs
    '''
    resp = RedirectResponse(url='/docs')
    return resp

# mount routes
app.include_router(
    elevation.router,
    prefix="/v1/elevation",
    tags=["Elevation"],
    responses={404: {"description": "Not found"}}
    )

# allow cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host=server_host, 
        port=server_port,
        ssl_keyfile=ssl_key,
        ssl_certfile=ssl_cert
        )