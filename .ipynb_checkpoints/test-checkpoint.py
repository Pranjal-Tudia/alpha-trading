import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

TICKER = 'AAPL'
print(f"Downloading data for {TICKER}...")
data = yf.download(TICKER, period='5y', interval='1d')

if isinstance(data.columns, pd.MultiIndex):
    data.columns = [col[0] for col in data.columns]

data.dropna(inplace=True)
print("Data downloaded successfully!")

# Cell 2
data['SMA_20'] = data['Close'].rolling(window=20).mean()
delta = data['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
data['RSI'] = 100 - (100 / (1 + rs))
data['Daily_Return'] = data['Close'].pct_change()
data.dropna(inplace=True)

# Cell 3
data['Future_Close'] = data['Close'].shift(-3)
data['Future_Return'] = (data['Future_Close'] - data['Close']) / data['Close']
def categorize_return(ret):
    if ret > 0.01:
        return 1
    elif ret < -0.01:
        return -1
    else:
        return 0

data['Target'] = data['Future_Return'].apply(categorize_return)
data.dropna(inplace=True)

# Cell 4
features = ['Close', 'SMA_20', 'RSI', 'Daily_Return']
X = data[features]
y = data['Target']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Cell 5
predictions = model.predict(X_test)
print(f"Accuracy: {accuracy_score(y_test, predictions) * 100:.2f}%")
