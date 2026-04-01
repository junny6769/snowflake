# imports 
import json
import streamlit as st
import altair as alt
import pydeck as pdk

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

# ── 상수 ─────────────────────────────────────────────────────────────────────
DISTRICT_COLORS = {
    "서초구":   [76,  139, 245, 160],
    "영등포구": [245, 166,  35, 160],
    "중구":     [80,  200, 120, 160],
}

# ── 지도 ─────────────────────────────────────────────────────────────────────
df_map = session.query(
    f"SELECT CITY_KOR_NAME, DISTRICT_KOR_NAME, DISTRICT_GEOM "
    f"FROM HACKATHON.DATA.M_SCCO_MST "
    f"WHERE CITY_KOR_NAME = '{selected_gu}'"
)

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

geojson = geom_to_features(df_map, selected_dong)

fill_color = DISTRICT_COLORS.get(selected_dong, [200, 200, 200, 160])

st.markdown(f"### 서울 상권 분포 지도 — {selected_dong} · {selected_dong}")

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
    "서초구":   {"latitude": 37.483, "longitude": 127.032, "zoom": 10, "dong_zoom": 4},
    "영등포구": {"latitude": 37.526, "longitude": 126.896, "zoom": 12, "dong_zoom": 12},
    "중구":     {"latitude": 37.559, "longitude": 126.998, "zoom": 13, "dong_zoom": 13.5},
}
vw_config = DISTRICT_VIEW.get(selected_dong, {"latitude": 37.524, "longitude": 126.975, "zoom": 12, "dong_zoom": 14})
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

tab1, tab2, tab3 = st.tabs(["💳 카드 매출", "🚶 유동인구", "💰 소득·자산"])

with tab1:
    st.subheader(f"{selected_gu} {selected_dong} — {selected_category} 카드 매출 분석")

    card_df = session.query(f"""
        SELECT STANDARD_YEAR_MONTH,
               SUM({sales_col}) AS SALES,
               SUM({count_col}) AS TX_COUNT,
               SUM(TOTAL_SALES) AS TOTAL_SALES
        FROM CONSUMPTION_ASSET.GRANDATA.CARD_SALES_INFO
        WHERE DISTRICT_CODE = '{district_code}'
        GROUP BY STANDARD_YEAR_MONTH
        ORDER BY STANDARD_YEAR_MONTH
    """)

    if card_df.empty:
        st.info("해당 조건에 맞는 카드 매출 데이터가 없습니다.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("총 매출", f"{format_amount(card_df['SALES'].sum())}원")
        m2.metric("총 건수", f"{card_df['TX_COUNT'].sum():,.0f}")
        m3.metric("업종 비중", f"{card_df['SALES'].sum() / card_df['TOTAL_SALES'].sum() * 100:.2f}%")

        card_df["SALES_BILLION"] = card_df["SALES"] / 1_0000_0000

        c1, c2 = st.columns(2)
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
        with c2:
            chart_count = alt.Chart(card_df).mark_line(point=True).encode(
                x=alt.X("STANDARD_YEAR_MONTH:N", title="기준년월"),
                y=alt.Y("TX_COUNT:Q", title="건수"),
                tooltip=["STANDARD_YEAR_MONTH", "TX_COUNT"]
            ).properties(title=f"{selected_category} 월별 이용건수 추이")
            st.altair_chart(chart_count, use_container_width=True)

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

with tab2:
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

with tab3:
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