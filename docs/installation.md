# Installation

You can set up the API on your own for free. To do so, you need at least
1.6 TB of disk space.

## Requirements
- Linux
- Anaconda
- Redis
- \>1.6 TB disk space

## Setup
```shell
$ conda env create --file /env/environment.yml
$ conda activate open-elevator
$ python openelevator.py
```
This will start downloading and preprocessing the neccessary [DEM files from AWS](https://registry.opendata.aws/terrain-tiles/). This step may take several hours up to a day depending
on the machine used.

## Configuration
Update the configuration file (/openelevator/api/config.yml) to your specific needs. You can
activate SSL encryption by passing a SSL cert and key file. The `rate-limit` specifies the **amount of allowed API calls** in a specific amount of time. The `rate-reset` specifies this amount of time **in seconds**. The `viz-active` enables the *plotting route*, which is deactivated at the public API.

```yml
ssl:
    ssl: True
    cert: /path/to/cert.pem
    cert-key: /path/to/privkey.pem

server:
    host: 0.0.0.0
    port: 8080
    rate-limit: 100
    rate-reset: 60
    viz-active: False
```

## Start the API
The API is serverd via [Uvicorn](https://www.uvicorn.org/). If you want to start
the API in background, you can use `nohup python server.py`.

```shell
$ python server.py

INFO:     Started server process [696905]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on https://0.0.0.0:8080 (Press CTRL+C to quit)
```