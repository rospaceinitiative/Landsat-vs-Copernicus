import os
import numpy as np
import xarray as xr
from shapely.geometry import box

# Directory containing downloaded Copernicus LST NetCDF files
DOWNLOAD_DIR = "copernicus_data"
# Output file name for the interactive map displaying heat islands
HTML_MAP_FILE = "copernicus_city_heatmap.html"

# Hardcoded bounding box coordinates for Cluj-Napoca
min_lon, min_lat, max_lon, max_lat = 23.53618, 46.73862, 23.63058, 46.80108
aoi = box(min_lon, min_lat, max_lon, max_lat)
lat_min, lon_min, lat_max, lon_max = aoi.bounds

# List to accumulate all temperature datasets from files
all_temperature_data = []

# Load temperature data from each NetCDF file in the directory, converting from Kelvin to Celsius
for root, _, files in os.walk(DOWNLOAD_DIR):
    for file in files:
        if file.endswith("LST_in.nc"):
            file_path = os.path.join(root, file)
            with xr.open_dataset(file_path) as ds:
                if 'LST' in ds.variables:
                    temp_data = ds['LST'].values - 273.15
                    all_temperature_data.append(temp_data)
                else:
                    print(f"'LST' variable not found in {file}")

if not all_temperature_data:
    raise ValueError("No temperature data found for the specified files.")

# Define spatial steps based on grid resolution of the temperature data
rows, cols = all_temperature_data[0].shape
lat_step = (lat_max - lat_min) / rows
lon_step = (lon_max - lon_min) / cols

# Sample temperature values and corresponding lat/lon coordinates for validation
sample_points = []
print("Sample coordinates and temperatures from data:")
for i in range(0, rows, rows // 10):
    for j in range(0, cols, cols // 10):
        lat = lat_max - i * lat_step
        lon = min_lon + j * lon_step
        temp = all_temperature_data[0][i, j]
        sample_points.append((lat, lon, temp))
        print(f"Latitude: {lat}, Longitude: {lon}, Temperature: {temp}")

# Display sampled points for verification of temperature and coordinate data accuracy
print("Sample Points Collected for Verification:", sample_points)