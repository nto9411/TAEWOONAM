import time
import sys
import pyupbit
import concurrent.futures
import requests
import json  # json 모듈 추가

WEBHOOK_URL = "https://discord.com/api/webhooks/1142643634592813127/cIafpJvSwzl50Ngeu1bNdWubkPr6_uQSPiIzsDNKaLehn4mvHv6DVWc0NQ7LFdhfcgP9"
MAX_WORKERS = 10
DELAY = 0.5

#

def send_discord_message(message, max_retries=5, delay_between_retries=10):
    #print(message)  # Instead of sending to Discord, we just print the content to the console
    
    for retry in range(max_retries):
        try:
            response = requests.post(WEBHOOK_URL, json={"content": message})
            response.raise_for_status()  # will raise an HTTPError if the HTTP request returned an unsuccessful status code
            return  # if successful, exit the function
        except requests.exceptions.HTTPError as err:
            if response.status_code == 429:  # Too Many Requests
                time.sleep(delay_between_retries)
            else:
                raise err  # if it's a different kind of error, raise it
    raise Exception(f"Max retries reached. Failed to send message to Discord: {response.status_code} {response.reason} for url: {response.url}")


# For the 2nd problem, adding logging statements to help us track data inconsistencies
def log_data_for_debugging(function_name, input_data=None, output_data=None, message=None):
    log_msg = f"Function: {function_name}"
    if input_data is not None:
        log_msg += f", Input: {input_data}"
    if output_data is not None:
        log_msg += f", Output: {output_data}"
    if message:
        log_msg += f", Message: {message}"
    send_discord_message(log_msg)



def get_krw_coin_list():
    markets = pyupbit.get_tickers(fiat="KRW")
    if not isinstance(markets, (list, tuple)) or not markets:
        send_discord_message("시장 데이터 가져오기 실패 또는 예상치 못한 데이터 형식.")
        log_data_for_debugging("get_krw_coin_list", output_data=markets)
        return []
    return markets

def safe_get_coin_price_and_volume_v3(market):
    try:
        for _ in range(2):  # Including the original request, we will have 3 tries in total
            ticker_info = pyupbit.get_current_price(market)
            if isinstance(ticker_info, float):
                ticker_info = {market: ticker_info}
            if ticker_info and market in ticker_info:
                # Ensure that the price is a float
                price = float(ticker_info[market])
                ohlcv = pyupbit.get_ohlcv(market, interval="minute1", count=1)
                if not ohlcv.empty:
                    # Ensure that the volume is a float
                    volume = float(ohlcv['volume'].iloc[0])
                else:
                    volume = None
                return market, price, volume  # Return the coin name as well for consistency

            # If failed, wait for DELAY * 5 seconds and try again
            time.sleep(DELAY * 5)
        return market, None, None



    except Exception as e:
        send_discord_message(f"Error fetching price and volume for {market}: {e}")
        return market, None, None  # Return coin name with None values for price and volume


def calculate_growth_rate(prev_volume, current_volume):
    if prev_volume == 0:
        return 0
    growth_rate = (current_volume - prev_volume) / prev_volume * 100
    return growth_rate



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
    
