import streamlit as st

st.set_page_config(page_title="AI 기반 상권 분석 플랫폼", layout="wide")

pg = st.navigation([
    st.Page("pages/home.py", title="플랫폼", default=True),
    st.Page("pages/analysis.py", title="상권 분석"),
    st.Page("pages/recommendation.py", title="상권 랭킹"),
])
pg.run()
