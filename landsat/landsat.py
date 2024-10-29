import ee
import datetime
import geemap.foliumap as geemap
import subprocess
import json
import time
import sys
import os

# Initialize Google Earth Engine with the provided service account credentials
service_account = 'copenricus-vs-landsat-workshop@ee-simoneldavid.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'ee-simoneldavid-84d91d8a227c.json')
ee.Initialize(credentials)

# Extract city, time range, and address type from command-line inputs
if len(sys.argv) != 7:
    print("Usage: python3 gee_export.py <city_name> <start_year> <end_year> <start_month> <end_month> <address_type>")
    sys.exit(1)

city_name = sys.argv[1]
start_year = int(sys.argv[2])
end_year = int(sys.argv[3])
start_month = int(sys.argv[4])
end_month = int(sys.argv[5])
address_type = sys.argv[6]

# Compute the range of days within the start and end years for filtering images
start_day_of_year = (datetime.datetime(start_year, start_month, 1) - datetime.datetime(start_year, 1, 1)).days + 1
end_day_of_year = (datetime.datetime(end_year, end_month, 1) - datetime.datetime(end_year, 1, 1)).days + 1

# Define a function to fetch the geographic bounding box for the specified city from OpenStreetMap
def get_bounding_boxes(city_name, address_type):
    url = f"https://nominatim.openstreetmap.org/search.php?q={city_name}&polygon_geojson=1&format=json"
    for attempt in range(5):
        try:
            result = subprocess.run(["curl", "-s", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print(f"Error running curl command: {result.stderr}. Retrying...")
                time.sleep(2 ** attempt)
                continue
            data = json.loads(result.stdout)
            bounding_box = None
            for city_data in data:
                if city_data.get('type') == 'administrative' and city_data.get('addresstype') == address_type:
                    bounding_box = city_data['geojson'].get('coordinates')
                    break
            if bounding_box:
                return bounding_box[0][0] if city_data['geojson']['type'] == 'MultiPolygon' else bounding_box[0]
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}. Retrying...")
            time.sleep(2 ** attempt)
    print("Failed to retrieve bounding box.")
    return None

# Set area of interest (AOI) for analysis using the obtained bounding box
aoi = get_bounding_boxes(city_name, address_type)
if aoi is None:
    sys.exit("No bounding box found for the specified city and address type.")
aoi_geom = ee.Geometry.Polygon(aoi)

# Initialize the map centered on the specified AOI
Map = geemap.Map()
Map.centerObject(aoi_geom, zoom=10)

# Define time range filters for the desired months and years
DATE_RANGE = ee.Filter.dayOfYear(start_day_of_year, end_day_of_year)
YEAR_RANGE = ee.Filter.calendarRange(start_year, end_year, 'year')

# Set the basemap type to satellite imagery
Map.setOptions('SATELLITE')

# Select and filter Landsat 8 thermal bands (ST_B10 for Surface Temperature) within the AOI and time range
L8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
      .select(['ST_B10', 'QA_PIXEL'])
      .filterBounds(aoi_geom)
      .filter(DATE_RANGE)
      .filter(YEAR_RANGE)
      .map(lambda img: img.updateMask(img.select('QA_PIXEL').bitwiseAnd(1 << 3).Or(img.select('QA_PIXEL').bitwiseAnd(1 << 4)).Not())))

# Filter image collection by cloud cover (<20%) for optimal data quality
filtered_L8 = L8.filter(ee.Filter.lt('CLOUD_COVER', 20))

# Convert Landsat Surface Temperature data from raw sensor values to Celsius
def applyScaleFactors(image):
    thermalBands = image.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    return image.addBands(thermalBands, None, True)

landsatST = filtered_L8.map(applyScaleFactors)

# Compute the mean Surface Temperature (ST) for each pixel across all images in the filtered collection
mean_LandsatST = landsatST.mean()

# Crop the ST imagery to the bounds of the AOI
clip_mean_ST = mean_LandsatST.clip(aoi_geom)

# Calculate dynamic threshold values for heat island detection based on the mean and standard deviation
mean_temp = clip_mean_ST.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=aoi_geom,
    scale=30,
    maxPixels=1e9
).get('ST_B10').getInfo()

std_dev_temp = clip_mean_ST.reduceRegion(
    reducer=ee.Reducer.stdDev(),
    geometry=aoi_geom,
    scale=30,
    maxPixels=1e9
).get('ST_B10').getInfo()

heat_island_threshold_temp = mean_temp + std_dev_temp

# Function to detect heat islands by identifying regions with temperatures above the threshold
def detect_heat_island_contours(image, threshold_temp):
    mask = image.gt(threshold_temp).selfMask()
    connected = mask.focal_max(kernel=ee.Kernel.circle(radius=7), iterations=8)
    vectors = connected.reduceToVectors(
        geometryType='polygon',
        reducer=ee.Reducer.countEvery(),
        scale=30,
        maxPixels=1e8,
        geometry=aoi_geom
    )
    return vectors

# Apply heat island detection to the clipped Surface Temperature image
heat_island_contours = detect_heat_island_contours(clip_mean_ST.select('ST_B10'), heat_island_threshold_temp)

# Display the Surface Temperature layer and detected heat island contours on the map
Map.addLayer(clip_mean_ST, {
    'bands': 'ST_B10',
    'min': mean_temp - std_dev_temp,
    'max': mean_temp + 2 * std_dev_temp,
    'palette': ['blue', 'white', 'red']
}, "ST", True)

Map.addLayer(heat_island_contours, {'color': 'yellow'}, "Heat Island", True)

# Save the map as an HTML file in the specified directory
download_dir = 'landsat_export'
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

html_file = os.path.join(download_dir, f'{city_name}_{start_year}_{end_year}_{start_month}_{end_month}_{address_type}.html')
Map.to_html(filename=html_file, title='Heat Island Map', width='100%', height='700px')
print(f"HTML file written successfully to {html_file}")
