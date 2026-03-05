import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# [테스트용] GitHub Secrets를 쓰지 않고 직접 값을 넣습니다.
# 성공 확인 후에는 다시 os.environ.get 방식으로 돌려놓으면 됩니다.
SLACK_BOT_TOKEN = "xoxb-7406884674743-9219227059376-K2MNiHgZmm2tFU0EWl96RJUS" 
CHANNEL_ID = "C07DZJ66FKJ" 

client = WebClient(token=SLACK_BOT_TOKEN)

# 통계 변수 생략 (로직 동일)
giver_total = Counter()
receiver_total = Counter()
giver_emojis = defaultdict(Counter)
receiver_emojis = defaultdict(Counter)
user_names = {}

def get_user_name(user_id):
    if user_id in user_names: return user_names[user_id]
    try:
        res = client.users_info(user=user_id)
        name = res["user"]["real_name"] or res["user"]["name"]
        user_names[user_id] = name
        return name
    except: return user_id

def run_monthly_analysis():
    try:
        print(f"🚀 진단 시작: 채널 ID {CHANNEL_ID}로 접속 시도 중...")
        
        # 테스트: 채널 정보 먼저 가져오기
        info = client.conversations_info(channel=CHANNEL_ID)
        print(f"✅ 채널 확인 성공: {info['channel']['name']}")

        # 기간 설정 (최근 30일로 확장)
        oldest_ts = (datetime.now() - timedelta(days=30)).timestamp()
        
        # 데이터 수집 로직
        response = client.conversations_history(channel=CHANNEL_ID, limit=100, oldest=str(oldest_ts))
        
        for msg in response.get("messages", []):
            receiver = msg.get("user")
            if "reactions" in msg and receiver:
                for reaction in msg["reactions"]:
                    emoji = reaction["name"]
                    count = reaction["count"]
                    givers = reaction.get("users", [])
                    for giver in givers:
                        giver_total[giver] += 1
                        giver_emojis[giver][emoji] += 1
                    receiver_total[receiver] += count
                    receiver_emojis[receiver][emoji] += count

        if not giver_total:
            msg_text = "📊 데이터가 없습니다. 이모지를 더 눌러보세요! 🥲"
        else:
            msg_text = "📊 *DC중부운용센터팀 이모지 리액션 결산 (테스트)* 📊\n"
            for i, (uid, total) in enumerate(giver_total.most_common(3), 1):
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({total}회)\n"

        # 전송
        client.chat_postMessage(channel=CHANNEL_ID, text=msg_text)
        print("✅ 슬랙 메시지 전송 성공!")

    except SlackApiError as e:
        print(f"❌ 슬랙 API 에러 상세: {e.response['error']}")
        if e.response['error'] == 'channel_not_found':
            print("👉 경고: 여전히 채널을 못 찾습니다. 봇이 채널에 '초대' 되었는지 다시 확인하세요!")
    except Exception as e:
        print(f"❌ 기타 에러: {e}")

if __name__ == "__main__":
    run_monthly_analysis()
