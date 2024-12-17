import os
import json
import requests
from datetime import datetime, timedelta
import pandas as pd
from dmi_open_data import DMIOpenDataClient, Parameter
import time
from dotenv import load_dotenv
import joblib

# Load environment variables
load_dotenv()

# Load environment variables (ensure your .env file has the API key for DMI)
API_KEY = os.getenv("DMI_MET_OBS")
BASE_URL = f"https://dmigw.govcloud.dk/v2/metObs/collections/observation/items?api-key={API_KEY}"
client = DMIOpenDataClient(api_key=API_KEY)

# Default coordinates (Odense)
DEFAULT_COORDS = [10.3883, 55.3959]

def get_date_ranges(start_date):
    """
    Get the date range for weather observations.
    """
    api_time = start_date.strftime("%d-%m-%Y")
    from_time = start_date
    to_time = start_date + timedelta(days=1)
    return api_time, from_time, to_time

def get_stations(parameter_name):
    """
    Get a list of stations that provide a specific parameter.
    """
    stations = client.get_stations(limit=10000)
    return [station for station in stations if parameter_name in station['properties'].get('parameterId', [])]

def find_closest_station(stations, coords):
    """
    Find the closest station to the given coordinates.
    """
    def min_distance(my_coords, station_coords):
        distance = abs(my_coords[0] - station_coords[0]), abs(my_coords[1] - station_coords[1])
        return (distance[0] + distance[1]) / 2
    
    distances = [min_distance(coords, station['geometry']['coordinates']) for station in stations]
    return stations[distances.index(min(distances))]

def get_observations(parameter, station_id, from_time, to_time, limit=144):
    """
    Get weather observations for a specified parameter and station.
    """
    return client.get_observations(
        parameter=parameter,
        station_id=station_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit
    )

def average_hourly(observations, decimals=1):
    """
    Average observations over each hour to get 24 measurements.
    """
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

    # Round values explicitly
    hourly_avg['value'] = pd.to_numeric(hourly_avg['value'], errors='coerce')
    hourly_avg['value'] = hourly_avg['value'].round(decimals)

    return hourly_avg['value'].tolist()

# Fetch wind speed data similar to cloud cover and temperature
def get_wind_speed(from_time, to_time, coords=DEFAULT_COORDS):
    stations_with_wind = get_stations('wind_speed')
    closest_station = find_closest_station(stations_with_wind, coords)
    observations = get_observations(Parameter.WindSpeed, closest_station['properties']['stationId'], from_time, to_time)
    return average_hourly(observations)

def get_cloud_cover(from_time, to_time, coords=DEFAULT_COORDS):
    stations_with_cloud = get_stations('cloud_cover')
    closest_station = find_closest_station(stations_with_cloud, coords)
    observations = get_observations(Parameter.CloudCover, closest_station['properties']['stationId'], from_time, to_time)
    return average_hourly(observations)

def get_temperature(from_time, to_time, coords=DEFAULT_COORDS):
    stations_with_temp = get_stations('temp_dry')
    closest_station = find_closest_station(stations_with_temp, coords)
    observations = get_observations(Parameter.TempDry, closest_station['properties']['stationId'], from_time, to_time)
    return average_hourly(observations)

def fetch_response_data(api_time):
    url = "https://api.energifyn.dk/api/graph/consumptionprice?date=" + api_time
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def prepare_data(EW: str, data: dict):
    EW = EW.lower()
    ugh = 'eastPrices' if EW == 'east' else 'westPrices'
    short_data = data[ugh][next(iter(data[ugh]))]["prices"]
    return [(d['hour'].split("T")[1], d["price"]) for d in short_data]

def get_daily_prices():
    west = prepare_data("West", response_data)
    east = prepare_data("east", response_data)
    return west, east

