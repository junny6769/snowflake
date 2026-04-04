# imports 
import streamlit as st
import altair as alt

#snowflake session 
session = st.connection("snowflake")

#page setup
st.set_page_config(page_title="AI 기반 상권 분석 플랫폼", layout="wide")
st.title("AI 기반 상권 분석 플랫폼")

#sales categories dictionary
SALES_CATEGORIES = {
    "음식": ("FOOD_SALES", "FOOD_COUNT"),
    "커피": ("COFFEE_SALES", "COFFEE_COUNT"),
    "오락": ("ENTERTAINMENT_SALES", "ENTERTAINMENT_COUNT"),
    "백화점": ("DEPARTMENT_STORE_SALES", "DEPARTMENT_STORE_COUNT"),
    "대형마트": ("LARGE_DISCOUNT_STORE_SALES", "LARGE_DISCOUNT_STORE_COUNT"),
    "소매점": ("SMALL_RETAIL_STORE_SALES", "SMALL_RETAIL_STORE_COUNT"),
    "의류·잡화": ("CLOTHING_ACCESSORIES_SALES", "CLOTHING_ACCESSORIES_COUNT"),
    "스포츠·문화·레저": ("SPORTS_CULTURE_LEISURE_SALES", "SPORTS_CULTURE_LEISURE_COUNT"),
    "숙박": ("ACCOMMODATION_SALES", "ACCOMMODATION_COUNT"),
    "여행": ("TRAVEL_SALES", "TRAVEL_COUNT"),
    "뷰티": ("BEAUTY_SALES", "BEAUTY_COUNT"),
    "생활서비스": ("HOME_LIFE_SERVICE_SALES", "HOME_LIFE_SERVICE_COUNT"),
    "교육": ("EDUCATION_ACADEMY_SALES", "EDUCATION_ACADEMY_COUNT"),
    "의료": ("MEDICAL_SALES", "MEDICAL_COUNT"),
    "가전·가구": ("ELECTRONICS_FURNITURE_SALES", "ELECTRONICS_FURNITURE_COUNT"),
    "자동차": ("CAR_SALES", "CAR_SALES_COUNT"),
    "자동차 서비스": ("CAR_SERVICE_SUPPLIES_SALES", "CAR_SERVICE_SUPPLIES_COUNT"),
    "주유소": ("GAS_STATION_SALES", "GAS_STATION_COUNT"),
    "이커머스": ("E_COMMERCE_SALES", "E_COMMERCE_COUNT"),
}

#숫자 변환
def format_amount(val):
    if abs(val) >= 1_0000_0000_0000:
        return f"{val / 1_0000_0000_0000:,.1f}조"
    elif abs(val) >= 1_0000_0000:
        return f"{val / 1_0000_0000:,.0f}억"
    elif abs(val) >= 1_0000:
        return f"{val / 1_0000:,.0f}만"
    return f"{val:,.0f}"

# 구/동 목록 테이블  
@st.cache_data
def load_districts():
    return session.query("""
        SELECT DISTINCT m.CITY_KOR_NAME, m.DISTRICT_KOR_NAME, m.CITY_CODE, m.DISTRICT_CODE
        FROM CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST m
        WHERE m.DISTRICT_CODE IN (
            SELECT DISTINCT DISTRICT_CODE FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        )
        ORDER BY m.CITY_KOR_NAME, m.DISTRICT_KOR_NAME
    """)

# 선택한 동에서 실제 데이터가 있는 업종만 보여줌 
@st.cache_data
def load_available_categories(d_code):
    sales_cols = [v[0] for v in SALES_CATEGORIES.values()]
    sum_exprs = ", ".join([f"SUM({c}) AS {c}" for c in sales_cols])
    df = session.query(f"""
        SELECT {sum_exprs}
        FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        WHERE DISTRICT_CODE = '{d_code}'
    """)
    available = []
    for name, (sales_col, _) in SALES_CATEGORIES.items():
        if df[sales_col].iloc[0] > 0:
            available.append(name)
    return available

# 구 목록 
districts_df = load_districts()
gu_list = districts_df["CITY_KOR_NAME"].unique().tolist()

#layout 3 columns 
col_a, col_b, col_c = st.columns(3)
with col_a:
    selected_gu = st.selectbox("구 선택", gu_list)
