import streamlit as st

st.title("AI 기반 상권 분석 플랫폼")
st.markdown("서울 주요 상권 데이터를 분석하고 인사이트를 발견하세요.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("상권 분석")
    st.write("구·동별 카드 매출, 유동인구, 소득·자산 데이터를 지도와 차트로 분석합니다.")
    st.page_link("pages/analysis.py", label="상권 분석 시작하기 →", use_container_width=True)

with col2:
    st.subheader("상권 랭킹")
    st.write("서울 주요 상권을 매출·유동인구·소득 기준으로 순위를 비교합니다.")
    st.page_link("pages/recommendation.py", label="랭킹 보기 →", use_container_width=True)
