<div style="text-align:center">
    <h1 >Open Elevator API</h1>
    <img src="assets/earth.png"></img>
    <p style="text-align:center">
        <strong>Open Elevator API</strong> is an easy to use elevation service with up to 3m resolution.<br> <a href="#selfservice">Run your own</a> or use our free <a href="#free-api">public API</a>.
    </p>
</div>
---

### API example

``` shell
$ curl http://localhost:8080/v1/elevation/json?lat=50.078217&lon=8.239761
```

``` json
{
  "elevation": 118.73242074762783,
  "location": {
    "lat": 50.078217,
    "lon": 8.239761
  }
}
```

### Package example

```python
from PIL import Image
from openelevator import OpenElevator

elevator = OpenElevator()

# visualize a specific location
img = elevator.plot_elevation(lat=50.078217, lon=8.239761)
with Image.open(img) as im:
    im.show()
```
![Vizalization](assets/viz.png)