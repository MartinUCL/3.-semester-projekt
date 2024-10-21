import requests, os
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime

api_url = "https://api.energifyn.dk/api/graph/consumptionprice?date=26-08-2024"


# InfluxDB setup
bucket = "elpris" #Navn på bucket, skal være oprettet først.
org = "ucl"
token = "II6Xkf4zPZhBs8MCdWHbU3pYNyrNgkBMVevPItDVkAdXSAyBxW6L-zApCKAzmTN81QvalTL2LijPxGZUw5ZNbw=="
url = "http://localhost:8086"

client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Fetch data from the API
response = requests.get(api_url)#, #headers=headers)

# Check if the response is successful
if response.status_code == 200:
    data = response.json()

    # Parse and write the data to InfluxDB
    customer_prices = data.get("westPrices", {})

    for date_str, day_data in customer_prices.items():
        prices = day_data.get("prices", [])
        for price_entry in prices:
            hour_str = price_entry["hour"]
            price = price_entry["price"]
            tarif_price = price_entry["tarifPrice"]

            # Convert hour to a datetime object
            hour_datetime = datetime.fromisoformat(hour_str)

            # Create InfluxDB point
            point = (
                Point("customer_prices")
                .tag("date", date_str)
                .field("price", price)
                .field("tarif_price", tarif_price)
                .time(hour_datetime, WritePrecision.NS)
            )

            # Write point to InfluxDB
            write_api.write(bucket=bucket, org=org, record=point)

    print("Data written to InfluxDB successfully.")

else:
    print(f"Failed to fetch data: {response.status_code} - {response.text}")

# Close the client
client.close()