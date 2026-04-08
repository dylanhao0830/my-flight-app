import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import airportsdata
import numpy as np

# 从 Streamlit 的 Secrets 中读取 Key
API_TOKEN = st.secrets["API_TOKEN"]
RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]

# --- 2. 数据获取函数 ---
@st.cache_resource
def get_location_and_db():
    db = airportsdata.load('IATA')
    list_for_search = []
    for code, info in db.items():
        if info['city'] and code:
            label = f"{info['city']} ({code})"
            list_for_search.append(label)
    
    default_city_code = "PVG" 
    try:
        geo_res = requests.get("https://ipapi.co/json/", timeout=5).json()
        city_name = geo_res.get("city", "Shanghai")
        for code, info in db.items():
            if info['city'] == city_name:
                default_city_code = code
                break
    except:
        pass 
        
    return db, sorted(list_for_search), default_city_code

def search_flights(origin, destination, date, direct_only):
    api_url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin, "destination": destination, "departure_at": date,
        "unique": "false", "sorting": "price", "currency": "cny", "limit": 15,
        "direct": "true" if direct_only else "false", "token": API_TOKEN
    }
    try:
        response = requests.get(api_url, params=params)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_calendar_prices(origin, destination, month_start):
    api_url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin, "destination": destination, "departure_at": month_start[:7],
        "unique": "false", "sorting": "price", "currency": "cny", "limit": 30, "token": API_TOKEN
    }
    try:
        response = requests.get(api_url, params=params)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_extra_details(flight_num, date_str):
    # 1. 彻底清洗航班号：转大写、去空格、去所有特殊字符
    import re
    clean_num = re.sub(r'[^a-zA-Z0-9]', '', flight_num).upper()
    
    # 【调试代码】在页面上显示一下到底发了什么（确认后可以删掉）
    #  st.write(f"调试信息：正在向 API 请求航班号 [{clean_num}] 日期 [{date_str}]")
    
    url = f"https://aerodatabox.p.rapidapi.com/flights/number/{clean_num}/{date_str}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
    }
    
    try:
        # 增加超时控制，防止卡死
        response = requests.get(url, headers=headers, timeout=10)
        
        # 如果返回 204 (No Content) 或 404，说明 API 数据库确实没这班
        if response.status_code == 204:
            return None
        
        data = response.json()
        
        # AeroDataBox 返回的是列表，我们取第一个
        if data and isinstance(data, list) and len(data) > 0:
            f = data[0]
            # 提取航站楼和机型
            return {
                "plane": f.get('aircraft', {}).get('model', '机型信息未发布'),
                "dep_term": f.get('departure', {}).get('terminal', '-'),
                "arr_term": f.get('arrival', {}).get('terminal', '-'),
                "status": f.get('status', '未知')
            }
    except Exception as e:
        # st.error(f"API 请求失败: {e}")
        return None
    return None

# --- 3. 界面逻辑 ---
st.set_page_config(page_title="智能机票搜索引擎", page_icon="✈️", layout="wide")
st.title("✈️ 机票全网比价 (专业增强版)")

if "flight_data" not in st.session_state:
    st.session_state.flight_data = None
if "search_info" not in st.session_state:
    st.session_state.search_info = ""

db, search_options, local_code = get_location_and_db()

with st.sidebar:
    st.header("行程设置")
    
    default_origin_idx = 0
    for i, opt in enumerate(search_options):
        if f"({local_code})" in opt:
            default_origin_idx = i
            break
            
    origin_label = st.selectbox("起飞城市", options=search_options, index=default_origin_idx)
    
    default_dest_idx = 0
    for i, opt in enumerate(search_options):
        if "(PEK)" in opt:
            default_dest_idx = i
            break
    dest_label = st.selectbox("到达城市", options=search_options, index=default_dest_idx)
    
    origin_code = origin_label.split('(')[-1].strip(')')
    dest_code = dest_label.split('(')[-1].strip(')')
    travel_date = st.date_input("出发日期", min_value=datetime.today())
    only_direct = st.checkbox("仅看直飞航班", value=False)
    
    st.divider()
    search_btn = st.button("🔍 搜索当天低价", use_container_width=True)
    calendar_btn = st.button("📅 查看本月趋势", use_container_width=True)

