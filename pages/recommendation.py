import streamlit as st
import altair as alt

session = st.connection("snowflake")

st.title("상권 랭킹")
