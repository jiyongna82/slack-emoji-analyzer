import os
import time
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# [보안] GitHub Secrets에서 설정한 환경 변수를 불러옵니다.
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

client = WebClient(token=SLACK_BOT_TOKEN)

# 통계용 변수 세팅
giver_total = Counter()              # 누른 횟수 총합
receiver_total = Counter()           # 받은 횟수 총합
giver_emojis = defaultdict(Counter)  # 인원별 누른 이모지 상세
receiver_emojis = defaultdict(Counter)# 인원별 받은 이모지 상세
user_names = {}

def get_user_name(user_id):
    """사용자 ID를 실명으로 변환 (캐싱 적용)"""
    if user_id in user_names: return user_names[user_id]
    try:
        res = client.users_info(user=user_id)
        name = res["user"]["real_name"] or res["user"]["name"]
        user_names[user_id] = name
        return name
    except: return user_id

def run_monthly_analysis():
    try:
        # 1. 집계 기간 설정 (전월 1일 00:00:00 ~ 이번 달 1일 00:00:00 직전)
        now = datetime.now()
        first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_prev_month = first_day_this_month - timedelta(seconds=1)
        first_day_prev_month = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0)

        oldest_ts = (datetime.now() - timedelta(days=30)).timestamp()
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
                # 메시지 작성자가 있고 리액션이 있는 경우만 집계
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

        # 3. 슬랙 메시지 구성 (마크다운 서식)
        if not giver_total:
            msg_text = f"📊 *{target_month_str} 이모지 리액션 결산*\n\n지난 달에는 수집된 데이터가 없습니다. 🥲"
        else:
            msg_text = f"📊 *{target_month_str} DC중부운용센터팀 이모지 리액션 결산* 📊\n\n"
            
            # (1) 이모지 사냥꾼 TOP 5 (많이 누른 사람)
            msg_text += "🏆 *[이모지 사냥꾼] Emoji를 가장 많이 누른 TOP 5*\n"
            for i, (uid, total) in enumerate(giver_total.most_common(5), 1):
                # 가장 많이 사용한 이모지 상위 3개 추출
                top_3 = " / ".join([f":{e}:({c})" for e, c in giver_emojis[uid].most_common(3)])
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({total}회) ➞ {top_3}\n"
                
            # (2) 이모지 마스터 TOP 5 (다양한 종류 사용)
            msg_text += "\n🎨 *[이모지 마스터] 가장 다양한 표현을 쓴 TOP 5*\n"
            variety_rank = sorted(giver_emojis.items(), key=lambda x: len(x[1]), reverse=True)[:5]
            for i, (uid, emoji_dict) in enumerate(variety_rank, 1):
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({len(emoji_dict)}종류 사용)\n"

            # (3) 이모지 부자 TOP 5 (많이 받은 사람)
            msg_text += "\n💖 *[이모지 부자] Emoji를 가장 많이 받은 TOP 5*\n"
            for i, (uid, total) in enumerate(receiver_total.most_common(5), 1):
                # 가장 많이 받은 이모지 상위 3개 추출
                top_3 = " / ".join([f":{e}:({c})" for e, c in receiver_emojis[uid].most_common(3)])
                msg_text += f"> *{i}위:* {get_user_name(uid)} ({total}개) ➞ {top_3}\n"
            
            msg_text += "\n_이번 달도 서로 격려하며 따뜻한 소통으로 훈훈한 분위기 만들어가요!_😀🤣"

        # 4. 슬랙 채널 전송
        client.chat_postMessage(channel=CHANNEL_ID, text=msg_text)
        print("✅ 슬랙 메시지 전송 성공!")

    except SlackApiError as e:
        print(f"❌ 슬랙 API 에러: {e.response['error']}")
    except Exception as e:
        print(f"❌ 예기치 못한 에러: {e}")

if __name__ == "__main__":
    run_monthly_analysis()
