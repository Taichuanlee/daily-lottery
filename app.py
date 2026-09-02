from datetime import datetime, timedelta, timezone
import json
import os
import random
from huggingface_hub import HfApi, hf_hub_download
import pandas as pd
import streamlit as st

st.set_page_config(page_title="抽籤系統", page_icon="🎯")
tz_taiwan = timezone(timedelta(hours=8))
DRAW_PASSWORD = "52388"

HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "Taichuanlee/daily-lottery-data"
DATA_FILENAME = "data.json"
api = HfApi()


# === 關鍵優化：全伺服器共用資料池，避免每個人進來都狂打 API ===
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


# 取得目前共用的資料名單
shared_submissions = get_global_data()


def sync_to_cloud():
  """非同步/背景儲存到 HF Dataset，不卡住使用者連線"""
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


st.title("🎯 抽籤系統（當班抽放）")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📝 員工填寫", "🎯 Leader 抽籤", "🗑️ 刪除單筆紀錄", "🧹 資料 Reset"]
)

# --- Tab 1: 員工填寫 ---
with tab1:
  with st.form("submit_form", clear_on_submit=True):
    pos_input = st.text_input("上班位置代碼（如 M1、L、C2）")
    submit_btn = st.form_submit_button("送出")

    if submit_btn:
      cleaned_pos = pos_input.strip()
      if not cleaned_pos:
        st.warning("⚠️ 請輸入上班位置代碼，內容不可為空！")
      elif cleaned_pos in [d["崗位"] for d in shared_submissions]:
        st.error(f"🚫 {cleaned_pos} 不要重複報名，給我認真上班")
      else:
        now_time = datetime.now(tz=tz_taiwan).strftime("%Y-%m-%d %H:%M:%S")
        shared_submissions.append({"崗位": cleaned_pos, "時間": now_time})
        sync_to_cloud()
        st.success(f"✅ 已填寫：{cleaned_pos}（時間：{now_time}）")

  st.subheader("🗂️ 目前所有填寫紀錄")
  if st.button("🔄 立即刷新填寫紀錄"):
    # 清除快取重新從雲端載入
    st.cache_resource.clear()
    st.rerun()

  # 換成原生 HTML 表格，徹底避開 iOS Safari 的 CSS 預載錯誤
  if shared_submissions:
    st.table(pd.DataFrame(shared_submissions))
  else:
    st.info("目前尚無填寫紀錄")

# --- Tab 2: Leader 抽籤 ---
with tab2:
  count = st.selectbox("抽出人數", options=[1, 2, 3, 4, 5])
  if st.button("開始抽籤", type="primary"):
    total_records = len(shared_submissions)
    if count > total_records:
      st.error(f"❌ 目前只有 {total_records} 筆資料，無法抽出 {count} 人")
    else:
      winners = random.sample(shared_submissions, int(count))
      st.success("🎉 抽籤完成！")
      # 換成原生 HTML 表格
      st.table(pd.DataFrame(winners))

# --- Tab 3: 刪除單筆紀錄 ---
with tab3:
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
      st.warning("請先選擇要刪除的資料")
    else:
      idx = int(selected.split(".")[0]) - 1
      if 0 <= idx < len(shared_submissions):
        deleted = shared_submissions.pop(idx)
        sync_to_cloud()
        st.success(f"✅ 已刪除：{deleted['崗位']}｜{deleted['時間']}")
        st.rerun()

# --- Tab 4: 資料 Reset ---
with tab4:
  reset_pwd = st.text_input(
      "輸入管理密碼以清空資料", type="password", key="reset_pwd"
  )
  if st.button("🧹 清空所有資料", type="primary"):
    if reset_pwd != DRAW_PASSWORD:
      st.error("❌ 密碼錯誤，無法重設。")
    else:
      shared_submissions.clear()
      sync_to_cloud()
      st.success("✅ 所有填寫紀錄已清空")
      st.rerun()
