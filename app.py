import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime

# 1. 页面配置
st.set_page_config(page_title="发票管理中心 - 智能台账", layout="wide")
DB_FILE = "invoice_ledger_v4.csv"

# 2. 数据库读写
def load_data():
    if os.path.exists(DB_FILE):
        try: return pd.read_csv(DB_FILE).to_dict('records')
        except: return []
    return []

def save_data(data):
    if data:
        df = pd.DataFrame(data)
        df = df.sort_values(by="日期", ascending=False)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return df.to_dict('records')
    return []

# 3. 解析逻辑 (保持不变)
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([p.extract_text() or "" for p in pdf.pages])
        try:
            amt_m = re.search(r"（小写）¥?\s*([\d\.]+)", text)
            amt = float(amt_m.group(1)) if amt_m else 0.0
            dt_m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", text)
            dt = f"{dt_m.group(1)}-{dt_m.group(2)}-{dt_m.group(3)}" if dt_m else datetime.now().strftime("%Y-%m-%d")
            names = re.findall(r"名称\s*[:：]\s*([^\n\s]+)", text)
            buyer = names[0] if len(names) > 0 else "待手动输入购方"
            seller = names[1] if len(names) > 1 else "待手动输入销方"
            project = "待输入项目"
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", text)
                if p_match:
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址|地址", p_match.group(1))[0].strip(" :,，：")
                    break
            return {"销方": seller, "购方": buyer, "项目": project, "日期": dt, "金额": amt, "已收": 0.0, "文件名": file.name}
        except: return None

# 4. 初始化
if 'db' not in st.session_state:
    st.session_state.db = load_data()
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# 5. 侧边栏
with st.sidebar:
    st.title("📂 发票管理中心")
    
    # --- 新增：下载功能 ---
    if st.session_state.db:
        st.subheader("💾 数据导出")
        df_download = pd.DataFrame(st.session_state.db)
        csv_data = df_download.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下载 CSV 账本到本地",
            data=csv_data,
            file_name=f"发票台账_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
        )
    st.divider()
    # ----------------------

    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if uploaded_files and st.button("🚀 录入并归档"):
        for f in uploaded_files:
            res = parse_pdf(f)
            if res and not any(d['文件名'] == res['文件名'] and d['销方'] == res['销方'] for d in st.session_state.db):
                st.session_state.db.append(res)
        st.session_state.db = save_data(st.session_state.db)
        st.session_state.uploader_key += 1
        st.rerun()

    if st.session_state.db:
        sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        selected_seller = st.sidebar.radio("📁 销方文件夹", sellers)
    else: selected_seller = None

# 6. 主界面 (逻辑与之前一致)
if selected_seller:
    st.title(f"🏢 {selected_seller}")
    current_data = [d for d in st.session_state.db if d["销方"] == selected_seller]
    for buyer in sorted(list(set(d["购方"] for d in current_data))):
        buyer_invoices = [d for d in current_data if d["购方"] == buyer]
        total_bal = sum(i["金额"] - i["已收"] for i in buyer_invoices)
        with st.expander(f"🤝 客户：{buyer} {' (✅ 已结清)' if total_bal <= 0 else ''}", expanded=total_bal > 0):
            t_amt = sum(i["金额"] for i in buyer_invoices)
            t_paid = sum(i["已收"] for i in buyer_invoices)
            c1, c2, c3 = st.columns(3)
            c1.metric("累计应收", f"¥{t_amt:,.2f}")
            c2.metric("已到账", f"¥{t_paid:,.2f}")
            c3.metric("待收余款", f"¥{total_bal:,.2f}")
            st.divider()
            for inv in buyer_invoices:
                g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                col_info, col_amt, col_action = st.columns([4, 3, 1])
                with col_info:
                    new_proj = st.text_input("项目名称", value=inv["项目"], key=f"p_{g_idx}")
                    new_date = st.text_input("开票日期", value=inv["日期"], key=f"d_{g_idx}")
                with col_amt:
                    new_paid = st.number_input("实收", value=float(inv["已收"]), key=f"v_{g_idx}")
                    new_total = st.number_input("总额", value=float(inv["金额"]), key=f"t_{g_idx}")
                with col_action:
                    st.write(" ")
                    if st.button("🗑️", key=f"del_{g_idx}"):
                        st.session_state.db.pop(g_idx)
                        save_data(st.session_state.db)
                        st.rerun()
                if (new_proj != inv["项目"] or new_date != inv["日期"] or new_paid != inv["已收"] or new_total != inv["金额"]):
                    st.session_state.db[g_idx].update({"项目": new_proj, "日期": new_date, "已收": new_paid, "金额": new_total})
                    save_data(st.session_state.db)
                    st.toast("已保存修改")
                st.markdown("---")
