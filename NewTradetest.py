import time
import pyupbit

# 프로그램 시작 시간
START_TIME = time.time()

# 거래소 객체 생성
upbit = pyupbit.Upbit('ACCESS_KEY', 'SECRET_KEY')  # 업비트 API 키 입력

# 거래량 증가율 계산 함수
def calculate_volume_change(prev_volume, current_volume):
    return ((current_volume - prev_volume) / prev_volume) * 100

# 메인 프로그램
def main():
    try:
        # 통장의 보유 KRW 초기값 설정 (업비트 환경에서 로그인된 내 계좌에서 불러옴)
        ACCOUNT_KRW = upbit.get_balance('KRW')

        while True:
            # 1. 업비트 내의 모든 KRW 코인의 1분단위 거래량, 가격을 조회한다.
            coin_data = pyupbit.get_tickers(fiat="KRW")

            # 2. 매수조건에 부합하는 코인 찾고 매수하기
            if time.time() - START_TIME >= 6 * 60:  # 프로그램 시작 6분 후부터 수행
                candidate_coins = []
                for market in coin_data:
                    ticker = pyupbit.get_ohlcv(market)
                    prev_volume = ticker.iloc[-2]['close']
                    current_volume = ticker.iloc[-1]['volume']
                    volume_change = calculate_volume_change(prev_volume, current_volume)

                    # 1분 기준 거래량이 가장 높은 코인을 1등으로 기록
                    if volume_change > 0 and (not candidate_coins or volume_change > candidate_coins[0]['volume_change']):
                        candidate_coins = [{'market': market, 'volume_change': volume_change}]

                # 5분간 기록된 1등 코인의 거래량 증가율이 가장 높은 코인을 선정
                if candidate_coins:
                    selected_coin = candidate_coins[0]
                    ticker = pyupbit.get_ticker(selected_coin['market'])
                    selected_coin_price = ticker['trade_price']

                    # 3. 매수는 통장의 보유 KRW가 5000원 이상일 경우에만 수행
                    if ACCOUNT_KRW >= 5000 and selected_coin_price > ticker['prev_closing_price']:
                        # 매수 로직 추가
                        upbit.buy_market_order(selected_coin['market'], ACCOUNT_KRW // selected_coin_price)
                        print(f"매수: {selected_coin['market']}, 가격: {selected_coin_price}")
                        # 매수 후 보유 KRW 업데이트
                        ACCOUNT_KRW -= (ACCOUNT_KRW // selected_coin_price) * selected_coin_price

            # 잠시 대기
            time.sleep(60)

    except Exception as e:
        # 오류 발생 시 디스코드 알림 보내고 프로그램 종료
        discord_payload = {"content": f"프로그램에서 오류가 발생했습니다: {str(e)}"}
        requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
        raise

if __name__ == "__main__":
    main()

