import time
import sys
import pyupbit
import concurrent.futures
import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/1142643634592813127/cIafpJvSwzl50Ngeu1bNdWubkPr6_uQSPiIzsDNKaLehn4mvHv6DVWc0NQ7LFdhfcgP9"  # 복사한 웹훅 URL을 여기에 붙여넣기



MAX_WORKERS = 10  # 동시 요청 수 제한
DELAY = 0.1  # 요청 간 지연


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
        send_discord_message("시장 데이터 가져오기 실패 또는 예상치 못한 데이터 형식.")
        return []
    return markets

def get_coin_price_and_volume(market):
    ticker_info = pyupbit.get_current_price(market)
    if isinstance(ticker_info, float):
        ticker_info = {market: ticker_info}
    if not ticker_info or market not in ticker_info:
        send_discord_message(f"{market}에 대한 가격 및 거래량 데이터 가져오기 실패.")
        return None, None
    price = ticker_info[market]
    ohlcv = pyupbit.get_ohlcv(market, interval="minute1", count=1)
    if not ohlcv.empty:
        volume = ohlcv['volume'].iloc[0]
    else:
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
        send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
        return 0
    if not isinstance(balance, (float, int)):
        send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
        return 0
    return balance

def buy_coin(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    krw_balance = upbit.get_balance("KRW")
    if krw_balance is not None and krw_balance >= 5000:
        upbit.buy_market_order(coin, krw_balance)
        send_discord_message(f"{coin} 시장가로 구매")

def sell_coin(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    coin_balance = upbit.get_balance(coin.split('-')[1])
    if coin_balance and coin_balance > 0:
        upbit.sell_market_order(coin, coin_balance)
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

# ... [rest of the code remains the same]
def main():
    try:
        access_key = "access_key"  # Replace with your access key
        secret_key = "secret_key"  # Replace with your secret key
        
        while True:
            krw_coins = get_krw_coin_list()
            coin_prices = {coin: [] for coin in krw_coins}
            coin_growth_rates = {coin: [] for coin in krw_coins}
            coin_volumes = {coin: [] for coin in krw_coins}
            loop_count = 0
            bought_coin = None
            buy_price = 0

            while True:
                krw_balance = get_balance(access_key, secret_key)
                if krw_balance < 5000:
                    send_discord_message("Insufficient KRW balance. Exiting...")
                    sys.exit(0)

                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(fetch_coin_data, krw_coins))

                for coin, price, volume in results:
                    if price is None:
                        continue
                    coin_prices[coin].append(price)
                    coin_volumes[coin].append(volume)

                    if loop_count >= 1:
                        growth_rate = calculate_growth_rate(coin_volumes[coin][-2], volume)
                        coin_growth_rates[coin].append(growth_rate)

                loop_count += 1
                send_discord_message(f"Loop count: {loop_count}")

                if loop_count % 3 == 0:
                    max_growth_rate = -float('inf')
                    max_growth_coin = None

                    for coin, rates in coin_growth_rates.items():
                        if len(rates) == 3 and sum(rates) > max_growth_rate:
                            max_growth_rate = sum(rates)
                            max_growth_coin = coin

                    if max_growth_coin is None:
                        send_discord_message("No max_growth_coin found. Restarting...")
                        break

                    if coin_prices[max_growth_coin][-1] > coin_prices[max_growth_coin][-2]:
                        krw_balance = get_balance(access_key, secret_key)
                        if krw_balance >= 5000:
                            buy_price = coin_prices[max_growth_coin][-1]
                            buy_coin(access_key, secret_key, max_growth_coin)
                            bought_coin = max_growth_coin
                        else:
                            send_discord_message("Insufficient KRW balance. Exiting...")
                            sys.exit(0)

                
                if bought_coin:
                    if check_sell_condition(bought_coin, buy_price, coin_prices, coin_volumes):
                        sell_coin(access_key, secret_key, bought_coin)
                        time.sleep(60)
                        if get_balance(access_key, secret_key, bought_coin.split('-')[1]) > 0:
                            sell_coin(access_key, secret_key, bought_coin)
                        send_discord_message("Restarting after selling the coin...")
                        break

                time.sleep(60)
                send_discord_message("다시 코인탐색을 시작합니다.")
                

    except Exception as e:
        send_discord_message("An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
