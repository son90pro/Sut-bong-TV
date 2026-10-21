import cloudscraper
import datetime
import time

# Khởi tạo cloudscraper với session giả lập Firefox Android tối ưu
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'firefox',
        'platform': 'android',
        'desktop': False
    }
)

API_URL = "https://sutbongtve.cc/wp-json/soco/v1/broadcasts?sport=football"

def fetch_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Android 16; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://sutbongtve.cc/",
        "Origin": "https://sutbongtve.cc"
    }
    
    # Thử lại tối đa 3 lần nếu gặp lỗi 503
    for attempt in range(3):
        try:
            response = scraper.get(API_URL, headers=headers, timeout=15)
            print(f"Lần thử {attempt + 1} - Status Code: {response.status_code}")
            if response.status_code == 200:
                return response.json()
            time.sleep(2) # Chờ 2 giây rồi thử lại nếu bị chặn
        except Exception as e:
            print(f"Lỗi kết nối (lần {attempt + 1}): {e}")
            time.sleep(2)
    return []

def generate_m3u():
    data = fetch_matches()
    matches = data if isinstance(data, list) else data.get("data", [])
    
    m3u_content = "#EXTM3U\n"
    
    if not matches:
        print("Cảnh báo: Không lấy được danh sách trận đấu do bị chặn hoặc server trống.")
    
    for match in matches:
        home_name = match.get("home_team", {}).get("name", "Đội nhà")
        away_name = match.get("away_team", {}).get("name", "Đội khách")
        home_logo = match.get("home_team", {}).get("logo", "")
        start_time_str = match.get("time", "Hôm nay")
        commentator = match.get("commentator", {}).get("name", "BLV")
        channels = match.get("channels", [])
        
        for ch in channels:
            quality = ch.get("name", "HD")
            stream_url = ch.get("url", "")
            if not stream_url:
                continue
                
            channel_title = f"[{start_time_str}] {home_name} vs {away_name} - {quality} (BLV: {commentator})"
            m3u_content += f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Sutbong TV",{channel_title}\n'
            m3u_content += f'{stream_url}\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("Đã cập nhật file playlist.m3u thành công!")

if __name__ == "__main__":
    generate_m3u()
    
