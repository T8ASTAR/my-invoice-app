import streamlit as st
import pandas as pd

st.set_page_config(page_title="财务发票整合系统", layout="wide")
st.title("📂 毅兴/旭达 - 发票进账管理系统")

# 初始化数据库
if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame()

# --- 侧边栏：数据导入 ---
st.sidebar.header("📥 数据导入")
import_type = st.sidebar.radio("选择导入方式", ["上传历史 Excel", "上传新发票(图片/PDF)"])

if import_type == "上传历史 Excel":
    uploaded_excel = st.sidebar.file_uploader("选择 Excel 文件", type=["xlsx"])
    if uploaded_excel and st.sidebar.button("开始整合"):
        sheets = pd.read_excel(uploaded_excel, sheet_name=None)
        all_data = []
        for sheet_name, df in sheets.items():
            if sheet_name in ["旭达", "毅兴"]:
                # 清洗列名，去掉空格
                df.columns = [str(c).strip() for c in df.columns]
                
                # 自动寻找表头（兼容你截图里第30行左右的表头）
                if '公司名称' not in df.columns:
                    for i, row in df.iterrows():
                        if "公司名称" in row.values:
                            df.columns = [str(c).strip() for c in row.values]
                            df = df.iloc[i+1:].reset_index(drop=True)
                            break
                
                # 提取核心列
                target_cols = ['公司名称', '开票时间', '项目名称', '金额', '汇入金额', '余额']
                existing_cols = [c for c in target_cols if c in df.columns]
                
                temp_df = df[existing_cols].copy()
                temp_df['所属销售方'] = sheet_name # 这里就是你的“大文件夹”标签
                all_data.append(temp_df)
        
        if all_data:
            st.session_state.db = pd.concat(all_data, ignore_index=True)
            st.sidebar.success(f"已从 Excel 加载数据")

elif import_type == "上传新发票(图片/PDF)":
    invoice_file = st.sidebar.file_uploader("上传发票文件", type=["png", "jpg", "pdf"])
    if invoice_file and st.sidebar.button("自动识别并入库"):
        # 模拟 OCR 识别过程
        # 实际使用时，OCR 会识别出“销售方”是毅兴还是旭达
        # 识别出的“购买方”填充到“公司名称”
        new_data = {
            "公司名称": "浙江省围海建设集团", # 识别到的购买方
            "开票时间": "2026/04/14",
            "项目名称": "象山县海塘安澜项目",
            "金额": 74025.00,
            "汇入金额": 0.0,
            "余额": 74025.00,
            "所属销售方": "毅兴" # 根据识别到的销售方自动判定归入哪个“文件夹”
        }
        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([new_data])], ignore_index=True)
        st.sidebar.success("发票识别成功，已自动归类！")

# --- 主界面 ---
if not st.session_state.db.empty:
    # 第一步：选择看哪个“大文件夹”
    target_folder = st.selectbox("选择管理主体", ["全部", "毅兴", "旭达"])
    
    view_df = st.session_state.db
    if target_folder != "全部":
        view_df = view_df[view_df['所属销售方'] == target_folder]

    # 第二步：显示表格
    st.subheader(f"📊 {target_folder} 的明细账单")
    edited_df = st.data_editor(
        view_df,
        column_config={
            "金额": st.column_config.NumberColumn("发票原额", format="¥%.2f"),
            "汇入金额": st.column_config.NumberColumn("已收金额(手动输入)", format="¥%.2f"),
            "余额": st.column_config.NumberColumn("未收余额", format="¥%.2f"),
        },
        disabled=["公司名称", "开票时间", "项目名称", "金额", "余额", "所属销售方"],
        use_container_width=True,
        key="editor"
    )

    # 自动计算：只要你改了汇入金额，余额自动更新
    edited_df['余额'] = edited_df['金额'] - edited_df['汇入金额']
    
    # 第三步：统计状态
    total_unpaid = edited_df['余额'].sum()
    st.metric("当前筛选下总欠款", f"¥ {total_unpaid:,.2f}")
    
    if st.button("💾 确认保存并更新余额"):
        # 将修改写回数据库
        st.session_state.db.update(edited_df)
        st.success("数据已更新！")
else:
    st.info("请先导入 Excel 或上传发票图片。")
