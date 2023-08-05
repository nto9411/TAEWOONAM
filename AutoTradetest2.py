import time
import pyupbit
import pandas as pd

# 업비트 API 키를 환경 변수로 설정
API_KEY = 'YOUR_API_KEY'
SECRET_KEY = 'YOUR_SECRET_KEY'
upbit = pyupbit.Upbit(API_KEY, SECRET_KEY)

# API 호출 제한 확인 및 대기 시간 설정
#def check_api_limit():
    # 초당 10회, 분당 600회
   # sec_limit = 10
   # min_limit = 600

   # current_sec_calls = upbit.get_call_count(1)  # 초당 호출 횟수 조회
   # current_min_calls = upbit.get_call_count(60)  # 분당 호출 횟수 조회

   # if current_sec_calls >= sec_limit:
        # 초당 호출 제한에 도달한 경우 1초 대기
    #    time.sleep(1)

   # if current_min_calls >= min_limit:
        # 분당 호출 제한에 도달한 경우 1분 대기
     #   time.sleep(60)

# 강제 종료 모듈
def force_exit(reason):
    print(f"프로그램이 강제 종료되었습니다. 사유: {reason}")
    exit()

# 거래량 증가율 계산 함수
def calculate_volume_change(prev_volume, current_volume):
    if prev_volume <= 0:
        return 0
    return ((current_volume - prev_volume) / prev_volume) * 100

# 코인 데이터 기록하기
def record_coin_data():
    # 업비트 내의 모든 KRW 코인의 거래량 정보를 조회한다.
   # check_api_limit()
    time.sleep(1)# API 호출 제한 확인 및 대기 시간 설정
    coin_data = pyupbit.get_tickers(fiat="KRW")
    
    coin_volume = {}
    for market in coin_data:
        #check_api_limit()
        time.sleep(1)# API 호출 제한 확인 및 대기 시간 설정
        ticker = pyupbit.get_ohlcv(market, interval='minute1', count=2)
        current_volume = ticker.iloc[-1]['volume']
        prev_volume = ticker.iloc[-2]['volume']
        coin_volume[market] = current_volume

    if len(coin_data) >= 5:
        # 5분 단위로 데이터가 모이면 best_coin 찾기 모듈 실행
        return find_best_coin(coin_volume)

    return None

# best_coin 찾기
def find_best_coin(coin_volume):
    candidate_coins = []
    for market in coin_volume.keys():
        #check_api_limit()
        time.sleep(1)# API 호출 제한 확인 및 대기 시간 설정
        current_volume = coin_volume[market]
        ticker = pyupbit.get_ohlcv(market, interval='minute1', count=1)
        prev_close = ticker.iloc[-1]['close']
        volume_change = calculate_volume_change(prev_close, current_volume)

        # 1분 기준 거래량이 가장 높은 코인을 1등으로 기록
        if volume_change > 0 and (not candidate_coins or volume_change > candidate_coins[0]['volume_change']):
            candidate_coins = [{'market': market, 'volume_change': volume_change}]
            print("== 최고 거래량 증가율을 찾았습니다 ==")
            print(candidate_coins)

    if candidate_coins:
        # best_coin 찾으면 코인 매수 모듈 실행
        return buy_coin(candidate_coins[0])

    return None

# 코인 매수하기
def buy_coin(best_coin):
    account_krw = upbit.get_balance('KRW')

    if account_krw >= 5000:
        # 보유 KRW가 5000원 이상일 경우
        best_coin_ticker = pyupbit.get_ticker(best_coin['market'])
        current_price = best_coin_ticker['trade_price']
        buying_price = best_coin_ticker['opening_price']

        if current_price < buying_price:
            # best_coin 가격이 1분 전보다 하락한 경우
            # 다시 best_coin 찾기
            print("== best_coin 가격이 하락하여 다시 찾습니다 ==")
            return record_coin_data()

        upbit.buy_market_order(best_coin['market'], account_krw)
        print("== 보유 KRW가 5000원 이상이므로 코인을 시장가로 매수합니다 ==")
        return best_coin['market']

    force_exit("보유 KRW가 5000원 미만입니다.")

# 코인 매도하기
def sell_coin(holding_coin):
    best_coin_ticker = pyupbit.get_ticker(holding_coin)
    current_price = best_coin_ticker['trade_price']
    buying_price = best_coin_ticker['opening_price']

    # 1분마다 매수한 코인의 가격증가율 확인
    ticker = pyupbit.get_ohlcv(holding_coin, interval='minute1', count=2)
    prev_close = ticker.iloc[-2]['close']
    current_close = ticker.iloc[-1]['close']
    price_change = ((current_close - prev_close) / prev_close) * 100

    # 매수한 코인의 현재 가격이 매수한 시점의 가격 * 0.98보다 작거나 같거나
    # 가격증가율이 음수인 경우 시장가로 매도
    if current_price <= buying_price * 0.98 or price_change < 0:
        upbit.sell_market_order(holding_coin, upbit.get_balance(holding_coin))
        print("== 매수한 코인의 현재 가격이 매수한 시점의 가격 * 0.98보다 작거나 같거나 가격증가율이 음수로 바뀌어 코인을 시장가로 매도합니다 ==")
        return record_coin_data()

    return holding_coin

# 메인 프로그램
def main():
    try:
        holding_coin = None
        while True:
            if not holding_coin:
                holding_coin = record_coin_data()
            else:
                holding_coin = sell_coin(holding_coin)

            # 1분 대기
            time.sleep(60)

    except KeyboardInterrupt:
        print("프로그램을 종료합니다.")

    except Exception as e:
        force_exit(f"예상치 못한 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
