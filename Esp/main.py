import network
import time
import machine
import ujson as json
import uasyncio as asyncio
from machine import Pin
import os  # To handle file operations
import ucryptolib
import ubinascii

# Pin Configuration
LED_PIN = 4          # GPIO for the state LED
BUTTON_PIN = 5       # GPIO for the Reset button
CONFIG_FILE = "wifi_config.json"

# Setup LED and Button
led = Pin(LED_PIN, Pin.OUT)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# Wi-Fi Interfaces
sta_if = network.WLAN(network.STA_IF)  # Station Interface (Client Mode)
ap_if = network.WLAN(network.AP_IF)    # Access Point Interface (AP Mode)

# Define States
STATE_CLIENT_MODE = 1  # Client mode, operational
STATE_AP_MODE = 2      # Access Point mode
STATE_CONNECTED = 3     # Connected state
STATE_ERROR = 4         # Error state
current_state = None

# AES Encryption/Decryption key (16 bytes)
KEY = b"mysecretkey12345"  # Must be 16, 24, or 32 bytes long

# Function to check button press
def is_button_pressed():
    pressed = button.value() == 0
    print(f"Button pressed: {pressed}")
    return pressed

# Save Wi-Fi credentials to a file with encryption
def save_wifi_config(ssid, password):
    print(f"Entering save_wifi_config with SSID: {ssid} and Password: {password}")
    try:
        # Ensure the password is not empty
        if not password:
            raise ValueError("Password cannot be empty.")
        
        # Print the encryption key for debugging
        print(f"Using Encryption Key: {KEY}")

        encrypted_password = encrypt_password(password)
        print(f"Saving config: SSID={ssid}, Encrypted Password={encrypted_password}")

        # Debug: Check if the config file exists before writing
        if CONFIG_FILE in os.listdir():
            print(f"{CONFIG_FILE} exists. Overwriting...")
        else:
            print(f"{CONFIG_FILE} does not exist. Creating new file...")

        with open(CONFIG_FILE, "w") as f:
            json.dump({"ssid": ssid, "password": encrypted_password}, f)
        print("Wi-Fi configuration saved successfully.")
    except Exception as e:
        print(f"Error saving Wi-Fi config: {e}")

# Load Wi-Fi credentials from a file and decrypt the password
def load_wifi_config():
    print("Attempting to load Wi-Fi configuration...")

    # Debug: Check if the config file exists
    if CONFIG_FILE in os.listdir():
        print(f"{CONFIG_FILE} found. Proceeding to load...")
    else:
        print(f"{CONFIG_FILE} does not exist. Cannot load configuration.")
        return None

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            print(f"Loaded config: {config}")
            config['password'] = decrypt_password(config['password'])  # Decrypt the password
            print(f"Decrypted Password: {config['password']}")
            return config
    except OSError as e:
        print(f"Error loading Wi-Fi config: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {CONFIG_FILE}: {e}")
        return None

# Encryption function
def encrypt_password(password):
    print(f"Encrypting password: {password}")

    # Debug: Print key information
    print(f"Using encryption key: {KEY}")
    print(f"Key Length: {len(KEY)} bytes")
    print(f"Key Type: {type(KEY)}")

    # Pad the password to be a multiple of 16 bytes
    padded_password = password + (16 - len(password) % 16) * ' '
    print(f"Padded Password: '{padded_password}' (Length: {len(padded_password)})")  # Debug: Show padded password

    try:
        # Create AES cipher in ECB mode
        cipher = ucryptolib.aes(KEY, 1)  # 1 is for ECB mode
        print("Cipher initialized successfully.")

        # Encrypt the padded password
        encrypted = cipher.encrypt(padded_password.encode('utf-8'))
        print(f"Encrypted data (bytes): {encrypted}")  # Debug: Show encrypted bytes

        # Encode the encrypted bytes to base64
        encrypted_b64 = ubinascii.b2a_base64(encrypted).decode('utf-8').strip()
        print(f"Encrypted password (base64): {encrypted_b64}")  # Debug: Show base64 encoded encrypted password

        return encrypted_b64
    except Exception as e:
        print(f"Error during encryption: {e}")
        raise  # Re-raise the exception for further handling

def decrypt_password(encrypted_password):
    print(f"Decrypting password: {encrypted_password}")
    try:
        # Decode the base64 encoded password
        encrypted_bytes = ubinascii.a2b_base64(encrypted_password)

        # Create AES cipher in ECB mode
        cipher = ucryptolib.aes(KEY, 1)  # 1 is for ECB mode

        # Decrypt the encrypted bytes
        decrypted = cipher.decrypt(encrypted_bytes)

        # Convert to string and remove padding
        decrypted_str = decrypted.decode('utf-8').rstrip()  # Remove any trailing spaces
        print(f"Decrypted password: {decrypted_str}")
        return decrypted_str
    except Exception as e:
        print(f"Error during decryption: {e}")
        raise

