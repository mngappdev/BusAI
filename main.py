from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bus_engine import BusSmartEngine

app = FastAPI()

# 允许跨域，方便本地 index.html 调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = BusSmartEngine()
BASE_DIR = Path(__file__).resolve().parent

# A kiosk browser stays open for days. Without this the browser falls back to
# heuristic caching and can keep running an old bundle long after a deploy —
# that is how a shipped fix for the walk-leg duration never reached the screen.
# "no-cache" means "revalidate before reusing", not "never store": the ETag
# turns each check into a cheap 304.
REVALIDATE = "no-cache, must-revalidate"


class RevalidatedStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = REVALIDATE
        return response


app.mount("/static", RevalidatedStaticFiles(directory=BASE_DIR / "static"), name="static")

class TripRequest(BaseModel):
    s_lat: float
    s_lon: float
    e_lat: float
    e_lon: float


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "index.html", headers={"Cache-Control": REVALIDATE})


@app.get("/api/v1/nearby-stops")
async def nearby_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(600, ge=50, le=3000),
    limit: int = Query(8, ge=1, le=20),
):
    return {
        "type": "nearby_stops",
        "location": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "stops": engine.nearby_stops(lat, lon, radius_m=radius_m, limit=limit),
    }


@app.get("/api/v1/nearby-places")
async def nearby_places(
    lat: float = Query(...),
    lon: float = Query(...),
):
    return engine.nearby_places(lat, lon)


@app.get("/api/v1/routes/{service_no}")
async def route_summary(service_no: str):
    summary = engine.route_summary(service_no)
    if not summary:
        raise HTTPException(status_code=404, detail="Service not found")
    return summary


@app.get("/api/v1/search-stops")
async def search_stops(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=20)):
    keyword = q.strip().lower()
    matches = []
    for stop in engine.stops:
        haystack = f"{stop.get('BusStopCode','')} {stop.get('Description','')} {stop.get('RoadName','')}".lower()
        if keyword in haystack:
            matches.append({
                "code": stop.get("BusStopCode"),
                "name": stop.get("Description", ""),
                "road": stop.get("RoadName", ""),
                "latitude": stop.get("Latitude"),
                "longitude": stop.get("Longitude"),
            })
    return {"query": q, "results": matches[:limit]}


@app.get("/api/v1/stops/{stop_code}/arrivals")
async def stop_arrivals(stop_code: str, service_no: str | None = None):
    stop = engine.stop_map.get(stop_code)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    services = []
    stop_routes = engine.stop_to_routes.get(stop_code, [])
    if service_no:
        stop_routes = [r for r in stop_routes if r["ServiceNo"] == service_no]

    seen = set()
    for route in stop_routes:
        svc = route["ServiceNo"]
        if svc in seen:
            continue
        seen.add(svc)
        services.append({
            "service": svc,
            "operator": route.get("Operator"),
            "arrival": engine.get_realtime_v3(stop_code, svc),
        })

    services.sort(key=lambda item: (0 if item["arrival"] else 1, item["arrival"]["minutes"] if item["arrival"] else 999))
    return {
        "stop": {
            "code": stop["BusStopCode"],
            "name": stop.get("Description", ""),
            "road": stop.get("RoadName", ""),
            "latitude": stop.get("Latitude"),
            "longitude": stop.get("Longitude"),
        },
        "services": services[:6],
    }

@app.post("/api/v1/plan")
async def plan(request: TripRequest):
    return engine.plan_trip(request.s_lat, request.s_lon, request.e_lat, request.e_lon)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/news/traffic_incidents")
async def traffic_incidents():
    return {"value": engine.get_traffic_incidents()}

@app.get("/api/v1/news/train_alerts")
async def train_alerts():
    return {"value": engine.get_train_service_alerts()}

@app.get("/api/v1/news/facilities_maintenance")
async def facilities_maintenance():
    return {"value": engine.get_facilities_maintenance()}

@app.get("/api/v1/news/air_temperature")
async def air_temperature(lat: float = Query(...), lon: float = Query(...)):
    """
    Return real-time air temperature at the nearest station for the given lat/lon.
    """
    temp = engine.get_air_temperature(lat, lon)
    if temp is None:
        return {"value": []}
    return {"value": [{"value": temp}]}

@app.get("/api/v1/news/2hr_forecast")
async def two_hr_forecast(lat: float = Query(...), lon: float = Query(...)):
    """
    Return 2-hour weather forecast for Singapore regions.
    """
    forecasts = engine.get_two_hr_forecast(lat, lon)
    return {"value": forecasts}