from datetime import datetime, timedelta, timezone
import json
import os
import random
import time
from huggingface_hub import HfApi, hf_hub_download
import pandas as pd
import streamlit as st

st.set_page_config(page_title="我.要.放.假！", page_icon="🎯")
tz_taiwan = timezone(timedelta(hours=8))
DRAW_PASSWORD = "52388"

# 相容 Streamlit Secrets 與系統環境變數
HF_TOKEN = st.secrets.get("HF_TOKEN", os.getenv("HF_TOKEN"))
REPO_ID = "Taichuanlee/daily-lottery-data"
DATA_FILENAME = "data.json"
api = HfApi()

# === 幹話與語錄庫 ===
crowd_roasts = [
    "🔥 你們也太多人報名了吧？到底誰留下來上班？",
    "👀 算一算都雙位數了... 單位唱空城計是吧？",
    "🚨 還有人不想回家嗎？是不是沒假了？",
    "🏃 搶成這樣，平常跑急救如果有這個速度就好了！",
    "☕ 留下來的人功德無量，建議院長明天請全體喝大冰拿。",
    "🙏 大家都想逃，這磁場已經壓不住了！",
]

suspense_texts = [
    "⏳ 正在計算功德值中...",
    "⏳ 正在祈求EOC電話乖乖...",
    "⏳ 病人不要來，我想回家...",
    "⏳ 正在計算今天誰不適合上班的磁場最容易觸霉頭，優先放生...",
    "⏳ 系統黑箱作業中...",
    "⏳ 我要爆炸了...",
    "⏳ 別搞...",
    "⏳ 一個都別想走...",
    "⏳ 給我留下來上班...",
    "⏳ 還有誰還沒被放過勒...",
]

win_greetings = [
    "🎉 恭喜脫離苦海！快走，趁 Leader 還沒反悔！",
    "🎉 今日陽壽已扣除，成功兌換提早下班一張！",
    "🎉 慢走不送！剩下的病人跟記錄我們會含淚替你守護的。",
    "🎉 跑快一點，千萬不要回頭看！記得上差勤請假！",
    "🎉 恭喜祖上積德！今日幸運值已達顛峰，下班請小心不要踩到狗屎！",
    "🎉 趁現在沒下雨，快跑！",
]

# ==========================================
# 🎯 崗位專屬幹話資料庫（隨時可自由增刪）
# ==========================================

# 1. 共通幹話群組（同區同仁共用）
COMMON_GROUPS = {
    # 重症區 (C1 ~ C5)
    "C": [
        "重症需要你。",
        "重症的別跑啊。",
        "重症的夥伴在看你。",
    ],
    # 大暫區 (A1 ~ A8)
    "A": [
        "大暫就好好交班吧。",
        "大暫的夥伴在瞪你。",
        "你走了其他的大暫夥伴會很孤單。",
        "大暫缺你不可。",
    ],
    # 後線 (M8 ~ M12)
    "M_BACK": [
        "都上後線就別走了吧...",
    ],
    # 門神/外傷區 (T1 ~ T2)
    "T": [
        "門神別走。",
        "守門的，鎮住阿。",
    ],
    # 點班區 (O1, O3)
    "O": [
        "點完班再走吧...",
        "來診的病人們等著你...",
    ],
}

# 2. 個別崗位專屬句（有獨立梗的寫這裡，會自動跟共通句合併）
INDIVIDUAL_POSITION_EGGS = {
    # Leader
    "L": [
        "Leader 還想跑啊？",
        "你走了誰卡你勒？",
        "下個替死鬼是誰勒？",
        "看一下你隔壁的，等下就是他上 Leader 了。",
    ],
    # 內科單獨崗位
    "M1": [
        "M1 也想走阿？哪個衰鬼會頂你勒？",
        "M1 今天很空ㄟ，確定要走嗎？",
        "M1 很滿喔，希望你可以抽中。",
    ],
    "M2": [
        "你走了 M23 很孤單ㄟ。",
    ],
    "M4": [
        "U 區感覺很多隔離ㄟ，快跑。",
        "U 區老人等著你 ><",
        "你沒抽中的話，今天就要一個人待在裡面了。",
    ],
    "M11": [
        "你們今天人力很奢侈喔...",
    ],
    "M12": [
        "你們今天人力很奢侈喔...",
    ],
    # 重症個別特別句
    "C1": [
        "重一就留下來好好交班，好嗎？",
    ],
    "C2": [
        "重二請好好外送。",
    ],
    # 兒科/特殊區
    "P": [
        "小人國，笑你。",
    ],
}


def get_position_roast(pos: str) -> str:
    """自動判定崗位並隨機抽取一句幹話"""
    p = pos.upper().strip()
    pool = []

    # 1. 抓取個別專屬句
    if p in INDIVIDUAL_POSITION_EGGS:
        pool.extend(INDIVIDUAL_POSITION_EGGS[p])

    # 2. 抓取所屬群組共通句
    if p in ["C1", "C2", "C3", "C4", "C5"]:
        pool.extend(COMMON_GROUPS["C"])
    elif p in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]:
        pool.extend(COMMON_GROUPS["A"])
    elif p in ["M8", "M9", "M10", "M11", "M12"]:
        pool.extend(COMMON_GROUPS["M_BACK"])
    elif p in ["T1", "T2", "T"]:
        pool.extend(COMMON_GROUPS["T"])
    elif p in ["O1", "O3"]:
        pool.extend(COMMON_GROUPS["O"])

    # 3. 如果有符合的句子，隨機挑一句回傳；沒有就回傳 None
    return random.choice(pool) if pool else None


