import os
import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Global variables
TICKER = 'AAPL'
LATEST_DATA = {}
CHAT_SESSION = None

def init_trading_bot(ticker_symbol):
    global TICKER, LATEST_DATA, CHAT_SESSION
    TICKER = ticker_symbol.upper()
    print(f"Initializing Trading Bot for {TICKER}...")
    
    data = yf.download(TICKER, period='5y', interval='1d')
    if data.empty:
        raise ValueError(f"No data found for {TICKER}. It might be delisted or invalid.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
    data.dropna(inplace=True)

    # Feature Engineering
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    # Calculate MACD
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    data['MACD'] = exp1 - exp2
    
    data['Daily_Return'] = data['Close'].pct_change()
    data.dropna(inplace=True)

    # Target Definition
    data['Future_Close'] = data['Close'].shift(-3)
    data['Future_Return'] = (data['Future_Close'] - data['Close']) / data['Close']
    def categorize_return(ret):
        if ret > 0.01: return 1
        elif ret < -0.01: return -1
        else: return 0
    data['Target'] = data['Future_Return'].apply(categorize_return)
    
    last_date = data.index[-1]
    last_row = data.iloc[-1]
    
    # Store full historical data for frontend timeframe slicing
    all_dates = data.index.strftime('%b %d, %Y').tolist()
    all_prices = [float(x) for x in data['Close'].tolist()]

    data.dropna(inplace=True)

    # Train Model
    features = ['Close', 'SMA_20', 'RSI', 'Daily_Return']
    X = data[features]
    y = data['Target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Predict today's signal
    today_features = pd.DataFrame([last_row[features]])
    pred = model.predict(today_features)[0]
    
    # Fetch News
    try:
        raw_news = yf.Ticker(TICKER).news
        # Take top 3 news articles
        news_data = []
        for n in raw_news[:3]:
            news_data.append({
                'title': n.get('title', ''),
                'publisher': n.get('publisher', ''),
                'link': n.get('link', '')
            })
    except Exception:
        news_data = []
        
    LATEST_DATA = {
        'ticker': TICKER,
        'date': last_date.strftime('%Y-%m-%d'),
        'close': float(last_row['Close']),
        'sma': float(last_row['SMA_20']),
        'rsi': float(last_row['RSI']),
        'macd': float(last_row['MACD']),
        'volume': int(last_row['Volume']),
        'prediction': "BUY" if pred == 1 else ("SELL" if pred == -1 else "HOLD"),
        'chart_dates': all_dates,
        'chart_prices': all_prices,
        'news': news_data
    }
    
    # Reset chat session because the stock changed
    CHAT_SESSION = None
    print(f"Bot Initialization Complete for {TICKER}!")
    return LATEST_DATA

@app.route('/')
def home():
    if not LATEST_DATA:
        init_trading_bot(TICKER)
    return render_template('index.html', data=LATEST_DATA)

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    req = request.json
    ticker = req.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
    try:
        new_data = init_trading_bot(ticker)
        return jsonify(new_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/live_price', methods=['POST'])
def live_price():
    req = request.json
    ticker = req.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return jsonify({
            'ticker': ticker,
            'price': float(info['last_price']),
            'volume': int(info['last_volume'])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/watchlist', methods=['POST'])
def watchlist():
    req = request.json
    tickers = req.get('tickers', [])
    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400
    
    results = []
    try:
        # Download batch data for last 2 days to calculate % change
        data = yf.download(tickers, period="5d", interval="1d", group_by="ticker", threads=True)
        for t in tickers:
            try:
                # Handle single ticker edge case vs multi-ticker
                if len(tickers) == 1:
                    df = data
                else:
                    df = data[t]
                
                df = df.dropna()
                if len(df) >= 2:
                    current = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    change_pct = ((current - prev) / prev) * 100
                    results.append({
                        'ticker': t,
                        'current': current,
                        'change': change_pct
                    })
            except Exception:
                pass
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    global CHAT_SESSION
    req = request.json
    user_msg = req.get('message')
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "paste_your_key_here_without_quotes":
        return jsonify({'error': 'API Key is missing on the server. Please add it to the .env file.'}), 400
        
    try:
        genai.configure(api_key=api_key)
        
        if CHAT_SESSION is None:
            ai_model = genai.GenerativeModel('gemini-flash-latest')
            system_prompt = f"You are an elite, highly-paid Wall Street Quantitative Analyst named 'Alpha'. You are giving advice to your top client. Here is the current stock data for {TICKER}: Close: ${LATEST_DATA['close']:.2f}, SMA: ${LATEST_DATA['sma']:.2f}, RSI: {LATEST_DATA['rsi']:.2f}. Your proprietary Machine Learning model's prediction is {LATEST_DATA['prediction']}. Format your response using markdown with bullet points and bold text. Keep it extremely concise, highly confident, and use relevant emojis (like 📈, 🚨, 💎, 📉) to emphasize your points."
            
            CHAT_SESSION = ai_model.start_chat(history=[
                {"role": "user", "parts": [system_prompt]},
                {"role": "model", "parts": [f"Understood. I am Alpha. I have analyzed {TICKER} and am ready to advise the client! 📈"]}
            ])
            
        response = CHAT_SESSION.send_message(user_msg)
        return jsonify({'reply': response.text})
    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg or 'not found' in error_msg.lower():
            try:
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                error_msg = f"Your Google account region or API key does not support the default model.\\n\\nHowever, your API key DOES have access to these models: {', '.join(available_models)}\\n\\nPlease reply with the name of a model from that list, and I will update the code to use it!"
            except Exception:
                pass
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    init_trading_bot(TICKER)
    app.run(debug=True, port=5000)
