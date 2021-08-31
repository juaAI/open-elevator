'''
Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021
'''

import aioredis
import uvicorn
from os import environ
from sys import argv

from starlette.responses import RedirectResponse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_limiter import FastAPILimiter

from api.routes import elevation
from os import environ


# develop version without docker
dev = False
if len(argv) > 1:
    if argv[1] == "--standalone":
        dev = True

# init app
app = FastAPI(
    title="Open Elevator API",
    description='This API gives access to elevation above sea level in 30 meter resolution.\
        More information about the dataset: <a href="https://registry.opendata.aws/terrain-tiles/">S3 Elevation Repo</a>',
    version=0.1,
    docs_url="/elevation/playground"
    )
app.add_middleware(GZipMiddleware, minimum_size=1000)

# init cache
@app.on_event("startup")
async def startup():
    '''
    Initializes redis for caching of API requests
    and rate limiting
    '''

    if dev:
        redis = await aioredis.from_url(
            "redis://localhost", 
            encoding="iso-8859-1", 
            decode_responses=True
            )
    else:
        redis = await aioredis.from_url(
            "redis://redis", 
            encoding="iso-8859-1", 
            decode_responses=True
            )
    FastAPICache.init(
        RedisBackend(redis), 
        prefix="fastapi-cache"
        )
    await FastAPILimiter.init(redis)

# index entrypoint
app.mount("/elevation/docs/", StaticFiles(directory="../site", html = True), name="docs")

@app.get("/")
async def index():
    ''' Redirects to the docs
    '''
    resp = RedirectResponse(url='/elevation/docs/')
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

    if dev:
        uvicorn.run(
            app, 
            host=server_host, 
            port=server_port,
            ssl_keyfile=ssl_key,
            ssl_certfile=ssl_cert,
            log_config="log_config.yaml"
        )    
    else:
        uvicorn.run(
            app, 
            host=environ["host"], 
            port=443,
            ssl_keyfile=environ["certkey"],
            ssl_certfile=environ["cert"],
            log_config="log_config.yaml"
        )