import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime

# 1. 页面配置与持久化文件定义
st.set_page_config(page_title="发票对账管理台账", layout="wide")
DB_FILE = "invoice_ledger_v2.csv" # 持久化数据库文件

# 自定义样式：区分“新增”与“老数据”
st.markdown("""
    <style>
    .stMetric { background-color: #fcfcfc; padding: 15px; border-radius: 12px; border: 1px solid #f0f0f0; }
    .status-new { background-color: #e3f2fd; color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 2. 数据库读取与保存逻辑
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            return df.to_dict('records')
        except: return []
    return []

def save_data(data):
    if data:
        pd.DataFrame(data).to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# 3. 核心解析引擎（兼容：项目名称/工程名称）
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([p.extract_text() or "" for p in pdf.pages])
        try:
            # 金额与日期
            amt = float(re.search(r"（小写）¥?\s*([\d\.]+)", text).group(1))
            dt_match = re.search(r"日期\s*[:：]\s*(\d{4})年(\d{2})月(\d{2})日", text)
            dt = f"{dt_match.group(1)}-{dt_match.group(2)}-{dt_match.group(3)}" if dt_match else "未知日期"
            
            # 销方与购方定位
            lines = [l.strip() for l in text.split('\n') if "名称" in l]
            buyer = lines[0].split(":")[-1].split("：")[-1].strip() if len(lines) > 0 else "未知购方"
            seller = lines[1].split(":")[-1].split("：")[-1].strip() if len(lines) > 1 else "未知销方"
            
            # 兼容“项目名称”或“工程名称”
            project = "未命名项目"
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", text)
                if p_match:
                    raw_p = p_match.group(1).strip()
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址|地址", raw_p)[0].strip(" :,，：")
                    break
            
            return {"销方": seller, "购方": buyer, "项目": project, "日期": dt, "金额": amt, "已收": 0.0, "文件名": file.name}
        except: return None

# 4. 初始化
if 'db' not in st.session_state:
    st.session_state.db = load_data()
if 'new_batch' not in st.session_state:
    st.session_state.new_batch = []

# 5. 侧边栏：精准查重上传
with st.sidebar:
    st.title("📂 归档中心")
    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files and st.button("🚀 开始解析并归类"):
        batch_added = []
        dups = 0
        for f in uploaded_files:
            temp_res = parse_pdf(f)
            if temp_res:
                # 【核心逻辑：局部查重】
                # 只有当 同一个销方(文件夹) 下 已经存在该文件名，才视为重复
                is_dup = any(d['文件名'] == temp_res['文件名'] and d['销方'] == temp_res['销方'] for d in st.session_state.db)
                
                if not is_dup:
                    st.session_state.db.append(temp_res)
                    batch_added.append(f.name)
                else:
                    dups += 1
        
        st.session_state.new_batch = batch_added
        save_data(st.session_state.db)
        if batch_added: st.success(f"新增 {len(batch_added)} 张发票")
        if dups: st.warning(f"跳过当前文件夹已存在的重复件: {dups} 张")

    st.divider()
    # 文件夹式切换
    if st.session_state.db:
        sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        selected_seller = st.radio("📁 销方目录 (文件夹)", sellers)
    else:
        selected_seller = None

# 6. 主界面展示
if selected_seller:
    st.title(f"📁 文件夹：{selected_seller}")
    # 筛选当前销方
    current_list = [d for d in st.session_state.db if d["销方"] == selected_seller]
    
    # 按购方分组
    for buyer in sorted(list(set(d["购方"] for d in current_list))):
        with st.expander(f"🤝 客户：{buyer}", expanded=True):
            invoices = [d for d in current_list if d["购方"] == buyer]
            
            # 客户汇总统计
            t_amt = sum(i["金额"] for i in invoices)
            t_paid = sum(i["已收"] for i in invoices)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("累计应收", f"¥{t_amt:,.2f}")
            m2.metric("已到账", f"¥{t_paid:,.2f}")
            m3.metric("余款", f"¥{t_amt - t_paid:,.2f}")
            
            st.divider()
            
            # 项目明细
            for inv in invoices:
                # 寻找在全局数据库中的位置以便修改
                g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                is_new = inv['文件名'] in st.session_state.new_batch
                
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    tag = '<span class="status-new">NEW</span>' if is_new else ''
                    st.markdown(f"**{inv['项目']}** {tag}", unsafe_allow_html=True)
                    st.caption(f"📅 {inv['日期']} | 📄 {inv['文件名']}")
                
                with c2:
                    new_val = st.number_input("录入实收", value=float(inv["已收"]), key=f"in_{g_idx}", step=100.0)
                    if new_val != inv["已收"]:
                        st.session_state.db[g_idx]["已收"] = new_val
                        save_data(st.session_state.db) # 自动保存
                
                bal = inv["金额"] - new_val
                with c3:
                    st.markdown(f"<p style='margin-top:30px; color:{'#28a745' if bal<=0 else '#f39c12'}'>{'✅ 已结清' if bal<=0 else f'待收: ¥{bal:,.2f}'}</p>", unsafe_allow_html=True)
                
                with c4:
                    st.write(" ")
                    if st.button("🗑️", key=f"del_{g_idx}"):
                        st.session_state.db.pop(g_idx)
                        save_data(st.session_state.db)
                        st.rerun()
else:
    st.info("💡 请在左侧上传并解析发票，数据将自动分类并永久保存。")
