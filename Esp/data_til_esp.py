import requests
from datetime import datetime


# Get the current date in the format "dd-mm-yyyy"
time = datetime.now()
time = time.strftime("%d-%m-%Y")

# Define the API URL to fetch electricity prices from Energi Fyn
url = "https://api.energifyn.dk/api/graph/consumptionprice?date="+time

# Make a GET request to the API
response = requests.get(url)

# Parse the JSON response
response_data = response.json()

def prepare_data(EW: str, data: dict, timer_aktiv: int):
    """
    This function takes the convoluted mess of data from energi Fyn and transforms it 
    into a set of times that the price is lowest. The function call looks like this:
    prepare_data(East/West of storebaelt (string), The data from Energi Fyn (dict), Amount of hours you want to receive (int))
    """
    # Convert the region string to lowercase for case-insensitive comparison
    EW = EW.lower()
    
    # Determine which region (East or West) to process
    if EW == "east":
        ugh = 'eastPrices' # Select East prices

    elif EW == 'west':
        ugh =  'westPrices' # Select West prices

    else:
         # Return an error if the region is not East or West
        error = "You can only get prices from East and West"
        return error
    
    # Get the first available date key in the data
    key = response_data[ugh].keys()
    key = next(iter(key))

    # Extract the prices data for the specified date
    short_data = response_data[ugh][key]["prices"]
    data_data = [] # To store price and time data
    esp_data = [] # To store the final extracted times

    # Store the number of hours (lowest prices) to retrieve
    timer_aktiv = timer_aktiv

    # Loop through the price data and build a list of dictionaries with time and price
    for data in short_data:
        # Add the hour and price information
        data_data.append({"hour": data['hour'], "price": data["price"]})

    # Sort the list based on the 'price' key in ascending order
    sorted_data = sorted(data_data, key=lambda x: x['price'])

    final_data = [] # To store the sorted times with the lowest prices

    # Collect the times corresponding to the lowest prices, up to the limit of 'timer_aktiv'
    for data in sorted_data:
        final_data.append(data['hour'])
        if len(final_data) == timer_aktiv:
            break # Stop once the required number of hours is collected
    
    # Extract only the hour part from the "hour" field (split on 'T')
    for data in final_data:
        data = data.split("T")
        esp_data.append(data[1]) # Append the hour (second part of the split)
    
    # sorter efter tid
    esp_data.sort()

    return esp_data # Return the list of times with the lowest prices


# Example usage of the function to get 6 hours of lowest prices for West and East
print("west data: ", prepare_data("West", response_data, 5))
print("east data: ", prepare_data("east", response_data, 6))