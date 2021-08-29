# API

The API provides global elevation data access via HTTP. It's possible to either
query a single location, or up to 100 locations at once. Optionally, it's possible to
select the interpolation method used. The overall resolution depends on the location
queried [(more Information)](/elevation/docs/dataset).

The API has 1 endpoint:

> https://opendata.predly.com/v1/elevation/json

## Single location

### Request

For a single location, use a **GET** request:
```shell
$ curl https://opendata.predly.com/v1/elevation/json?lat=50.078217&lon=8.239761
```

### Parameters

    required
        lat: float
        lon: float
    optional
        interpolation: str in ["none", "linear", "cubic", "nearest]

### Response

```json
{
  "elevation": 118.73242074762783,
  "location": {
    "lat": 50.078217,
    "lon": 8.239761
  }
}
```

## Multiple locations 

To query up to 100 locations at once, use a **POST** request.

### Request

```shell
$ curl -X 'POST' \
  'https://opendata.predly.com/v1/elevation/json' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "locations": [
    [50,8],[50,9],[51,8]
  ],
  "interpolation": "linear"
}'
```

### Parameters

    required
        list of:
            [
                lon: float, 
                lat: float
            ]
    optional
        interpolation: str in ["none", "linear", "cubic", "nearest]

### Response
```json
{
  "results": [
    {
      "elevation": -32,
      "location": {
        "lat": 50,
        "lon": 8
      }
    },
    {
      "elevation": 397,
      "location": {
        "lat": 50,
        "lon": 9
      }
    },
    {
      "elevation": -3361,
      "location": {
        "lat": 51,
        "lon": 8
      }
    }
  ]
}
```