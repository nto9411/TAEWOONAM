import time
import sys
import pyupbit
import concurrent.futures
import requests
import json  # json 모듈 추가

WEBHOOK_URL = "https://discord.com/api/webhooks/1142643634592813127/cIafpJvSwzl50Ngeu1bNdWubkPr6_uQSPiIzsDNKaLehn4mvHv6DVWc0NQ7LFdhfcgP9"
MAX_WORKERS = 10
DELAY = 0.1

#

def send_discord_message(content, retries=3, delay_between_retries=5):
    data = {
        "content": content
    }

    for _ in range(retries):
        try:
            response = requests.post(WEBHOOK_URL, json=data)
            response.raise_for_status()  # will raise an HTTPError if the HTTP request returned an unsuccessful status code
            return  # If successful, exit the function
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as err:
            send_discord_message(f"Error sending message to Discord: {err}")
            if _ < retries - 1:  # i.e. if it's not the last iteration
                send_discord_message(f"Retrying in {delay_between_retries} seconds...")
                time.sleep(delay_between_retries)  # wait before trying again
            else:
                send_discord_message("Max retries reached. Failed to send message to Discord.")



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
    try:
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
    except Exception as e:
        send_discord_message(f"Error fetching price and volume for {market}: {e}")
        return None, None


def calculate_growth_rate(prev_volume, current_volume):
    if prev_volume == 0:
        return 0
    growth_rate = (current_volume - prev_volume) / prev_volume * 100
    return growth_rate


#def get_balance(access_key, secret_key, ticker="KRW"):
#    try:
#        upbit = pyupbit.Upbit(access_key, secret_key)
#        balance = upbit.get_balance(ticker=ticker)
#        if balance is None:
#            send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
#            return 0
#        if not isinstance(balance, (float, int)):
#            send_discord_message(f"{ticker}에 대한 fetch balance 가져오기 실패.")
#            return 0
#        return balance
#    except Exception as e:
#        send_discord_message(f"Error fetching balance for {ticker}: {e}")
#        return 0

def get_balance(access_key, secret_key, ticker="KRW"):
    try:
        upbit = pyupbit.Upbit(access_key, secret_key)
        balances = upbit.get_balances()

        # balances가 문자열일 경우, 파이썬 객체로 변환
        if isinstance(balances, str):
            balances = json.loads(balances)

        # balances에서 해당 ticker의 잔액을 찾아 반환
        for balance_info in balances:
            if balance_info['currency'] == ticker:
                balance = balance_info.get('balance', 0)
                return float(balance)
        return 0  # 해당 ticker가 balances 목록에 없으면 0 반환

    except Exception as e:
        send_discord_message(f"Error fetching balance for {ticker}: {e}")
        return 0


def enhanced_buy_coin(access_key, secret_key, coin):
    krw_balance = get_balance(access_key, secret_key, "KRW")  # 변경된 부분
    
    if krw_balance is not None and krw_balance >= 5000:
        upbit = pyupbit.Upbit(access_key, secret_key)
        response = upbit.buy_market_order(coin, krw_balance)
        
        # Check if the order was successful
        if "error" in response:
            error_message = response["error"]["message"]
            send_discord_message(f"Failed to buy {coin}: {error_message}")
        else:
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

#... [기존의 코드 부분은 유지]

def updated_main():
    try:

        access_key = "access"
        secret_key = "secret"


        # 프로그램 시작하자마자 KRW 잔액 확인 및 디스코드로 메시지 전송
        krw_balance = get_balance(access_key, secret_key, "KRW")
        send_discord_message(f"프로그램 시작! 현재 KRW 잔액: {krw_balance:.2f} KRW")


        highest_volume_coins = []
        weighted_growth_rates = []

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

                # 최고 거래량 증가율 계산
                growth_rates = {coin: calculate_growth_rate(coin_volumes[coin][-2], coin_volumes[coin][-1]) if len(coin_volumes[coin]) > 1 else 0 for coin in krw_coins}
                max_growth_rate_coin = max(growth_rates, key=growth_rates.get)
                highest_volume_coins.append(max_growth_rate_coin)
                weighted_growth_rates.append(growth_rates[max_growth_rate_coin])
                
                send_discord_message(f"Coin with the highest volume growth in this minute: {max_growth_rate_coin}")

                time.sleep(60)

            # 가중치 적용하여 최종 코인 선택
            weights = [0.2, 0.3, 0.5]
            total_weighted_growth = sum([coin_rate * weight for coin_rate, weight in zip(weighted_growth_rates, weights)])
            max_growth_coin = highest_volume_coins[weighted_growth_rates.index(max(weighted_growth_rates))]
            
            # Send discord message for the selected highest volume growth coin after 3 loops
            send_discord_message(f"Selected coin with the highest volume growth after 3 minutes: {max_growth_coin}")

            # Initialize buy_price outside the condition
            buy_price = 0

            if coin_prices[max_growth_coin][-1] > coin_prices[max_growth_coin][-2]:
                buy_price = coin_prices[max_growth_coin][-1]
                enhanced_buy_coin(access_key, secret_key, max_growth_coin)
                send_discord_message(f"The selected coin {max_growth_coin} has a rising price.")
            else:
                send_discord_message(f"The selected coin {max_growth_coin} does not have a rising price.")
                continue  # Return to the start of the main loop if the price isn't rising

            while True:
                krw_balance = get_balance(access_key, secret_key, "KRW")
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
            weighted_growth_rates = []  # Reset the list

    except Exception as e:
        send_discord_message(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    updated_main()
