import time
import sys
import pyupbit
import concurrent.futures
import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/1142643634592813127/cIafpJvSwzl50Ngeu1bNdWubkPr6_uQSPiIzsDNKaLehn4mvHv6DVWc0NQ7LFdhfcgP9"
MAX_WORKERS = 10
DELAY = 0.1

#

def send_discord_message(content):
    data = {
        "content": content
    }
    response = requests.post(WEBHOOK_URL, json=data)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)


def fetch_coin_data(coin):
    time.sleep(DELAY)  # 각 요청 사이에 약간의 지연 추가
    for _ in range(3):  # 최대 3번 재시도
        price, volume = get_coin_price_and_volume(coin)
        if price is not None:
            return coin, price, volume
        time.sleep(DELAY * 5)  # 재시도 전에 0.5초 대기
    return coin, None, None


def get_krw_coin_list():
    markets = pyupbit.get_tickers(fiat="KRW")
    if not isinstance(markets, (list, tuple)) or not markets:
        print("Failed to fetch market data or unexpected data format.")
        send_discord_message("시장 데이터 가져오기 실패 또는 예상치 못한 데이터 형식.")
        return []
    return markets

def get_coin_price_and_volume(market):
    ticker_info = pyupbit.get_current_price(market)
    if isinstance(ticker_info, float):
        ticker_info = {market: ticker_info}
    if not ticker_info or market not in ticker_info:
        print(f"Failed to fetch price and volume data for {market}.")
        send_discord_message(f"{market}에 대한 가격 및 거래량 데이터 가져오기 실패.")
        return None, None
    price = ticker_info[market]
    ohlcv = pyupbit.get_ohlcv(market, interval="minute1", count=1)
    if not ohlcv.empty:
        volume = ohlcv['volume'].iloc[0]
    else:
        print(f"Failed to fetch OHLCV data for {market}.")
        send_discord_message(f"{market}에 대한 가격 및 거래량 데이터 가져오기 실패.")
        volume = None
    return price, volume

def calculate_growth_rate(prev_volume, current_volume):
    if prev_volume == 0:
        return 0
    growth_rate = (current_volume - prev_volume) / prev_volume * 100
    return growth_rate

def get_balance(access_key, secret_key, ticker="KRW"):
    upbit = pyupbit.Upbit(access_key, secret_key)
    balance = upbit.get_balance(ticker=ticker)
    if balance is None:
        print(f"Failed to fetch balance for {ticker}.")
        send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
        return 0
    if not isinstance(balance, (float, int)):
        print(f"Unexpected balance data format for {ticker}.")
        send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
        return 0
    return balance


