import nbformat as nbf

nb = nbf.v4.new_notebook()

# Markdown Cell 1
md1 = nbf.v4.new_markdown_cell("""# Algorithmic Trading Bot (Buy/Sell/Hold)
This notebook builds a classification model to predict trading signals based on technical indicators.

## Step 1: Setup & Data Gathering
First, we will import our libraries and download historical stock data using `yfinance`.""")

# Code Cell 1
code1 = nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

# You can change the ticker to any stock (e.g., 'AAPL', 'RELIANCE.NS') or crypto ('BTC-USD')
TICKER = 'AAPL'

# Download the last 5 years of daily data
print(f"Downloading data for {TICKER}...")
data = yf.download(TICKER, period='5y', interval='1d')

# If the data has a MultiIndex column (common with newer yfinance versions), flatten it
if isinstance(data.columns, pd.MultiIndex):
    data.columns = [col[0] for col in data.columns]

data.dropna(inplace=True)
print("Data downloaded successfully!")
data.tail()""")

# Markdown Cell 2
md2 = nbf.v4.new_markdown_cell("""## Step 2: Feature Engineering (The "Trader" Math)
We need to give the AI some context about the stock's momentum. We will calculate:
* **SMA (Simple Moving Average):** A 20-day average price.
* **RSI (Relative Strength Index):** A momentum indicator (0-100) that tells us if a stock is overbought (>70) or oversold (<30).""")

# Code Cell 2
code2 = nbf.v4.new_code_cell("""# 1. Simple Moving Average (20 days)
data['SMA_20'] = data['Close'].rolling(window=20).mean()

# 2. Relative Strength Index (RSI - 14 days)
delta = data['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
data['RSI'] = 100 - (100 / (1 + rs))

# 3. Daily Return percentage
data['Daily_Return'] = data['Close'].pct_change()

# Drop rows with NaN values created by rolling windows
data.dropna(inplace=True)
data.tail()""")

# Markdown Cell 3
md3 = nbf.v4.new_markdown_cell("""## Step 3: Defining the Target Variable (Buy/Sell/Hold)
We need to tell the model what a "good" trade looks like. 
We will look 3 days into the future. 
* If the price goes UP by more than 1%, we label it **BUY (1)**.
* If the price goes DOWN by more than 1%, we label it **SELL (-1)**.
* Otherwise, we label it **HOLD (0)**.""")

# Code Cell 3
code3 = nbf.v4.new_code_cell("""# Shift the close price backwards to get the future price
data['Future_Close'] = data['Close'].shift(-3)

# Calculate the future return percentage
data['Future_Return'] = (data['Future_Close'] - data['Close']) / data['Close']

# Define the condition
def categorize_return(ret):
    if ret > 0.01:
        return 1  # BUY
    elif ret < -0.01:
        return -1 # SELL
    else:
        return 0  # HOLD

data['Target'] = data['Future_Return'].apply(categorize_return)

# Drop the last 3 rows because we don't know their future yet
data.dropna(inplace=True)

print("Target variable counts:")
print(data['Target'].value_counts())""")

# Markdown Cell 4
md4 = nbf.v4.new_markdown_cell("""## Step 4: Train the Classification Model
We will use a **Random Forest Classifier**. It will look at our features (RSI, SMA, Daily Return) and try to guess the Target (Buy/Sell/Hold).""")

# Code Cell 4
code4 = nbf.v4.new_code_cell("""# Define our input features (X) and our target (y)
features = ['Close', 'SMA_20', 'RSI', 'Daily_Return']
X = data[features]
y = data['Target']

# Split the data into Training (80%) and Testing (20%) sets
# We use shuffle=False to keep the dates in order!
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# Create and train the model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print("Model training complete!")""")

# Markdown Cell 5
md5 = nbf.v4.new_markdown_cell("""## Step 5: Evaluate Model and Plot Results
Let's see how well our AI performed on the test data. We will also plot a graph showing the exact dates the model told us to BUY.""")

# Code Cell 5
code5 = nbf.v4.new_code_cell("""# Make predictions on the test set
predictions = model.predict(X_test)

# Print accuracy and classification report
print(f"Accuracy: {accuracy_score(y_test, predictions) * 100:.2f}%")
print("\\nClassification Report:")
print(classification_report(y_test, predictions, target_names=['SELL', 'HOLD', 'BUY']))

# Add predictions to our test dataframe for plotting
test_data = data.iloc[X_test.index.copy()].copy()
test_data['Prediction'] = predictions

# PLOTTING
plt.figure(figsize=(14, 7))
plt.plot(test_data.index, test_data['Close'], label='Close Price', alpha=0.5)

# Highlight BUY signals
buy_signals = test_data[test_data['Prediction'] == 1]
plt.scatter(buy_signals.index, buy_signals['Close'], label='Predicted BUY', marker='^', color='green', s=100)

# Highlight SELL signals
sell_signals = test_data[test_data['Prediction'] == -1]
plt.scatter(sell_signals.index, sell_signals['Close'], label='Predicted SELL', marker='v', color='red', s=100)

plt.title(f'Algorithmic Trading Bot Signals for {TICKER}')
plt.xlabel('Date')
plt.ylabel('Price')
plt.legend()
plt.show()""")

nb.cells = [md1, code1, md2, code2, md3, code3, md4, code4, md5, code5]

with open('Trading_Bot.ipynb', 'w') as f:
    nbf.write(nb, f)
print("Notebook Trading_Bot.ipynb created successfully.")
