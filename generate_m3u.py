import cloudscraper
import datetime

# Khởi tạo cloudscraper giả lập trình duyệt Firefox trên Android để vượt Cloudflare (tránh lỗi 503)
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'firefox',
        'platform': 'android',
        'desktop': False
    }
)

API_URL = "https://sutbongtve.cc/wp-json/soco/v1/broadcasts?sport=football"

def fetch_matches():
    try:
        response = scraper.get(API_URL, timeout=15)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Lỗi HTTP: {response.status_code}")
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
    return []

def generate_m3u():
    data = fetch_matches()
    matches = data if isinstance(data, list) else data.get("data", [])
    
    m3u_content = "#EXTM3U\n"
    
    for match in matches:
        home_name = match.get("home_team", {}).get("name", "Đội nhà")
        away_name = match.get("away_team", {}).get("name", "Đội khách")
        home_logo = match.get("home_team", {}).get("logo", "")
        start_time_str = match.get("time", "Hôm nay")
        commentator = match.get("commentator", {}).get("name", "BLV")
        channels = match.get("channels", [])
        
        for ch in channels:
            quality = ch.get("name", "HD") # FHD, HD, HD1, HD2...
            stream_url = ch.get("url", "")
            if not stream_url:
                continue
                
            # Định dạng tên hiển thị trên danh sách IPTV theo yêu cầu
            channel_title = f"[{start_time_str}] {home_name} vs {away_name} - {quality} (BLV: {commentator})"
            m3u_content += f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Sutbong TV",{channel_title}\n'
            m3u_content += f'{stream_url}\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("Đã cập nhật file playlist.m3u thành công!")

if __name__ == "__main__":
    generate_m3u()
