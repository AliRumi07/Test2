from datetime import datetime, timedelta
import asyncio
import websockets
import json
from flask import Flask, render_template_string
from threading import Thread
import time

# Customizable variables
Timeframe_15m = '15m'
Timeframe_5m = '5m'
portfolio_balance = 1000
trade_amount = 100
leverage_x = 10
fee_rate = 0.001
risk_reward_ratio = 1.5

# Add the Pair variable
Pairs = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "TONUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT"
]

app = Flask(__name__)

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.positions = {pair: None for pair in pairs}
        self.entry_prices = {pair: None for pair in pairs}
        self.stop_loss_prices = {pair: None for pair in pairs}
        self.take_profit_prices = {pair: None for pair in pairs}
        self.total_trades = 0
        self.trades_in_profit = 0
        self.trades_in_loss = 0
        self.total_profit_loss = 0
        self.max_drawdown = 0
        self.lowest_balance = portfolio_balance
        self.candle_15m = {pair: None for pair in pairs}
        self.candle_5m = {pair: None for pair in pairs}
        self.last_15m_close_time = {pair: None for pair in pairs}

        self.pair_stats = {pair: {
            'Price': 0,
            'Position': 'None',
            'Longs': 0,
            'Shorts': 0,
            'In Profit': 0,
            'In Loss': 0,
            'Total P/L': 0,
            'Current P/L': 0
        } for pair in pairs}

        self.overall_stats = {
            'Total P/L': 0,
            'Portfolio Balance': portfolio_balance,
            'Total Trades': 0,
            'Trades in Profit': 0,
            'Trades in Loss': 0,
            'Accuracy': 0,
            'Max Drawdown': 0
        }

    def process_price(self, pair, timestamp, open_price, high_price, low_price, close_price, volume, is_closed, timeframe):
        self.pair_stats[pair]['Price'] = close_price

        if self.positions[pair] is not None:
            if self.positions[pair] == "Long":
                current_pl = (close_price - self.entry_prices[pair]) / self.entry_prices[pair] * trade_amount * leverage_x
            else:
                current_pl = (self.entry_prices[pair] - close_price) / self.entry_prices[pair] * trade_amount * leverage_x
            current_pl -= trade_amount * leverage_x * fee_rate
            self.pair_stats[pair]['Current P/L'] = current_pl
        else:
            self.pair_stats[pair]['Current P/L'] = 0

        if timeframe == Timeframe_15m:
            self.candle_15m[pair] = {
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'timestamp': timestamp
            }
            if is_closed:
                self.last_15m_close_time[pair] = timestamp
        elif timeframe == Timeframe_5m:
            self.candle_5m[pair] = {
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'timestamp': timestamp
            }

        if self.candle_15m[pair] and self.candle_5m[pair] and self.last_15m_close_time[pair]:
            self.check_entry_conditions(pair)

        if self.positions[pair] is not None:
            self.check_exit_conditions(pair, close_price)

    def check_entry_conditions(self, pair):
        if self.positions[pair] is not None:
            return

        candle_15m = self.candle_15m[pair]
        candle_5m = self.candle_5m[pair]

        # Check if it's the first 5m candle after 15m candle close
        if candle_5m['timestamp'] - self.last_15m_close_time[pair] <= timedelta(minutes=5):
            # Long condition
            if candle_5m['close'] > candle_15m['high']:
                self.open_long_position(pair, candle_5m['close'], candle_15m['low'])
            # Short condition
            elif candle_5m['close'] < candle_15m['low']:
                self.open_short_position(pair, candle_5m['close'], candle_15m['high'])

    def open_long_position(self, pair, price, stop_loss_price):
        self.positions[pair] = "Long"
        self.entry_prices[pair] = price
        self.stop_loss_prices[pair] = stop_loss_price
        risk = price - stop_loss_price
        self.take_profit_prices[pair] = price + (risk * risk_reward_ratio)
        self.pair_stats[pair]['Longs'] += 1
        self.update_stats(pair, price)

    def open_short_position(self, pair, price, stop_loss_price):
        self.positions[pair] = "Short"
        self.entry_prices[pair] = price
        self.stop_loss_prices[pair] = stop_loss_price
        risk = stop_loss_price - price
        self.take_profit_prices[pair] = price - (risk * risk_reward_ratio)
        self.pair_stats[pair]['Shorts'] += 1
        self.update_stats(pair, price)

    def check_exit_conditions(self, pair, current_price):
        if self.positions[pair] == "Long":
            if current_price >= self.take_profit_prices[pair]:
                self.close_position(pair, self.take_profit_prices[pair], True)
            elif current_price <= self.stop_loss_prices[pair]:
                self.close_position(pair, self.stop_loss_prices[pair], False)
        elif self.positions[pair] == "Short":
            if current_price <= self.take_profit_prices[pair]:
                self.close_position(pair, self.take_profit_prices[pair], True)
            elif current_price >= self.stop_loss_prices[pair]:
                self.close_position(pair, self.stop_loss_prices[pair], False)

    def close_position(self, pair, exit_price, is_profit):
        self.total_trades += 1

        if is_profit:
            self.trades_in_profit += 1
            self.pair_stats[pair]['In Profit'] += 1
        else:
            self.trades_in_loss += 1
            self.pair_stats[pair]['In Loss'] += 1

        if self.positions[pair] == "Long":
            profit_loss = (exit_price - self.entry_prices[pair]) / self.entry_prices[pair] * trade_amount * leverage_x
        else:
            profit_loss = (self.entry_prices[pair] - exit_price) / self.entry_prices[pair] * trade_amount * leverage_x

        profit_loss -= trade_amount * leverage_x * fee_rate
        self.total_profit_loss += profit_loss
        self.pair_stats[pair]['Total P/L'] += profit_loss

        current_balance = portfolio_balance + self.total_profit_loss
        drawdown = (portfolio_balance - current_balance) / portfolio_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)
        self.lowest_balance = min(self.lowest_balance, current_balance)

        self.positions[pair] = None
        self.entry_prices[pair] = None
        self.stop_loss_prices[pair] = None
        self.take_profit_prices[pair] = None
        self.update_stats(pair, exit_price)

    def update_stats(self, pair, current_price):
        self.pair_stats[pair]['Price'] = current_price
        self.pair_stats[pair]['Position'] = self.positions[pair] or 'None'

        self.overall_stats['Total P/L'] = self.total_profit_loss
        self.overall_stats['Portfolio Balance'] = portfolio_balance + self.total_profit_loss
        self.overall_stats['Total Trades'] = self.total_trades
        self.overall_stats['Trades in Profit'] = self.trades_in_profit
        self.overall_stats['Trades in Loss'] = self.trades_in_loss
        self.overall_stats['Accuracy'] = (self.trades_in_profit / self.total_trades) * 100 if self.total_trades > 0 else 0
        self.overall_stats['Max Drawdown'] = self.max_drawdown * 100

