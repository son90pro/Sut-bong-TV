from datetime import datetime
import json
import re
from curl_cffi import requests
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def parse_timestamp(ts):
  """Chuyển đổi thời gian sang múi giờ Việt Nam UTC+7."""
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


def fetch_full_matches():
  session = requests.Session(impersonate='chrome120')
  headers = {
      'Referer': 'https://sutbongtve.cc/',
      'Origin': 'https://sutbongtve.cc',
      'Accept': 'application/json, text/plain, *_/*',
  }

  raw_matches = []

  # 1. Quét qua các API nội bộ của trang web Sút Bóng TV
  api_endpoints = [
      'https://sutbongtve.cc/api/v1/matches',
      'https://sutbongtve.cc/api/matches',
      'https://api.rainbowbridge.fit/api/matches',
      'https://sutbongtve.cc/json/matches.json',
  ]

  for api_url in api_endpoints:
    try:
      res = session.get(api_url, headers=headers, timeout=10)
      if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and len(data) > 0:
          raw_matches = data
          break
        elif isinstance(data, dict):
          arr = (
              data.get('data') or data.get('matches') or data.get('list') or []
          )
          if isinstance(arr, list) and len(arr) > 0:
            raw_matches = arr
            break
    except Exception:
      continue

  # 2. Nếu API bị khóa, quét toàn bộ state dữ liệu nhúng sẵn trên trang chủ HTML
  if not raw_matches:
    try:
      res = session.get('https://sutbongtve.cc/', headers=headers, timeout=15)
      if res.status_code == 200:
        html = res.text
        # Trích xuất dữ liệu JSON khởi tạo của trang web
        match_json = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL
        )
        if match_json:
          state_data = json.loads(match_json.group(1))
          raw_matches = (
              state_data.get('matches')
              or state_data.get('matchList')
              or state_data.get('list')
              or []
          )
    except Exception as e:
      print(f'Lỗi kết nối trang web: {e}')

  return raw_matches


def generate_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches:
    print('Không lấy được danh sách trận đấu.')
    return '\n'.join(m3u_lines)

  print(f'Đang xử lý {len(matches)} trận đấu thực tế...')
  seen = set()

  for item in matches:
    try:
      # Lấy tên đội nhà và đội khách
      home = (
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else ''
          )
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else ''
          )
      )

      if not home or not away or home == away:
        continue

      # Lấy logo đội bóng
      logo = (
          item.get('home_logo')
          or (
              item.get('home', {}).get('logo')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or item.get('logo')
          or ''
      )
      if logo and logo.startswith('/'):
        logo = f'https://sutbongtve.cc{logo}'

      # Thời gian trận đấu (chuẩn múi giờ VN)
      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)

      # Danh sách luồng phát và Bình luận viên (BLV)
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
        blv = item.get('commentator') or item.get('blv') or 'Sút Bóng TV'
        links = [{'url': stream_url, 'blv': blv, 'quality': 'FHD'}]

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
          quality = link.get('quality') or 'FHD'
        else:
          s_url = str(link)
          blv_name = f'BLV {idx}'
          quality = 'FHD'

        if not s_url:
          continue

        # Tránh trùng lặp các luồng
        unique_key = f'{home}-{away}-{blv_name}'
        if unique_key in seen:
          continue
        seen.add(unique_key)

        # Định dạng chuẩn hiển thị theo yêu cầu:
        # 09:00 20/10 ⚽ Đội A vs Đội B (Tên BLV) [FHD]
        title_display = f'{time_str} {date_str} ⚽ {home} vs {away} ({blv_name}) [{quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
            f' TV",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi định dạng trận đấu: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  matches_data = fetch_full_matches()
  m3u_content = generate_m3u(matches_data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã cập nhật toàn bộ danh sách trận đấu vào file playlist.m3u thành công!')
  
