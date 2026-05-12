import streamlit as st
import plotly.graph_objects as go
from data_fetcher import fetch_stock_data
import pandas as pd
import socket
import google.generativeai as genai

def get_ai_analysis(api_key, stock_data):
    if not api_key:
        return "API 키가 제공되지 않았습니다. 좌측 사이드바에 Gemini API 키를 입력해주세요."
        
    try:
        genai.configure(api_key=api_key)
        
        # Dynamically find a valid model for text generation
        valid_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
                
        if not valid_models:
            return "사용 가능한 Gemini 모델이 없습니다. API 키 상태를 확인해주세요."
            
        model_name = valid_models[0] # Fallback to first available
        # Prioritize flash or pro models
        for pref in ['models/gemini-1.5-flash-latest', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro-latest', 'models/gemini-pro', 'models/gemini-1.0-pro']:
            if pref in valid_models:
                model_name = pref
                break
                
        model = genai.GenerativeModel(model_name)
        
        info = stock_data['info']
        market = stock_data['market']
        name = stock_data['name']
        ticker = stock_data['ticker']
        
        hist_df = stock_data['history']
        if not hist_df.empty:
            recent_hist = hist_df.tail(10).to_markdown()
        else:
            recent_hist = "최근 주가 데이터가 없습니다."
            
        news_text = "\n".join([f"- {n}" for n in info.get('news', [])])
        disc_text = "\n".join([f"- {d}" for n, d in enumerate(info.get('disclosures', []))])
        
        fin_df = info.get('financials')
        if fin_df is not None:
            fin_text = fin_df.to_markdown()
        else:
            fin_text = "재무제표 정보가 없습니다."
        
        prompt = f"""
당신은 최고의 월스트리트 주식 분석가이자 AI 투자 고문입니다.
아래 제공된 '{name} ({ticker}, {market} 시장)'의 최신 주식 데이터를 바탕으로 분석 리포트를 작성해주세요.

[제공된 데이터]
- 현재 가격: {info.get('current_price')}
- 시가 총액: {info.get('market_cap')}
- 거래량: {info.get('volume')}

- 최근 주요 뉴스:
{news_text}

- 최근 공시/발표:
{disc_text}

- 최근 10일 주가 추이:
{recent_hist}

- 재무제표 (일부 발췌):
{fin_text}

[요청 사항]
위 데이터를 종합적으로 분석하여, **아래 3가지 항목을 반드시 빠짐없이** 포함하는 마크다운 리포트를 작성하세요. 특히 구체적인 가격과 투자 의견은 무조건 명시해야 합니다.

1. **현재 상황 요약**: 위 데이터(뉴스, 재무제표, 주가 흐름)를 기반으로 이 기업의 현재 상황을 요약.
2. **단기 및 중장기 예상 주가 시나리오**: 
   (AI의 추론일 뿐 실제와 다를 수 있다는 경고를 포함하되, **반드시 아래 기간별 구체적인 예상 가격(원/달러)**을 명시하세요. 두루뭉술하게 회피하지 말고, 제공된 데이터를 근거로 과감하게 추론하세요.)
   - 당일 종가 예상: (가격)
   - 내일 예상: (가격)
   - 1주일 뒤 예상: (가격)
   - 1달 뒤 예상: (가격)
   - 6개월 뒤 예상: (가격)
   - 1년 뒤 예상: (가격)
3. **투자 의견 및 가이드**: 매수 / 매도 / 관망 중 **하나의 의견을 명확히** (예: [매수]) 제시하고 이유를 설명.

(한국어로 작성하고, 가독성 좋은 마크다운 포맷을 사용해주세요. 경고 문구로 "본 예측은 AI의 가상 시나리오이며, 실제 투자 책임은 본인에게 있습니다."를 마지막에 포함해주세요.)
"""
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"AI 분석 중 오류가 발생했습니다: {str(e)}"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

import subprocess
import threading
import re
import time

@st.cache_resource
def start_ssh_tunnel():
    try:
        # ssh 커맨드로 pinggy.io에 포워딩 요청 (안정성 및 모바일 접속 개선)
        cmd = ["ssh", "-p", "443", "-R0:127.0.0.1:8501", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "a.pinggy.io"]
        # ssh.exe가 Windows에서 STARTF_USESHOWWINDOW 옵션이 켜지면 배너(URL)를 출력하지 않는 버그 우회
        # 그리고 stdin을 막아서 키보드 입력을 가로채지 않게 함
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            stdin=subprocess.PIPE,
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        
        url_info = {"url": None}
        
        def read_output():
            for line in iter(process.stdout.readline, ''):
                print(f"[SSH TUNNEL] {line.strip()}", flush=True)  # 디버그용 출력
                # pinggy.io 출력 패턴 매칭
                match = re.search(r'(https://[a-zA-Z0-9.-]+\.pinggy-free\.link)', line)
                if match:
                    url_info["url"] = match.group(1)
                    break
        
        t = threading.Thread(target=read_output, daemon=True)
        t.start()
        
        # URL이 나올 때까지 최대 20초 대기
        for _ in range(200):
            if url_info["url"]:
                break
            time.sleep(0.1)
            
        if not url_info["url"]:
            raise Exception("Pinggy 서버 응답 지연 (Timeout)")
            
        return process, url_info["url"]
    except Exception as e:
        start_ssh_tunnel.clear()
        return None, f"터널링 오류: {e}"

st.set_page_config(page_title="AI 주식 분석 및 예측", layout="wide")

st.title("📈 AI 주식 분석 및 예측 프로그램")
st.markdown("한국 주식(이름/종목코드) 및 미국 주식(티커)을 입력하면 실시간 데이터와 AI 분석 예측을 제공합니다.")

# Sidebar for API Key
with st.sidebar:
    st.header("설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    st.markdown("""
    **API 키 발급 방법:**
    1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
    2. 'Create API Key' 클릭하여 생성
    """)
    st.divider()
    st.write("📌 **사용 예시**")
    st.write("- 한국주식: 삼성전자, 005930, 카카오")
    st.write("- 미국주식: AAPL, TSLA, MSFT")
    
    st.divider()
    local_ip = get_local_ip()
    st.markdown("📱 **접속 주소 안내**")
    st.write("🏠 **내부망(같은 와이파이) 접속:**")
    st.code(f"http://{local_ip}:8501", language="text")
    
    st.write("🌐 **외부망(LTE/5G 등 모바일) 접속:**")
    with st.spinner("모바일 접속용 공개 주소 생성 중 (pinggy.io)..."):
        tunnel_process, public_url = start_ssh_tunnel()
        if public_url and public_url.startswith("http"):
            st.success("외부 접속 주소 생성 완료!")
            st.code(public_url, language="text")
            st.caption("위 주소를 스마트폰에 입력하면 외부에서도 접속할 수 있습니다.")
        else:
            st.error(f"주소 생성 실패: {public_url if public_url else '응답 지연'}")
            st.caption("새로고침을 하거나 잠시 후 다시 시도해주세요.")

# Main Search
query = st.text_input("주식 이름 또는 종목 코드(티커)를 입력하세요:", "")

if "stock_data" not in st.session_state:
    st.session_state.stock_data = None

if st.button("데이터 검색"):
    if not query:
        st.warning("종목을 입력해주세요.")
    else:
        with st.spinner(f"'{query}' 데이터를 수집 중입니다..."):
            data = fetch_stock_data(query)
            if "error" in data:
                st.error(data["error"])
                st.session_state.stock_data = None
            else:
                st.session_state.stock_data = data
                st.success("데이터 수집 완료! AI 분석을 시작합니다...")
                if api_key:
                    with st.spinner("AI가 수집된 데이터를 바탕으로 분석 중입니다. 잠시만 기다려주세요..."):
                        report = get_ai_analysis(api_key, data)
                        st.session_state.ai_report = report
                else:
                    st.session_state.ai_report = "⚠️ AI 분석을 위해 좌측 사이드바에 Gemini API 키를 입력해주세요."

if st.session_state.stock_data:
    data = st.session_state.stock_data
    info = data['info']
    
    st.subheader(f"🏢 {data['name']} ({data['ticker']})")
    
    # Basic Info
    col1, col2, col3 = st.columns(3)
    col1.metric("현재가", info.get('current_price', 'N/A'))
    col2.metric("시가총액", info.get('market_cap', 'N/A'))
    col3.metric("거래량", info.get('volume', 'N/A'))
    
    # Chart
    hist_df = data['history']
    if not hist_df.empty:
        st.subheader("📊 최근 1년 주가 차트")
        fig = go.Figure()
        # fdr vs yfinance index might be named 'Date' or just datetime index
        # yfinance columns might be multi-index if we use yf.download(ticker) in newer versions
        # let's try to handle standard OHLC
        if isinstance(hist_df.columns, pd.MultiIndex):
            # for newer yfinance
            close_col = ('Close', data['ticker']) if ('Close', data['ticker']) in hist_df.columns else ('Close', hist_df.columns.levels[1][0])
            try:
                y_data = hist_df[close_col]
            except:
                y_data = hist_df.iloc[:, 0] # fallback
        else:
            y_data = hist_df['Close'] if 'Close' in hist_df.columns else hist_df.iloc[:, 0]
            
        fig.add_trace(go.Scatter(x=hist_df.index, y=y_data, mode='lines', name='Close Price'))
        fig.update_layout(xaxis_title="Date", yaxis_title="Price", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{data['ticker']}")
    
    # Tabs for Info
    tab1, tab2, tab3 = st.tabs(["최근 뉴스", "공시 정보", "재무제표"])
    
    with tab1:
        if info.get('news'):
            for n in info['news']:
                st.write(f"- {n}")
        else:
            st.write("관련 뉴스가 없습니다.")
            
    with tab2:
        if info.get('disclosures'):
            for d in info['disclosures']:
                st.write(f"- {d}")
        else:
            st.write("공시 정보가 없습니다.")
            
    with tab3:
        if info.get('financials') is not None:
            st.dataframe(info['financials'], use_container_width=True, key=f"df_{data['ticker']}")
        else:
            st.write("재무제표 정보가 없습니다.")
        
    st.divider()
    
    # AI Analysis
    st.subheader("🤖 AI 주가 예측 및 분석 리포트")
    if hasattr(st.session_state, 'ai_report') and st.session_state.ai_report:
        st.markdown(st.session_state.ai_report)


# Force reload

# Force reload 2
