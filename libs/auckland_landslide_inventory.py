import json
import os
import urllib.request
import geopandas as gpd

# Source https://www.arcgis.com/home/item.html?id=f7ca84d9c1524f99ab94e03b547cd143#data
# Currently, there are total 146,813 records
def fetch_data(output_dir, num_records=999999999, batch_size=2000):
    '''
    Fetch Auckland landslide inventory data from ArcGIS REST API and save to a GeoPackage file.
    Args:
        output_dir (str): Path to save the GeoPackage file.
        num_records (int): Total number of records to fetch. Default is a large number to fetch all available records.
        batch_size (int): Number of records to fetch per request. Default is 2000.
    '''

    os.makedirs(output_dir, exist_ok=True)

    for start in range(0, num_records, batch_size):
        
        print(f"Fetching records {start} to {min(start + batch_size, num_records)}")

        url = f'https://services-ap1.arcgis.com/9R0qvCUXav3QPG1F/arcgis/rest/services/ValidatedLandslides/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount={num_records}&resultOffset={start}'

        try:
            with urllib.request.urlopen(url) as response:
                if response.getcode() == 200:
                    json_string = response.read().decode('utf-8')
                    geojson_data = json.loads(json_string)
                else:
                    print(f"Error fetching data: {response.getcode()}")
                    return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

        if not gdf.empty:
            gdf.to_file(f"{output_dir}/raw_data.gpkg", driver='GPKG', layer='landslides', mode='a')
            gdf.to_file(f"{output_dir}/raw_data.geojson", driver='GeoJSON')
        else:
            print("Warning: No features returned; skipping shapefile write.")
            break
    