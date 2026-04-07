# imports
import json
import streamlit as st
import altair as alt
import pydeck as pdk

#snowflake session
session = st.connection("snowflake")

st.title("상권 분석")

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
        SELECT DISTINCT CITY_KOR_NAME, DISTRICT_KOR_NAME, CITY_CODE, DISTRICT_CODE
        FROM UNIFIED_DISTRICT_MONTHLY
        ORDER BY CITY_KOR_NAME, DISTRICT_KOR_NAME
    """)

# Load monthly category sales and total sales for the selected district
@st.cache_data
def load_card_df(d_code, s_col):
    return session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               {s_col} AS SALES,
               TOTAL_SALES
        FROM UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{d_code}'
        ORDER BY STANDARD_YEAR_MONTH
    """)

# Load monthly average category sales across all districts in the same gu (for benchmark comparison)
@st.cache_data
def load_gu_card_df(c_code, s_col):
    return session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               AVG({s_col}) AS GU_AVG_SALES
        FROM UNIFIED_DISTRICT_MONTHLY
        WHERE CITY_CODE = '{c_code}'
        GROUP BY CITY_CODE, STANDARD_YEAR_MONTH
        ORDER BY STANDARD_YEAR_MONTH
    """)
    
@st.cache_data
def load_weekday_weekend_card_df(d_code, s_col):
    return session.query(f"""
            SELECT STANDARD_YEAR_MONTH, WEEKDAY_WEEKEND,
                   SUM({s_col}) AS SALES
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
            WHERE DISTRICT_CODE = '{d_code}'
            GROUP BY STANDARD_YEAR_MONTH, WEEKDAY_WEEKEND
        """)

@st.cache_data
def load_lifestyle_card_df(d_code, s_col):
    return session.query(f"""
            SELECT STANDARD_YEAR_MONTH, LIFESTYLE,
                   SUM({s_col}) AS SALES
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
            WHERE DISTRICT_CODE = '{d_code}'
              AND LIFESTYLE IS NOT NULL
              AND LIFESTYLE != '*'
            GROUP BY LIFESTYLE, STANDARD_YEAR_MONTH
            ORDER BY SALES DESC
        """)

@st.cache_data
def load_demography_card_df(d_code, s_col):
    return session.query(f"""
            SELECT GENDER, AGE_GROUP, STANDARD_YEAR_MONTH,
                   SUM({s_col}) AS SALES
            FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
            WHERE DISTRICT_CODE = '{d_code}'
              AND AGE_GROUP != '*'
            GROUP BY GENDER, AGE_GROUP, STANDARD_YEAR_MONTH
            ORDER BY AGE_GROUP, GENDER
        """)

@st.cache_data
def load_population_df(d_code):
    return session.query(f"""
        SELECT STANDARD_YEAR_MONTH, TIME_SLOT,
               SUM(RESIDENTIAL_POPULATION) AS RESIDENTIAL,
               SUM(WORKING_POPULATION) AS WORKING,
               SUM(VISITING_POPULATION) AS VISITING
        FROM CONSUMPTION_ASSET.GRANDATA.FLOATING_POPULATION_INFO
        WHERE DISTRICT_CODE = '{d_code}'
        GROUP BY STANDARD_YEAR_MONTH, TIME_SLOT
        ORDER BY STANDARD_YEAR_MONTH, TIME_SLOT
    """)

@st.cache_data
def load_income_df(d_code):
    return session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               MEDIAN_INCOME,
               AVERAGE_ASSET_AMOUNT AS AVG_ASSET,
               AVERAGE_SCORE AS AVG_CREDIT_SCORE,
               RATE_INCOME_UNDER_20M AS RATE_UNDER_20M,
               RATE_INCOME_20M_30M AS RATE_20M_30M,
               RATE_INCOME_30M_40M AS RATE_30M_40M,
               RATE_INCOME_40M_50M AS RATE_40M_50M,
               RATE_INCOME_50M_60M AS RATE_50M_60M,
               RATE_INCOME_60M_70M AS RATE_60M_70M,
               RATE_INCOME_OVER_70M AS RATE_OVER_70M,
               RATE_MODEL_GROUP_LARGE_COMPANY_EMPLOYEE AS RATE_LARGE_CO,
               RATE_MODEL_GROUP_GENERAL_EMPLOYEE AS RATE_GENERAL_EMP,
               RATE_MODEL_GROUP_PROFESSIONAL_EMPLOYEE AS RATE_PROFESSIONAL,
               RATE_MODEL_GROUP_EXECUTIVES AS RATE_EXEC,
               RATE_MODEL_GROUP_GENERAL_SELF_EMPLOYED AS RATE_SELF_EMP,
               RATE_MODEL_GROUP_PROFESSIONAL_SELF_EMPLOYED AS RATE_PRO_SELF_EMP,
               RATE_MODEL_GROUP_OTHERS AS RATE_OTHERS
        FROM UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{d_code}'
        ORDER BY STANDARD_YEAR_MONTH
    """)

