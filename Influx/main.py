from influx import Influx
import api, os, datetime
from dotenv import load_dotenv
load_dotenv()


res = api.req("")


print( )


bucket = "elpris" #Navn på bucket, skal være oprettet først.
org = "ucl"
token = os.getenv('influxToken')
url = "http://localhost:8086"



db = Influx(url=url, org=org, token=token, bucket=bucket)
for date_str, day_data in res.get("westPrices", {}).items():
        prices = day_data.get("prices", [])
        for price_entry in prices:
            # Convert hour to a datetime object
            hour_datetime = datetime.datetime.fromisoformat(price_entry["hour"])
            db.write(
                "customer_prices",
                hour_datetime,
                {"key":"date" ,"value": date_str},
                {"key":"price" ,"value": price_entry["price"]},
                {"key":"tarif_price" ,"value": price_entry["tarifPrice"]}
            )

#db.read("as")