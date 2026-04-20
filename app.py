import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime

# 1. 页面配置
st.set_page_config(page_title="发票管理中心 - 智能台账", layout="wide")
DB_FILE = "invoice_ledger_v4.csv"

# 自定义样式
st.markdown("""
    <style>
    .stMetric { background-color: #fcfcfc; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    .status-new { background-color: #e3f2fd; color: #0d47a1; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
    .settled-tag { color: #28a745; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 2. 数据库读写
def load_data():
    if os.path.exists(DB_FILE):
        try: return pd.read_csv(DB_FILE).to_dict('records')
        except: return []
    return []

def save_data(data):
    if data:
        df = pd.DataFrame(data)
        # 统一按日期排序（降序）
        df = df.sort_values(by="日期", ascending=False)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return df.to_dict('records')
    return []

# 3. 增强解析逻辑
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([p.extract_text() or "" for p in pdf.pages])
        try:
            amt_m = re.search(r"（小写）¥?\s*([\d\.]+)", text)
            amt = float(amt_m.group(1)) if amt_m else 0.0
            dt_m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", text)
            dt = f"{dt_m.group(1)}-{dt_m.group(2)}-{dt_m.group(3)}" if dt_m else datetime.now().strftime("%Y-%m-%d")
            
            # 改进名称抓取：优先匹配备注栏上方的销售方信息
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
    st.session_state.uploader_key = 0 # 用于清空上传组件

# 5. 侧边栏：上传与清空
with st.sidebar:
    st.title("📂 发票管理中心")
    # 使用 key 动态刷新来实现上传后自动清空
    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    
    if uploaded_files and st.button("🚀 录入并归档"):
        for f in uploaded_files:
            res = parse_pdf(f)
            if res:
                # 局部查重
                if not any(d['文件名'] == res['文件名'] and d['销方'] == res['销方'] for d in st.session_state.db):
                    st.session_state.db.append(res)
        
        st.session_state.db = save_data(st.session_state.db)
        st.session_state.uploader_key += 1 # 改变 key，清空上传器
        st.rerun()

    st.divider()
    if st.session_state.db:
        sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        selected_seller = st.radio("📁 销方文件夹", sellers)
    else: selected_seller = None

# 6. 主界面
if selected_seller:
    st.title(f"🏢 {selected_seller}")
    current_data = [d for d in st.session_state.db if d["销方"] == selected_seller]
    
    # 购方分组
    for buyer in sorted(list(set(d["购方"] for d in current_data))):
        buyer_invoices = [d for d in current_data if d["购方"] == buyer]
        
        # 计算该客户是否全部结清
        total_bal = sum(i["金额"] - i["已收"] for i in buyer_invoices)
        is_all_settled = total_bal <= 0
        
        # 需求：已结清的自动折叠 (expanded=False)
        with st.expander(f"🤝 客户：{buyer} {' (✅ 已结清)' if is_all_settled else ''}", expanded=not is_all_settled):
            # 汇总统计
            t_amt = sum(i["金额"] for i in buyer_invoices)
            t_paid = sum(i["已收"] for i in buyer_invoices)
            c1, c2, c3 = st.columns(3)
            c1.metric("累计应收", f"¥{t_amt:,.2f}")
            c2.metric("已到账", f"¥{t_paid:,.2f}")
            c3.metric("待收余款", f"¥{total_bal:,.2f}")
            
            st.divider()
            
            # 发票明细
            for inv in buyer_invoices:
                # 唯一定位
                g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                
                # 计算单笔差额
                bal = inv["金额"] - inv["已收"]
                
                # 每一行发票提供手动修改功能
                with st.container():
                    col_info, col_amt, col_action = st.columns([4, 3, 1])
                    
                    with col_info:
                        # 增加手动修改项目名称和日期的功能
                        new_proj = st.text_input("项目名称", value=inv["项目"], key=f"p_{g_idx}")
                        sub_c1, sub_c2 = st.columns(2)
                        new_date = sub_c1.text_input("开票日期", value=inv["日期"], key=f"d_{g_idx}")
                        sub_c2.caption(f"文件名: {inv['文件名']}")
                    
                    with col_amt:
                        new_paid = st.number_input("实收金额", value=float(inv["已收"]), key=f"v_{g_idx}", step=100.0)
                        new_total = st.number_input("票面总额", value=float(inv["金额"]), key=f"t_{g_idx}", step=100.0)
                    
                    with col_action:
                        st.write(" ")
                        if st.button("🗑️", key=f"del_{g_idx}"):
                            st.session_state.db.pop(g_idx)
                            save_data(st.session_state.db)
                            st.rerun()
                    
                    # 状态同步与实时保存
                    if (new_proj != inv["项目"] or new_date != inv["日期"] or 
                        new_paid != inv["已收"] or new_total != inv["金额"]):
                        st.session_state.db[g_idx].update({
                            "项目": new_proj, "日期": new_date, 
                            "已收": new_paid, "金额": new_total
                        })
                        save_data(st.session_state.db)
                        st.toast("修改已保存")
                    
                    st.markdown("---")