strategy = TradingStrategy(Pairs)

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Strategy Stats</title>
        <style>
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid black; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .positive { color: green; }
            .negative { color: red; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            setInterval(refreshPage, 1000);
        </script>
    </head>
    <body>
        <h1>Pair Stats</h1>
        <table>
            <tr>
                <th>Pair</th>
                <th>Price</th>
                <th>Position</th>
                <th>Longs</th>
                <th>Shorts</th>
                <th>In Profit</th>
                <th>In Loss</th>
                <th>Total P/L</th>
                <th>Current P/L</th>
            </tr>
            {% for pair, stats in pair_stats.items() %}
            <tr>
                <td>{{ pair }}</td>
                <td>${{ "%.2f"|format(stats['Price']) }}</td>
                <td>{{ stats['Position'] }}</td>
                <td>{{ stats['Longs'] }}</td>
                <td>{{ stats['Shorts'] }}</td>
                <td>{{ stats['In Profit'] }}</td>
                <td>{{ stats['In Loss'] }}</td>
                <td>${{ "%.2f"|format(stats['Total P/L']) }}</td>
                <td class="{{ 'positive' if stats['Current P/L'] > 0 else 'negative' if stats['Current P/L'] < 0 else '' }}">
                    ${{ "%.2f"|format(stats['Current P/L']) }}
                </td>
            </tr>
            {% endfor %}
        </table>

        <h1>Overall Stats</h1>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            {% for metric, value in overall_stats.items() %}
            <tr>
                <td>{{ metric }}</td>
                <td>
                    {% if metric in ['Total P/L', 'Portfolio Balance'] %}
                        ${{ "%.2f"|format(value) }}
                    {% elif metric in ['Accuracy', 'Max Drawdown'] %}
                        {{ "%.2f"|format(value) }}%
                    {% else %}
                        {{ value }}
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    '''
    return render_template_string(template, pair_stats=strategy.pair_stats, overall_stats=strategy.overall_stats)

async def connect_to_binance_futures():
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@kline_' + Timeframe_15m + '/' + pair.lower() + '@kline_' + Timeframe_5m for pair in Pairs])}"

    async with websockets.connect(uri) as websocket:
        print("Connected to Binance Futures WebSocket")

        last_ping_time = time.time()

        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1)
                process_message(json.loads(message))

                current_time = time.time()
                if current_time - last_ping_time > 60:
                    await websocket.ping()
                    last_ping_time = current_time
                    print("Ping sent to keep connection alive")

            except asyncio.TimeoutError:
                current_time = time.time()
                if current_time - last_ping_time > 60:
                    await websocket.ping()
                    last_ping_time = current_time
                    print("Ping sent to keep connection alive")

            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed. Attempting to reconnect...")
                break

    await asyncio.sleep(5)
    await connect_to_binance_futures()

def process_message(message):
    stream = message['stream']
    pair = stream.split('@')[0].upper()
    data = message['data']
    candle = data['k']

    open_time = datetime.fromtimestamp(candle['t'] / 1000)
    open_price = float(candle['o'])
    high_price = float(candle['h'])
    low_price = float(candle['l'])
    close_price = float(candle['c'])
    volume = float(candle['v'])
    is_closed = candle['x']

    timeframe = Timeframe_15m if 'kline_15m' in stream else Timeframe_5m

    strategy.process_price(pair, open_time, open_price, high_price, low_price, close_price, volume, is_closed, timeframe)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
