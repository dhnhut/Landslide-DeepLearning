import json
import os
import urllib.request
import geopandas as gpd
    
def layers():
    return {
        "points": 0,
        "lines": 1,
        "polygons": 2,
    }

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

    for layer_name, layer_id in layers().items():
        geojson_data = {}

        for start in range(0, num_records, batch_size):

            url = f'https://services-ap1.arcgis.com/9R0qvCUXav3QPG1F/arcgis/rest/services/ValidatedLandslides/FeatureServer/{layer_id}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount={num_records}&resultOffset={start}'
        
            print(f"Fetching records {start} to {min(start + batch_size, num_records)} for layer {layer_name}...")
            try:
                with urllib.request.urlopen(url) as response:
                    if response.getcode() == 200:
                        json_string = response.read().decode('utf-8')
                        geojson_data[layer_name] = json.loads(json_string)
                    else:
                        print(f"Error fetching data: {response.getcode()}")
                        return None
            except Exception as e:
                print(f"An error occurred: {e}")
                return None
            gdf = gpd.GeoDataFrame.from_features(geojson_data[layer_name]["features"])
            if not gdf.empty:
                gdf.to_file(f"{output_dir}/inventory.gpkg", driver='GPKG', layer=layer_name, mode='a')
                gdf.to_file(f"{output_dir}/inventory_{layer_name}.geojson", driver='GeoJSON', mode='a')
            else:
                print(f"No more records to fetch for layer {layer_name}.")
                break
    print("Data fetching completed.")
