import yfinance as yf
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
from datetime import datetime, timedelta

US_STOCK_KO_MAPPING = {
    "애플": "AAPL", "테슬라": "TSLA", "알파벳": "GOOGL", "알파벳A": "GOOGL", 
    "알파벳C": "GOOG", "구글": "GOOGL", "엔비디아": "NVDA", "마이크로소프트": "MSFT", 
    "아마존": "AMZN", "메타": "META", "페이스북": "META", "넷플릭스": "NFLX", 
    "에이엠디": "AMD", "인텔": "INTC", "퀄컴": "QCOM", "브로드컴": "AVGO", 
    "티에스엠씨": "TSM", "TSMC": "TSM", "제이피모건": "JPM", "존슨앤드존슨": "JNJ", 
    "버크셔해서웨이": "BRK-B", "버크셔": "BRK-B", "일라이릴리": "LLY", "비자": "V", 
    "마스터카드": "MA", "엑슨모빌": "XOM", "월마트": "WMT", "유나이티드헬스": "UNH", 
    "코스트코": "COST", "프록터앤갬블": "PG", "홈디포": "HD", "디즈니": "DIS", 
    "코카콜라": "KO", "펩시": "PEP", "맥도날드": "MCD", "스타벅스": "SBUX", 
    "나이키": "NKE", "보잉": "BA", "팔란티어": "PLTR", "아이비엠": "IBM", 
    "오라클": "ORCL", "어도비": "ADBE", "시스코": "CSCO", "우버": "UBER", 
    "에어비앤비": "ABNB", "쇼피파이": "SHOP", "로블록스": "RBLX", "니콜라": "NKLA", 
    "루시드": "LCID", "리비안": "RIVN", "니오": "NIO", "쿠팡": "CPNG", 
    "스퀘어": "SQ", "블록": "SQ", "페이팔": "PYPL", "줌": "ZM", "인튜이트": "INTU", 
    "암": "ARM", "슈퍼마이크로": "SMCI", "슈퍼마이크로컴퓨터": "SMCI", "델": "DELL"
}

def is_korean(text):
    return bool(re.search('[가-힣]', text))

def is_numeric(text):
    return text.isdigit()

def get_krx_ticker(name_or_code):
    if is_numeric(name_or_code):
        # We don't have the exact name, so just use code as name for now, or we can fetch it later
        return name_or_code.zfill(6), name_or_code
    
    try:
        df = fdr.StockListing('KRX')
        result = df[df['Name'] == name_or_code]
        if not result.empty:
            return result.iloc[0]['Code'], result.iloc[0]['Name']
        
        result = df[df['Name'].str.contains(name_or_code, na=False)]
        if not result.empty:
            return result.iloc[0]['Code'], result.iloc[0]['Name']
    except:
        pass
        
    return None, name_or_code

