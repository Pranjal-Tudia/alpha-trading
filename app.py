import os
import json
import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import google.generativeai as genai
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alpha-trading-super-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    wallet_balance = db.Column(db.Float, default=100000.0)

class PortfolioItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    avg_price = db.Column(db.Float, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables for Gunicorn deployment
with app.app_context():
    db.create_all()

# --- GLOBAL VARIABLES & BOT LOGIC ---
TICKER = 'AAPL'
LATEST_DATA = {}
CHAT_SESSION = {} # Dict to hold sessions per user

def init_trading_bot(ticker_symbol):
    global TICKER, LATEST_DATA
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
    
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    data['MACD'] = exp1 - exp2
    
    data['Daily_Return'] = data['Close'].pct_change()
    data.dropna(inplace=True)

    data['Future_Close'] = data['Close'].shift(-3)
    data['Future_Return'] = (data['Future_Close'] - data['Close']) / data['Close']
    def categorize_return(ret):
        if ret > 0.01: return 1
        elif ret < -0.01: return -1
        else: return 0
    data['Target'] = data['Future_Return'].apply(categorize_return)
    
    last_date = data.index[-1]
    last_row = data.iloc[-1]
    
    all_dates = data.index.strftime('%b %d, %Y').tolist()
    all_prices = [float(x) for x in data['Close'].tolist()]

    data.dropna(inplace=True)

    features = ['Close', 'SMA_20', 'RSI', 'Daily_Return']
    X = data[features]
    y = data['Target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    today_features = pd.DataFrame([last_row[features]])
    pred = model.predict(today_features)[0]
    
    try:
        raw_news = yf.Ticker(TICKER).news
        news_data = [{'title': n.get('title', ''), 'publisher': n.get('publisher', ''), 'link': n.get('link', '')} for n in raw_news[:3]]
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
    
    # Reset chat sessions globally when ticker changes
    CHAT_SESSION.clear()
    return LATEST_DATA

# --- AUTHENTICATION ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login failed. Check your username and password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- MAIN ROUTES ---
@app.route('/')
@login_required
def home():
    if not LATEST_DATA:
        init_trading_bot(TICKER)
        
    # Get user's portfolio and format it for JS
    user_portfolio = PortfolioItem.query.filter_by(user_id=current_user.id).all()
    portfolio_dict = {}
    for item in user_portfolio:
        portfolio_dict[item.ticker] = {'shares': item.shares, 'avgPrice': item.avg_price}
        
    return render_template('index.html', data=LATEST_DATA, user=current_user, portfolio=portfolio_dict)

@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze_stock():
    req = request.json
    ticker = req.get('ticker')
    if not ticker: return jsonify({'error': 'Ticker is required'}), 400
    try:
        new_data = init_trading_bot(ticker)
        return jsonify(new_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/live_price', methods=['POST'])
@login_required
def live_price():
    ticker = request.json.get('ticker')
    try:
        info = yf.Ticker(ticker).fast_info
        return jsonify({'ticker': ticker, 'price': float(info['last_price']), 'volume': int(info['last_volume'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/watchlist', methods=['POST'])
@login_required
def watchlist():
    tickers = request.json.get('tickers', [])
    results = []
    try:
        data = yf.download(tickers, period="5d", interval="1d", group_by="ticker", threads=True)
        for t in tickers:
            try:
                df = data if len(tickers) == 1 else data[t]
                df = df.dropna()
                if len(df) >= 2:
                    curr, prev = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
                    results.append({'ticker': t, 'current': curr, 'change': ((curr - prev) / prev) * 100})
            except Exception: pass
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# --- SECURE TRADING ENDPOINT ---
@app.route('/api/trade', methods=['POST'])
@login_required
def trade():
    req = request.json
    action = req.get('action') # 'BUY' or 'SELL'
    ticker = req.get('ticker')
    price = float(req.get('price'))
    shares_to_trade = int(req.get('shares', 10))
    
    total_cost = price * shares_to_trade
    
    # Check if user already owns this asset
    portfolio_item = PortfolioItem.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    
    if action == 'BUY':
        if current_user.wallet_balance < total_cost:
            return jsonify({'error': 'Insufficient funds.'}), 400
            
        current_user.wallet_balance -= total_cost
        
        if portfolio_item:
            # Calculate new average price
            total_value = (portfolio_item.shares * portfolio_item.avg_price) + total_cost
            portfolio_item.shares += shares_to_trade
            portfolio_item.avg_price = total_value / portfolio_item.shares
        else:
            new_item = PortfolioItem(user_id=current_user.id, ticker=ticker, shares=shares_to_trade, avg_price=price)
            db.session.add(new_item)
            
    elif action == 'SELL':
        if not portfolio_item or portfolio_item.shares < shares_to_trade:
            return jsonify({'error': 'Insufficient shares to sell.'}), 400
            
        current_user.wallet_balance += total_cost
        portfolio_item.shares -= shares_to_trade
        
        if portfolio_item.shares == 0:
            db.session.delete(portfolio_item)
            
    else:
        return jsonify({'error': 'Invalid action'}), 400

    db.session.commit()
    
    # Return updated wallet and portfolio
    user_portfolio = PortfolioItem.query.filter_by(user_id=current_user.id).all()
    portfolio_dict = {item.ticker: {'shares': item.shares, 'avgPrice': item.avg_price} for item in user_portfolio}
    
    return jsonify({
        'success': True,
        'wallet_balance': current_user.wallet_balance,
        'portfolio': portfolio_dict,
        'message': f"Successfully {action}ED {shares_to_trade} shares of {ticker}."
    })

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    user_msg = request.json.get('message')
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "paste_your_key_here_without_quotes":
        return jsonify({'error': 'API Key missing.'}), 400
        
    try:
        genai.configure(api_key=api_key)
        user_id = current_user.id
        
        if user_id not in CHAT_SESSION:
            ai_model = genai.GenerativeModel('gemini-flash-latest')
            sys_prompt = f"You are Alpha. {TICKER}: Close: ${LATEST_DATA['close']}, RSI: {LATEST_DATA['rsi']:.2f}. Predict: {LATEST_DATA['prediction']}."
            CHAT_SESSION[user_id] = ai_model.start_chat(history=[{"role": "user", "parts": [sys_prompt]}, {"role": "model", "parts": ["I am Alpha. Ready!"]}])
            
        response = CHAT_SESSION[user_id].send_message(user_msg)
        return jsonify({'reply': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_trading_bot(TICKER)
    app.run(debug=True, port=5000, host="0.0.0.0")
