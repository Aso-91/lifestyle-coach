import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import json
import sqlite3

MENU_FILE = "menu_data.json"
# 昨日の勉強内容を保存・読み込み
def save_yesterday(subject):
    conn = sqlite3.connect("coach.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO study_log (subject)
        VALUES (?)
        """,
        (subject,)
    )
    conn.commit()
    conn.close()

def save_daily_record(
        subject,
        sleep_hours,
        mood,
        fatigue        
):
    conn = sqlite3.connect("coach.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO study_log (
        record_date,
        subject,
        sleep_hours,
        mood,
        fatigue
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        subject,
        sleep_hours,
        mood,
        fatigue
    ))
    conn.commit()
    conn.close()

def get_previous_record():
    conn = sqlite3.connect("coach.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        sleep_hours,
        mood,
        fatigue
    FROM study_log
    ORDER BY id DESC
    LIMIT 1
    """)

    row =cursor.fetchone()
    conn.close()
    return row

def init_db():
    conn = sqlite3.connect("coach.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT,
    subject TEXT,
    sleep_hours REAL,
    mood TEXT,
    fatigue INTEGER
    )
    """)
    conn.commit()
    conn.close()

def load_yesterday():
    conn = sqlite3.connect("coach.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT subject
    FROM study_log
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return None
    
# 献立データ読み込み
def load_menu():
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "breakfast": ["パン", "おにぎり", "ヨーグルト"],
            "lunch": ["パスタ", "カレー", "ラーメン"],
            "dinner": ["焼き魚", "味噌汁", "ハンバーグ"],
            "tomato_dishes": ["トマトパスタ", "トマトスープ"],
            "potato_dishes": ["じゃがバター", "ポテトグラタン"]
        }
# 今日の状態から献立をAIが勝手に選ぶ
def smart_menu_choice(mood, fatigue, body_condition):
    menu = load_menu()
    # 気分が良い日はトマト料理
    if mood == "good":
        return (
            random.choice(menu["tomato_dishes"]),
            random.choice(menu["tomato_dishes"]),
            random.choice(menu["tomato_dishes"])
        )
    # 疲労度が高い日はじゃがいも料理
    if fatigue >= 7:
        return (
            random.choice(menu["potato_dishes"]),
            random.choice(menu["potato_dishes"]),
            random.choice(menu["potato_dishes"])
        )
    # 体調がだるい日はスープ系
    if body_condition == "だるい":
        soup_options = ["トマトスープ", "ミネストローネ"]
        return (
            random.choice(soup_options),
            random.choice(soup_options),
            random.choice(soup_options)
        )
    # 普通の日は通常献立
    return (
        random.choice(menu["breakfast"]),
        random.choice(menu["lunch"]),
        random.choice(menu["dinner"])
    )
# 勉強内容の細分化
SUBJECT_DETAILS = {
    "英語": ["単語", "文法", "長文", "英作文", "リスニング"],
    "数学": ["計算", "図形", "関数", "確率", "ベクトル"],
    "国語": ["漢字", "現代文", "古文", "漢文"],
    "理科": ["生物", "化学", "物理"],
    "社会": ["地理", "日本史", "世界史", "公民"]
}
# ★最低50分を絶対確保するバージョン
def decide_block_length(mood, fatigue, body_condition):
    base = 50
    if mood == "good":
        base += 10
    elif mood == "bad":
        base -= 10
    if fatigue >= 7:
        base -= 10
    if body_condition in ["頭痛", "だるい"]:
        base -= 10
    return max(50, min(base, 60))
class UserStatus:
    def __init__(self, sleep_hours, study_hours, mood, fatigue,
                 plans, body_condition, anxious_subject, want_subject,
                 yesterday_subject, today_food, study_subjects):
        self.sleep_hours = sleep_hours
        self.study_hours = study_hours
        self.mood = mood
        self.fatigue = fatigue
        self.plans = plans
        self.body_condition = body_condition
        self.anxious_subject = anxious_subject
        self.want_subject = want_subject
        self.yesterday_subject = yesterday_subject
        self.today_food = today_food
        self.study_subjects = study_subjects
class DayScheduler:
    def __init__(self, user_status):
        self.user_status = user_status
        self.schedule = []
    def _parse_time(self, time_str):
        return datetime.strptime(time_str, "%H:%M")
    def generate_base_schedule(self):
        plans_sorted = sorted(self.user_status.plans,
                              key=lambda x: self._parse_time(x['start']))
        for plan in plans_sorted:
            self.schedule.append({
                "title": plan['title'],
                "start": plan['start'],
                "end": plan['end']
            })
        return self.schedule
# 勉強内容を決める
def decide_subjects(yesterday, anxious, want, study_subjects):
    subjects = []
    if anxious:
        subjects.append(anxious)
    if want and want not in subjects:
        subjects.append(want)
    if yesterday and yesterday not in subjects:
        subjects.append(yesterday)
    for s in study_subjects:
        if s not in subjects:
            subjects.append(s)
    if not subjects:
        subjects.append("復習")
    return subjects
# 勉強ブロック生成
def create_study_blocks(subjects, fatigue, start_str, total_hours, mood, body_condition):
    blocks = []
    start = datetime.strptime(start_str, "%H:%M")
    remaining_minutes = int(total_hours * 60)
    block_len = decide_block_length(mood, fatigue, body_condition)
    rest_len = 10 if mood == "good" else 15 if mood == "normal" else 20
    i = 0
    while remaining_minutes > 0:
        subj = subjects[i % len(subjects)]
        detail = random.choice(SUBJECT_DETAILS.get(subj, ["復習"]))
        study_m = min(block_len, remaining_minutes)
        blocks.append({
            "title": f"{subj}（{detail}）",
            "start": start.strftime("%H:%M"),
            "end": (start + timedelta(minutes=study_m)).strftime("%H:%M")
        })
        start += timedelta(minutes=study_m)
        remaining_minutes -= study_m
        if remaining_minutes <= 0:
            break
        blocks.append({
            "title": "休憩",
            "start": start.strftime("%H:%M"),
            "end": (start + timedelta(minutes=rest_len)).strftime("%H:%M")
        })
        start += timedelta(minutes=rest_len)
        i += 1
    return blocks, start
# 睡眠提案
def sleep_schedule(fatigue, sleep_hours, last_time):
    if fatigue >= 7:
        return {"title": "就寝", "start": "22:30", "end": "07:30"}
    elif sleep_hours < 6:
        return {"title": "就寝", "start": "23:00", "end": "07:00"}
    else:
        return {"title": "就寝", "start": "23:30", "end": "07:00"}
# 生活モードの提案
def lifestyle_suggestions():
    suggestions = [
        "軽く散歩して気分転換するのはどう？",
        "好きな音楽を聴きながらゆっくりする時間も大事だよ。",
        "部屋の片付けを10分だけやると気持ちがスッキリするよ。",
        "趣味を少しだけやってみるのも良いと思う。",
        "明日の準備をちょっとだけしておくと安心できるよ。"
    ]
    return random.choice(suggestions)
# ★「なし」を正しく判定する最新版
def food_recommendation(fatigue, mood, body_condition, today_food):
    # 入力が None または「なし」系なら「何も食べてない」と判断
    if today_food is None or today_food.strip() in ["なし", "何も食べてない", "食べてない", "未食"]:
        base_msg = "今日はまだ何も食べていないみたいだね。"
        if fatigue >= 7:
            return base_msg + " エネルギー補給のために、軽く何か食べておくといいかも。"
        if mood == "bad":
            return base_msg + " 甘いものを少し食べると気分転換になるかも。"
        return base_msg + " 水分だけでも少し取っておこう。"
    if fatigue >= 7:
        return "疲れているため、水分と塩分をしっかり取るのがおすすめです。"
    if mood == "bad":
        return "気分が落ちているため、甘いものを少し食べると気分転換になります。"
    if body_condition == "頭痛":
        return "頭痛がある場合は水分をしっかり取りましょう。"
    return f"今日は『{today_food}』を食べましたね。水分も少し足しておくと良いです。"

def main():
    init_db()
    st.title("生活改善AIコーチ（完全版）")
    st.link_button(
        "使い方についてはこちらでダウンロード（クリックまたは長押し）",
        "https://raw.githubusercontent.com/Aso-91/lifestyle-coach/main/%E3%82%A2%E3%83%97%E3%83%AA%E8%AA%AC%E6%98%8E%E6%9B%B8.pdf"
    )
    # ★ 勉強するかどうか
    study_mood = st.radio("今日は勉強したい気分ですか？", ["yes" , "no"])
    # ★ 勉強しない日は生活モード
    if study_mood == "no":
        st.header("今日は勉強はお休みモードだね")
        st.write(lifestyle_suggestions())
        # 献立はAIが勝手に選ぶ
        breakfast, lunch, dinner = smart_menu_choice("normal", 0, "普通")
        st.subheader("今日の献立案")
        st.write(f"朝：{breakfast}")
        st.write(f"昼：{lunch}")
        st.write(f"夜：{dinner}")
        return
    # ★ 勉強モード
    sleep_hours = st.number_input("昨夜の睡眠時間（時間）を入力してください: ",
                                  min_value=0.0,
                                  max_value=24.0,
                                  value=7.0,
                                  step=0.5
                                  )
    study_hours = st.number_input("今日の勉強予定時間（時間）を入力してください: ",
                                  min_value=0.5,
                                  max_value=12.0,
                                  value=3.0,
                                  step=0.5
                                  )
    mood = st.selectbox("今の気分 ：", ["good", "normal", "bad"])
    fatigue = st.slider("今の疲労度（0〜10）: ", min_value=0, max_value=10, value=5)
    body_condition = st.selectbox("今日の体調: ", ["頭痛" ,"だるい" , "普通" , "元気"])
    today_food = st.text_input("今日食べたもの・飲んだもので印象的なもの")

    subjects_text = st.text_area(
        "勉強したい科目（複数ならカンマで区切る）",
        placeholder="英語,数学,物理"
    )
    study_subjects = [
        s.strip()
        for s in subjects_text.split(",")
        if s.strip()
    ]

    st.subheader("今日の予定入力")
    st.caption("学校や部活、習い事など本日の予定を入れてください。例：バイト 16:00 20:00")
    plan_df = st.data_editor(
        pd.DataFrame(
            columns=["title", "start", "end"]
        ),
        num_rows="dynamic"
    )
    plans = []

    for _, row in plan_df.iterrows():
        if row["title"]:
            plans.append({
                "title": row["title"],
                "start": row["start"],
                "end": row["end"]
            })

    yesterday_subject = load_yesterday()

    anxious_subject = st.text_input("今日一番不安な科目は？: ")
    want_subject = st.text_input("今日一番やりたい科目は？: ")
    if st.button("スケジュール作成"):
        previous = get_previous_record()

        user_status = UserStatus(
                sleep_hours, study_hours, mood, fatigue,
                plans, body_condition, anxious_subject,
                want_subject, yesterday_subject, today_food, study_subjects
            )
        scheduler = DayScheduler(user_status)
        base_schedule = scheduler.generate_base_schedule()
        subjects = decide_subjects(
                yesterday_subject,
                anxious_subject,
                want_subject,
                study_subjects
            )
        if plans:
                study_start = plans[-1]["end"]
        else:
                study_start = "18:00"
        study_blocks, last_time = create_study_blocks(
                subjects,
                fatigue,
                study_start,
                study_hours,
                mood,
                body_condition
            )
        sleep_block = sleep_schedule(fatigue, sleep_hours, last_time)

        st.subheader("予定")
        st.dataframe(
                pd.DataFrame(base_schedule)
            )
        
        st.subheader("勉強スケジュール")
        st.dataframe(
                pd.DataFrame(study_blocks)
            )
        
        st.subheader("睡眠提案")
        st.write(
                f"{sleep_block['start']} - "
                f"{sleep_block['end']} : "
                f"{sleep_block['title']}"
            )
            
            # ★ 献立はAIが勝手に選ぶ
        breakfast, lunch, dinner = smart_menu_choice(mood, fatigue, body_condition)
        st.subheader("今日の献立案")
        st.write(f"朝：{breakfast}")
        st.write(f"昼：{lunch}")
        st.write(f"夜：{dinner}")
        
        st.info(food_recommendation(fatigue, mood, body_condition, today_food))

        if previous:
            prev_sleep = previous[0]
            prev_mood = previous[1]
            prev_fatigue = previous[2]

            st.subheader("前回との比較")

            sleep_diff = sleep_hours - prev_sleep
            if sleep_diff > 0:
                st.success(
                    f"睡眠時間が前回より"
                    f"{sleep_diff:.1f}時間増えています"
                )
            elif sleep_diff < 0:
                st.warning(
                    f"睡眠時間が前回より"
                    f"{abs(sleep_diff):.1f}時間減っています"
                )
            else:
                st.info("睡眠時間は前回と同じです")

            fatigue_diff = fatigue - prev_fatigue
            if fatigue_diff > 0:
                st.warning(
                    f"疲労度が"
                    f"{fatigue_diff}上がっています"
                )
            elif fatigue_diff < 0:
                st.success(
                    f"疲労度が"
                    f"{abs(fatigue_diff)}下がっています"
                )
            else:
                st.info("疲労度は前回と同じです")

            st.write(
                f"前回の気分:{prev_mood}"
            )
            if mood == prev_mood:
                st.success(
                    f"気分は前回と同じ「{mood}」です"
                )
            else:
                st.write(
                    f"気分は{prev_mood} ⇒ {mood}"
                )

        conn = sqlite3.connect("coach.db")
        df = pd.read_sql_query(
            """
            SELECT *
            FROM study_log
            ORDER BY id
            """,
            conn
        )
        conn.close()

        st.subheader("📈睡眠時間の推移")
        st.line_chart(
            df.set_index("record_date")["sleep_hours"]
        )

        st.subheader("📈疲労度の推移")
        st.line_chart(
            df.set_index("record_date")["fatigue"]
        )

        if subjects:
            save_daily_record(
                subjects[0],
                sleep_hours,
                mood,
                fatigue
            )
main()