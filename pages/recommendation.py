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
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        ),
        card AS (
            SELECT
                c.CITY_CODE,
                c.DISTRICT_CODE,
                SUM(c.{sales_col}) AS TOTAL_CARD_SALES
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO c, latest l
            WHERE c.STANDARD_YEAR_MONTH = l.max_ym
            GROUP BY c.CITY_CODE, c.DISTRICT_CODE
        ),
        pop AS (
            SELECT
                f.CITY_CODE,
                f.DISTRICT_CODE,
                SUM(f.RESIDENTIAL_POPULATION + f.WORKING_POPULATION + f.VISITING_POPULATION) AS TOTAL_POPULATION
            FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO f, latest l
            WHERE f.STANDARD_YEAR_MONTH = l.max_ym
            GROUP BY f.CITY_CODE, f.DISTRICT_CODE
        ),
        income AS (
            SELECT
                a.CITY_CODE,
                a.DISTRICT_CODE,
                ROUND(SUM(a.CUSTOMER_COUNT * a.MEDIAN_INCOME) / NULLIF(SUM(a.CUSTOMER_COUNT), 0) / 10) AS MEDIAN_INCOME
            FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO a, latest l
            WHERE a.STANDARD_YEAR_MONTH = l.max_ym AND a.INCOME_TYPE = '1'
            GROUP BY a.CITY_CODE, a.DISTRICT_CODE
        ),
        combined AS (
            SELECT
                m.CITY_KOR_NAME,
                m.DISTRICT_KOR_NAME,
                c.TOTAL_CARD_SALES,
                p.TOTAL_POPULATION,
                i.MEDIAN_INCOME
            FROM card c
            JOIN pop p ON c.CITY_CODE = p.CITY_CODE AND c.DISTRICT_CODE = p.DISTRICT_CODE
            JOIN income i ON c.CITY_CODE = i.CITY_CODE AND c.DISTRICT_CODE = i.DISTRICT_CODE
            JOIN CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST m ON c.DISTRICT_CODE = m.DISTRICT_CODE
            WHERE c.TOTAL_CARD_SALES > 0 AND p.TOTAL_POPULATION > 0 AND i.MEDIAN_INCOME > 0
        ),
        normalized AS (
            SELECT
                CITY_KOR_NAME,
                DISTRICT_KOR_NAME,
                TOTAL_CARD_SALES,
                TOTAL_POPULATION,
                MEDIAN_INCOME,
                (TOTAL_CARD_SALES - MIN(TOTAL_CARD_SALES) OVER()) * 1.0
                    / NULLIF(MAX(TOTAL_CARD_SALES) OVER() - MIN(TOTAL_CARD_SALES) OVER(), 0) AS norm_card,
                (TOTAL_POPULATION - MIN(TOTAL_POPULATION) OVER()) * 1.0
                    / NULLIF(MAX(TOTAL_POPULATION) OVER() - MIN(TOTAL_POPULATION) OVER(), 0) AS norm_pop,
                (MEDIAN_INCOME - MIN(MEDIAN_INCOME) OVER()) * 1.0
                    / NULLIF(MAX(MEDIAN_INCOME) OVER() - MIN(MEDIAN_INCOME) OVER(), 0) AS norm_income
            FROM combined
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
            MEDIAN_INCOME AS "중위소득(만원)"
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