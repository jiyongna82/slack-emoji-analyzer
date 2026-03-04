import os
import time
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# [보안] GitHub Secrets에서 설정한 값을 불러옵니다.
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

client = WebClient(token=SLACK_BOT_TOKEN)

# 통계용 변수
giver_total = Counter()
receiver_total = Counter()
giver_emojis = defaultdict(Counter)
receiver_emojis = defaultdict(Counter)
user_names = {}

def get_user_name(user_id):
    """사용자 ID를 실명으로 변환"""
    if user_id in user_names: return user_names[user_id]
    try:
        res = client.users_info(user=user_id)
        name = res["user"]["real_name"] or res["user"]["name"]
        user_names[user_id] = name
        return name
    except: return user_id

def run_monthly_analysis():
    try:
        # 1. 집계 기간 설정 (전월 1일 ~ 말일)
        now = datetime.now()
        first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_prev_month = first_day_this_month - timedelta(seconds=1)
        first_day_prev_month = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0)

        oldest_ts = first_day_prev_month.timestamp()
        latest_ts = first_day_this_month.timestamp()
        target_month_str = first_day_prev_month.strftime("%Y년 %m월")

        print(f"📅 분석 기간: {first_day_prev_month} ~ {last_day_prev_month}")
        
        # 2. 데이터 수집 (Pagination 처리)
        cursor = None
        while True:
            response = client.conversations_history(
                channel=CHANNEL_ID,
                cursor=cursor,
                limit=100,
                oldest=str(oldest_ts),
                latest=str(latest_ts)
            )
            
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
            
            if response.get("has_more"):
                cursor = response["response_metadata"]["next_cursor"]
            else:
                break

        # 3. 슬랙 메시지 구성
        if not giver_total:
            msg_text = f"📊 *{target_month_str} 이모지 결산*\n\n지난 달에는 수집된 리액션 데이터가 없습니다. 🥲"
        else:
            msg_text = f"📊 *{target_month_str} DC중부운용센터 이모지 리액션 결산* 📊\n\n"
            
            msg_text += "🏆 *[이모지 사냥꾼] Emoji를 가장 많이 누른 사람 TOP 5*\n"
            for i, (uid, total) in enumerate(giver_total.most_common(5), 1):
                top = " / ".join([f":{e}:({c}회)" for e, c in giver_emojis[uid].most_common(3)])
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({total}회) ➞ 선호: {top}\n"
                
            msg_text += "\n💖 *[이모지 부자] Emoji를 가장 많이 받은 사람 TOP 5*\n"
            for i, (uid, total) in enumerate(receiver_total.most_common(5), 1):
                top = " / ".join([f":{e}:({c}개)" for e, c in receiver_emojis[uid].most_common(3)])
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({total}개) ➞ 인기: {top}\n"
            
            msg_text += "\n_이번 달도 서로 격려하며 화이팅해요!_ 👏"

        # 4. 슬랙 전송
        client.chat_postMessage(channel=CHANNEL_ID, text=msg_text)
        print("✅ 성공적으로 슬랙에 전송되었습니다.")

    except SlackApiError as e:
        print(f"❌ 슬랙 에러: {e.response['error']}")
    except Exception as e:
        print(f"❌ 일반 에러: {e}")

if __name__ == "__main__":
    run_monthly_analysis()
