import streamlit as st
import altair as alt

session = st.connection("snowflake")

INDUSTRY_MAP = {
    "음식": "FOOD_SALES",
    "커피": "COFFEE_SALES",
    "엔터테인먼트": "ENTERTAINMENT_SALES",
    "백화점": "DEPARTMENT_STORE_SALES",
    "대형마트": "LARGE_DISCOUNT_STORE_SALES",
    "소매점": "SMALL_RETAIL_STORE_SALES",
    "의류/잡화": "CLOTHING_ACCESSORIES_SALES",
    "스포츠/문화/레저": "SPORTS_CULTURE_LEISURE_SALES",
    "숙박": "ACCOMMODATION_SALES",
    "여행": "TRAVEL_SALES",
    "뷰티": "BEAUTY_SALES",
    "생활서비스": "HOME_LIFE_SERVICE_SALES",
    "교육/학원": "EDUCATION_ACADEMY_SALES",
    "의료": "MEDICAL_SALES",
    "전자/가구": "ELECTRONICS_FURNITURE_SALES",
    "자동차": "CAR_SALES",
    "주유소": "GAS_STATION_SALES",
    "이커머스": "E_COMMERCE_SALES",
}

METRIC_LABELS = {
    "카드매출": "card_sales",
    "유동인구": "floating_pop",
    "중위소득": "median_income",
}
st.title("상권 랭킹")
st.markdown("업종과 우선순위를 선택하면 **최적 상권 Top 10**을 추천해드립니다.")

col1, col2 = st.columns([1, 2])

with col1:
    industry = st.selectbox("업종 선택", list(INDUSTRY_MAP.keys()))

with col2:
    st.markdown("##### 우선순위 설정")
    st.caption("1순위(0.5) → 2순위(0.3) → 3순위(0.2)")
    metrics = list(METRIC_LABELS.keys())
    p1 = st.selectbox("1순위 (가중치 0.5)", metrics, index=0)
    remaining1 = [m for m in metrics if m != p1]
    p2 = st.selectbox("2순위 (가중치 0.3)", remaining1, index=0)
    remaining2 = [m for m in remaining1 if m != p2]
    p3 = remaining2[0]
    st.info(f"3순위 (가중치 0.2): **{p3}**")

weights = {METRIC_LABELS[p1]: 0.5, METRIC_LABELS[p2]: 0.3, METRIC_LABELS[p3]: 0.2}
sales_col = INDUSTRY_MAP[industry]

if st.button("🔍 추천 받기", type="primary", use_container_width=True):
    with st.spinner("분석 중..."):
        query = f"""
        WITH latest AS (
            SELECT MAX(STANDARD_YEAR_MONTH) AS max_ym
            FROM UNIFIED_DISTRICT_MONTHLY
        ),
        normalized AS (
            SELECT
                u.CITY_KOR_NAME,
                u.DISTRICT_KOR_NAME,
                u.{sales_col} AS TOTAL_CARD_SALES,
                u.TOTAL_POPULATION,
                u.WEIGHTED_MEDIAN_INCOME,
                (TOTAL_CARD_SALES - MIN(TOTAL_CARD_SALES) OVER()) * 1.0
                    / NULLIF(MAX(TOTAL_CARD_SALES) OVER() - MIN(TOTAL_CARD_SALES) OVER(), 0) AS norm_card,
                (u.TOTAL_POPULATION - MIN(u.TOTAL_POPULATION) OVER()) * 1.0
                    / NULLIF(MAX(u.TOTAL_POPULATION) OVER() - MIN(u.TOTAL_POPULATION) OVER(), 0) AS norm_pop,
                (u.WEIGHTED_MEDIAN_INCOME - MIN(u.WEIGHTED_MEDIAN_INCOME) OVER()) * 1.0
                    / NULLIF(MAX(u.WEIGHTED_MEDIAN_INCOME) OVER() - MIN(u.WEIGHTED_MEDIAN_INCOME) OVER(), 0) AS norm_income
            FROM UNIFIED_DISTRICT_MONTHLY u, latest l
            WHERE u.STANDARD_YEAR_MONTH = l.max_ym
        )
        SELECT
            CITY_KOR_NAME AS "구",
            DISTRICT_KOR_NAME AS "동",
            HACKATHON.DATA.WEIGHTED_SCORE(
                norm_card, norm_pop, norm_income,
                {weights['card_sales']}, {weights['floating_pop']}, {weights['median_income']}
            ) AS "종합점수",
            ROUND(norm_card * 100, 2) AS "매출점수",
            ROUND(norm_pop * 100, 2) AS "유동인구점수",
            ROUND(norm_income * 100, 2) AS "소득점수",
            TOTAL_CARD_SALES AS "카드매출(원)",
            ROUND(TOTAL_POPULATION, 0) AS "유동인구(명)",
            WEIGHTED_MEDIAN_INCOME AS "중위소득(만원)"
        FROM normalized
        ORDER BY "종합점수" DESC
        LIMIT 10
        """
        df = session.query(query)

    if df.empty:
        st.warning("결과가 없습니다.")
    else:
        st.markdown(f"### 📍 {industry} 업종 추천 상권 Top 10")
        st.caption(f"가중치: {p1}(0.5) / {p2}(0.3) / {p3}(0.2)")

        st.dataframe(
            df.style.format({
                "종합점수": "{:.2f}",
                "매출점수": "{:.2f}",
                "유동인구점수": "{:.2f}",
                "소득점수": "{:.2f}",
                "카드매출(원)": "{:,.0f}",
                "유동인구(명)": "{:,.0f}",
                "중위소득(만원)": "{:,.0f}",
            }),
            use_container_width=True,
            hide_index=True,
        )