# === 全伺服器共用資料池 ===
@st.cache_resource
def get_global_data():
    try:
        local_path = hf_hub_download(
            repo_id=REPO_ID,
            repo_type="dataset",
            filename=DATA_FILENAME,
            token=HF_TOKEN,
        )
        with open(local_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


shared_submissions = get_global_data()


def sync_to_cloud():
    """背景儲存到 HF Dataset"""
    try:
        with open(DATA_FILENAME, "w", encoding="utf-8") as f:
            json.dump(shared_submissions, f, ensure_ascii=False, indent=2)
        api.upload_file(
            path_or_fileobj=DATA_FILENAME,
            path_in_repo=DATA_FILENAME,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN,
            commit_message=f"update data.json ({len(shared_submissions)} records)",
        )
    except Exception as e:
        print(f"[WARN] 儲存失敗: {e}")


st.title("🎯 猜猜誰是幸運兒")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📝 員工填寫", "🎯 Leader 抽籤", "🗑️ 刪除單筆紀錄", "🧹 資料 Reset"]
)

# --- Tab 1: 員工填寫 ---
with tab1:
    with st.form("submit_form", clear_on_submit=True):
        pos_input = st.text_input("上班位置（如 M1、L、C2）")
        submit_btn = st.form_submit_button("送出")

        if submit_btn:
            cleaned_pos = pos_input.strip()
            if not cleaned_pos:
                st.warning("⚠️ 你搞個空白誰知道你是誰！")
            elif cleaned_pos.upper() in [d["崗位"].upper() for d in shared_submissions]:
                st.error(f"🚫 {cleaned_pos} 不要重複報名，給我認真上班")
            else:
                now_time = datetime.now(tz=tz_taiwan).strftime("%Y-%m-%d %H:%M:%S")
                shared_submissions.append({"崗位": cleaned_pos, "時間": now_time})
                sync_to_cloud()
                st.success(f"✅ 已填寫：{cleaned_pos}（時間：{now_time}）")

                # 💬 觸發崗位專屬幹話
                roast_msg = get_position_roast(cleaned_pos)
                if roast_msg:
                    st.info(f"👉 {cleaned_pos}：{roast_msg}")

                # 滿 10 人以上觸發大群體吐槽
                if len(shared_submissions) >= 10:
                    st.warning(f"📢 目前已達 {len(shared_submissions)} 人報名！\n\n{random.choice(crowd_roasts)}")

    st.subheader("🗂️ 目前所有填寫紀錄")
    if st.button("🔄 立即刷新填寫紀錄"):
        st.cache_resource.clear()
        st.rerun()

    if shared_submissions:
        st.table(pd.DataFrame(shared_submissions))
    else:
        st.info("目前尚無填寫紀錄")

# --- Tab 2: Leader 抽籤 ---
with tab2:
    count = st.selectbox("抽出人數", options=[1, 2, 3, 4, 5])

    if st.button("🎲 開始抽籤", type="primary"):
        total_records = len(shared_submissions)
        if count > total_records:
            st.error(f"❌ 目前只有 {total_records} 筆資料，無法抽出 {count} 人")
        else:
            random_suspense = random.choice(suspense_texts)
            with st.spinner(random_suspense):
                time.sleep(2)

            winners = random.sample(shared_submissions, int(count))

            st.success(random.choice(win_greetings))
            st.table(pd.DataFrame(winners))

# --- Tab 3: 刪除單筆紀錄 ---
with tab3:
    if "del_success_msg" in st.session_state:
        st.success(st.session_state["del_success_msg"])
        del st.session_state["del_success_msg"]

    del_pwd = st.text_input("輸入管理密碼", type="password", key="del_pwd")
    options = [
        f"{i+1}. {d['崗位']}｜{d['時間']}"
        for i, d in enumerate(shared_submissions)
    ]
    selected = st.selectbox(
        "選擇要刪除的紀錄", options=["請選擇..."] + options
    )

    if st.button("確認刪除", type="primary"):
        if del_pwd != DRAW_PASSWORD:
            st.error("❌ 密碼錯誤，無法刪除")
        elif selected == "請選擇...":
            st.warning("⚠️ 請先選擇要刪除的資料")
        else:
            idx = int(selected.split(".")[0]) - 1
            if 0 <= idx < len(shared_submissions):
                deleted = shared_submissions.pop(idx)
                sync_to_cloud()
                st.session_state["del_success_msg"] = f"✅ 已成功刪除：{deleted['崗位']}｜{deleted['時間']}"
                st.rerun()

# --- Tab 4: 資料 Reset ---
with tab4:
    if "reset_success_msg" in st.session_state:
        st.success(st.session_state["reset_success_msg"])
        del st.session_state["reset_success_msg"]

    if "confirm_reset" not in st.session_state:
        st.session_state["confirm_reset"] = False

    reset_pwd = st.text_input(
        "輸入管理密碼以清空資料", type="password", key="reset_pwd"
    )

    if st.button("🧹 清空所有資料", type="secondary"):
        if reset_pwd != DRAW_PASSWORD:
            st.error("❌ 密碼錯了，你是誰？不要搞。")
            st.session_state["confirm_reset"] = False
        elif len(shared_submissions) == 0:
            st.info("目前資料庫已經是空的，無需清空。")
            st.session_state["confirm_reset"] = False
        else:
            st.session_state["confirm_reset"] = True

    if st.session_state["confirm_reset"]:
        st.warning("⚠️ **警告：此操作將抹除所有同仁填寫的紀錄，無法復原！**")
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🚨 你確定嗎？刪錯了你就是千古罪人！", type="primary"):
                shared_submissions.clear()
                sync_to_cloud()
                st.session_state["reset_success_msg"] = "✅ 所有填寫紀錄已清空"
                st.session_state["confirm_reset"] = False
                st.rerun()
        with col2:
            if st.button("點此反悔取消"):
                st.session_state["confirm_reset"] = False
                st.rerun()