# --- 4. 逻辑处理区 ---

# 功能 A: 搜索并存入 Session
if search_btn:
    with st.spinner("正在同步全球低价数据..."):
        res = search_flights(origin_code, dest_code, travel_date.strftime("%Y-%m-%d"), only_direct)
        if "data" in res and res["data"]:
            st.session_state.flight_data = res["data"]
            st.session_state.search_info = travel_date.strftime("%Y-%m-%d")
        else:
            st.session_state.flight_data = None
            st.warning("📅 当天暂无数据记录。")

# 功能 B: 渲染搜索结果 (通过 Session State)
if st.session_state.flight_data:
    st.subheader(f"📍 {st.session_state.search_info} 的低价推荐")
    for idx, flight in enumerate(st.session_state.flight_data):
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 1])
            airline = flight.get('airline', '')
            price = flight.get('price', 0)
            flight_num = f"{airline}{flight.get('flight_number', '')}"
            
            with col1:
                st.image(f"https://pics.avs.io/200/80/{airline}.png", width=100)
                st.markdown(f"### ¥{price}")
                st.caption(f"航班号: {flight_num}")
            
            with col2:
                try:
                    dep_time_dt = datetime.fromisoformat(flight['departure_at'].replace('Z', '+00:00'))
                except:
                    dep_time_dt = datetime.strptime(flight['departure_at'][:19].replace('T', ' '), '%Y-%m-%d %H:%M:%S')
                
                # 👈 之前报错的 duration 就在这里，现在已经对齐
                duration = flight.get('duration', 0)
                arr_time_dt = dep_time_dt + timedelta(minutes=duration)
                
                st.write(f"🛫 **{dep_time_dt.strftime('%H:%M')}** ➔ 🛬 **{arr_time_dt.strftime('%H:%M')}**")
                st.caption(f"⏱️ 历时: {duration//60}时{duration%60}分 | 📍 {flight['origin_airport']} ➔ {flight['destination_airport']}")
                
                with st.expander("🔍 详细机型与航站楼"):
                    if st.button(f"获取实时详情", key=f"btn_extra_{idx}"):
                        with st.spinner("正在从全球数据库检索..."):
                            details = get_extra_details(flight_num, st.session_state.search_info)
                            
                            if details:
                                # 成功的情况
                                st.success(f"✈️ 机型: **{details['plane']}**")
                                st.info(f"🏢 航站楼: 起 **{details['dep_term']}** | 终 **{details['arr_term']}**")
                            else:
                                # 💡 优雅保底：实时查不到时，从本地数据库提取机场名称
                                st.warning("⚠️ 该航班实时详情暂未发布（建议离出发前4小时再查）")
                                
                                # 从 db 中获取起飞和到达机场的详细资料
                                dep_info = db.get(flight['origin_airport'], {})
                                arr_info = db.get(flight['destination_airport'], {})
                                
                                st.markdown("---")
                                st.write("**📍 基础位置参考：**")
                                st.write(f"🏠 **始发机场：** {dep_info.get('name', '未知机场')} ({flight['origin_airport']})")
                                st.write(f"🏁 **终到机场：** {arr_info.get('name', '未知机场')} ({flight['destination_airport']})")
                                st.caption("💡 提示：大型机场通常有多个航站楼，请以航司最新短信或机场大屏为准。")

            with col3:
                st.write("")
                st.write("")
                st.link_button("✈️ 去订票", f"https://www.aviasales.com{flight.get('link','')}", type="primary", use_container_width=True)

# 功能 C: 价格日历 (确保它在 if st.session_state.flight_data 之外，即最左侧对齐)
if calendar_btn:
    month_str = travel_date.strftime("%Y-%m-01")
    with st.spinner("分析本月趋势..."):
        cal_res = get_calendar_prices(origin_code, dest_code, month_str)
        if "data" in cal_res and len(cal_res["data"]) > 0:
            st.subheader(f"📊 {month_str[:7]} 价格走势")
            cal_df = pd.DataFrame(cal_res["data"])
            cal_df['date'] = pd.to_datetime(cal_df['departure_at']).dt.date
            st.bar_chart(cal_df.set_index('date')['price'])
        else:
            st.info("提示：当前航线本月缓存数据较少。")
