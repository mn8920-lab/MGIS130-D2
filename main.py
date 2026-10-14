import time
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Weather Dashboard Backend")

# Serve visual frontend assets from /static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-Memory Cache dictionary: { cache_key: (timestamp, payload) }
CACHE = {}
CACHE_TTL = 600  # 10 minutes cache expiration in seconds


@app.get("/")
def read_root():
    return FileResponse("static/index.html")


@app.get("/api/weather")
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """Fetches weather data from Open-Meteo API with 10-minute caching."""
    cache_key = f"{round(lat, 2)}:{round(lon, 2)}"
    current_time = time.time()

    # Check Data Layer Cache
    if cache_key in CACHE:
        timestamp, cached_data = CACHE[cache_key]
        if current_time - timestamp < CACHE_TTL:
            return {"source": "cache", "data": cached_data}

    # Fetch fresh data from Open-Meteo API
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
        ],
        "hourly": ["temperature_2m", "precipitation_probability"],
        "daily": ["temperature_2m_max", "temperature_2m_min", "weather_code"],
        "timezone": "auto",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            raw_data = response.json()
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"Weather provider error: {str(e)}"
            )

    # Save to local memory cache
    CACHE[cache_key] = (current_time, raw_data)

    return {"source": "live_api", "data": raw_data}
