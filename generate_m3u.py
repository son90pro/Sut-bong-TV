import requests
import datetime

# Sử dụng API nguồn tổng hợp không bị chặn Cloudflare gắt gao
API_URL = "https://api.vebo.xyz/api/match/featured"

def fetch_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://vebo.xyz/"
    }
    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
    return []

def format_time(timestamp):
    try:
        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
        return dt.strftime("%d/%m %H:%M")
    except:
        return "Hôm nay"

def generate_m3u():
    matches = fetch_matches()
    
    m3u_content = "#EXTM3U\n"
    
    if not matches:
        print("Cảnh báo: Không lấy được danh sách trận đấu từ API.")
    
    for match in matches:
        home_name = match.get("home_name", "Đội nhà")
        away_name = match.get("away_name", "Đội khách")
        home_logo = match.get("home_logo", "")
        start_time = format_time(match.get("match_time", 0))
        commentator = match.get("commentator", "BLV")
        
        # Danh sách luồng phát
        play_urls = match.get("play_urls", [])
        
        for stream in play_urls:
            quality = stream.get("name", "HD")
            stream_url = stream.get("url", "")
            
            if not stream_url:
                continue
                
            channel_title = f"[{start_time}] {home_name} vs {away_name} - {quality} (BLV: {commentator})"
            m3u_content += f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Bóng Đá Tổng Hợp",{channel_title}\n'
            m3u_content += f'{stream_url}\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("Đã cập nhật file playlist.m3u thành công!")

if __name__ == "__main__":
    generate_m3u()
    