# 선택한 동에서 실제 데이터가 있는 업종만 보여줌
@st.cache_data
def load_available_categories(d_code):
    sales_cols = [v[0] for v in SALES_CATEGORIES.values()]
    sum_exprs = ", ".join([f"SUM({c}) AS {c}" for c in sales_cols])
    df = session.query(f"""
        SELECT {sum_exprs}
        FROM UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{d_code}'
    """)
    available = []
    for name, (sales_col, _) in SALES_CATEGORIES.items():
        if df[sales_col].iloc[0] > 0:
            available.append(name)
    return available

def geom_to_features(df, selected):
    features = []
    for _, row in df.iterrows():
        try:
            geom = json.loads(row["DISTRICT_GEOM"])
        except (TypeError, ValueError):
            continue
        is_selected = row["DISTRICT_KOR_NAME"] == selected
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "district": str(row["DISTRICT_KOR_NAME"]) if row["DISTRICT_KOR_NAME"] else "",
                "is_selected": is_selected,
            },
        })
    return {"type": "FeatureCollection", "features": features}

def get_centroid(geojson_str):
    try:
        geom = json.loads(geojson_str)
        coords = geom.get("coordinates", [])
        if geom["type"] == "MultiPolygon":
            pts = [p for poly in coords for ring in poly for p in ring]
        elif geom["type"] == "Polygon":
            pts = [p for ring in coords for p in ring]
        else:
            return None, None
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        return lat, lon
    except Exception:
        return None, None

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

# ── 상수 ─────────────────────────────────────────────────────────────────────
DISTRICT_COLORS = {
    "서초구":   [76,  139, 245, 160],
    "영등포구": [245, 166,  35, 160],
    "중구":     [80,  200, 120, 160],
}

# ── 지도 ─────────────────────────────────────────────────────────────────────
df_map = session.query(
    f"SELECT CITY_KOR_NAME, DISTRICT_KOR_NAME, DISTRICT_GEOM "
    f"FROM CONSUMPTION_ASSET.GRANDATA.M_SCCO_MST "
    f"WHERE CITY_KOR_NAME = '{selected_gu}'"
)

geojson = geom_to_features(df_map, selected_dong)

fill_color = DISTRICT_COLORS.get(selected_dong, [200, 200, 200, 160])

st.markdown(f"### 서울 상권 분포 지도 — {selected_gu} · {selected_dong}")

geojson_layer = pdk.Layer(
    "GeoJsonLayer",
    data=geojson,
    get_fill_color=f"[{fill_color[0]}, {fill_color[1]}, {fill_color[2]}, properties.is_selected ? 180 : 60]",
    get_line_color="properties.is_selected ? [255, 60, 60, 255] : [150, 150, 150, 120]",
    get_line_width="properties.is_selected ? 40 : 10",
    line_width_min_pixels=1,
    pickable=True,
    auto_highlight=True,
)

selected_row = df_map[df_map["DISTRICT_KOR_NAME"] == selected_dong]
pin_lat, pin_lon = None, None
if not selected_row.empty:
    pin_lat, pin_lon = get_centroid(selected_row.iloc[0]["DISTRICT_GEOM"])

layers = [geojson_layer]

DISTRICT_VIEW = {
    "서초구":   {"latitude": 37.483, "longitude": 127.032, "zoom": 10, "dong_zoom": 12},
    "영등포구": {"latitude": 37.526, "longitude": 126.896, "zoom": 12, "dong_zoom": 12.5},
    "중구":     {"latitude": 37.559, "longitude": 126.998, "zoom": 13, "dong_zoom": 13.5},
}
vw_config = DISTRICT_VIEW.get(selected_gu, {"latitude": 37.524, "longitude": 126.975, "zoom": 12, "dong_zoom": 14})
vw = {"latitude": vw_config["latitude"], "longitude": vw_config["longitude"], "zoom": vw_config["zoom"]}
if pin_lat and pin_lon:
    vw["latitude"] = pin_lat
    vw["longitude"] = pin_lon
    vw["zoom"] = vw_config["dong_zoom"]