# Connect to Wi-Fi as a client (STA mode)
async def connect_to_wifi():
    wifi_config = load_wifi_config()
    if wifi_config:
        print(f"Attempting to connect to Wi-Fi SSID: {wifi_config['ssid']}")
        try:
            sta_if.active(True)
            sta_if.connect(wifi_config['ssid'], wifi_config['password'])
        except Exception as e:
            print(f"An error occurred: {e}")
        
        # Wait for the connection to be established with a timeout
        timeout = time.time() + 20  # 20 seconds from now
        while time.time() < timeout:  # Loop until timeout
            print(f"Checking connection... (Time left: {int(timeout - time.time())} seconds)")
            if sta_if.isconnected():
                print("Connected to Wi-Fi")
                return True
            
            # Check for button press to allow reset
            if is_button_pressed():
                print("Button pressed! Resetting ESP32...")
                machine.reset()  # Reset the ESP32 if the button is pressed
            
            await asyncio.sleep(0.5)  # Non-blocking sleep

        print("Failed to connect to Wi-Fi after 20 seconds.")
    else:
        print("No Wi-Fi configuration found.")
    
    return False


# Setup Access Point (AP Mode)
def start_ap_mode():
    print("Starting Access Point Mode...")
    ap_if.active(True)
    ap_if.config(essid='ESP32_Setup', authmode=network.AUTH_OPEN)
    print("Access Point Mode - Connect to 'ESP32_Setup'")

# LED State Indicators
def set_led_blinking():
    print("LED blinking to indicate AP mode.")
    for _ in range(5):
        led.value(1)
        time.sleep(0.5)
        led.value(0)
        time.sleep(0.5)
    
def set_led_blinking_error():
    print("LED blinking to indicate error state.")
    for _ in range(10):  # Fast blinking for error state
        led.value(1)
        time.sleep(0.2)
        led.value(0)
        time.sleep(0.2)

def set_led_on():
    led.value(1)
    print("LED is ON, indicating connected state.")

def set_led_off():
    led.value(0)
    print("LED is OFF.")

# Wi-Fi Scanning for AP Mode
def scan_wifi_networks():
    print("Scanning for Wi-Fi networks...")
    sta_if.active(True)  # Activate the station interface for scanning
    networks = sta_if.scan()  # Scan for networks
    network_list = []

    for net in networks:
        ssid = net[0].decode('utf-8')
        rssi = net[3]  # Signal strength
        network_list.append(f"{ssid} (Signal: {rssi} dBm)")

    print("Scan complete. Networks found:")
    for network in network_list:
        print(network)

    return network_list

# Function to decode URL-encoded characters
def url_decode(query):
    # Replace known URL-encoded characters with their actual values
    decoded_query = query.replace('%20', ' ').replace('%21', '!').replace('%22', '"') \
                         .replace('%23', '#').replace('%24', '$').replace('%25', '%') \
                         .replace('%26', '&').replace('%27', "'").replace('%28', '(') \
                         .replace('%29', ')').replace('%2A', '*').replace('%2B', '+') \
                         .replace('%2C', ',').replace('%2F', '/').replace('%3A', ':') \
                         .replace('%3B', ';').replace('%3D', '=').replace('%3F', '?') \
                         .replace('%40', '@').replace('%5B', '[').replace('%5D', ']')
    return decoded_query