with col_b:
    dong_options = districts_df[districts_df["CITY_KOR_NAME"] == selected_gu]["DISTRICT_KOR_NAME"].tolist()
    selected_dong = st.selectbox("동 선택", dong_options)
# DB code 
district_code = districts_df[
    (districts_df["CITY_KOR_NAME"] == selected_gu) &
    (districts_df["DISTRICT_KOR_NAME"] == selected_dong)
]["DISTRICT_CODE"].iloc[0]

# 카드 매출 데이터 있는 업종들만 available
available_categories = load_available_categories(district_code)

with col_c:
    selected_category = st.selectbox("업종 선택", available_categories)

sales_col, count_col = SALES_CATEGORIES[selected_category]

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Overview","💳 카드 매출", "🚶 유동인구", "💰 소득·자산"])

with tab1:
    st.subheader(f"{selected_gu} {selected_dong} - {selected_category} Overview")

    city_code = districts_df[
        districts_df["CITY_KOR_NAME"] == selected_gu
    ]["CITY_CODE"].iloc[0]

    latest_ym = session.query(f"""
        SELECT MAX(STANDARD_YEAR_MONTH) AS YM
        FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        WHERE DISTRICT_CODE = '{district_code}'
    """)["YM"].iloc[0]

    # 1) 해당 동 총매출 & 업종별 매출
    dong_card = session.query(f"""
        SELECT
            SUM(TOTAL_SALES) AS TOTAL_SALES,
            SUM({sales_col}) AS CATEGORY_SALES
        FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    dong_total_sales = dong_card["TOTAL_SALES"].iloc[0] or 0
    dong_cat_sales = dong_card["CATEGORY_SALES"].iloc[0] or 0
    cat_ratio = (dong_cat_sales / dong_total_sales * 100) if dong_total_sales else 0

    # 2) 구 평균 총매출 & 업종비중
    gu_avg = session.query(f"""
        SELECT
            AVG(d_total) AS AVG_TOTAL_SALES,
            AVG(d_cat / NULLIF(d_total, 0)) * 100 AS AVG_CAT_RATIO
        FROM (
            SELECT
                DISTRICT_CODE,
                SUM(TOTAL_SALES) AS d_total,
                SUM({sales_col}) AS d_cat
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
            WHERE DISTRICT_CODE IN (
                SELECT DISTINCT DISTRICT_CODE
                FROM CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST
                WHERE CITY_CODE = '{city_code}'
            )
            AND STANDARD_YEAR_MONTH = '{latest_ym}'
            GROUP BY DISTRICT_CODE
        )
    """)
    gu_avg_sales = gu_avg["AVG_TOTAL_SALES"].iloc[0] or 0
    gu_avg_cat_ratio = gu_avg["AVG_CAT_RATIO"].iloc[0] or 0

    # 3) 유동인구
    dong_pop = session.query(f"""
        SELECT SUM(RESIDENTIAL_POPULATION + WORKING_POPULATION + VISITING_POPULATION) AS TOTAL_POP
        FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    dong_total_pop = dong_pop["TOTAL_POP"].iloc[0] or 0

    gu_avg_pop = session.query(f"""
        SELECT AVG(d_pop) AS AVG_POP
        FROM (
            SELECT DISTRICT_CODE,
                   SUM(RESIDENTIAL_POPULATION + WORKING_POPULATION + VISITING_POPULATION) AS d_pop
            FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO
            WHERE DISTRICT_CODE IN (
                SELECT DISTINCT DISTRICT_CODE
                FROM CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST
                WHERE CITY_CODE = '{city_code}'
            )
            AND STANDARD_YEAR_MONTH = '{latest_ym}'
            GROUP BY DISTRICT_CODE
        )
    """)
    gu_avg_pop_val = gu_avg_pop["AVG_POP"].iloc[0] or 0

    # 4) 평균소득
    dong_income = session.query(f"""
        SELECT AVG(AVERAGE_INCOME) AS AVG_INCOME
        FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    dong_avg_income = dong_income["AVG_INCOME"].iloc[0] or 0

    gu_avg_income = session.query(f"""
        SELECT AVG(AVERAGE_INCOME) AS AVG_INCOME
        FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO
        WHERE DISTRICT_CODE IN (
            SELECT DISTINCT DISTRICT_CODE
            FROM CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST
            WHERE CITY_CODE = '{city_code}'
        )
        AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    gu_avg_income_val = gu_avg_income["AVG_INCOME"].iloc[0] or 0

    # 구 평균 대비 delta 계산
    sales_diff = dong_total_sales - gu_avg_sales
    ratio_diff = cat_ratio - gu_avg_cat_ratio
    pop_diff = dong_total_pop - gu_avg_pop_val
    income_diff = dong_avg_income - gu_avg_income_val

    # 카드 표시
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="총매출",
            value=format_amount(dong_total_sales),
            delta=f"{'+' if sales_diff >= 0 else ''}{format_amount(sales_diff)} vs 구 평균"
        )
    with c2:
        st.metric(
            label=f"{selected_category} 업종비중",
            value=f"{cat_ratio:.1f}%",
            delta=f"{ratio_diff:+.1f}%p vs 구 평균"
        )
    with c3:
        st.metric(
            label="총 유동인구",
            value=format_amount(dong_total_pop),
            delta=f"{'+' if pop_diff >= 0 else ''}{format_amount(pop_diff)} vs 구 평균"
        )
    with c4:
        st.metric(
            label="평균소득",
            value=format_amount(dong_avg_income),
            delta=f"{'+' if income_diff >= 0 else ''}{format_amount(income_diff)} vs 구 평균"
        )

    st.caption(f"기준: {latest_ym[:4]}년 {latest_ym[4:]}월 | 구 평균 = {selected_gu} 내 전체 동 평균")

with tab2:
    st.subheader(f"{selected_gu} {selected_dong} — {selected_category} 카드 매출 분석")

    card_df = session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               SUM({sales_col}) AS SALES,
               SUM(TOTAL_SALES) AS TOTAL_SALES
        FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        WHERE DISTRICT_CODE = '{district_code}'
        GROUP BY STANDARD_YEAR_MONTH
        ORDER BY STANDARD_YEAR_MONTH
    """)

    if card_df.empty:
        st.info("해당 조건에 맞는 카드 매출 데이터가 없습니다.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("총 매출", f"{format_amount(card_df['SALES'].sum())}원")
        m2.metric("업종 비중", f"{card_df['SALES'].sum() / card_df['TOTAL_SALES'].sum() * 100:.2f}%")

        card_df["SALES_BILLION"] = card_df["SALES"] / 1_0000_0000

        c1 = st.columns(2)
        with c1:
            chart_sales = alt.Chart(card_df).mark_bar().encode(
                x=alt.X("STANDARD_YEAR_MONTH:N", title="기준년월"),
                y=alt.Y("SALES_BILLION:Q", title="매출액(억원)"),
                tooltip=[
                    alt.Tooltip("STANDARD_YEAR_MONTH", title="기준년월"),
                    alt.Tooltip("SALES_BILLION:Q", title="매출액(억원)", format=",.1f")
                ]
            ).properties(title=f"{selected_category} 월별 매출 추이")
            st.altair_chart(chart_sales, use_container_width=True)
    

        st.subheader("성별·연령대별 매출 분포")
        demo_df = session.query(f"""
            SELECT GENDER, AGE_GROUP,
                   SUM({sales_col}) AS SALES
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
            WHERE DISTRICT_CODE = '{district_code}'
              AND AGE_GROUP != '*'
            GROUP BY GENDER, AGE_GROUP
            ORDER BY AGE_GROUP, GENDER
        """)

        demo_df["GENDER"] = demo_df["GENDER"].map({"M": "남성", "F": "여성"})
        demo_df["AGE_GROUP"] = demo_df["AGE_GROUP"].astype(str)
        demo_df["SALES_BILLION"] = demo_df["SALES"] / 1_0000_0000
        chart_demo = alt.Chart(demo_df).mark_bar().encode(
            x=alt.X("AGE_GROUP:N", title="연령대"),
            y=alt.Y("SALES_BILLION:Q", title="매출액(억원)"),
            color=alt.Color("GENDER:N", title="성별"),
            tooltip=[
                alt.Tooltip("AGE_GROUP", title="연령대"),
                alt.Tooltip("GENDER", title="성별"),
                alt.Tooltip("SALES_BILLION:Q", title="매출액(억원)", format=",.1f")
            ]
        ).properties(title=f"{selected_category} 성별·연령대별 매출")
        st.altair_chart(chart_demo, use_container_width=True)

with tab3:
    st.subheader(f"{selected_gu} {selected_dong} — 유동인구 분석")

    pop_df = session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               SUM(RESIDENTIAL_POPULATION) AS RESIDENTIAL,
               SUM(WORKING_POPULATION) AS WORKING,
               SUM(VISITING_POPULATION) AS VISITING
        FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO
        WHERE DISTRICT_CODE = '{district_code}'
        GROUP BY STANDARD_YEAR_MONTH
        ORDER BY STANDARD_YEAR_MONTH
    """)

    if pop_df.empty:
        st.info("해당 조건에 맞는 유동인구 데이터가 없습니다.")
    else:
        pm1, pm2, pm3 = st.columns(3)
        pm1.metric("거주인구(평균)", f"{pop_df['RESIDENTIAL'].mean():,.0f}")
        pm2.metric("직장인구(평균)", f"{pop_df['WORKING'].mean():,.0f}")
        pm3.metric("방문인구(평균)", f"{pop_df['VISITING'].mean():,.0f}")

        pop_long = pop_df.melt(
            id_vars=["STANDARD_YEAR_MONTH"],
            value_vars=["RESIDENTIAL", "WORKING", "VISITING"],
            var_name="TYPE", value_name="POPULATION"
        )
        pop_long["TYPE"] = pop_long["TYPE"].map({
            "RESIDENTIAL": "거주", "WORKING": "직장", "VISITING": "방문"
        })
        chart_pop = alt.Chart(pop_long).mark_line(point=True).encode(
            x=alt.X("STANDARD_YEAR_MONTH:N", title="기준년월"),
            y=alt.Y("POPULATION:Q", title="인구수"),
            color=alt.Color("TYPE:N", title="유형"),
            tooltip=["STANDARD_YEAR_MONTH", "TYPE", "POPULATION"]
        ).properties(title="유동인구 월별 추이")
        st.altair_chart(chart_pop, use_container_width=True)

        st.subheader("시간대별 유동인구")
        time_df = session.query(f"""
            SELECT TIME_SLOT,
                   SUM(RESIDENTIAL_POPULATION) AS RESIDENTIAL,
                   SUM(WORKING_POPULATION) AS WORKING,
                   SUM(VISITING_POPULATION) AS VISITING
            FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO
            WHERE DISTRICT_CODE = '{district_code}'
            GROUP BY TIME_SLOT
            ORDER BY TIME_SLOT
             """)

        time_long = time_df.melt(
            id_vars=["TIME_SLOT"],
            value_vars=["RESIDENTIAL", "WORKING", "VISITING"],
            var_name="TYPE", value_name="POPULATION"
        )
        time_long["TYPE"] = time_long["TYPE"].map({
            "RESIDENTIAL": "거주", "WORKING": "직장", "VISITING": "방문"
        })
        chart_time = alt.Chart(time_long).mark_bar().encode(
            x=alt.X("TIME_SLOT:N", title="시간대"),
            y=alt.Y("POPULATION:Q", title="인구수"),
            color=alt.Color("TYPE:N", title="유형"),
            tooltip=["TIME_SLOT", "TYPE", "POPULATION"]
        ).properties(title="시간대별 유동인구 분포")
        st.altair_chart(chart_time, use_container_width=True)

