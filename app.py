import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="财务对账系统", layout="wide")
st.title("📂 毅兴/旭达 - 多批次汇款对账系统")

if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame()

# --- 数据导入 ---
st.sidebar.header("📥 数据导入")
uploaded_excel = st.sidebar.file_uploader("导入历史 Excel", type=["xlsx"])

if uploaded_excel and st.sidebar.button("同步 Excel 数据"):
    sheets = pd.read_excel(uploaded_excel, sheet_name=None, header=None)
    all_data = []
    for sheet_name, df in sheets.items():
        if sheet_name in ["旭达", "毅兴"]:
            # 1. 定位表头
            header_idx = -1
            for i, row in df.iterrows():
                if "公司名称" in row.values:
                    header_idx = i
                    df.columns = [str(c).strip() for c in row.values]
                    break
            
            if header_idx != -1:
                data_df = df.iloc[header_idx + 1:].copy()
                
                # 2. 处理合并单元格 (关键：公司名称、开票时间、金额都要填充)
                fill_cols = ['公司名称', '开票时间', '项目名称', '金额']
                for col in fill_cols:
                    if col in data_df.columns:
                        data_df[col] = data_df[col].replace(r'^\s*$', np.nan, regex=True).ffill()
                
                # 3. 数字格式化
                for col in ['金额', '汇入金额']:
                    if col in data_df.columns:
                        data_df[col] = pd.to_numeric(data_df[col], errors='coerce').fillna(0)
                
                # 4. 汇总逻辑：按公司、时间、金额分组，计算汇入总额
                # 这样即使分三行汇入，系统也会知道它们合起来是多少
                data_df['所属销售方'] = sheet_name
                all_data.append(data_df)
    
    if all_data:
        st.session_state.db = pd.concat(all_data, ignore_index=True)
        st.sidebar.success("同步成功！已自动关联分批汇款。")

# --- 界面展示与逻辑计算 ---
if not st.session_state.db.empty:
    target = st.selectbox("筛选销售方", ["全部", "毅兴", "旭达"])
    view_df = st.session_state.db.copy()
    if target != "全部":
        view_df = view_df[view_df['所属销售方'] == target]

    # 计算：我们需要按“组”来观察是否结清
    # 这里的组定义为：同一个公司、同一天、同一个总金额
    # 自动计算每行的余额（基于组汇总）
    group_cols = ['公司名称', '开票时间', '金额']
    view_df['当前组已汇入'] = view_df.groupby(group_cols)['汇入金额'].transform('sum')
    view_df['余额'] = view_df['金额'] - view_df['当前组已汇入']
    
    # 状态判定
    def check_status(row):
        if row['余额'] <= 0: return "✅ 已结清"
        return f"❌ 欠款 ¥{row['余额']:,.2f}"
    
    view_df['状态'] = view_df.apply(check_status, axis=1)

    st.subheader(f"📊 {target} 明细看板")
    
    # 使用可编辑表格，让你能随时修改汇入金额
    edited_df = st.data_editor(
        view_df,
        column_config={
            "金额": st.column_config.NumberColumn("开票总额", format="¥%.2f"),
            "汇入金额": st.column_config.NumberColumn("本次汇入", format="¥%.2f"),
            "余额": st.column_config.NumberColumn("总剩余未收", format="¥%.2f"),
            "状态": st.column_config.TextColumn("结清状态"),
        },
        disabled=['公司名称', '开票时间', '项目名称', '金额', '余额', '状态', '所属销售方'],
        use_container_width=True,
        hide_index=True
    )

    if st.button("💾 保存数据更新"):
        st.session_state.db.update(edited_df)
        st.success("数据已持久化保存！")
else:
    st.info("请先导入 Excel 数据。")
