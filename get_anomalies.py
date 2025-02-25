import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

# SQL query to select time series data
query = """
SELECT pod, memory, timestamp
FROM memory WHERE pod='memory-demo-ctr' AND namespace='default'
ORDER BY timestamp
"""

# Read the SQL query into a pandas DataFrame
conn = sqlite3.connect("/Users/surabhi.kumar/go/src/github.com/stackrox/k8s-anomaly-detection/k8s_logs.db")
data = pd.read_sql_query(query, conn, parse_dates=['timestamp'])
data['memory'] = data['memory'].str[:-2].fillna(0).astype(int)
conn.close()
data.to_csv("/Users/surabhi.kumar/go/src/github.com/stackrox/k8s-anomaly-detection/data.csv",index=False)

data.set_index('timestamp', inplace=True)

# Check for stationarity
def test_stationarity(timeseries):
    result = adfuller(timeseries, autolag='AIC')
    print('ADF Statistic:', result[0])
    print('p-value:', result[1])
    return result

result = test_stationarity(data['memory'])

# Differencing if needed
if result[1] > 0.05:
    data['diff'] = data['memory'].diff()
    data = data.dropna()

# Fit ARIMA model
model = ARIMA(data['memory'], order=(1,1,1))  # Adjust (p,d,q) as needed
results = model.fit()

# Forecast the next 20 periods (adjust as needed)
forecast_steps = 5
forecast_obj = results.get_forecast(steps=forecast_steps)

# Obtain a summary frame including forecast mean and confidence intervals (default is 95% CI)
forecast_df = forecast_obj.summary_frame(alpha=0.05)

# Extract the forecasted mean, lower, and upper confidence intervals
forecast_mean = forecast_df['mean']
forecast_lower = forecast_df['mean_ci_lower']
forecast_upper = forecast_df['mean_ci_upper']

# Create a new datetime index for the forecast if your data has a known frequency
last_date = data.index[-1]
forecast_index = pd.date_range(start=last_date + pd.Timedelta(hours=1), periods=forecast_steps, freq='1h')
forecast_mean.index = forecast_index
forecast_lower.index = forecast_index
forecast_upper.index = forecast_index

#Plot the Actual Values and Forecast with Confidence Bands

plt.figure(figsize=(12, 6))

# Plot actual historical data
plt.plot(data.index, data['memory'], label='Actual Values', color='blue')

# Plot forecasted values
plt.plot(forecast_mean.index, forecast_mean, label='Forecast', color='red', linestyle='--')

# Shade the confidence interval area between the lower and upper bands
plt.fill_between(forecast_mean.index, forecast_lower, forecast_upper, color='pink', alpha=0.3,
                 label='95% Confidence Interval')

plt.xlabel('Date')
plt.ylabel('Memory KB')
plt.title('ARIMA Forecast with Confidence Intervals')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()