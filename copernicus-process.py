import os
import numpy as np
import xarray as xr
import folium
from folium.plugins import HeatMap
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
import geojson
from shapely.geometry import mapping

# Directory for downloaded LST files
DOWNLOAD_DIR = "downloaded_products"
# Base name for the HTML output files
HTML_MAP_BASE_NAME = "copernicus_cluj_heatmap_"

# Hardcoded Area of Interest (AOI) for Cluj-Napoca
aoi = box(23.53618, 46.73862, 23.63058, 46.80108)  # (lon_min, lat_min, lon_max, lat_max)
lon_min, lat_min, lon_max, lat_max = aoi.bounds

# Target shape for resampling (can be adjusted as needed)
target_shape = (500, 500)

# Iterate over downloaded NetCDF LST files, creating one map per file
for root, _, files in os.walk(DOWNLOAD_DIR):
    for file in files:
        if file.endswith("LST_in.nc"):
            file_path = os.path.join(root, file)
            with xr.open_dataset(file_path) as ds:
                if 'LST' in ds.variables:
                    # Resize the data to the target shape
                    temp_data = ds['LST'].values
                    temp_data_resized = np.resize(temp_data, target_shape)

                    # Calculate the mean and std deviation for this dataset
                    mean_temp = np.nanmean(temp_data_resized)
                    std_dev_temp = np.nanstd(temp_data_resized)
                    heat_island_threshold_value = mean_temp + std_dev_temp

                    # Normalize temperature data for heatmap
                    temp_data_normalized = (temp_data_resized - np.nanmin(temp_data_resized)) / (np.nanmax(temp_data_resized) - np.nanmin(temp_data_resized))

                    # Prepare data for heatmap layer and point markers
                    heat_data = []
                    rows, cols = temp_data_resized.shape
                    lat_step = (lat_max - lat_min) / rows
                    lon_step = (lon_max - lon_min) / cols

                    # Create Folium map for the specific day
                    map_name = f"{HTML_MAP_BASE_NAME}{file.split('.')[0]}.html"
                    m = folium.Map(location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2], zoom_start=13)
                    folium.TileLayer('Esri.WorldImagery', name="Esri World Imagery").add_to(m)
                    folium.TileLayer('OpenStreetMap', name="OpenStreetMap").add_to(m)

                    for i in range(rows):
                        for j in range(cols):
                            if not np.isnan(temp_data_resized[i, j]):
                                lat = lat_min + i * lat_step
                                lon = lon_min + j * lon_step
                                temp_value = float(temp_data_resized[i, j])
                                heat_data.append([lat, lon, temp_value])

                                # Add circle markers for exact temperature popups
                                folium.CircleMarker(
                                    location=[lat, lon],
                                    radius=3,
                                    color="red" if temp_value > heat_island_threshold_value else "blue",
                                    fill=True,
                                    fill_opacity=0.6,
                                    popup=f"Temperature: {temp_value:.2f} °C"
                                ).add_to(m)

                    # Add heatmap layer for this day
                    HeatMap(heat_data, min_opacity=0.2, radius=15, blur=10, max_zoom=13).add_to(folium.FeatureGroup(name="Heat Map").add_to(m))

                    # Identify heat island regions based on threshold
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

                    # Merge individual polygons into contiguous heat island areas
                    merged_heat_island = unary_union(heat_island_polygons)

                    # Add heat island contours to the map as GeoJSON
                    heat_island_geojson = geojson.Feature(geometry=mapping(merged_heat_island))
                    folium.GeoJson(heat_island_geojson, name="Heat Island Contours", style_function=lambda x: {'color': 'yellow', 'weight': 2}).add_to(m)

                    # Add layer control and save the map for the specific day
                    folium.LayerControl().add_to(m)
                    m.save(map_name)
                    print(f"Map for {file} saved to {map_name}")
                else:
                    print(f"'LST' variable not found in {file}")
