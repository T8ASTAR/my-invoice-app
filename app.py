import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

# 页面配置
st.set_page_config(page_title="发票管理助手", layout="wide")

# 自定义 CSS 让界面更极简
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .new-tag { background-color: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 增强版解析函数 ---
def parse_invoice_pdf(file):
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            content = page.extract_text()
            if content: full_text += content
        
        try:
            # 1. 提取金额
            amt_match = re.search(r"（小写）¥?\s*([\d\.]+)", full_text)
            amount = float(amt_match.group(1)) if amt_match else 0.0
            
            # 2. 提取日期
            date_match = re.search(r"日期\s*[:：]\s*(\d{4})年(\d{2})月(\d{2})日", full_text)
            inv_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "未知日期"

            # 3. 提取销方与购方
            lines = full_text.split('\n')
            name_lines = [l for l in lines if "名称" in l and (":" in l or "：" in l)]
            buyer, seller = "未知购方", "未知销方"
            if len(name_lines) >= 2:
                buyer = name_lines[0].split(":")[-1].split("：")[-1].strip()
                seller = name_lines[1].split(":")[-1].split("：")[-1].strip()

            # 4. 兼容“项目名称”或“工程名称”
            project = "未命名项目"
            keywords = ["项目名称", "工程名称", "项目", "工程"]
            for kw in keywords:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", full_text)
                if p_match:
                    raw_p = p_match.group(1).strip()
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址", raw_p)[0].strip(" :,，：")
                    break

            return {
                "销方": seller, "购方": buyer, "项目": project, 
                "日期": inv_date, "金额": amount, "已收": 0.0, 
                "文件名": file.name, "录入时间": datetime.now()
            }
        except Exception:
            return None

# --- 数据管理 ---
if 'invoice_db' not in st.session_state:
    st.session_state.invoice_db = []
if 'last_upload_batch' not in st.session_state:
    st.session_state.last_upload_batch = []

# --- 侧边栏 ---
with st.sidebar:
    st.title("📂 归档中心")
    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 开始处理"):
            new_count = 0
            duplicate_files = []
            current_batch_names = []
            
            for f in uploaded_files:
                # 【查重逻辑】
                is_duplicate = any(d['文件名'] == f.name for d in st.session_state.invoice_db)
                if is_duplicate:
                    duplicate_files.append(f.name)
                else:
                    res = parse_invoice_pdf(f)
                    if res:
                        st.session_state.invoice_db.append(res)
                        current_batch_names.append(f.name)
                        new_count += 1
            
            st.session_state.last_upload_batch = current_batch_names
            
            if new_count > 0: st.success(f"新增成功: {new_count} 张")
            if duplicate_files:
                st.warning(f"跳过重复文件: {len(duplicate_files)} 张")
                with st.expander("点击查看重复名单"):
                    for df in duplicate_files: st.write(f"🚫 {df}")

    st.divider()
    if st.session_state.invoice_db:
        all_sellers = sorted(list(set(d["销方"] for d in st.session_state.invoice_db)))
        selected_folder = st.radio("当前销方目录", all_sellers)
    else:
        selected_folder = None

# --- 主界面 ---
if selected_folder:
    st.title(f"📁 {selected_folder}")
    current_data = [d for d in st.session_state.invoice_db if d["销方"] == selected_folder]
    
    for buyer in sorted(list(set(d["购方"] for d in current_data))):
        with st.expander(f"🤝 购方：{buyer}", expanded=True):
            invoices = [d for d in current_data if d["购方"] == buyer]
            
            # 汇总显示
            t_amt = sum(i["金额"] for i in invoices)
            t_paid = sum(i["已收"] for i in invoices)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("总应收", f"¥{t_amt:,.2f}")
            m2.metric("总到账", f"¥{t_paid:,.2f}")
            m3.metric("总欠款", f"¥{t_amt-t_paid:,.2f}")
            
            st.divider()
            
            for inv in invoices:
                idx = st.session_state.invoice_db.index(inv)
                # 【标注逻辑】如果是本次刚上传的，显示“新”标签
                is_new = inv['文件名'] in st.session_state.last_upload_batch
                
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    new_tag = '<span class="new-tag">🆕 本次新增</span>' if is_new else ''
                    st.markdown(f"**{inv['项目']}** {new_tag}", unsafe_allow_html=True)
                    st.caption(f"日期: {inv['日期']} | 文件: {inv['文件名']}")
                
                with c2:
                    val = st.number_input("到账金额", value=inv["已收"], key=f"v_{idx}", step=100.0)
                    st.session_state.invoice_db[idx]["已收"] = val
                
                bal = inv["金额"] - val
                with c3:
                    if bal <= 0: st.markdown("<b style='color:green'>✅ 结清</b>", unsafe_allow_html=True)
                    else: st.markdown(f"待收: <b style='color:orange'>¥{bal:,.2f}</b>", unsafe_allow_html=True)
                
                with cols_del := c4:
                    if st.button("🗑️", key=f"d_{idx}"):
                        st.session_state.invoice_db.pop(idx)
                        st.rerun()
