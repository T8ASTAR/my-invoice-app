import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

# 页面配置
st.set_page_config(page_title="极简发票管家", layout="wide")

# --- 核心逻辑：从 PDF 提取发票数据 ---
def extract_invoice_data(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
        
        # 使用正则表达式抓取核心字段（适配中国标准发票格式）
        try:
            seller = re.search(r"名称:(.*?)纳税人识别号", text, re.S).group(1).strip() if "名称:" in text else "未知销方"
            # 简化逻辑：通常发票第二个“名称”是销方，第一个是购方
            names = re.findall(r"名称:(.*?)\n", text)
            buyer_name = names[0].strip() if len(names) > 0 else "未知购方"
            seller_name = names[1].strip() if len(names) > 1 else "未知销方"
            
            amount = re.search(r"（小写）¥?(\d+\.\d+)", text).group(1)
            date_str = re.search(r"开票日期:(\d{4})年(\d{2})月(\d{2})日", text)
            invoice_date = datetime(int(date_str.group(1)), int(date_str.group(2)), int(date_str.group(3)))
            
            # 备注栏提取项目名称（匹配您发票中的规律）
            project = "未识别项目"
            memo = re.search(r"备\s*注(.*)", text, re.S)
            if memo:
                project_match = re.search(r"项目名称:(.*?)\n", memo.group(1))
                if project_match:
                    project = project_match.group(1).strip()

            return {
                "销方": seller_name,
                "购方": buyer_name,
                "项目": project,
                "日期": invoice_date,
                "应收金额": float(amount),
                "已收金额": 0.0
            }
        except Exception as e:
            st.error(f"识别解析失败，请手动检查 PDF 格式。错误: {e}")
            return None

# --- 初始化数据存储 ---
if 'invoice_data' not in st.session_state:
    st.session_state.invoice_data = []

# --- 侧边栏：功能与目录 ---
with st.sidebar:
    st.title("📂 功能面板")
    
    # 1. 录入模块
    st.subheader("1. 录入发票")
    uploaded_file = st.file_uploader("上传 PDF 电子发票", type="pdf")
    if uploaded_file:
        if st.button("开始识别并存入"):
            new_data = extract_invoice_data(uploaded_file)
            if new_data:
                st.session_state.invoice_data.append(new_data)
                st.success("录入成功！")

    st.divider()
    
    # 2. 目录切换（一级目录：销方）
    st.subheader("2. 销方切换")
    if st.session_state.invoice_data:
        all_sellers = list(set(item["销方"] for item in st.session_state.invoice_data))
        selected_seller = st.sidebar.radio("当前主体", all_sellers)
    else:
        selected_seller = None
        st.info("暂无数据，请先上传发票")

# --- 主界面：展示与核销 ---
if selected_seller:
    st.title(f"📊 {selected_seller}")
    
    # 数据过滤
    df = pd.DataFrame(st.session_state.invoice_data)
    current_df = df[df["销方"] == selected_seller]
    
    # 二级目录：购方汇总
    for buyer in current_df["购方"].unique():
        with st.expander(f"🏢 购方：{buyer}", expanded=True):
            buyer_items = current_df[current_df["购方"] == buyer]
            
            # 购方总计
            b_total = buyer_items["应收金额"].sum()
            b_paid = buyer_items["已收金额"].sum()
            b_bal = b_total - b_paid
            
            m1, m2, m3 = st.columns(3)
            m1.metric("累计应收", f"¥{b_total:,.2f}")
            m2.metric("已收总额", f"¥{b_paid:,.2f}")
            m3.metric("待收余额", f"¥{b_bal:,.2f}", delta=-b_bal if b_bal>0 else None)
            
            st.write("") # 间距
            
            # 三级目录：项目明细
            for idx, row in buyer_items.iterrows():
                # 使用 container 让界面更像卡片
                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    with c1:
                        st.markdown(f"**项目：{row['项目']}**")
                        st.caption(f"📅 开票时间: {row['日期'].strftime('%Y-%m-%d')}")
                    with c2:
                        # 核销输入
                        # 注意：这里使用 session_state 索引确保修改生效
                        new_val = st.number_input(f"录入到账 (¥{row['应收金额']:,.2f})", 
                                                min_value=0.0, 
                                                value=row["已收金额"], 
                                                key=f"input_{idx}")
                        st.session_state.invoice_data[idx]["已收金额"] = new_val
                    
                    bal = row["应收金额"] - new_val
                    with c3:
                        if bal <= 0:
                            st.markdown("### <span style='color:green'>✅ 已结清</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"未结：**¥{bal:,.2f}**")
                            if (datetime.now() - row["日期"]).days > 30:
                                st.markdown("<span style='color:red'>⚠️ 逾期预警</span>", unsafe_allow_html=True)
                    with c4:
                        if st.button("🗑️", key=f"del_{idx}"):
                            st.session_state.invoice_data.pop(idx)
                            st.rerun()
                st.divider()

# --- 导出 ---
if st.sidebar.button("📤 导出全量数据为 Excel"):
    if st.session_state.invoice_data:
        final_df = pd.DataFrame(st.session_state.invoice_data)
        final_df.to_csv("发票管理台账.csv", index=False, encoding='utf-8-sig')
        st.sidebar.success("导出成功！")
