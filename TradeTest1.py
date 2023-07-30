import time
import pyupbit
import datetime

# 내 access, secret 정보
access = "PzZBIxyRO5Wdxxz6LgormuEULaLD8dC6mIOEk0zP"
secret = "bxxaRezyfkQzC5qmZ0yxoaaesxFNx0SN2lXriBZz"

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")

# 이전에 매수한 코인 정보를 저장하는 변수
bought_coin_ticker = None

# 모든 KRW 코인 리스트 가져오기
all_krw_coins = pyupbit.get_tickers(fiat="KRW")

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()

        # 9:00 < 현재 < 8:59:50까지 동작
        if start_time < now < end_time - datetime.timedelta(seconds=10):
            # 가장 가까운 타겟 가격과 해당 코인 저장용 변수
            nearest_target_price_diff = None
            nearest_target_coin = None

            # 모든 KRW 코인에 대해 검사
            for ticker in all_krw_coins:
                start_time = get_start_time(ticker)
                end_time = start_time + datetime.timedelta(days=1)

                target_price = get_target_price(ticker, 0.3)
                current_price = get_current_price(ticker)

                # 가장 가까운 타겟 가격 코인 찾기
                target_price_diff = abs(target_price - current_price)
                if nearest_target_price_diff is None or target_price_diff < nearest_target_price_diff:
                    nearest_target_price_diff = target_price_diff
                    nearest_target_coin = ticker

                if target_price < current_price:
                    krw = get_balance("KRW")
                    if krw > 5000 and not bought_coin_ticker:  # 이전에 매수한 코인이 없을 때만 매수
                        upbit.buy_market_order(ticker, krw*0.9995)
                        # 매수한 코인 정보 저장
                        bought_coin_ticker = ticker
                        break  # 매수 후 바로 루프를 빠져나가기

            # 평균 매수가 조회 및 수익률 확인
            if bought_coin_ticker:
                avg_buy_price = upbit.get_avg_buy_price(bought_coin_ticker)
                if avg_buy_price is not None:
                    current_price = get_current_price(bought_coin_ticker)
                    # 현재 가격과 평균 매수가 비교하여 2% 이상이거나 매수가격의 0.98배 이상이면 전량 매도
                    if current_price >= avg_buy_price * 1.02 or current_price <= avg_buy_price * 0.98:
                        upbit.sell_market_order(bought_coin_ticker, get_balance(bought_coin_ticker))
                        # 매도 후 코인 정보 초기화
                        bought_coin_ticker = None

        time.sleep(1)

    except Exception as e:
        print(e)
        time.sleep(1)