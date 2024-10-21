from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

class Influx:
    def __init__(self, url, bucket, org, token):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.org = org
        self.bucket = bucket
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        
    def write(self,measurement, dateTime, *data):
        try:
            point = (
                Point(measurement)
                .tag(data[0]["key"], data[0]["value"])
                .field(data[1]["key"], data[1]["value"])
                .field(data[2]["key"], data[2]["value"])
                .time(dateTime, WritePrecision.NS)
            )
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            print("Data written to InfluxDB successfully.")
        except:
            print("Could not write data")


    def read(self, query):
        query_api = self.client.query_api().query

        query = """from(bucket: "elpris")
            |> range(start: -180m)
            |> filter(fn: (r) => r._measurement == "customer_prices")"""
        tables = query_api.query(query, org="ucl")
        for tabel in tables:
            for record in tabel.records:
                print(record)
                print("")


    def exit(self):
        self.client.close()

