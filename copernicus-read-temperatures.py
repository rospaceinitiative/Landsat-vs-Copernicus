import os
import sys
import numpy as np
import xarray as xr
import folium
from folium.plugins import HeatMap
from shapely.geometry import box, Polygon
import subprocess
import json
import time
import geojson
from shapely.geometry import mapping
from shapely.ops import unary_union
from scipy.ndimage import binary_dilation

# Directory for downloaded LST files
DOWNLOAD_DIR = "downloaded_products"
# HTML output file for the interactive map
HTML_MAP_FILE = "copernicus_city_heatmap.html"

def get_bounding_box(city_name, address_type):
    url = f"https://nominatim.openstreetmap.org/search.php?q={city_name}&polygon_geojson=1&format=json"
    for attempt in range(5):
        try:
            result = subprocess.run(["curl", "-s", url], stdout=subprocess.PIPE, text=True)
            data = json.loads(result.stdout)
            for city_data in data:
                if city_data.get('type') == 'administrative' and city_data.get('addresstype') == address_type:
                    coordinates = city_data['geojson']['coordinates'][0]
                    if isinstance(coordinates[0][0], list):
                        coordinates = coordinates[0]
                    lat_min = min(coord[1] for coord in coordinates)
                    lat_max = max(coord[1] for coord in coordinates)
                    lon_min = min(coord[0] for coord in coordinates)
                    lon_max = max(coord[0] for coord in coordinates)
                    return lon_min, lat_min, lon_max, lat_max
        except Exception as e:
            print(f"Error fetching bounding box: {e}. Retrying...")
            time.sleep(2 ** attempt)
    print("Failed to retrieve bounding box.")
    return None

# Ensure arguments for city name and address type are provided
if len(sys.argv) != 3:
    print("Usage: python3 copernicus-process.py <city_name> <address_type>")
    sys.exit(1)

city_name = sys.argv[1]
address_type = sys.argv[2]

# Get bounding box for the city
bounding_box = get_bounding_box(city_name, address_type)
if not bounding_box:
    sys.exit("No bounding box found for the specified city and address type.")

min_lon, min_lat, max_lon, max_lat = bounding_box

# Define AOI using bounding box
aoi = box(min_lon, min_lat, max_lon, max_lat)
lat_min, lon_min, lat_max, lon_max = aoi.bounds

# Initialize list for all temperature data arrays
all_temperature_data = []

# Iterate over downloaded NetCDF LST files and extract temperature data
for root, _, files in os.walk(DOWNLOAD_DIR):
    for file in files:
        if file.endswith("LST_in.nc"):
            file_path = os.path.join(root, file)
            with xr.open_dataset(file_path) as ds:
                if 'LST' in ds.variables:
                    temp_data = ds['LST'].values - 273.15  # Convert to Celsius
                    all_temperature_data.append(temp_data)
                else:
                    print(f"'LST' variable not found in {file}")

# Verify if data is available
if not all_temperature_data:
    raise ValueError("No temperature data found for the specified files.")

# Calculate sample coordinates based on data shape
rows, cols = all_temperature_data[0].shape
lat_step = (lat_max - lat_min) / rows
lon_step = (lon_max - lon_min) / cols

# Extract sample coordinates and temperatures
sample_points = []
print("Sample coordinates and temperatures from data:")
for i in range(0, rows, rows // 10):  # Sample approximately 10 points along the latitude
    for j in range(0, cols, cols // 10):  # Sample approximately 10 points along the longitude
        lat = lat_max - i * lat_step  # Adjust for correct orientation
        lon = min_lon + j * lon_step
        temp = all_temperature_data[0][i, j]  # Get temperature at this point
        sample_points.append((lat, lon, temp))
        print(f"Latitude: {lat}, Longitude: {lon}, Temperature: {temp}")

# Confirm the sample_points to validate coordinates
print("Sample Points Collected for Verification:", sample_points)

# Remaining processing (dynamic thresholding, contour detection, heatmap generation, etc.) can follow here
