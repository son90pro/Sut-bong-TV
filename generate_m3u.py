import requests
import datetime

# Endpoint API chuẩn lấy từ Network tab
API_URL = "https://sutbongtve.cc/wp-json/soco/v1/broadcasts?sport=football"

headers = {
    "User-Agent": "Mozilla/5.0 (Android 16; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://sutbongtve.cc/",
    "X-Requested-With": "XMLHttpRequest"
}

def fetch_matches():
    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Lỗi HTTP: {response.status_code}")
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
    return []

def generate_m3u():
    data = fetch_matches()
    
    # Kiểm tra cấu trúc dữ liệu trả về từ API WordPress
    matches = data if isinstance(data, list) else data.get("data", [])
    
    m3u_content = "#EXTM3U\n"
    
    for match in matches:
        # Lấy thông tin cơ bản trận đấu
        home_name = match.get("home_team", {}).get("name", "Đội nhà")
        away_name = match.get("away_team", {}).get("name", "Đội khách")
        home_logo = match.get("home_team", {}).get("logo", "")
        
        # Thời gian trận đấu
        start_time_str = match.get("time", "Hôm nay")
        
        # Bình luận viên
        commentator = match.get("commentator", {}).get("name", "BLV")
        
        # Danh sách các link luồng phát (FHD, HD, SD...)
        channels = match.get("channels", [])
        
        for ch in channels:
            quality = ch.get("name", "HD") # FHD, HD, HD1, HD2...
            stream_url = ch.get("url", "")
            
            if not stream_url:
                continue
                
            # Định dạng tên kênh hiển thị trên IPTV
            channel_title = f"[{start_time_str}] {home_name} vs {away_name} - {quality} (BLV: {commentator})"
            
            m3u_content += f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Sutbong TV",{channel_title}\n'
            m3u_content += f'{stream_url}\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("Đã cập nhật file playlist.m3u thành công!")

if __name__ == "__main__":
    generate_m3u()
  
