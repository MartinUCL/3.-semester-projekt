import json
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib

# Step 1: Load the data from the JSON file
with open('ml_data.json') as f:
    data = json.load(f)

# Convert the loaded JSON data to a pandas DataFrame
df = pd.DataFrame(data)

# Check if 'timestamp' is a valid column in the DataFrame
if 'timestamp' not in df.columns:
    raise KeyError("The 'timestamp' column is missing from the dataset.")

# Step 2: Feature extraction from the timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['hour'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month'] = df['timestamp'].dt.month

# Drop the original timestamp column (if you want to keep it for sorting, comment this out)
# df = df.drop('timestamp', axis=1)

# Step 3: Handle NaN values
df = df.dropna(subset=['west_price', 'east_price'])

# **Reverse the dataset** - Uncomment the next two lines if you want to reverse it
df = df.sort_values('timestamp')  # Ensure it’s sorted in chronological order
df = df.reset_index(drop=True)     # Reset index after sorting

# Step 4: Define the feature matrix (X) and the target vector (y)
X = df[['cloud_cover', 'temperature', 'hour', 'day_of_week', 'month']]
y = df[['west_price', 'east_price']]

# Step 5: Train-test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, shuffle=True)

# Step 6: Feature scaling
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Step 7: Initialize the RandomForestRegressor model
print("Training model...")
model = MultiOutputRegressor(RandomForestRegressor(n_estimators=100, max_depth=10))

# Train the model
model.fit(X_train_scaled, y_train)

# Make predictions
y_pred = model.predict(X_test_scaled)

# Step 8: Evaluate the model
mse_west = mean_squared_error(y_test['west_price'], y_pred[:, 0])
mse_east = mean_squared_error(y_test['east_price'], y_pred[:, 1])
print(f'West Price Mean Squared Error: {mse_west}')
print(f'East Price Mean Squared Error: {mse_east}')

# Step 9: Save the model and the scaler
joblib.dump(model, 'multi_output_model.pkl')
joblib.dump(scaler, 'scaler.pkl')
