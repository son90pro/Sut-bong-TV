from datetime import datetime
import json
import re
from curl_cffi import requests
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def parse_timestamp(ts):
  """Quy đổi thời gian sang chuẩn múi giờ Việt Nam UTC+7."""
  try:
    if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
      ts_val = float(ts)
      if ts_val > 1e11:
        ts_val /= 1000.0
      dt = datetime.fromtimestamp(ts_val, tz=pytz.utc).astimezone(TZ_VN)
      return dt.strftime('%H:%M'), dt.strftime('%d/%m')
    elif isinstance(ts, str) and len(ts) >= 10:
      dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S').replace(
          tzinfo=TZ_VN
      )
      return dt.strftime('%H:%M'), dt.strftime('%d/%m')
  except Exception:
    pass
  now_vn = datetime.now(TZ_VN)
  return now_vn.strftime('%H:%M'), now_vn.strftime('%d/%m')


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


def fetch_sutbong_data():
  session = requests.Session(impersonate='chrome120')

  # 1. Gửi request xác thực tracking API theo đúng chuẩn của website
  track_url = 'https://api.rainbowbridge.fit/track'
  track_payload = {
      'session_id': 'edd08ea4-67db-4950-a90a-441f7db72d14',
      'user_cookie': 'd4d05370-ba46-4394-b1fe-61d51da8df28',
      'url': 'https://sutbongtve.cc/',
      'hostname': 'sutbongtve.cc',
      'referer': 'https://www.google.com/',
      'browser': (
          'Mozilla/5.0 (Android 16; Mobile; rv:157.0) Gecko/157.0'
          ' Firefox/157.0'
      ),
      'is_bot': 0,
  }

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Android 16; Mobile; rv:157.0) Gecko/157.0'
          ' Firefox/157.0'
      ),
      'Referer': 'https://sutbongtve.cc/',
      'Origin': 'https://sutbongtve.cc',
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/plain, */*',
  }

  try:
    session.post(track_url, json=track_payload, headers=headers, timeout=10)
  except Exception:
    pass

  matches = []

  # 2. Quét qua các nguồn API soco-engine / sportdb thực tế của hệ thống
  api_endpoints = [
      'https://sutbongtve.cc/wp-json/soco/v1/aes-pull',
      'https://sutbongtve.cc/wp-json/soco/v1/matches',
      'https://api.rainbowbridge.fit/api/matches',
      'https://sportdb.live/api/matches',
      'https://sutbongtve.cc/json/matches.json',
  ]

  for url in api_endpoints:
    try:
      res = session.get(url, headers=headers, timeout=10)
      if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and len(data) > 0:
          matches = data
          break
        elif isinstance(data, dict):
          arr = (
              data.get('data')
              or data.get('matches')
              or data.get('list')
              or data.get('key')
              or []
          )
          if isinstance(arr, list) and len(arr) > 0:
            matches = arr
            break
          elif isinstance(arr, str):
            # Nếu trả về dạng token/key cấu hình
            pass
    except Exception:
      continue

  # 3. Lấy trực tiếp trang chủ và trích xuất toàn bộ state khởi tạo
  if not matches:
    try:
      res = session.get(
          'https://sutbongtve.cc/', headers=headers, timeout=15
      )
      if res.status_code == 200:
        html = res.text
        match_json = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL
        )
        if match_json:
          state_data = json.loads(match_json.group(1))
          matches = (
              state_data.get('matches')
              or state_data.get('matchList')
              or state_data.get('list')
              or []
          )

        # Nếu không có state, dùng regex quét các luồng trận đấu trong HTML
        if not matches:
          # Fallback tạo mục chung từ trang chủ nếu dữ liệu động ẩn qua JS bảo vệ
          matches.append({
              'home_name': 'Sút Bóng TV Trực Tiếp',
              'away_name': 'Hôm Nay',
              'match_time': datetime.now(TZ_VN).strftime('%H:%M'),
              'logo': (
                  'https://sutbongtve.cc/wp-content/uploads/2026/08/logo-subongtv-vin.png'
              ),
              'stream_url': 'https://sutbongtve.cc/',
              'commentator': 'BLV Sút Bóng',
              'quality': 'Full HD',
          })
    except Exception as e:
      print(f'Lỗi kết nối trang: {e}')

  return matches


def generate_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches:
    print('Không có dữ liệu trận đấu.')
    return '\n'.join(m3u_lines)

  print(f'Đang tổng hợp {len(matches)} mục hiển thị...')
  seen = set()

  for item in matches:
    try:
      if isinstance(item, str):
        continue

      home = (
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or 'Đội Nhà'
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else ''
          )
          or 'Đội Khách'
      )

      logo = (
          item.get('home_logo')
          or (
              item.get('home', {}).get('logo')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or item.get('logo')
          or 'https://sutbongtve.cc/wp-content/uploads/2026/08/logo-subongtv-vin.png'
      )
      if logo and logo.startswith('/'):
        logo = f'https://sutbongtve.cc{logo}'

      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)
      sport_icon = get_sport_icon(item.get('sport_type', 'football'))

      links = (
          item.get('links')
          or item.get('play_urls')
          or item.get('channels')
          or []
      )

      if not links:
        stream_url = (
            item.get('stream_url')
            or item.get('play_url')
            or item.get('m3u8')
            or 'https://sutbongtve.cc/'
        )
        blv = item.get('commentator') or item.get('blv') or 'BLV Sút Bóng'
        links = [{'url': stream_url, 'blv': blv, 'quality': 'Full HD'}]

      for idx, link in enumerate(links, 1):
        if isinstance(link, dict):
          s_url = (
              link.get('url')
              or link.get('play_url')
              or link.get('m3u8')
              or link.get('link')
          )
          blv_name = (
              link.get('blv')
              or link.get('commentator')
              or link.get('name')
              or f'BLV {idx}'
          )
          quality = link.get('quality') or 'Full HD'
        else:
          s_url = str(link)
          blv_name = f'BLV {idx}'
          quality = 'Full HD'

        if not s_url:
          continue

        unique_key = f'{home}-{away}-{blv_name}'
        if unique_key in seen:
          continue
        seen.add(unique_key)

        title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({blv_name}) [{quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
            f' TV",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi xử lý trận đấu: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  matches_data = fetch_sutbong_data()
  m3u_content = generate_m3u(matches_data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã cập nhật hoàn tất file playlist.m3u!')
  
