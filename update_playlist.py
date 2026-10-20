from datetime import datetime, timedelta
import json
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def get_sport_icon(sport_text):
  sport = str(sport_text).lower()
  if 'basket' in sport or 'rổ' in sport:
    return '🏀'
  elif 'tennis' in sport or 'vợt' in sport:
    return '🎾'
  elif 'volley' in sport or 'chuyền' in sport:
    return '🏐'
  elif 'badminton' in sport or 'cầu lông' in sport:
    return '🏸'
  return '⚽'


def scrape_sutbongtv():
  matches_data = []

  with sync_playwright() as p:
    # Mở trình duyệt Chromium giả lập thiết bị di động/desktop
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()

    # Bắt các response API dạng JSON phát ra từ web
    def handle_response(response):
      try:
        if 'api' in response.url or 'json' in response.url or 'match' in response.url:
          if response.status == 200 and 'json' in response.headers.get('content-type', ''):
            data = response.json()
            if isinstance(data, dict) and 'data' in data:
              matches_data.extend(data['data'])
            elif isinstance(data, list):
              matches_data.extend(data)
      except Exception:
        pass

    page.on('response', handle_response)

    try:
      print('Đang truy cập sutbongtve.cc...')
      page.goto('https://sutbongtve.cc/', wait_until='networkidle', timeout=30000)
      page.wait_for_timeout(5000)  # Chờ 5s để trang nạp xong dữ liệu

      # Bóc tách trực tiếp DOM nếu không bắt được API JSON
      if not matches_data:
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Quét các thẻ chứa thông tin trận đấu trên giao diện
        match_cards = soup.select('.match-item, .game-item, div[class*="match"], div[class*="game"]')
        for card in match_cards:
          text = card.get_text(strip=True)
          if 'vs' in text.lower():
            img_tag = card.find('img')
            logo = img_tag['src'] if img_tag and 'src' in img_tag.attrs else ''
            
            matches_data.append({
                'raw_text': text,
                'logo': logo,
                'home_team': 'Đội Nhà',
                'away_team': 'Đội Khách',
                'match_time': datetime.now(TZ_VN).strftime('%H:%M'),
                'stream_url': page.url
            })
    except Exception as e:
      print(f'Lỗi khi cào dữ liệu: {e}')
    finally:
      browser.close()

  return matches_data


def generate_m3u(matches):
  m3u = ['#EXTM3U x-tvg-url=""']
  now_vn = datetime.now(TZ_VN)
  today_str = now_vn.strftime('%d/%m')

  if not matches:
    print('Không tìm thấy dữ liệu từ web.')
    return '\n'.join(m3u)

  for idx, m in enumerate(matches, 1):
    time_str = m.get('match_time', '00:00')
    home = m.get('home_team', m.get('home_name', 'Đội A'))
    away = m.get('away_team', m.get('away_name', 'Đội B'))
    logo = m.get('logo', m.get('home_logo', ''))
    blv = m.get('blv', m.get('commentator', 'Gà Vàng'))
    quality = m.get('quality', 'FHD')
    group = m.get('group', 'Gà Vàng 33 TV')
    url = m.get('stream_url', m.get('play_url', 'https://sutbongtve.cc'))

    sport_icon = get_sport_icon(m.get('sport', 'football'))

    # Cấu hình định dạng tên hiển thị chuẩn theo yêu cầu hình mẫu
    title = f"{time_str} {today_str} {sport_icon} {home} vs {away} ({blv}) [{quality}]"

    m3u.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{title}')
    m3u.append(url)

  return '\n'.join(m3u)


if __name__ == '__main__':
  data = scrape_sutbongtv()
  print(f'Thu thập được {len(data)} danh mục/trận đấu.')
  
  m3u_text = generate_m3u(data)
  
  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_text)
  print('Đã cập nhật file playlist.m3u thành công!')
    
