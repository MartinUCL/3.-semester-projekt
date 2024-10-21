import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd  # Import pandas for data manipulation
from dmi_open_data import DMIOpenDataClient, Parameter
import time

# Load environment variables
load_dotenv()

# Global variables
API_KEY = os.getenv("DMI_MET_OBS")
BASE_URL = f"https://dmigw.govcloud.dk/v2/metObs/collections/observation/items?api-key={API_KEY}"
LAST_DATE_FILE = 'last_date.json'
# Initialize the DMI client
client = DMIOpenDataClient(api_key=API_KEY)

# Default coordinates (Odense)
DEFAULT_COORDS = [10.3883, 55.3959]

def read_last_date():
    """Reads the last date from a JSON file."""
    if os.path.exists(LAST_DATE_FILE):
        with open(LAST_DATE_FILE, 'r') as f:
            data = json.load(f)
            return datetime.strptime(data['last_date'], "%Y-%m-%d")
    return None

def save_last_date(last_date):
    """Saves the last date to a JSON file."""
    with open(LAST_DATE_FILE, 'w') as f:
        json.dump({'last_date': last_date.strftime("%Y-%m-%d")}, f)


def get_date_ranges(start_date):
    """
    Get the date range for weather observations.
    
    Args:
        start_date (datetime): The date for which to gather data.
    
    Returns:
        tuple: A tuple containing the api_time (str), to_time (datetime), 
               and from_time (datetime).
    """
    api_time = start_date.strftime("%d-%m-%Y")
    from_time = start_date
    to_time = start_date + timedelta(days=1)
    return api_time, from_time, to_time

def get_stations(parameter_name):
    """
    Get a list of stations that provide a specific parameter.
    
    Args:
        parameter_name (str): The name of the weather parameter (e.g., 'cloud_cover', 'temp_dry').
    
    Returns:
        list: A list of stations that have the specified parameter.
    """
    stations = client.get_stations(limit=10000)
    stations_with_parameter = [
        station for station in stations 
        if parameter_name in station['properties'].get('parameterId', [])
    ]
    return stations_with_parameter

def find_closest_station(stations, coords):
    """
    Find the closest station to the given coordinates.
    
    Args:
        stations (list): List of stations.
        coords (list): Target coordinates as [longitude, latitude].
    
    Returns:
        dict: The closest station.
    """
    def min_distance(my_coords, station_coords):
        distance = abs(my_coords[0] - station_coords[0]), abs(my_coords[1] - station_coords[1])
        return (distance[0] + distance[1]) / 2
    
    distances = [min_distance(coords, station['geometry']['coordinates']) for station in stations]
    min_index = distances.index(min(distances))
    return stations[min_index]

def get_observations(parameter, station_id, from_time, to_time, limit=144):
    """
    Get weather observations for a specified parameter and station.
    """
    observations = client.get_observations(
        parameter=parameter,
        station_id=station_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit
    )
    return observations

def average_hourly(observations, decimals=1):
    """
    Average observations over each hour to get 24 measurements.
    
    Args:
        observations (list): A list of observation dictionaries.
        decimals (int): Number of decimal places to round the results.
    
    Returns:
        list: A list of 24 averaged values, rounded to the specified number of decimals.
    """
    # Create a DataFrame from the observations
    df = pd.DataFrame([{
        'timestamp': pd.to_datetime(obs['properties']['observed']),
        'value': obs['properties'].get('value')
    } for obs in observations])

    if df['value'].isna().all():
        return []

    df = df.sort_values('timestamp')
    
    # Resample to hourly, taking the mean
    hourly_avg = df.resample('h', on='timestamp').mean().reset_index()

    hourly_avg = hourly_avg.set_index('timestamp').reindex(pd.date_range(start=df['timestamp'].min().floor('h'), 
                                                                          periods=24, 
                                                                          freq='h')).ffill()

    # Rounding the values explicitly
    hourly_avg['value'] = pd.to_numeric(hourly_avg['value'], errors='coerce')
    
    # Round the values, handling NaNs
    for index in hourly_avg.index:
        value = hourly_avg.at[index, 'value']
        if pd.notna(value):
            hourly_avg.at[index, 'value'] = round(value, decimals)

    return hourly_avg['value'].tolist()

def get_cloud_cover(from_time, to_time, coords=DEFAULT_COORDS):
    """
    Retrieve cloud cover data from the closest station and average hourly.
    
    Args:
        from_time (datetime): Start time for data collection.
        to_time (datetime): End time for data collection.
        coords (list): Coordinates [longitude, latitude] to search closest station.
    
    Returns:
        list: A list of averaged cloud cover values (24 measurements).
    """
    stations_with_cloud = get_stations('cloud_cover')

    if not stations_with_cloud:
        raise ValueError("No stations available for cloud cover data.")

    closest_station = find_closest_station(stations_with_cloud, coords)
    observations = get_observations(Parameter.CloudCover, closest_station['properties']['stationId'], from_time, to_time)
    
    if not observations:
        raise ValueError("No observations returned for cloud cover.")

    return average_hourly(observations)