# Serve a basic web page to configure Wi-Fi
async def web_page_handler(reader, writer):
    print("Web page handler activated.")
    try:
        # Read the request from the client
        request = await reader.read(1024)
        request = request.decode('utf-8')  # Decode the request from bytes to string
        print(f"Received request: {request[:100]}...")  # Print the first 100 characters for debugging

        if '/scan' in request:
            # Scan for Wi-Fi networks and return the result as JSON
            networks = scan_wifi_networks()
            response = json.dumps(networks)
            await writer.awrite("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n")
            await writer.awrite(response)
        
        elif '/submit' in request:
            # Extract SSID and password from the request and save it
            try:
                print("Processing form submission...")
                
                # Extract query parameters after the '?' in the URL
                query_string = request.split('?', 1)[1].split(' ')[0]
                
                # Split and decode the parameters manually
                params = query_string.split('&')
                ssid = url_decode(params[0].split('=')[1])
                password = url_decode(params[1].split('=')[1])

                # Print SSID and password for debugging purposes
                print(f"Extracted SSID: {ssid}, Password: {password}")
                
                if ssid and password:
                    save_wifi_config(ssid, password)  # Save the Wi-Fi configuration
                    
                    # Respond with a redirect to the main page after successful submission
                    await writer.awrite("HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n")
                    # Wait for the client to process the response before restarting
                    await asyncio.sleep(1)  # Small delay to let the client handle the response

                    print("Restarting ESP32 to apply the new Wi-Fi configuration...")
                    machine.reset()  # Restart the ESP32 to apply the new configuration
                else:
                    raise ValueError("SSID or password missing in form submission.")
            
            except Exception as e:
                print(f"Error processing form submission: {e}")
                await writer.awrite("HTTP/1.1 400 Bad Request\r\n\r\n")
        
        else:
            # Serve the main Wi-Fi configuration page
            html = """<!DOCTYPE html>
            <html>
            <head><title>ESP32 Wi-Fi Config</title></head>
            <body>
            <h1>ESP32 Wi-Fi Configuration</h1>
            <form action="/submit" method="get">
                SSID: <input type="text" name="ssid"><br>
                Password: <input type="password" name="password"><br>
                <input type="submit" value="Submit">
            </form>
            <button onclick="scanNetworks()">Scan Networks</button>
            <pre id="results"></pre>
            <script>
            function scanNetworks() {
                fetch('/scan')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('results').innerText = JSON.stringify(data, null, 2);
                });
            }
            </script>
            </body>
            </html>"""
            await writer.awrite("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
            await writer.awrite(html)

    except Exception as e:
        print(f"Error in web_page_handler: {e}")
    
    finally:
        # Close the writer connection to the client after the response is sent
        await writer.aclose()



# Start Web Server in AP Mode
async def start_web_server():
    print("Starting Web Server...")
    # Create a server that listens on port 80
    server = await asyncio.start_server(web_page_handler, "0.0.0.0", 80)

    # Keep the server running indefinitely
    await server.wait_closed()  # Wait for the server to close (this should not happen)



# Main State Machine
async def run_state_machine():
    global current_state

    reset_wifi_config()  # Check if reset button is pressed on boot

    if load_wifi_config() is not None:
        print("Wi-Fi configuration found. Attempting to connect...")

        retry_count = 0
        while retry_count < 10:  # Try connecting up to 10 times with backoff
            if await connect_to_wifi():
                current_state = STATE_CONNECTED
                set_led_on()  # Indicate successful connection
                print("Connected successfully. Operational mode (Client Mode)")
                break
            else:
                print(f"Retry {retry_count + 1}: Failed to connect. Retrying...")
                retry_count += 1
                await asyncio.sleep(5)  # Wait 5 seconds before trying again

        if retry_count >= 10:
            print("Reached maximum retries. Entering error state.")
            current_state = STATE_ERROR

    else:
        print("No previous Wi-Fi configuration found. Starting in AP mode.")
        current_state = STATE_AP_MODE
        set_led_blinking()

    while True:  # Loop to maintain state
        reset_wifi_config()  # Continuously check the button state

        if current_state == STATE_AP_MODE:
            start_ap_mode()
            await start_web_server()
            break  # Exit the while loop to prevent continuous AP mode

        elif current_state == STATE_CONNECTED:
            print("Device is in operational mode.")
            await asyncio.sleep(1)  # Placeholder for operational tasks

        elif current_state == STATE_ERROR:
            print("Handling error state. Retrying connection...")
            set_led_blinking_error()  # Blink the LED in error state pattern
            retry_count = 0  # Reset the retry count for error handling

            while retry_count < 10:
                if await connect_to_wifi():
                    current_state = STATE_CONNECTED
                    set_led_on()  # Indicate successful connection
                    print("Reconnected successfully.")
                    break
                else:
                    print(f"Error retry {retry_count + 1}: Still unable to connect.")
                    retry_count += 1
                    await asyncio.sleep(5)  # Wait 5 seconds before retrying

            if retry_count >= 10:
                print("Max retries reached during error state. Continuing retries...")
                # Continue in error state, retry indefinitely until reset

        await asyncio.sleep(1)

# Button press detection for resetting Wi-Fi configuration
def reset_wifi_config():
    if is_button_pressed():
        press_start = time.time()  # Record the time when the button is first pressed
        while is_button_pressed():  # Wait for the button release
            if time.time() - press_start >= 5:  # If pressed for more than 5 seconds
                print("Resetting Wi-Fi configuration")
                if CONFIG_FILE in os.listdir():
                    os.remove(CONFIG_FILE)
                machine.reset()
        print("Button press too short for reset. Rebooting the device.")
        machine.reset()  # Reboot if pressed for a short time but not long enough for reset

# Main Function to Run the Program
async def main():
    global current_state
    current_state = STATE_CLIENT_MODE  # Initialize state
    await run_state_machine()

# Start the main function
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Program terminated.")
finally:
    # Clean-up operations can be added here
    set_led_off()
