import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime

# 1. 页面基本配置
st.set_page_config(page_title="发票持久化管理台账", layout="wide")

DB_FILE = "invoice_data.csv" # 永久存储文件名

# 2. 数据持久化函数
def load_db():
    """从本地文件加载数据"""
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            # 确保金额列是浮点数
            df['金额'] = df['金额'].astype(float)
            df['已收'] = df['已收'].astype(float)
            return df.to_dict('records')
        except:
            return []
    return []

def save_db(data_list):
    """保存数据到本地文件"""
    if data_list:
        df = pd.DataFrame(data_list)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# --- 核心解析引擎 ---
def extract_invoice_info(file):
    with pdfplumber.open(file) as pdf:
        full_text = "".join([p.extract_text() or "" for p in pdf.pages])
        
        try:
            amt_match = re.search(r"（小写）¥?\s*([\d\.]+)", full_text)
            amount = float(amt_match.group(1)) if amt_match else 0.0
            
            date_match = re.search(r"日期\s*[:：]\s*(\d{4})年(\d{2})月(\d{2})日", full_text)
            inv_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "未知日期"

            lines = [l.strip() for l in full_text.split('\n') if "名称" in l]
            buyer, seller = "未知购方", "未知销方"
            if len(lines) >= 2:
                buyer = lines[0].split(":")[-1].split("：")[-1].strip()
                seller = lines[1].split(":")[-1].split("：")[-1].strip()

            project = "未命名项目"
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", full_text)
                if p_match:
                    raw_p = p_match.group(1).strip()
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址|地址", raw_p)[0].strip(" :,，：")
                    break

            return {
                "销方": seller, "购方": buyer, "项目": project, 
                "日期": inv_date, "金额": amount, "已收": 0.0, 
                "文件名": file.name
            }
        except Exception:
            return None

# 3. 初始化或加载数据
if 'db' not in st.session_state:
    st.session_state.db = load_db()

# 4. 侧边栏：操作区
with st.sidebar:
    st.title("📂 档案存储中心")
    files = st.file_uploader("批量拖入 PDF", type="pdf", accept_multiple_files=True)
    
    if files and st.button("🚀 录入并存档"):
        new_added = 0
        for f in files:
            if not any(d['文件名'] == f.name for d in st.session_state.db):
                data = extract_invoice_info(f)
                if data:
                    st.session_state.db.append(data)
                    new_added += 1
        if new_added > 0:
            save_db(st.session_state.db) # 立即存档
            st.success(f"已存档 {new_added} 张新发票")
        else:
            st.warning("未检测到新发票（已跳过重复文件）")

    st.divider()
    if st.session_state.db:
        # 获取所有销方，形成文件夹目录
        all_sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        current_seller = st.radio("📁 切换销方文件夹", all_sellers)
    else:
        current_seller = None

# 5. 主界面
if current_seller:
    st.title(f"📁 当前主体：{current_seller}")
    seller_data = [d for d in st.session_state.db if d["销方"] == current_seller]
    
    for buyer in sorted(list(set(d["购方"] for d in seller_data))):
        with st.expander(f"🤝 客户：{buyer}", expanded=True):
            invoices = [d for d in seller_data if d["购方"] == buyer]
            
            # 指标汇总
            t_amt = sum(i["金额"] for i in invoices)
            t_paid = sum(i["已收"] for i in invoices)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("总金额", f"¥{t_amt:,.2f}")
            c2.metric("已收", f"¥{t_paid:,.2f}")
            c3.metric("余款", f"¥{t_amt - t_paid:,.2f}")
            
            st.divider()
            
            for inv in invoices:
                # 获取该条数据在全局列表中的原始索引，以便修改
                global_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'])
                
                cols = st.columns([3, 2, 2, 1])
                with cols[0]:
                    # 允许手动修改识别错的项目名称
                    new_proj = st.text_input("项目/工程名称", value=inv['项目'], key=f"p_{global_idx}")
                    st.session_state.db[global_idx]['项目'] = new_proj
                    st.caption(f"📅 {inv['日期']} | 📄 {inv['文件名']}")
                
                with cols[1]:
                    new_val = st.number_input("到账金额录入", value=inv["已收"], key=f"v_{global_idx}", step=100.0)
                    if new_val != inv["已收"]:
                        st.session_state.db[global_idx]["已收"] = new_val
                        save_db(st.session_state.db) # 金额变动自动保存
                
                bal = inv["金额"] - new_val
                with cols[2]:
                    st.markdown(f"<p style='margin-top:30px; color:{'green' if bal<=0 else 'orange'}'>{'✅ 已结清' if bal<=0 else f'待收: ¥{bal:,.2f}'}</p>", unsafe_allow_html=True)
                
                with cols[3]:
                    st.write(" ")
                    if st.button("🗑️", key=f"del_{global_idx}"):
                        st.session_state.db.pop(global_idx)
                        save_db(st.session_state.db)
                        st.rerun()

else:
    st.info("💡 请先在左侧上传 PDF。数据将自动保存至本地 invoice_data.csv 文件中。")