def fetch_naver_finance(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res = requests.get(url, headers=headers)
    html_text = res.content.decode('utf-8', 'replace')
    soup = BeautifulSoup(html_text, 'html.parser')
    
    data = {}
    
    try:
        price_tag = soup.select_one('.no_today .blind')
        if price_tag:
            data['current_price'] = price_tag.text
        else:
            data['current_price'] = "N/A"
    except:
        data['current_price'] = "N/A"
        
    try:
        mcap = soup.select_one('#_market_sum')
        if mcap:
            data['market_cap'] = ' '.join(mcap.text.split()) + "억원"
        else:
            data['market_cap'] = "N/A"
    except:
        data['market_cap'] = "N/A"
        
    try:
        # 거래량
        vol_tag = soup.select_one('.no_info span.blind')
        if vol_tag:
            data['volume'] = "최근 데이터 참조" # Will be overwritten by hist_df
        else:
            data['volume'] = "N/A"
    except:
        data['volume'] = "N/A"
        
    news_list = []
    try:
        news_tags = soup.select('.news_section ul li a')
        for tag in news_tags[:10]: # Fetch up to 10 since news and disclosures are mixed
            title = tag.get('title') or tag.text
            if title: news_list.append(title.strip())
    except:
        pass
    data['news'] = list(dict.fromkeys(news_list)) # 중복제거
    
    disc_list = []
    try:
        # 네이버 금융이 뉴스와 공시를 합쳤으므로, 공시 탭이 따로 없으면 뉴스로 안내
        disc_tags = soup.select('.sub_section.news_section_2 ul li a')
        if not disc_tags:
            disc_list.append("최신 공시는 위 '최근 뉴스' 목록에 통합되어 표시됩니다.")
        else:
            for tag in disc_tags[:5]:
                title = tag.get('title') or tag.text
                if title: disc_list.append(title.strip())
    except:
        disc_list.append("공시 정보를 파싱할 수 없습니다.")
    data['disclosures'] = list(dict.fromkeys(disc_list))
    
    try:
        dfs = pd.read_html(url, encoding='utf-8')
        fin_df = None
        for df in dfs:
            # Flatten multi-index if exists to check for keywords
            cols = " ".join([str(c) for c in df.columns])
            if '매출액' in cols or '영업이익' in cols:
                fin_df = df
                break
        if fin_df is None and len(dfs) > 4:
            fin_df = dfs[4] # Fallback to table 4
            
        if fin_df is not None:
            # Flatten columns for easier display
            if isinstance(fin_df.columns, pd.MultiIndex):
                fin_df.columns = ['_'.join(str(c) for c in col).strip() for col in fin_df.columns.values]
            fin_df = fin_df.astype(str)
            data['financials'] = fin_df.head(10)
        else:
            data['financials'] = None
    except Exception as e:
        data['financials'] = None
        
    return data

def fetch_yfinance_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    
    data = {}
    data['current_price'] = str(info.get('currentPrice', info.get('regularMarketPrice', 'N/A')))
    data['market_cap'] = str(info.get('marketCap', 'N/A'))
    data['volume'] = str(info.get('volume', 'N/A'))
    
    news_list = []
    try:
        for news in ticker.news[:5]:
            news_list.append(news.get('title', ''))
    except:
        pass
    data['news'] = news_list
    
    data['disclosures'] = ["야후 파이낸스는 개별 공시를 별도로 제공하지 않습니다. 주요 뉴스를 참고하세요."]
    
    try:
        fin = ticker.financials
        if fin is not None and not fin.empty:
            fin = fin.astype(str)
            data['financials'] = fin.head(10)
        else:
            data['financials'] = None
    except:
        data['financials'] = None
        
    return data

def fetch_stock_data(query):
    query = query.strip()
    
    if query in US_STOCK_KO_MAPPING:
        market = 'US'
        ticker = US_STOCK_KO_MAPPING[query]
        name = query
    elif is_korean(query) or is_numeric(query):
        market = 'KR'
        krx_code, krx_name = get_krx_ticker(query)
        if not krx_code:
            return {"error": f"주식 종목을 찾을 수 없습니다: {query}"}
        ticker = krx_code
        name = krx_name
    else:
        market = 'US'
        ticker = query.upper()
        name = ticker
    
    try:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if market == 'KR':
            info_data = fetch_naver_finance(ticker)
            hist_df = fdr.DataReader(ticker, start_date)
        else:
            info_data = fetch_yfinance_data(ticker)
            hist_df = yf.download(ticker, start=start_date, progress=False)
            if hist_df.empty:
                return {"error": f"미국 주식 티커를 찾을 수 없거나 데이터가 없습니다: {query}"}
            
        if not hist_df.empty:
            try:
                if 'Volume' in hist_df.columns or hasattr(hist_df.columns, 'levels'):
                    vol_data = hist_df['Volume']
                    if isinstance(vol_data, pd.DataFrame):
                        last_vol = vol_data.iloc[-1, 0]
                    else:
                        last_vol = vol_data.iloc[-1]
                    info_data['volume'] = f"{int(last_vol):,}"
            except Exception as e:
                pass
                
            try:
                if info_data.get('current_price', 'N/A') == 'N/A':
                    if 'Close' in hist_df.columns or hasattr(hist_df.columns, 'levels'):
                        close_data = hist_df['Close']
                        if isinstance(close_data, pd.DataFrame):
                            last_close = close_data.iloc[-1, 0]
                        else:
                            last_close = close_data.iloc[-1]
                        info_data['current_price'] = f"{int(last_close):,}"
            except Exception as e:
                pass
            
        result = {
            "market": market,
            "ticker": ticker,
            "name": name,
            "info": info_data,
            "history": hist_df
        }
        return result
    except Exception as e:
        return {"error": f"데이터 수집 중 오류 발생: {str(e)}"}