with tab4:
    st.subheader(f"{selected_gu} {selected_dong} — 소득·자산 분석")

    income_df = session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               SUM(CUSTOMER_COUNT) AS CUSTOMERS,
               AVG(AVERAGE_INCOME) AS AVG_INCOME,
               AVG(MEDIAN_INCOME) AS MEDIAN_INCOME,
               AVG(AVERAGE_HOUSEHOLD_INCOME) AS AVG_HH_INCOME,
               AVG(AVERAGE_ASSET_AMOUNT) AS AVG_ASSET,
               AVG(AVERAGE_SCORE) AS AVG_CREDIT_SCORE
        FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO
        WHERE DISTRICT_CODE = '{district_code}'
        GROUP BY STANDARD_YEAR_MONTH
        ORDER BY STANDARD_YEAR_MONTH
    """)

    if income_df.empty:
        st.info("해당 조건에 맞는 소득·자산 데이터가 없습니다.")
    else:
        income_df["AVG_INCOME_MANWON"] = income_df["AVG_INCOME"] / 10
        income_df["MEDIAN_INCOME_MANWON"] = income_df["MEDIAN_INCOME"] / 10
        income_df["AVG_ASSET_MANWON"] = income_df["AVG_ASSET"] / 10

        im1, im2, im3, im4 = st.columns(4)
        im1.metric("평균소득(만원)", f"{income_df['AVG_INCOME_MANWON'].mean():,.0f}")
        im2.metric("중위소득(만원)", f"{income_df['MEDIAN_INCOME_MANWON'].mean():,.0f}")
        im3.metric("평균자산(만원)", f"{income_df['AVG_ASSET_MANWON'].mean():,.0f}")
        im4.metric("평균신용점수", f"{income_df['AVG_CREDIT_SCORE'].mean():,.0f}")

        inc_chart = alt.Chart(income_df).mark_line(point=True).encode(
            x=alt.X("STANDARD_YEAR_MONTH:N", title="기준년월"),
            y=alt.Y("AVG_INCOME_MANWON:Q", title="평균소득(만원)"),
            tooltip=[
                alt.Tooltip("STANDARD_YEAR_MONTH:N", title="기준년월"),
                alt.Tooltip("AVG_INCOME_MANWON:Q", title="평균소득(만원)", format=",.0f")
            ]
        ).properties(title="월별 평균소득 추이")
        st.altair_chart(inc_chart, use_container_width=True)

        st.subheader("소득 분포")
        dist_df = session.query(f"""
            SELECT
                AVG(RATE_INCOME_UNDER_20M) AS "~2천만원",
                AVG(RATE_INCOME_20M_TO_30M) AS "2~3천만원",
                AVG(RATE_INCOME_30M_TO_40M) AS "3~4천만원",
                AVG(RATE_INCOME_40M_TO_50M) AS "4~5천만원",
                AVG(RATE_INCOME_50M_TO_60M) AS "5~6천만원",
                AVG(RATE_INCOME_60M_TO_70M) AS "6~7천만원",
                AVG(RATE_INCOME_OVER_70M) AS "7천만원~"
            FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO
            WHERE DISTRICT_CODE = '{district_code}'
        """)

        dist_long = dist_df.T.reset_index()
        dist_long.columns = ["소득구간", "비율(%)"]
        chart_dist = alt.Chart(dist_long).mark_bar().encode(
            x=alt.X("소득구간:N", sort=None, title="소득구간"),
            y=alt.Y("비율(%):Q", title="비율(%)"),
            tooltip=["소득구간", "비율(%)"]
        ).properties(title="소득 구간별 인구 비율")
        st.altair_chart(chart_dist, use_container_width=True)

        st.subheader("직업군 분포")
        occ_df = session.query(f"""
            SELECT
                AVG(RATE_MODEL_GROUP_LARGE_COMPANY_EMPLOYEE) AS "대기업",
                AVG(RATE_MODEL_GROUP_GENERAL_EMPLOYEE) AS "일반직장인",
                AVG(RATE_MODEL_GROUP_PROFESSIONAL_EMPLOYEE) AS "전문직",
                AVG(RATE_MODEL_GROUP_EXECUTIVES) AS "임원",
                AVG(RATE_MODEL_GROUP_GENERAL_SELF_EMPLOYED) AS "일반자영업",
                AVG(RATE_MODEL_GROUP_PROFESSIONAL_SELF_EMPLOYED) AS "전문자영업",
                AVG(RATE_MODEL_GROUP_OTHERS) AS "기타"
            FROM CONSUMPTION_ASSET.GRANDATA.ASSET_INCOME_INFO
            WHERE DISTRICT_CODE = '{district_code}'
        """)

        occ_long = occ_df.T.reset_index()
        occ_long.columns = ["직업군", "비율(%)"]
        chart_occ = alt.Chart(occ_long).mark_bar().encode(
            x=alt.X("직업군:N", sort=None, title="직업군"),
            y=alt.Y("비율(%):Q", title="비율(%)"),
            color=alt.Color("직업군:N", legend=None),
            tooltip=["직업군", "비율(%)"]
        ).properties(title="직업군별 인구 비율")
        st.altair_chart(chart_occ, use_container_width=True)