def enhanced_buy_coin(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    krw_balance = upbit.get_balance("KRW")
    
    if krw_balance is not None and krw_balance >= 5000:
        response = upbit.buy_market_order(coin, krw_balance)
        
        # Check if the order was successful
        if "error" in response:
            error_message = response["error"]["message"]
            print(f"Failed to buy {coin}: {error_message}")
            send_discord_message(f"Failed to buy {coin}: {error_message}")
        else:
            print(f"Bought {coin} at market price with balance.")
            send_discord_message(f"{coin} 시장가로 구매")


def sell_coin(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    coin_balance = upbit.get_balance(coin.split('-')[1])
    if coin_balance and coin_balance > 0:
        upbit.sell_market_order(coin, coin_balance)
        print(f"Sold {coin} at market price.")
        send_discord_message(f"{coin} 시장가로 매도")

def check_volume_increase(coin, coin_volumes):
    """최근 5분 동안의 평균 거래량의 1.6배 이상인지 확인"""
    if len(coin_volumes[coin]) < 5:
        return False
    avg_volume = sum(coin_volumes[coin][-5:]) / 5
    return coin_volumes[coin][-1] >= avg_volume * 1.6

def check_price_drop(coin, buy_price, coin_prices):
    """가격이 1% 이상 하락했는지 확인"""
    if len(coin_prices[coin]) < 2:
        return False
    return coin_prices[coin][-1] <= coin_prices[coin][-2] * 0.99


def check_sell_condition(coin, buy_price, coin_prices, coin_volumes):
    # 가격이 2% 이하로 하락했는지 확인
    if coin_prices[coin][-1] <= buy_price * 0.98:
        return True
    # 거래량이 1.6배 이상 증가하고 가격이 1% 이상 하락했는지 확인
    if check_volume_increase(coin, coin_volumes) and check_price_drop(coin, buy_price, coin_prices):
        return True
    return False


# ... [기존의 함수들은 동일하게 유지]

# Update the main function to use the enhanced_buy_coin function
def updated_main():
    try:
        access_key = "access"
        secret_key = "secret"
        
        highest_volume_coins = []

        while True:
            krw_coins = get_krw_coin_list()
            coin_prices = {coin: [] for coin in krw_coins}
            coin_volumes = {coin: [] for coin in krw_coins}
            
            for _ in range(3):  # Loop for 3 times
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(fetch_coin_data, krw_coins))
                
                for coin, price, volume in results:
                    if price is not None:
                        coin_prices[coin].append(price)
                        coin_volumes[coin].append(volume)
                
                max_volume_coin = max(coin_volumes.keys(), key=lambda k: coin_volumes[k][-1] if coin_volumes[k] else 0)
                highest_volume_coins.append(max_volume_coin)
                
                # Send discord message for the highest volume coin every minute
                send_discord_message(f"Coin with the highest volume in this minute: {max_volume_coin}")
                
                time.sleep(60)
            
            growth_rates = [
                calculate_growth_rate(coin_volumes[highest_volume_coins[0]][-2], coin_volumes[highest_volume_coins[0]][-1]),
                calculate_growth_rate(coin_volumes[highest_volume_coins[1]][-2], coin_volumes[highest_volume_coins[1]][-1]),
                calculate_growth_rate(coin_volumes[highest_volume_coins[2]][-2], coin_volumes[highest_volume_coins[2]][-1])
            ]
            
            max_growth_rate_idx = growth_rates.index(max(growth_rates))
            max_growth_coin = highest_volume_coins[max_growth_rate_idx]
            
            # Send discord message for the selected highest volume coin after 3 loops
            send_discord_message(f"Selected coin with the highest volume after 3 minutes: {max_growth_coin}")

            # Initialize buy_price outside the condition
            buy_price = 0
            
            if coin_prices[max_growth_coin][-1] > coin_prices[max_growth_coin][-2]:
                buy_price = coin_prices[max_growth_coin][-1]
                enhanced_buy_coin(access_key, secret_key, max_growth_coin)
                send_discord_message(f"The selected coin {max_growth_coin} has a rising price.")
            else:
                send_discord_message(f"The selected coin {max_growth_coin} does not have a rising price.")

            while True:
                krw_balance = get_balance(access_key, secret_key)
                if krw_balance < 5000:
                    send_discord_message("Insufficient KRW balance. Exiting...")
                    sys.exit(0)

                price, _ = get_coin_price_and_volume(max_growth_coin)
                if price:
                    coin_prices[max_growth_coin].append(price)
                
                if check_sell_condition(max_growth_coin, buy_price, coin_prices, coin_volumes):
                    sell_coin(access_key, secret_key, max_growth_coin)
                    time.sleep(60)
                    if get_balance(access_key, secret_key, max_growth_coin.split('-')[1]) > 0:
                        sell_coin(access_key, secret_key, max_growth_coin)
                    send_discord_message("Restarting after selling the coin...")
                    break

                time.sleep(60)
            
            highest_volume_coins = []  # Reset the list

    except Exception as e:
        send_discord_message(f"An error occurred: {e}")
        sys.exit(1)

# The actual main function is commented to avoid accidental execution
if __name__ == "__main__":
     updated_main()