def get_temperature(from_time, to_time, coords=DEFAULT_COORDS):
    """
    Retrieve temperature data from the closest station and average hourly.
    
    Args:
        from_time (datetime): Start time for data collection.
        to_time (datetime): End time for data collection.
        coords (list): Coordinates [longitude, latitude] to search closest station.
    
    Returns:
        list: A list of averaged temperature values (24 measurements).
    """
    stations_with_temp = get_stations('temp_dry')
    
    if not stations_with_temp:
        raise ValueError("No stations available for temperature data.")
    
    closest_station = find_closest_station(stations_with_temp, coords)
    observations = get_observations(Parameter.TempDry, closest_station['properties']['stationId'], from_time, to_time)
    
    if not observations:
        raise ValueError("No observations returned for temperature.")

    return average_hourly(observations)

def fetch_response_data(api_time, retries=3, delay=2):
    url = "https://api.energifyn.dk/api/graph/consumptionprice?date=" + api_time
    
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()  # Assuming the response is in JSON format
            else:
                print(f"Attempt {attempt + 1} failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed with exception: {e}")

        time.sleep(delay)

    raise ValueError("Failed to fetch response data after multiple attempts")

def prepare_data(EW: str, data: dict):
    EW = EW.lower()
    if EW == "east":
        ugh = 'eastPrices'
    elif EW == 'west':
        ugh =  'westPrices'
    else:
        return "You can only get prices from East and West"
    
    key = next(iter(response_data[ugh].keys()))
    short_data = response_data[ugh][key]["prices"]
    esp_data = []

    for data in short_data:
        esp_data.append((data['hour'].split("T")[1], data["price"]))  # Append hour and price

    return esp_data 

def get_daily_prices():
    west = prepare_data("West", response_data)
    east = prepare_data("east", response_data)
    return west, east

def check_for_empty_elements(cloud_cover_data, temperature_data, west_prices, east_prices):
    datasets = {
        "Cloud Cover": cloud_cover_data,
        "Temperature": temperature_data,
        "West Prices": west_prices,
        "East Prices": east_prices
    }
    
    for name, data in datasets.items():
        if any(pd.isna(value) or value == '' for value in data):
            print(f"Warning: Some values are missing in {name}.")
        else:
            pass

def combine_hourly_data(start_timex, cloud_cover_data, temperature_data, west_prices, east_prices):
    combined_data = []
    start_time = start_timex.replace(hour=0, minute=0, second=0, microsecond=0)

    for hour in range(24):
        timestamp = start_time + timedelta(hours=hour)
        cloud_cover = cloud_cover_data[hour] if hour < len(cloud_cover_data) else None
        temperature = temperature_data[hour] if hour < len(temperature_data) else None
        west_price = west_prices[hour][1] if hour < len(west_prices) else None
        east_price = east_prices[hour][1] if hour < len(east_prices) else None
        
        combined_data.append({
            'timestamp': timestamp.isoformat(),
            'cloud_cover': cloud_cover,
            'temperature': temperature,
            'west_price': west_price,
            'east_price': east_price
        })

    return combined_data

def save_to_json(data, filename):
    """
    Save data to a JSON file, appending to existing data if the file already exists.
    
    Args:
        data (list): The data to be saved.
        filename (str): The name of the JSON file.
    """
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as json_file:
                existing_data = json.load(json_file)
                if not isinstance(existing_data, list):  # Ensure it's a list
                    existing_data = []  # Reset if not a list
        except (json.JSONDecodeError, ValueError):  # Handle invalid JSON
            print(f"Warning: {filename} contains invalid JSON. Starting fresh.")
            existing_data = []
    else:
        existing_data = []

    existing_data.extend(data)

    with open(filename, 'w') as json_file:
        json.dump(existing_data, json_file, indent=4)


def main():
    global response_data  # Declare it as global if you plan to modify it in other functions
    last_date = read_last_date()  # Read last date at the start
    #start_date = datetime.strptime(input("Enter start date (YYYY-MM-DD): "), "%Y-%m-%d")
    start_date = last_date - timedelta(days=1)
    #num_days = int(input("Enter number of days to retrieve data for: "))
    num_days = 100
    
    combined_hourly_data = []

    for day in range(num_days):
        current_date = start_date - timedelta(days=day)
        api_time, from_time, to_time = get_date_ranges(current_date)

        response_data = fetch_response_data(api_time)
        
        cloud_cover_data = get_cloud_cover(from_time, to_time)

        temperature_data = get_temperature(from_time, to_time)

        west_prices, east_prices = get_daily_prices()

        check_for_empty_elements(cloud_cover_data, temperature_data, west_prices, east_prices)

        combined_hourly_data.extend(combine_hourly_data(current_date, cloud_cover_data, temperature_data, west_prices, east_prices))
        
        # Calculate and print the progress
        percentage_done = ((day + 1) / num_days) * 100
        print(f"Progress: {percentage_done:.2f}% done")
    
        save_to_json(combined_hourly_data, 'ml_data.json')
        save_last_date(current_date)  
    
    print("Data saved to ml_data.json")



if __name__ == "__main__":
    quit_ = False
    while True: 
        print("Gathering data new data... \n")
        try:
            if quit_ == True:
                break
            else:
                main() 
        except KeyboardInterrupt:
            print("\nProgram interrupted by user. Exiting...")
            quit_ = True
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Restarting the program...")
            time.sleep(3)