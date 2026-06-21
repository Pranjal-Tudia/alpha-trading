const STOCKS_DB = [
    { name: "Apple Inc.", ticker: "AAPL", current: 189.24, change: 1.2 },
    { name: "Microsoft Corporation", ticker: "MSFT", current: 415.32, change: 0.8 },
    { name: "NVIDIA Corporation", ticker: "NVDA", current: 890.11, change: -1.5 },
    { name: "Alphabet Inc.", ticker: "GOOGL", current: 175.43, change: 0.4 },
    { name: "Amazon.com Inc.", ticker: "AMZN", current: 182.50, change: -0.2 },
    { name: "Meta Platforms", ticker: "META", current: 485.12, change: 2.1 },
    { name: "Tesla Inc.", ticker: "TSLA", current: 175.22, change: -3.4 },
    { name: "Berkshire Hathaway", ticker: "BRK-B", current: 405.12, change: 0.1 },
    { name: "Eli Lilly", ticker: "LLY", current: 750.32, change: 1.5 },
    { name: "Broadcom", ticker: "AVGO", current: 1300.50, change: 2.3 },
    { name: "JPMorgan Chase", ticker: "JPM", current: 195.40, change: -0.5 },
    { name: "Bitcoin USD", ticker: "BTC-USD", current: 67210.00, change: 4.5 },
    { name: "Ethereum USD", ticker: "ETH-USD", current: 3500.20, change: 2.8 },
    { name: "S&P 500 ETF", ticker: "VOO", current: 478.10, change: 0.5 },
    { name: "Reliance Industries", ticker: "RELIANCE.NS", current: 2900.50, change: 1.5 },
    { name: "Tata Consultancy", ticker: "TCS.NS", current: 4050.20, change: -0.8 }
];

