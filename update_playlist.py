from datetime import datetime, timedelta
import json
import re
from bs4 import BeautifulSoup
import pytz
import requests

# Cấu hình múi giờ Việt Nam (GMT+7)
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)

url = 'https://sutbongtve.cc/'
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://sutbongtve.cc/',
}

try:
  response = requests.get(url, headers=headers, timeout=15)
  soup = BeautifulSoup(response.text, 'html.parser')

  # Khởi tạo nội dung file M3U chuẩn
  m3u_content = '#EXTM3U x-tvg-url=""\n'

  # Tìm kiếm danh sách các trận đấu trên trang (tùy thuộc vào cấu trúc HTML thực tế của web)
  # Dưới đây là cấu trúc mẫu quét qua các thẻ chứa thông tin trận đấu
  match_cards = soup.find_all(
      ['div', 'a'], class_=re.compile('match|card|game|item', re.I)
  )

  # Nếu trang sử dụng dữ liệu JSON nhúng (Next.js / Nuxt.js)
  script_data = soup.find('script', id='__NEXT_DATA__')
  if script_data:
    try:
      json_data = json.loads(script_data.string)
      # Xử lý trích xuất từ JSON nếu web dạng render phía server/client API
    except:
      pass

  # Mẫu dòng lệnh M3U tiêu chuẩn hiển thị giống hình mẫu:
  # #EXTINF:-1 tvg-id="" tvg-logo="URL_LOGO" group-title="Gà Vàng 33 TV",06:00 20/10 ⚽ Corinthians - SP vs Vitória - BA (Gà Siêu Nhí) [hls]
  # LINK_STREAM

  # Ghi file playlist.m3u
  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Cập nhật danh sách M3U thành công!')

except Exception as e:
  print(f'Lỗi khi cào dữ liệu: {e}')