view = pdk.ViewState(**vw, pitch=0)
st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"html": "<b>{district}</b>", "style": {"backgroundColor": "white", "color": "black"}},
    )
)

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Overview","💳 카드 매출", "🚶 유동인구", "💰 소득·자산"])

with tab1:
    st.subheader(f"{selected_gu} {selected_dong} - {selected_category} Overview")

    city_code = districts_df[
        districts_df["CITY_KOR_NAME"] == selected_gu
    ]["CITY_CODE"].iloc[0]

    latest_ym = session.query(f"""
        SELECT MAX(STANDARD_YEAR_MONTH) AS YM
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{district_code}'
    """)["YM"].iloc[0]

    # 1) 해당 동 총매출 & 업종별 매출
    dong_card = session.query(f"""
        SELECT
            TOTAL_SALES,
            {sales_col} AS CATEGORY_SALES
        FROM UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    dong_total_sales = float(dong_card["TOTAL_SALES"].iloc[0] or 0)
    dong_cat_sales = float(dong_card["CATEGORY_SALES"].iloc[0] or 0)
    cat_ratio = (dong_cat_sales / dong_total_sales * 100) if dong_total_sales else 0

    # 2) 구 평균 총매출 & 업종비중
    gu_avg = session.query(f"""
        SELECT
            AVG(TOTAL_SALES) AS AVG_TOTAL_SALES,
            AVG({sales_col}) AS AVG_CAT_SALES
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE CITY_CODE = '{city_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    gu_avg_sales = float(gu_avg["AVG_TOTAL_SALES"].iloc[0] or 0)
    gu_avg_cat_sales = float(gu_avg["AVG_CAT_SALES"].iloc[0] or 0)
    gu_avg_cat_ratio = (gu_avg_cat_sales / gu_avg_sales * 100) if dong_total_sales else 0

    # 3) 유동인구
    dong_pop = session.query(f"""
        SELECT TOTAL_POPULATION AS TOTAL_POP
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    dong_total_pop = float(dong_pop["TOTAL_POP"].iloc[0] or 0)

    gu_avg_pop = session.query(f"""
        SELECT AVG(TOTAL_POPULATION) AS AVG_POP
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE CITY_CODE = '{city_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    gu_avg_pop_val = float(gu_avg_pop["AVG_POP"].iloc[0] or 0)

    # 4) Average Median Income
    dong_income = session.query(f"""
        SELECT MEDIAN_INCOME AS AVG_MEDIAN_INCOME
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{district_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    # DB stores value in units of 1,000 KRW; divide by 10 to display in units of 10,000 KRW (만원)
    dong_avg_median_income = float(dong_income["AVG_MEDIAN_INCOME"].iloc[0] or 0) / 10

    gu_avg_income = session.query(f"""
        SELECT AVG(MEDIAN_INCOME) AS AVG_MEDIAN_INCOME
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE CITY_CODE = '{city_code}'
          AND STANDARD_YEAR_MONTH = '{latest_ym}'
    """)
    # DB stores value in units of 1,000 KRW; divide by 10 to display in units of 10,000 KRW (만원)
    gu_avg_median_income_val = float(gu_avg_income["AVG_MEDIAN_INCOME"].iloc[0] or 0) / 10

    # 구 평균 대비 delta 계산
    sales_diff = dong_cat_sales - gu_avg_cat_sales
    ratio_diff = cat_ratio - gu_avg_cat_ratio
    pop_diff = dong_total_pop - gu_avg_pop_val
    income_diff = dong_avg_median_income - gu_avg_median_income_val

    # 카드 표시
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="총매출",
            value=f"{format_amount(dong_cat_sales)}원",
            delta=f"{'+' if sales_diff >= 0 else ''}{format_amount(sales_diff)}원 vs 구 평균"
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
            value=f"{format_amount(dong_total_pop)}명",
            delta=f"{'+' if pop_diff >= 0 else ''}{format_amount(pop_diff)}명 vs 구 평균"
        )
    with c4:
        st.metric(
            label="평균 중위 소득",
            value=f"{dong_avg_median_income:,.0f}만원",
            delta=f"{income_diff:+,.0f}만원 vs 구 평균"
        )

    st.caption(f"기준: {latest_ym[:4]}년 {latest_ym[4:]}월 | 구 평균 = {selected_gu} 내 전체 동 평균")
    
    summary_prompt = f"""
        당신은 대한민국 상권 분석 보고서를 작성하는 전문 컨설턴트입니다.

        [분석 대상]
        - 지역: {selected_dong}
        - 업종: {selected_category}

        [핵심 지표 (구 평균 대비)]
        1. 매출: 총 {format_amount(dong_total_sales)}원 (구 평균 대비 {'+' if sales_diff >= 0 else ''}{format_amount(sales_diff)}원, {'상회' if sales_diff >= 0 else '하회'})
        2. 업종 비중: {cat_ratio:.1f}% (구 평균 대비 {ratio_diff:+.1f}%p, {'경쟁 과밀 주의' if ratio_diff > 3 else '진입 여지 있음' if ratio_diff < -1 else '평균 수준'})
        3. 유동인구: 총 {format_amount(dong_total_pop)}명 (구 평균 대비 {'+' if pop_diff >= 0 else ''}{format_amount(pop_diff)}명, {'상회' if pop_diff >= 0 else '하회'})
        4. 평균소득: {dong_avg_median_income:,.0f}만원 (구 평균 대비 {income_diff:+,.0f}만원, {'상회' if income_diff >= 0 else '하회'})

        [구 평균 상회 지표 수: {sum([sales_diff >= 0, pop_diff >= 0, income_diff >= 0, ratio_diff <= 0])}/4]

        [판정 기준]
        - 상: 4개 지표 중 3개 이상 긍정적이며, 매출 또는 유동인구가 구 평균 상회
        - 중: 긍정 지표 2개, 또는 매출은 높으나 경쟁 과밀 등 리스크 존재
        - 하: 긍정 지표 1개 이하, 또는 매출과 유동인구 모두 구 평균 하회

        [출력 형식]
        정확히 5문장, 하나의 문단으로 작성하세요.
        - 1문장: "창업 성공 가능성은 [상/중/하]로 판정됩니다." 로 시작
        - 2문장: 가장 강한 긍정 요인 (지표의 의미 해석 중심)
        - 3문장: 두 번째 긍정 요인 또는 보완 강점
        - 4문장: 핵심 리스크 1~2개 (수치 나열이 아닌 사업적 함의로 설명)
        - 5문장: 종합 전망 + 성공 가능성을 높이기 위한 구체적 조건 1가지

        [주의사항]
        - 수치를 그대로 나열하지 말고, 사업적 의미로 해석하세요.
        - "~원입니다" 식의 단순 보고가 아닌, "수요 기반이 탄탄하다" 등 분석적 표현을 사용하세요.
        - 불릿포인트, 번호 매기기 없이 자연스러운 문단으로 작성하세요.
        """
    ai_summary = session.query(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', '{summary_prompt.replace("'", "''")}') AS SUMMARY
    """)["SUMMARY"].iloc[0]
    st.info(f"**AI 창업 성공률 예측:** {ai_summary}")

with tab2:
    st.subheader(f"{selected_gu} {selected_dong} — {selected_category} 카드 매출 분석")

    col_start, col_end = st.columns(2)
    all_ym = session.query(f"""
        SELECT DISTINCT STANDARD_YEAR_MONTH
        FROM HACKATHON.DATA.UNIFIED_DISTRICT_MONTHLY
        WHERE DISTRICT_CODE = '{district_code}'
        ORDER BY STANDARD_YEAR_MONTH
    """)["STANDARD_YEAR_MONTH"].tolist()

    with col_start:
        start_ym = st.selectbox("시작 기간", all_ym, index=0, key="start_ym")
    with col_end:
        # end options are limited to months >= start
        end_options = [ym for ym in all_ym if ym >= start_ym]
        end_ym = st.selectbox("종료 기간", end_options, index=len(end_options) - 1, key="end_ym")

    if start_ym > end_ym:
        st.error("시작 기간은 종료 기간보다 늦을 수 없습니다.")
        st.stop()

    card_df_full = load_card_df(district_code, sales_col)
    gu_card_df_full = load_gu_card_df(city_code, sales_col)

    card_df = card_df_full[
        (card_df_full["STANDARD_YEAR_MONTH"] >= start_ym) &
        (card_df_full["STANDARD_YEAR_MONTH"] <= end_ym)
    ].copy()
    gu_card_df = gu_card_df_full[
        (gu_card_df_full["STANDARD_YEAR_MONTH"] >= start_ym) &
        (gu_card_df_full["STANDARD_YEAR_MONTH"] <= end_ym)
    ].copy()

    if card_df.empty:
        st.info("해당 조건에 맞는 카드 매출 데이터가 없습니다.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("총 매출", f"{format_amount(card_df['SALES'].sum())}원")
        m2.metric("업종 비중", f"{card_df['SALES'].sum() / card_df['TOTAL_SALES'].sum() * 100:.2f}%")

        card_df["SALES_BILLION"] = card_df["SALES"].astype(float) / 1_0000_0000
        gu_card_df["GU_AVG_BILLION"] = gu_card_df["GU_AVG_SALES"].astype(float) / 1_0000_0000

        show_gu_avg = st.checkbox("구 평균 비교", value=True, key="show_gu_avg")

        if show_gu_avg:
            merged = card_df[["STANDARD_YEAR_MONTH", "SALES_BILLION"]].merge(
                gu_card_df[["STANDARD_YEAR_MONTH", "GU_AVG_BILLION"]],
                on="STANDARD_YEAR_MONTH", how="left"
            )
            line_long = merged.melt(
                id_vars=["STANDARD_YEAR_MONTH"],
                value_vars=["SALES_BILLION", "GU_AVG_BILLION"],
                var_name="TYPE", value_name="VALUE"
            )
            line_long["TYPE"] = line_long["TYPE"].map({
                "SALES_BILLION": selected_dong,
                "GU_AVG_BILLION": f"{selected_gu} 평균"
            })
        else:
            line_long = card_df[["STANDARD_YEAR_MONTH", "SALES_BILLION"]].rename(
                columns={"SALES_BILLION": "VALUE"}
            )
            line_long["TYPE"] = selected_dong

        chart_sales = alt.Chart(line_long).mark_line(point=True).encode(
            x=alt.X("STANDARD_YEAR_MONTH:N", title="기준년월"),
            y=alt.Y("VALUE:Q", title="매출액(원)"),
            color=alt.Color("TYPE:N", title="구분"),
            strokeDash=alt.StrokeDash("TYPE:N"),
            tooltip=[
                alt.Tooltip("STANDARD_YEAR_MONTH", title="기준년월"),
                alt.Tooltip("TYPE", title="구분"),
                alt.Tooltip("VALUE:Q", title="매출액(원)", format=",.1f")
            ]
        ).properties(title=f"{selected_category} 월별 매출 추이")
        st.altair_chart(chart_sales, width="stretch")


        wd_df_full = load_weekday_weekend_card_df(district_code, sales_col)
        wd_df = wd_df_full[
            (wd_df_full["STANDARD_YEAR_MONTH"] >= start_ym) &
            (wd_df_full["STANDARD_YEAR_MONTH"] <= end_ym)
        ].copy()
        wd_df = wd_df.groupby("WEEKDAY_WEEKEND", as_index=False)["SALES"].sum()
        wd_df["WEEKDAY_WEEKEND"] = wd_df["WEEKDAY_WEEKEND"].map({"W": "평일", "H": "주말"})
        wd_df["SALES_BILLION"] = wd_df["SALES"] / 1_0000_0000


        LIFESTYLE_MAP = {
            "L01": "가성비 소비형",
            "L02": "생활 밀착형",
            "L03": "프리미엄 소비형",
            "L04": "자기관리형",
            "L05": "가정 중심형",
            "L06": "여가·문화형",
        }

        ls_df_full = load_lifestyle_card_df(district_code, sales_col)
        ls_df = ls_df_full[
            (ls_df_full["STANDARD_YEAR_MONTH"] >= start_ym) &
            (ls_df_full["STANDARD_YEAR_MONTH"] <= end_ym)
        ].copy()
        ls_df = ls_df.groupby("LIFESTYLE", as_index=False)["SALES"].sum()
        ls_df["LIFESTYLE"] = ls_df["LIFESTYLE"].map(LIFESTYLE_MAP).fillna(ls_df["LIFESTYLE"])
        ls_df["SALES_BILLION"] = ls_df["SALES"] / 1_0000_0000

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("평일/주말 매출 비교")
        chart_wd_sales = alt.Chart(wd_df).mark_arc().encode(
            theta=alt.Theta("SALES_BILLION:Q"),
            color=alt.Color("WEEKDAY_WEEKEND:N", title="구분"),
            tooltip=[
                alt.Tooltip("WEEKDAY_WEEKEND", title="구분"),
                alt.Tooltip("SALES_BILLION:Q", title="매출액(원)", format=",.1f")
            ]
        )
        st.altair_chart(chart_wd_sales, width="stretch")

    with c2:
        st.subheader("라이프스타일별 매출")
        chart_ls = alt.Chart(ls_df).mark_arc().encode(
            theta=alt.Theta("SALES_BILLION:Q"),
            color=alt.Color("LIFESTYLE:N", title="라이프스타일"),
            tooltip=[
                alt.Tooltip("LIFESTYLE", title="라이프스타일"),
                alt.Tooltip("SALES_BILLION:Q", title="매출액(원)", format=",.1f")
            ]
        )
        st.altair_chart(chart_ls, width="stretch")


    st.subheader("성별·연령대별 매출 분포")
    demo_df_full = load_demography_card_df(district_code, sales_col)
    demo_df = demo_df_full[
            (demo_df_full["STANDARD_YEAR_MONTH"] >= start_ym) &
            (demo_df_full["STANDARD_YEAR_MONTH"] <= end_ym)
        ].copy()

    # combine monthly data by summing across the selected period
    demo_df = demo_df.groupby(["GENDER", "AGE_GROUP"], as_index=False)["SALES"].sum()

    demo_df["GENDER"] = demo_df["GENDER"].map({"M": "남성", "F": "여성"})
    demo_df["AGE_GROUP"] = demo_df["AGE_GROUP"].astype(str)
    demo_df["SALES_BILLION"] = demo_df["SALES"] / 1_0000_0000

    total_df = demo_df.groupby("AGE_GROUP", as_index=False)["SALES_BILLION"].sum().rename(columns={"SALES_BILLION": "TOTAL_BILLION"})
    demo_df = demo_df.merge(total_df, on="AGE_GROUP")

    chart_demo = alt.Chart(demo_df).mark_bar().encode(
            x=alt.X("AGE_GROUP:N", title="연령대"),
            y=alt.Y("SALES_BILLION:Q", title="매출액(억원)"),
            color=alt.Color("GENDER:N", title="성별"),
            tooltip=[
                alt.Tooltip("AGE_GROUP", title="연령대"),
                alt.Tooltip("GENDER", title="성별"),
                alt.Tooltip("SALES_BILLION:Q", title="매출액(억원)", format=",.1f"),
                alt.Tooltip("TOTAL_BILLION:Q", title="합계(억원)", format=",.1f"),
            ]
        ).properties(title=f"{selected_category} 성별·연령대별 매출")
    st.altair_chart(chart_demo, width="stretch")

with tab3:
    st.subheader(f"{selected_gu} {selected_dong} — 유동인구 분석")

    pop_df_full = load_population_df(district_code)
    all_ym_pop = sorted(pop_df_full["STANDARD_YEAR_MONTH"].unique().tolist())

    col_start3, col_end3 = st.columns(2)
    with col_start3:
        start_ym3 = st.selectbox("시작 기간", all_ym_pop, index=0, key="start_ym3")
    with col_end3:
        end_options3 = [ym for ym in all_ym_pop if ym >= start_ym3]
        end_ym3 = st.selectbox("종료 기간", end_options3, index=len(end_options3) - 1, key="end_ym3")

    pop_filtered = pop_df_full[
        (pop_df_full["STANDARD_YEAR_MONTH"] >= start_ym3) &
        (pop_df_full["STANDARD_YEAR_MONTH"] <= end_ym3)
    ]
    pop_df = pop_filtered.groupby("STANDARD_YEAR_MONTH", as_index=False)[
        ["RESIDENTIAL", "WORKING", "VISITING"]
    ].sum()

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
        st.altair_chart(chart_pop, width="stretch")

        st.subheader("시간대별 유동인구")
        time_df = pop_filtered.groupby("TIME_SLOT", as_index=False)[
            ["RESIDENTIAL", "WORKING", "VISITING"]
        ].sum().sort_values("TIME_SLOT")

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
        st.altair_chart(chart_time, width="stretch")

with tab4:
    st.subheader(f"{selected_gu} {selected_dong} — 소득·자산 분석")

    income_df_full = load_income_df(district_code)
    all_ym_income = sorted(income_df_full["STANDARD_YEAR_MONTH"].unique().tolist())

    col_start4, col_end4 = st.columns(2)
    with col_start4:
        start_ym4 = st.selectbox("시작 기간", all_ym_income, index=0, key="start_ym4")
    with col_end4:
        end_options4 = [ym for ym in all_ym_income if ym >= start_ym4]
        end_ym4 = st.selectbox("종료 기간", end_options4, index=len(end_options4) - 1, key="end_ym4")

    income_df = income_df_full[
        (income_df_full["STANDARD_YEAR_MONTH"] >= start_ym4) &
        (income_df_full["STANDARD_YEAR_MONTH"] <= end_ym4)
    ].copy()

    if income_df.empty:
        st.info("해당 조건에 맞는 소득·자산 데이터가 없습니다.")
    else:
        income_df["MEDIAN_INCOME_MANWON"] = income_df["MEDIAN_INCOME"] / 10
        income_df["AVG_ASSET_MANWON"] = income_df["AVG_ASSET"] / 10

        im1, im2, im3 = st.columns(3)
        im1.metric("중위소득(만원)", f"{income_df['MEDIAN_INCOME_MANWON'].mean():,.0f}")
        im2.metric("평균자산(만원)", f"{income_df['AVG_ASSET_MANWON'].mean():,.0f}")
        im3.metric("평균신용점수", f"{income_df['AVG_CREDIT_SCORE'].mean():,.0f}")

        dist_df = income_df[[
            "RATE_UNDER_20M", "RATE_20M_30M", "RATE_30M_40M", "RATE_40M_50M",
            "RATE_50M_60M", "RATE_60M_70M", "RATE_OVER_70M"
        ]].mean().rename({
            "RATE_UNDER_20M": "~2천만원", "RATE_20M_30M": "2~3천만원",
            "RATE_30M_40M": "3~4천만원", "RATE_40M_50M": "4~5천만원",
            "RATE_50M_60M": "5~6천만원", "RATE_60M_70M": "6~7천만원",
            "RATE_OVER_70M": "7천만원~"
        }).to_frame().T

        occ_df = income_df[[
            "RATE_LARGE_CO", "RATE_GENERAL_EMP", "RATE_PROFESSIONAL",
            "RATE_EXEC", "RATE_SELF_EMP", "RATE_PRO_SELF_EMP", "RATE_OTHERS"
        ]].mean().rename({
            "RATE_LARGE_CO": "대기업", "RATE_GENERAL_EMP": "일반직장인",
            "RATE_PROFESSIONAL": "전문직", "RATE_EXEC": "임원",
            "RATE_SELF_EMP": "일반자영업", "RATE_PRO_SELF_EMP": "전문자영업",
            "RATE_OTHERS": "기타"
        }).to_frame().T

        st.subheader("소득 / 직업군 분포")
        c1, c2 = st.columns(2)
        with c1:
            dist_long = dist_df.T.reset_index()
            dist_long.columns = ["소득구간", "비율(%)"]
            chart_dist = alt.Chart(dist_long).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("비율(%):Q"),
                color=alt.Color("소득구간:N", sort=None, title="소득구간"),
                tooltip=["소득구간", alt.Tooltip("비율(%):Q", format=".1f")]
            ).properties(title="소득 구간별 인구 비율")
            st.altair_chart(chart_dist, width="stretch")

        with c2:
            occ_long = occ_df.T.reset_index()
            occ_long.columns = ["직업군", "비율(%)"]
            chart_occ = alt.Chart(occ_long).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("비율(%):Q"),
                color=alt.Color("직업군:N", sort=None, title="직업군"),
                tooltip=["직업군", alt.Tooltip("비율(%):Q", format=".1f")]
            ).properties(title="직업군별 인구 비율")
            st.altair_chart(chart_occ, width="stretch")