document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chat-window');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    // Dashboard elements
    const tickerInput = document.getElementById('ticker-input');
    const dashTicker = document.getElementById('dash-ticker');
    const dashDate = document.getElementById('dash-date');
    const dashClose = document.getElementById('dash-close');
    const dashRsi = document.getElementById('dash-rsi');
    const dashSma = document.getElementById('dash-sma');
    const dashMacd = document.getElementById('dash-macd');
    const dashVolume = document.getElementById('dash-volume');
    const dashSignal = document.getElementById('dash-signal');
    const autocompleteList = document.getElementById('autocomplete-list');
    const watchlistList = document.getElementById('watchlist-list');
    
    // News Elements
    const newsList = document.getElementById('news-list');
    const dashSentiment = document.getElementById('dash-sentiment');

    // Portfolio State (Loaded from Server)
    let walletBalance = window.INITIAL_WALLET || 100000.00;
    let portfolio = window.INITIAL_PORTFOLIO || {}; 

    const walletBalanceEl = document.getElementById('wallet-balance');
    const walletPnlEl = document.getElementById('wallet-pnl');
    const holdingsInfoEl = document.getElementById('holdings-info');
    const holdAmountEl = document.getElementById('hold-amount');
    const holdPnlEl = document.getElementById('hold-pnl');

    // Update Wallet UI
    function updateWalletUI(currentTickerPrice) {
        walletBalanceEl.textContent = "$" + walletBalance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        // Calculate open PNL across all portfolio items (simplified: we just check current ticker for now if we hold it)
        const currentTicker = dashTicker.textContent;
        if (portfolio[currentTicker]) {
            const pos = portfolio[currentTicker];
            const currentVal = pos.shares * currentTickerPrice;
            const costBasis = pos.shares * pos.avgPrice;
            const pnl = currentVal - costBasis;
            
            holdingsInfoEl.style.display = 'flex';
            holdAmountEl.textContent = `${pos.shares} Shares`;
            holdPnlEl.textContent = (pnl >= 0 ? "+" : "") + "$" + pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            holdPnlEl.className = 'hold-pnl ' + (pnl >= 0 ? 'pnl-positive' : 'pnl-negative');
            
            // Total PNL (simplified to just this active position for the demo)
            walletPnlEl.textContent = (pnl >= 0 ? "+" : "") + "$" + pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            walletPnlEl.className = 'value ' + (pnl >= 0 ? 'pnl-positive' : 'pnl-negative');
        } else {
            holdingsInfoEl.style.display = 'none';
            walletPnlEl.textContent = "$0.00";
            walletPnlEl.className = 'value pnl-neutral';
        }
    }

    // Modal Elements
    const tradeModal = document.getElementById('trade-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalAsset = document.getElementById('modal-asset');
    const modalAction = document.getElementById('modal-action');
    const modalPrice = document.getElementById('modal-price');
    const modalTotal = document.getElementById('modal-total');
    const modalBtnCancel = document.getElementById('modal-btn-cancel');
    const modalBtnConfirm = document.getElementById('modal-btn-confirm');
    
    let pendingTrade = null;

    modalBtnCancel.addEventListener('click', () => {
        tradeModal.style.display = 'none';
        pendingTrade = null;
    });

    modalBtnConfirm.addEventListener('click', async () => {
        if (!pendingTrade) return;
        
        const { type, ticker, price, cost } = pendingTrade;
        const originalText = modalBtnConfirm.textContent;
        modalBtnConfirm.textContent = "Processing...";
        modalBtnConfirm.disabled = true;
        
        try {
            const response = await fetch('/api/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: type, ticker: ticker, price: price, shares: 10 })
            });
            const data = await response.json();
            
            if (response.ok) {
                // Update local state from server truth
                walletBalance = data.wallet_balance;
                portfolio = data.portfolio;
                updateWalletUI(price);
                appendMessage(`**EXECUTED:** ${data.message}`, 'ai');
                tradeModal.style.display = 'none';
            } else {
                alert(`Trade Failed: ${data.error}`);
            }
        } catch (error) {
            alert(`Error processing trade: ${error}`);
        } finally {
            modalBtnConfirm.textContent = originalText;
            modalBtnConfirm.disabled = false;
            pendingTrade = null;
            if (!tradeModal.style.display || tradeModal.style.display === 'none') {
                tradeModal.style.display = 'none';
            }
        }
    });

    // Trade Buttons
    document.getElementById('btn-buy').addEventListener('click', () => {
        const currentTicker = dashTicker.textContent;
        const currentPrice = parseFloat(dashClose.textContent.replace('$', '').replace(/,/g, ''));
        if (!currentTicker || isNaN(currentPrice) || currentTicker === "Loading...") return;

        const cost = currentPrice * 10;
        if (walletBalance >= cost) {
            pendingTrade = { type: 'BUY', ticker: currentTicker, price: currentPrice, cost: cost };
            modalTitle.textContent = "Confirm Purchase";
            modalAsset.textContent = currentTicker;
            modalAction.textContent = "BUY 10 Shares";
            modalPrice.textContent = "$" + currentPrice.toFixed(2);
            modalTotal.textContent = "$" + cost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            modalBtnConfirm.textContent = "Confirm Purchase";
            modalBtnConfirm.className = "m-btn m-btn-confirm";
            tradeModal.style.display = 'flex';
        } else {
            alert("Insufficient Buying Power!");
        }
    });

    document.getElementById('btn-sell').addEventListener('click', () => {
        const currentTicker = dashTicker.textContent;
        const currentPrice = parseFloat(dashClose.textContent.replace('$', '').replace(/,/g, ''));
        if (!currentTicker || isNaN(currentPrice) || currentTicker === "Loading...") return;

        if (portfolio[currentTicker] && portfolio[currentTicker].shares >= 10) {
            const revenue = currentPrice * 10;
            pendingTrade = { type: 'SELL', ticker: currentTicker, price: currentPrice, cost: revenue };
            modalTitle.textContent = "Confirm Sale";
            modalAsset.textContent = currentTicker;
            modalAction.textContent = "SELL 10 Shares";
            modalPrice.textContent = "$" + currentPrice.toFixed(2);
            modalTotal.textContent = "$" + revenue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            modalBtnConfirm.textContent = "Confirm Sale";
            modalBtnConfirm.className = "m-btn m-btn-confirm sell-mode";
            tradeModal.style.display = 'flex';
        } else {
            alert("You don't own enough shares to sell!");
        }
    });


    // Populate Watchlist with LIVE DATA
    async function populateWatchlist() {
        watchlistList.innerHTML = '<li style="padding: 1rem 1.5rem; color: #888;">Fetching live market data...</li>';
        
        const shuffled = STOCKS_DB.sort(() => 0.5 - Math.random());
        const selected = shuffled.slice(0, 7);
        const tickersToFetch = selected.map(s => s.ticker);

        try {
            const response = await fetch('/api/watchlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers: tickersToFetch })
            });
            const data = await response.json();
            
            watchlistList.innerHTML = '';
            
            if (data.results && data.results.length > 0) {
                data.results.forEach(liveStock => {
                    const dbStock = selected.find(s => s.ticker === liveStock.ticker);
                    const name = dbStock ? dbStock.name.split(' ')[0] : liveStock.ticker;
                    
                    const li = document.createElement('li');
                    li.className = 'watchlist-item';
                    
                    const changeClass = liveStock.change >= 0 ? 'wl-positive' : 'wl-negative';
                    const changeSign = liveStock.change >= 0 ? '+' : '';

                    li.innerHTML = `
                        <div class="wl-left">
                            <span class="wl-ticker">${liveStock.ticker}</span>
                            <span class="wl-name">${name}</span>
                        </div>
                        <div class="wl-right">
                            <span class="wl-price">$${liveStock.current.toFixed(2)}</span>
                            <span class="wl-change ${changeClass}">${changeSign}${liveStock.change.toFixed(2)}%</span>
                        </div>
                    `;
                    
                    li.addEventListener('click', () => {
                        tickerInput.value = liveStock.ticker;
                        analyzeStock();
                    });

                    watchlistList.appendChild(li);
                });
            } else {
                watchlistList.innerHTML = '<li style="padding: 1rem 1.5rem; color: #ef4444;">Market data unavailable.</li>';
            }
        } catch (err) {
            watchlistList.innerHTML = '<li style="padding: 1rem 1.5rem; color: #ef4444;">Network Error.</li>';
        }
    }
    populateWatchlist();

    // Auto-Refresh Logic & Live Order Book
    let autoRefreshInterval = null;
    let orderBookInterval = null;
    let currentDashboardTicker = dashTicker.textContent;

    const obAsksEl = document.getElementById('ob-asks');
    const obBidsEl = document.getElementById('ob-bids');
    const obSpreadEl = document.getElementById('ob-spread');

    function simulateOrderBook(centerPrice) {
        if (isNaN(centerPrice) || centerPrice <= 0) return;
        
        obAsksEl.innerHTML = '';
        obBidsEl.innerHTML = '';
        
        const tickSize = centerPrice > 1000 ? 0.5 : (centerPrice > 100 ? 0.05 : 0.01);
        const spread = tickSize * (Math.floor(Math.random() * 3) + 1);
        
        const bestAsk = centerPrice + (spread/2);
        const bestBid = centerPrice - (spread/2);
        
        obSpreadEl.textContent = `$${spread.toFixed(2)} Spread`;

        // Generate Asks (going up from best ask)
        for(let i=0; i<6; i++) {
            const price = bestAsk + (i * tickSize);
            const size = Math.floor(Math.random() * 500) + 10;
            const row = document.createElement('div');
            row.className = 'ob-row';
            if (Math.random() > 0.7) row.classList.add('flash-ask');
            row.innerHTML = `<span class="ob-ask-price">${price.toFixed(2)}</span><span class="ob-size">${size}</span>`;
            obAsksEl.appendChild(row);
        }

        // Generate Bids (going down from best bid)
        for(let i=0; i<6; i++) {
            const price = bestBid - (i * tickSize);
            const size = Math.floor(Math.random() * 500) + 10;
            const row = document.createElement('div');
            row.className = 'ob-row';
            if (Math.random() > 0.7) row.classList.add('flash-bid');
            row.innerHTML = `<span class="ob-bid-price">${price.toFixed(2)}</span><span class="ob-size">${size}</span>`;
            obBidsEl.appendChild(row);
        }
    }

    // Start fast order book ticking
    orderBookInterval = setInterval(() => {
        const currentPriceText = dashClose.textContent.replace('$', '').replace(/,/g, '');
        simulateOrderBook(parseFloat(currentPriceText));
    }, 1200);

    // Initial Order Book
    setTimeout(() => {
        const p = parseFloat(dashClose.textContent.replace('$', '').replace(/,/g, ''));
        simulateOrderBook(p);
    }, 500);

    async function tickLivePrice() {
        if (!currentDashboardTicker || currentDashboardTicker === "Loading...") return;

        try {
            const response = await fetch('/api/live_price', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: currentDashboardTicker })
            });
            const data = await response.json();

            if (!data.error) {
                const newPrice = data.price;
                const oldPriceText = dashClose.textContent.replace('$', '').replace(/,/g, '');
                const oldPrice = parseFloat(oldPriceText);

                if (!isNaN(oldPrice) && newPrice !== oldPrice) {
                    dashClose.textContent = "$" + newPrice.toFixed(2);
                    
                    dashClose.classList.remove('flash-green', 'flash-red');
                    void dashClose.offsetWidth;
                    
                    if (newPrice > oldPrice) {
                        dashClose.classList.add('flash-green');
                    } else {
                        dashClose.classList.add('flash-red');
                    }
                }
                
                if (data.volume) {
                    dashVolume.textContent = data.volume.toLocaleString();
                }
                
                // Update wallet if we hold this
                updateWalletUI(newPrice);
            }
        } catch (e) {
            console.log("Live tick failed", e);
        }
    }

    autoRefreshInterval = setInterval(tickLivePrice, 8000);

    // Setup Chart
    let currentDates = window.ALL_CHART_DATES || [];
    let currentPrices = window.ALL_CHART_PRICES || [];

    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            const days = e.target.getAttribute('data-days');
            let slicedDates = [];
            let slicedPrices = [];

            if (days === 'all' || currentDates.length === 0) {
                slicedDates = currentDates;
                slicedPrices = currentPrices;
            } else {
                const limit = parseInt(days);
                slicedDates = currentDates.slice(-limit);
                slicedPrices = currentPrices.slice(-limit);
            }
            
            updateChart(slicedDates, slicedPrices);
        });
    });

    // Autocomplete Logic
    tickerInput.addEventListener('input', function() {
        const val = this.value.trim().toLowerCase();
        autocompleteList.innerHTML = '';
        
        if (!val) {
            autocompleteList.style.display = 'none';
            return;
        }
        
        let matchCount = 0;
        STOCKS_DB.forEach(stock => {
            if (stock.name.toLowerCase().includes(val) || stock.ticker.toLowerCase().includes(val)) {
                if (matchCount < 8) {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${stock.name}</strong> <span style="color:#666; font-size:0.85em;">(${stock.ticker})</span>`;
                    li.addEventListener('click', () => {
                        tickerInput.value = stock.ticker;
                        autocompleteList.style.display = 'none';
                        analyzeStock();
                    });
                    autocompleteList.appendChild(li);
                    matchCount++;
                }
            }
        });
        
        autocompleteList.style.display = matchCount > 0 ? 'block' : 'none';
    });

    document.addEventListener('click', function(e) {
        if (e.target !== tickerInput && e.target !== autocompleteList) {
            autocompleteList.style.display = 'none';
        }
    });

    const ctx = document.getElementById('priceChart').getContext('2d');
    Chart.defaults.color = '#555';
    Chart.defaults.font.family = 'Outfit';
    
    let priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Price',
                data: [],
                borderColor: '#00f2fe',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointBackgroundColor: '#00f2fe'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#111',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#333',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false
                }
            },
            scales: {
                x: { grid: { display: false, drawBorder: false }, ticks: { maxRotation: 0 } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false }, ticks: { callback: function(value) { return '$' + value; } }, border: { display: false } }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false }
        }
    });

    function updateChart(dates, prices) {
        priceChart.data.labels = dates;
        priceChart.data.datasets[0].data = prices;
        
        if (prices.length > 0) {
            const firstPrice = prices[0];
            const lastPrice = prices[prices.length - 1];
            if (lastPrice >= firstPrice) {
                priceChart.data.datasets[0].borderColor = '#10b981';
                priceChart.data.datasets[0].pointBackgroundColor = '#10b981';
            } else {
                priceChart.data.datasets[0].borderColor = '#ef4444';
                priceChart.data.datasets[0].pointBackgroundColor = '#ef4444';
            }
        }
        priceChart.update();
    }
    
    if (currentPrices.length > 0) {
        updateChart(currentDates.slice(-21), currentPrices.slice(-21));
    }

    function appendMessage(text, sender) {
        const wrapperDiv = document.createElement('div');
        wrapperDiv.classList.add('message-wrapper', sender === 'user' ? 'user-wrapper' : 'ai-wrapper');
        
        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('avatar');
        avatarDiv.innerHTML = sender === 'ai' ? '<i class="fa-solid fa-robot"></i>' : '<i class="fa-solid fa-user"></i>';
        
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender === 'user' ? 'user-message' : 'ai-message');
        
        if (sender === 'ai') {
            msgDiv.innerHTML = marked.parse(text);
        } else {
            msgDiv.textContent = text;
        }
        
        wrapperDiv.appendChild(avatarDiv);
        wrapperDiv.appendChild(msgDiv);
        
        chatWindow.appendChild(wrapperDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    async function analyzeStock() {
        const ticker = tickerInput.value.trim();
        if (!ticker) return;

        const oldTicker = dashTicker.textContent;
        dashTicker.textContent = "Loading...";

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: ticker })
            });
            const data = await response.json();

            if (data.error) {
                alert("Error: " + data.error);
                dashTicker.textContent = oldTicker;
            } else {
                dashTicker.textContent = data.ticker;
                dashDate.textContent = data.date;
                dashClose.textContent = "$" + data.close.toFixed(2);
                dashRsi.textContent = data.rsi.toFixed(2);
                dashSma.textContent = "$" + data.sma.toFixed(2);
                dashMacd.textContent = data.macd ? data.macd.toFixed(2) : "N/A";
                dashVolume.textContent = data.volume ? data.volume.toLocaleString() : "N/A";
                dashSignal.textContent = data.prediction;

                dashSignal.className = 'signal-badge'; 
                if(data.prediction === 'BUY') dashSignal.classList.add('signal-buy');
                else if(data.prediction === 'SELL') dashSignal.classList.add('signal-sell');
                else dashSignal.classList.add('signal-hold');

                currentDates = data.chart_dates;
                currentPrices = data.chart_prices;

                const activeBtn = document.querySelector('.tf-btn.active');
                const days = activeBtn ? activeBtn.getAttribute('data-days') : '21';
                
                let slicedDates = currentDates;
                let slicedPrices = currentPrices;

                if (days !== 'all') {
                    const limit = parseInt(days);
                    slicedDates = currentDates.slice(-limit);
                    slicedPrices = currentPrices.slice(-limit);
                }

                updateChart(slicedDates, slicedPrices);
                
                // Update News
                newsList.innerHTML = '';
                if (data.news && data.news.length > 0) {
                    data.news.forEach(n => {
                        newsList.innerHTML += `<li><a href="${n.link}" target="_blank" class="news-title">${n.title}</a><span class="news-pub">${n.publisher}</span></li>`;
                    });
                } else {
                    newsList.innerHTML = `<li><span class="news-title" style="color:#666;">No recent news found.</span></li>`;
                }
                
                // Update Sentiment Badge
                dashSentiment.className = 'badge';
                if(data.prediction === 'BUY') {
                    dashSentiment.classList.add('badge-bullish');
                    dashSentiment.textContent = "BULLISH";
                } else if(data.prediction === 'SELL') {
                    dashSentiment.classList.add('badge-bearish');
                    dashSentiment.textContent = "BEARISH";
                } else {
                    dashSentiment.classList.add('badge-neutral');
                    dashSentiment.textContent = "NEUTRAL";
                }

                currentDashboardTicker = data.ticker;
                
                // Reset order book
                simulateOrderBook(data.close);
                
                // Update wallet view
                updateWalletUI(data.close);

                chatWindow.innerHTML = '';
                appendMessage(`Greetings. I am Alpha. I have just finished crunching the numbers on ${data.ticker}. 📈 What's our next move?`, 'ai');
            }
        } catch (error) {
            alert("Network Error: Could not reach the server to analyze the stock.");
            dashTicker.textContent = oldTicker;
        }
        tickerInput.value = '';
    }

    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') analyzeStock();
    });

    document.querySelectorAll('.quick-reply-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            chatInput.value = btn.textContent;
            sendMessage();
        });
    });

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        appendMessage(text, 'user');
        chatInput.value = '';

        const wrapperDiv = document.createElement('div');
        wrapperDiv.classList.add('message-wrapper', 'ai-wrapper', 'typing-message');
        
        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('avatar');
        avatarDiv.innerHTML = '<i class="fa-solid fa-robot"></i>';
        
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', 'ai-message');
        msgDiv.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        
        wrapperDiv.appendChild(avatarDiv);
        wrapperDiv.appendChild(msgDiv);
        
        chatWindow.appendChild(wrapperDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            chatWindow.removeChild(wrapperDiv);

            if (data.error) {
                appendMessage('**Error:** ' + data.error, 'ai');
            } else {
                appendMessage(data.reply, 'ai');
            }
        } catch (error) {
            chatWindow.removeChild(wrapperDiv);
            appendMessage('**Network Error:** Could not connect to server.', 'ai');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});
