import requests
from datetime import datetime

def req(url:str):
    if url == "" or None:
        dato = datetime.now()
        print(dato)
        return
        d = dato.strftime("%d")
        m = dato.strftime("%m")
        y = dato.strftime("%Y")
        url = f"https://api.energifyn.dk/api/graph/consumptionprice?date={d}-{m}-{y}"

    response = requests.get(url)#, #headers=headers)

    # Check if the response is successful
    if response.status_code == 200:
        return response.json()

    else:
        return f"Failed to fetch data: {response.status_code} - {response.text}"

if __name__ == "__main__":
    req("")