def get_balance1(access_key, secret_key, ticker):
    #"""잔고 조회"""
    upbit = pyupbit.Upbit(access_key, secret_key)
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def enhanced_buy_coin_with_pyupbit(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    krw_balance = get_balance1(access_key, secret_key, "KRW")
    
    # Check if krw_balance is None or unexpected type
    if krw_balance is None or not isinstance(krw_balance, (float, int)):
        send_discord_message(f"Failed to fetch KRW balance for buying {coin}. Unknown balance type or None.")
        return

    if krw_balance >= 5000:
        # Using pyupbit.Upbit instance to buy
        response = upbit.buy_market_order(coin, krw_balance * 0.9995)
        
        # If response is None, attempt to buy using an alternative method
        if response is None:
            send_discord_message(f"Received None response for buying {coin}. Trying alternative method...")
            response = alternative_buy_market_order(upbit, coin, krw_balance)
        
        # Log the API response for debugging
        send_discord_message(f"API Response for buying {coin}: {response}")
        
        # Check if the order was successful
        if response and "error" in response:
            error_message = response["error"]["message"]
            send_discord_message(f"Failed to buy {coin}: {error_message}")
        else:
            send_discord_message(f"{coin} was purchased at market price.")
    else:
        send_discord_message(f"Insufficient KRW balance for buying {coin}. Current balance: {krw_balance}")


def alternative_buy_market_order(upbit_instance, coin, amount):
    try:
        response = upbit_instance.buy_market_order(coin, amount * 0.9995)
        return response
    except Exception as e:
        send_discord_message(f"Alternative method error for buying {coin}: {e}")
        return None


def updated_sell_coin(access_key, secret_key, coin):
    upbit = pyupbit.Upbit(access_key, secret_key)
    
    # 코인 이름만 추출 (예: BTC-KRW -> BTC)
    coin_name = coin.split('-')[1] if '-' in coin else coin

    coin_balance = upbit.get_balance(coin_name)
    
    # 수수료를 고려하여 조정된 잔고 계산
    adjusted_balance = coin_balance * (1 - 0.00005)
    
    if adjusted_balance and adjusted_balance > 0:
        response = upbit.sell_market_order(coin, adjusted_balance)
        
        # Log the API response for debugging
        send_discord_message(f"API Response for selling {coin}: {response}")
        
        # Check if the order was successful
        if "error" in response:
            error_message = response["error"]["message"]
            send_discord_message(f"Failed to sell {coin}: {error_message}")
        else:
            send_discord_message(f"{coin} was sold at market price.")

# 위의 코드 변경사항을 적용하였습니다.


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


def safe_check_sell_condition(coin, buy_price, coin_prices, coin_volumes):
    # Check if there's enough data to compute
    if coin not in coin_prices or len(coin_prices[coin]) < 2:
        return False

    # 가격이 2% 이하로 하락했는지 확인
    if coin_prices[coin][-1] <= buy_price * 0.98:
        return True

    # 거래량이 1.6배 이상 증가하고 가격이 1% 이상 하락했는지 확인
    if coin in coin_volumes and check_volume_increase(coin, coin_volumes) and check_price_drop(coin, buy_price, coin_prices):
        return True
    return False
#... [기존의 코드 부분은 유지]

def updated_main_v2():
    try:
        access_key = "access"
        secret_key = "secret"

        krw = get_balance1(access_key,secret_key,"KRW")
        print("현재 잔고: ", krw)


        highest_volume_coins = []
        weighted_growth_rates = []

        # Store selected coin symbol locally
        selected_coin_symbol = ""

        while True:
            krw_coins = get_krw_coin_list()
            coin_prices = {coin: [] for coin in krw_coins}
            coin_volumes = {coin: [] for coin in krw_coins}

            for _ in range(3):  # Loop for 3 times
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(safe_get_coin_price_and_volume_v3, krw_coins))

                for coin, price, volume in results:
                    if None in [coin, price, volume]:
                        send_discord_message(f"Failed to get data for {coin}")
                        continue
                    coin_prices[coin].append(price)
                    coin_volumes[coin].append(volume)

                # 최고 거래량 증가율 계산
                growth_rates = {coin: calculate_growth_rate(coin_volumes[coin][-2], coin_volumes[coin][-1]) if len(coin_volumes[coin]) > 1 else 0 for coin in krw_coins}
                max_growth_rate_coin = max(growth_rates, key=growth_rates.get)
                highest_volume_coins.append(max_growth_rate_coin)
                weighted_growth_rates.append(growth_rates[max_growth_rate_coin])
                
                send_discord_message(f"Coin with the highest volume growth in this minute: {max_growth_rate_coin}")

                time.sleep(60)

            selected_coin_symbol = max_growth_rate_coin.split('-')[1] if '-' in max_growth_rate_coin else max_growth_rate_coin


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
                enhanced_buy_coin_with_pyupbit(access_key, secret_key, max_growth_coin)
                send_discord_message(f"The selected coin {max_growth_coin} has a rising price.")
            else:
                send_discord_message(f"The selected coin {max_growth_coin} does not have a rising price.")
                continue  # Return to the start of the main loop if the price isn't rising

            while True:

                _, price, _ = safe_get_coin_price_and_volume_v3(max_growth_coin)
                if price:
                    coin_prices[max_growth_coin].append(price)

                if safe_check_sell_condition(max_growth_coin, buy_price, coin_prices, coin_volumes):
                    updated_sell_coin(access_key, secret_key, max_growth_coin)
                    time.sleep(60)
                    if get_balance(access_key, secret_key, max_growth_coin.split('-')[1]) > 0:
                        updated_sell_coin(access_key, secret_key, max_growth_coin)
                    send_discord_message("Restarting after selling the coin...")
                    break

                time.sleep(60)

            highest_volume_coins = []  # Reset the list
            weighted_growth_rates = []  # Reset the list

    except Exception as e:
        send_discord_message(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    updated_main_v2()
