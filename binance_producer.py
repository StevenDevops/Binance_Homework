from binance.spot import Spot as Client
from prometheus_client import start_http_server, Gauge
import pandas as pd
import json
import time

class BinanceProducer:

    def __init__(self):
        API_BASE_URL = "https://api.binance.com/api"
        self.spot_client = Client(API_BASE_URL)

    def test_connectivity(self):
        '''
        GET /api/v3/ping
        https://binance-docs.github.io/apidocs/spot/en/#test-connectivity
        '''

        while True:
            try:
                self.spot_client.ping()
                print("Looks good")
                break
            except Exception as e:
                print("There are something wrong with Binance APIs.", e)
                print("Retry in 5s")
                time.sleep(5) # Keeps trying every 5s

    def get_symbols_by_quote_asset(self,quoteAsset):
        '''
        GET /api/v3/exchangeinfo
        https://binance-docs.github.io/apidocs/spot/en/#exchange-information
        '''

        symbols = self.spot_client.exchange_info()
        symbols_lst = []

        df = pd.DataFrame(symbols["symbols"])

        for index, data in df.iterrows():
            if data["quoteAsset"] == quoteAsset:
                symbols_lst.append(data["symbol"])
        return symbols_lst

    def get_top_symbols_by_quote_asset(self,top,quoteAsset,type):
        '''
        GET /api/v3/ticker/24hr
        https://binance-docs.github.io/apidocs/spot/en/#24hr-ticker-price-change-statistics
        '''

        # Collect sysmbols by quoteAsset
        symbol_by_quoteAsset = self.get_symbols_by_quote_asset(quoteAsset)
        r = self.spot_client.ticker_24hr(symbols=symbol_by_quoteAsset)
        df = pd.DataFrame.from_dict(r)
        df = df[["symbol", type]]

        # Convert to numeric for sorting
        df[type] = pd.to_numeric(df[type], downcast="float", errors="coerce")
        df = df.sort_values(by=[type], ascending=False).head(top)

        # Print the results
        print("\n Top Symbols for %s by %s \n" %  (quoteAsset, type))
        print(df.to_string(index = False))

        # Return value for question 3
        return df['symbol'].values.tolist()

    def get_total_notional_value(self,symbols):
        '''
        https://binance-docs.github.io/apidocs/spot/en/#order-book
        I use this formula
        notional_values = price * qty
        The output will be like:

        {
          "PERLBTC": {
            "total_notional_asks": 0.01487556,
            "total_notional_bids": 0.20440431000000003
          },
          "JASMYBTC": {
            "total_notional_asks": 10.706644556,
            "total_notional_bids": 15.437807622000001
        }
        '''

        notional_list = {}
        for symbol in symbols:
            notional_list[symbol] = {}
            r = self.spot_client.depth(symbol,limit=200)
            df = pd.DataFrame.from_dict(r, orient="index")

            for column in ["asks","bids"]:
                sum_lst = []

                for i in df[0][column]:
                    df_column = pd.DataFrame(i,dtype=float)
                    sum_lst.append(df_column[0][0] * df_column[0][1])

                notional_list[symbol].update({
                        "total_notional_"+column: sum(sum_lst)
                })

        # Print the results
        print("\n The total notional value of the top 200 bids and asks currently on each order book for %s \n" %  symbols)
        print (json.dumps(notional_list, indent=2))

    def get_price_spread(self,symbols,output=True):
        '''
        The spread price is the difference between the current market price for that asset and the price you buy or sell that asset for.
        I use this formula:
        Current market price - Best asks/bids price on the order book for a symbol or symbols.
        We need to get data from 2 APIs:
        GET /api/v3/ticker/bookTicker
        https://binance-docs.github.io/apidocs/spot/en/#symbol-order-book-ticker
        GET /api/v3/ticker/price
        https://binance-docs.github.io/apidocs/spot/en/#symbol-price-ticker
        The output will be like:

        {
          "BTCUSDT": {
            "price_spread_askPrice": -1.25,
            "price_spread_bidPrice": 0.0
          },
          "ETHUSDT": {
            "price_spread_askPrice": 0.0,
            "price_spread_bidPrice": 0.009999999999990905
          }
        }
        '''

        price_spread_list = {}

        for symbol in symbols:
            price_spread_list[symbol] = {}

            # Get current price
            r  = self.spot_client.ticker_price(symbol)
            df = pd.DataFrame.from_dict(r, orient="index")
            live_price = df[0]["price"]

            # Get best birds and asks price
            s = self.spot_client.book_ticker(symbol)
            ds = pd.DataFrame.from_dict(s, orient="index")

            for price_type in ["askPrice","bidPrice"]:
                price_spread_list[symbol].update({
                        "price_spread_"+price_type: float(live_price) - float(ds[0][price_type])
                })

        if output:
                print("\n The price spread for each of %s \n" %  symbols)
                print (json.dumps(price_spread_list, indent=2))

        return price_spread_list
    def get_absolute_delta(self, symbols):
        '''
        I used this formula:
            abs(old_spread - new_spread)

        The output will be like:
        {
          "BTCUSDT": {
            "absolute_delta_askPrice": 0.5800000000017462,
            "absolute_delta_bidPrice": 0.11999999999898137
          },
          "ETHUSDT": {
            "absolute_delta_askPrice": 0.0,
            "absolute_delta_bidPrice": 0.0
          },
          "VGXUSDT": {
            "absolute_delta_askPrice": 0.0010000000000000009,
            "absolute_delta_bidPrice": 0.0
          },
          "MATICUSDT": {
            "absolute_delta_askPrice": 0.0,
            "absolute_delta_bidPrice": 0.0
          },
          "BEAMUSDT": {
            "absolute_delta_askPrice": 0.0006999999999999784,
            "absolute_delta_bidPrice": 0.0002999999999999947
          }
        }

        Prometheus metrics will be:

        # HELP absolute_delta Absolute Delta Value of Price Spread
        # TYPE absolute_delta gauge
        absolute_delta{price_type="absolute_delta_askPrice",symbol="BTCUSDT"} 2.2700000000004366
        absolute_delta{price_type="absolute_delta_bidPrice",symbol="BTCUSDT"} 0.819999999999709
        absolute_delta{price_type="absolute_delta_askPrice",symbol="ETHUSDT"} 0.0
        '''
        prom_gauge = Gauge('absolute_delta',
                                'Absolute Delta Value of Price Spread', ['symbol','price_type'])
        #gauge_services = GaugeMetricFamily('system_services_state', 'System services status', labels=['service'])
        while True:
            try:
                delta = {}
                old_spread = self.get_price_spread(symbols,False)
                print("\n Refresh in 10s \n")
                time.sleep(10)
                new_spread = self.get_price_spread(symbols,False)
                for symbol in symbols:
                    delta[symbol] = {}
                    for key in old_spread[symbol]:
                        delta[symbol][key.replace("price_spread_","absolute_delta_")] = abs(old_spread[symbol][key] - new_spread[symbol][key])
                    for key in delta[symbol]:
                         prom_gauge.labels(symbol,key).set(delta[symbol][key])

                print("\n The Absolute Delta Value of Price Spread for %s \n" %  symbols)
                print(json.dumps(delta, indent=2))
            except Exception as e:
                print("There are something wrong.", e)
                break

if __name__ == "__main__":
    client = BinanceProducer()
    client.test_connectivity()

    # Question 1,2
    q1 = client.get_top_symbols_by_quote_asset(5,'BTC','volume')
    q2 = client.get_top_symbols_by_quote_asset(5,'USDT','count')
    # Question 3
    client.get_total_notional_value(q1)
    # Question 4
    client.get_price_spread(q2)
    # Question 5,6
    start_http_server(8080)
    client.get_absolute_delta(q2)
