import os
import numpy as np
import xarray as xr
import folium
from folium.plugins import HeatMap
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
import geojson
from shapely.geometry import mapping

# Define paths for the downloaded Copernicus satellite LST files and output heatmap files
DOWNLOAD_DIR = "copernicus_data"
EXPORT_DIR = "copernicus_export"
HTML_MAP_BASE_NAME = "copernicus_cluj_heatmap_"

# Ensure the export directory exists
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

# Define the specific Area of Interest (AOI) for Cluj-Napoca using hardcoded bounding box coordinates
aoi = box(23.53618, 46.73862, 23.63058, 46.80108)
lon_min, lat_min, lon_max, lat_max = aoi.bounds

# Set the target resolution for temperature data resampling to enhance visualization
target_shape = (500, 500)

# Process each NetCDF file in the directory to generate a heatmap for each dataset
for root, _, files in os.walk(DOWNLOAD_DIR):
    for file in files:
        if file.endswith("LST_in.nc"):
            file_path = os.path.join(root, file)
            with xr.open_dataset(file_path) as ds:
                if 'LST' in ds.variables:
                    date = ds.attrs.get("start_time", "unknown_date")[:10]

                    # Resample the temperature data array to the specified target shape
                    temp_data = ds['LST'].values
                    temp_data_resized = np.resize(temp_data, target_shape)

                    # Calculate statistical metrics for temperature: mean, standard deviation, and threshold for heat islands
                    mean_temp = np.nanmean(temp_data_resized)
                    std_dev_temp = np.nanstd(temp_data_resized)
                    heat_island_threshold_value = mean_temp + std_dev_temp

                    # Normalize temperature values to be used in the heatmap display
                    temp_data_normalized = (temp_data_resized - np.nanmin(temp_data_resized)) / (np.nanmax(temp_data_resized) - np.nanmin(temp_data_resized))

                    # Prepare data for Folium heatmap by converting grid points to geographical coordinates
                    heat_data = []
                    rows, cols = temp_data_resized.shape
                    lat_step = (lat_max - lat_min) / rows
                    lon_step = (lon_max - lon_min) / cols

                    # Initialize a new Folium map centered on the AOI for each dataset
                    map_name = os.path.join(EXPORT_DIR, f"{HTML_MAP_BASE_NAME}{date}.html")
                    m = folium.Map(location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2], zoom_start=13)
                    folium.TileLayer('Esri.WorldImagery', name="Esri World Imagery").add_to(m)
                    folium.TileLayer('OpenStreetMap', name="OpenStreetMap").add_to(m)

                    # Create a list of heat data points using latitude, longitude, and normalized temperature intensity
                    for i in range(rows):
                        for j in range(cols):
                            if not np.isnan(temp_data_resized[i, j]):
                                lat = lat_min + i * lat_step
                                lon = lon_min + j * lon_step
                                heat_data.append([lat, lon, float(temp_data_normalized[i, j])])

                    # Add the heatmap layer to the map using the prepared heat data points
                    HeatMap(heat_data, min_opacity=0.2, radius=15, blur=10, max_zoom=13).add_to(folium.FeatureGroup(name="Heat Map").add_to(m))

                    # Identify areas above the threshold temperature and define these as heat island polygons
                    heat_island_polygons = []
                    for i in range(rows):
                        for j in range(cols):
                            if temp_data_resized[i, j] > heat_island_threshold_value:
                                lat = lat_min + i * lat_step
                                lon = lon_min + j * lon_step
                                heat_island_polygons.append(Polygon([
                                    (lon, lat),
                                    (lon + lon_step, lat),
                                    (lon + lon_step, lat + lat_step),
                                    (lon, lat + lat_step),
                                    (lon, lat)
                                ]))

                    # Merge individual heat island polygons into contiguous areas to create larger heat island zones
                    merged_heat_island = unary_union(heat_island_polygons)

                    # Convert the merged heat island areas to GeoJSON format and add them as overlay contours
                    heat_island_geojson = geojson.Feature(geometry=mapping(merged_heat_island))
                    folium.GeoJson(heat_island_geojson, name="Heat Island Contours", style_function=lambda x: {'color': 'yellow', 'weight': 2}).add_to(m)

                    # Add controls for layer visibility and save the map for the specific dataset date
                    folium.LayerControl().add_to(m)
                    m.save(map_name)
                    print(f"Map for {file} saved to {map_name}")
                else:
                    print(f"'LST' variable not found in {file}")
