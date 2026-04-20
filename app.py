import streamlit as st
import pandas as pd
import numpy as np

# 1. 页面基本配置
st.set_page_config(page_title="毅兴&旭达发票管理", layout="wide", initial_sidebar_state="expanded")

# 自定义 CSS：让“已结清”的行颜色变浅
st.markdown("""
    <style>
    .stDataFrame [data-testid="stTable"] tr:has(td:contains("✅")) {
        color: #A0A0A0; /* 浅灰色 */
        opacity: 0.6;
    }
    .main-header {
        font-size: 24px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 初始化模拟数据库（实际生产可对接数据库）
if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame(columns=[
        "销售方", "购买方", "日期", "项目名称", "发票金额", "已进账", "余额", "状态"
    ])

# --- 侧边栏：目录页/导航 ---
with st.sidebar:
    st.markdown("## 📂 业务目录")
    # 选择查看的主体
    menu = st.radio("请选择公司看板：", ["💡 概览首页", "🏢 毅兴机械", "🏗️ 旭达建筑"])
    
    st.divider()
    
    st.markdown("## 📤 上传中心")
    upload_files = st.file_uploader("支持图片或 PDF", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True)
    
    if upload_files and st.button("🚀 开始识别并入库"):
        # 这里模拟 OCR 识别过程
        for file in upload_files:
            # 模拟：如果是 PDF 且文件名含“旭达”
            company = "旭达建筑" if "旭达" in file.name else "毅兴机械"
            new_record = {
                "销售方": company,
                "购买方": "浙江宁慈建设工程有限公司", # 模拟识别
                "日期": "2026-04-20",
                "项目名称": "明祥路道路工程",
                "发票金额": 220800.0,
                "已进账": 0.0,
                "余额": 220800.0,
                "状态": "⏳ 待进账"
            }
            st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([new_record])], ignore_index=True)
        st.success("发票已自动分类入库！")

# --- 主界面逻辑 ---

# 过滤数据
if menu == "🏢 毅兴机械":
    display_df = st.session_state.db[st.session_state.db["销售方"] == "毅兴机械"]
    st.markdown(f"<div class='main-header'>毅兴机械 - 发票回收明细</div>", unsafe_allow_html=True)
elif menu == "🏗️ 旭达建筑":
    display_df = st.session_state.db[st.session_state.db["销售方"] == "旭达建筑"]
    st.markdown(f"<div class='main-header'>旭达建筑 - 发票回收明细</div>", unsafe_allow_html=True)
else:
    display_df = st.session_state.db
    st.markdown(f"<div class='main-header'>全业务数据概览</div>", unsafe_allow_html=True)

# 数据展示与编辑
if not display_df.empty:
    # 自动计算逻辑
    display_df['余额'] = display_df['发票金额'] - display_df['已进账']
    
    # 状态判定逻辑：结清项自动带上勾号
    def get_status(rem):
        return "✅ 已结清" if rem <= 0 else "⏳ 未结清"
    display_df['状态'] = display_df['余额'].apply(get_status)

    # 统计板块
    c1, c2, c3 = st.columns(3)
    c1.metric("总开票额", f"¥{display_df['发票金额'].sum():,.2f}")
    c2.metric("已回收", f"¥{display_df['已进账'].sum():,.2f}", delta_color="normal")
    c3.metric("待收尾款", f"¥{display_df['余额'].sum():,.2f}", delta="-待收")

    st.divider()

    # 可编辑表格
    edited_df = st.data_editor(
        display_df,
        column_config={
            "发票金额": st.column_config.NumberColumn(format="¥%.2f"),
            "已进账": st.column_config.NumberColumn("本次汇入金额", format="¥%.2f", help="在此修改收到的钱款"),
            "余额": st.column_config.NumberColumn("剩余欠款", format="¥%.2f"),
            "状态": st.column_config.TextColumn("状态")
        },
        disabled=["销售方", "购买方", "日期", "项目名称", "发票金额", "余额", "状态"],
        use_container_width=True,
        hide_index=True
    )

    if st.button("💾 保存本次录入"):
        # 同步回全局 session_state
        st.session_state.db.update(edited_df)
        st.rerun()
else:
    st.info("当前暂无数据，请通过左侧上传中心录入发票图片或 PDF。")