def combine_hourly_data(start_timex, cloud_cover_data, temperature_data, wind_speed_data, west_prices, east_prices):
    combined_data = []
    start_time = start_timex.replace(hour=0, minute=0, second=0, microsecond=0)

    for hour in range(24):
        timestamp = start_time + timedelta(hours=hour)
        combined_data.append({
            'timestamp': timestamp.isoformat(),
            'cloud_cover': cloud_cover_data[hour] if hour < len(cloud_cover_data) else None,
            'temperature': temperature_data[hour] if hour < len(temperature_data) else None,
            'wind_speed': wind_speed_data[hour] if hour < len(wind_speed_data) else None,
            'west_price': west_prices[hour][1] if hour < len(west_prices) else None,
            'east_price': east_prices[hour][1] if hour < len(east_prices) else None
        })

    return combined_data

def main():
    global response_data

    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=7)

    print("Getting data for:", str(yesterday))
    # Prepare time ranges for weather and price data retrieval
    api_time, from_time, to_time = get_date_ranges(yesterday)

    # Fetch electricity prices
    response_data = fetch_response_data(api_time)

    # Fetch weather data
    cloud_cover_data = get_cloud_cover(from_time, to_time)
    temperature_data = get_temperature(from_time, to_time)
    wind_speed_data = get_wind_speed(from_time, to_time)  # Fetch wind speed data

    # Fetch daily electricity prices for west and east
    west_prices, east_prices = get_daily_prices()

    # Combine the data, now including wind speed
    combined_hourly_data = combine_hourly_data(yesterday, cloud_cover_data, temperature_data, wind_speed_data, west_prices, east_prices)

    # Load pre-trained model and scaler
    model = joblib.load('multi_output_model.pkl')
    scaler = joblib.load('scaler.pkl')  # Load the scaler

    # Prepare features for prediction (cloud cover, temperature, wind speed, hour, day_of_week, month)
    features = []
    for hour in range(24):
        entry = combined_hourly_data[hour]
        timestamp = pd.to_datetime(entry['timestamp'])  # Convert timestamp to datetime
        hour_of_day = timestamp.hour
        day_of_week = timestamp.dayofweek
        month = timestamp.month

        features.append([
            entry['cloud_cover'],
            entry['temperature'],
            entry['wind_speed'],  # Include wind speed as a feature
            hour_of_day,
            day_of_week,
            month
        ])

    # Convert features to a DataFrame or array
    features_df = pd.DataFrame(features, columns=['cloud_cover', 'temperature', 'wind_speed', 'hour', 'day_of_week', 'month'])

    # Scale the features before making predictions
    features_scaled = scaler.transform(features_df)

    print("Making prediction...")
    # Make predictions
    predicted_prices = model.predict(features_scaled)

    # Compare predicted and actual prices
    actual_west_prices = [price[1] for price in west_prices]
    actual_east_prices = [price[1] for price in east_prices]
    final_prices_Prediction = []
    final_prices_actual = []

    print("Hour  | Predicted West Price | Actual West Price | Predicted East Price | Actual East Price")
    for hour in range(24):
        #print(f"{hour:02d}:00 | {predicted_prices[hour][0]:.2f}                 | {actual_west_prices[hour]:.2f}              | "
         #     f"{predicted_prices[hour][1]:.2f}                 | {actual_east_prices[hour]:.2f}")
        print(f"{hour:02d}:00 | {predicted_prices[hour][0]:.2f}/{predicted_prices[hour][1]:.2f}  | {actual_west_prices[hour]:.2f}/{actual_east_prices[hour]:.2f}")
        # Create the Excel-compatible lists
        final_prices_Prediction.append(f"{predicted_prices[hour][0]:.2f}/{predicted_prices[hour][1]:.2f}")
        final_prices_actual.append(f"{actual_west_prices[hour]:.2f}/{actual_east_prices[hour]:.2f}")

    print("Prediction of prices Excel compatible:")
    for i in final_prices_Prediction:
        print(i)

    print("Actual prices Excel compatible:")
    for i in final_prices_actual:
        print(i)
    


if __name__ == "__main__":
    main()
