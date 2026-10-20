from datetime import datetime, timedelta
import json
import re
import pytz
import requests

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://sutbongtve.cc/',
    'Origin': 'https://sutbongtve.cc',
    'Accept': 'application/json, text/plain, */*',
}


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


def parse_timestamp(ts):
  """Chuyển thời gian sang múi giờ Việt Nam UTC+7."""
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


def fetch_data():
  session = requests.Session()
  session.headers.update(HEADERS)
  matches = []

  # Danh sách các API endpoint trực tiếp của hệ thống Sút Bóng TV
  api_endpoints = [
      'https://sutbongtve.cc/api/v1/matches',
      'https://sutbongtve.cc/api/matches',
      'https://api.rainbowbridge.fit/api/matches',
      'https://sutbongtve.cc/json/matches.json',
  ]

  for api_url in api_endpoints:
    try:
      res = session.get(api_url, timeout=10)
      if res.status_code == 200:
        data = res.json()
        if isinstance(data, list):
          matches = data
          break
        elif isinstance(data, dict):
          matches = (
              data.get('data') or data.get('matches') or data.get('list') or []
          )
          if matches:
            break
    except Exception:
      continue

  # Cào dữ liệu nhúng sẵn trên HTML nếu API direct bị chặn
  if not matches:
    try:
      res = session.get('https://sutbongtve.cc/', timeout=12)
      if res.status_code == 200:
        html = res.text
        # Tìm dữ liệu JSON state nhúng sẵn trong thẻ script
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
    except Exception as e:
      print(f'Lỗi cào HTML: {e}')

  return matches


def generate_m3u(matches_data):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches_data:
    print('Không tìm thấy dữ liệu từ Sút Bóng TV.')
    return '\n'.join(m3u_lines)

  print(f'Đang tổng hợp dữ liệu {len(matches_data)} trận đấu...')
  seen = set()

  for item in matches_data:
    try:
      home = (
          item.get('home_name')
          or item.get('home_team')
          or item.get('home', {}).get('name')
          or 'Đội A'
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or item.get('away', {}).get('name')
          or 'Đội B'
      )

      if home == away or 'Đội' in home:
        continue

      logo = (
          item.get('home_logo')
          or item.get('home', {}).get('logo')
          or item.get('logo')
          or ''
      )
      if logo and logo.startswith('/'):
        logo = f'https://sutbongtve.cc{logo}'

      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)

      sport_type = item.get('sport_type') or item.get('sport') or 'football'
      sport_icon = get_sport_icon(sport_type)

      # Bóc tách danh sách các luồng phát của từng BLV (THOMAS, BLV TAP, ZIDANE...)
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
            or item.get('url')
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
              or item.get('commentator')
              or f'BLV {idx}'
          )
          quality = link.get('quality') or 'FHD'
        else:
          s_url = str(link)
          blv_name = item.get('commentator') or f'BLV {idx}'
          quality = 'FHD'

        if not s_url:
          continue

        # Đảm bảo không trùng lặp kênh
        unique_key = f'{home}-{away}-{blv_name}'
        if unique_key in seen:
          continue
        seen.add(unique_key)

        # Định dạng chuẩn hiển thị theo hình mẫu yêu cầu:
        # 09:00 20/10 ⚽ Escorpiones Belen vs Puntarenas FC (THOMAS) [FHD]
        title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({blv_name}) [{quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
            f' TV",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi xử lý kênh: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  data = fetch_data()
  m3u_content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã cập nhật file playlist.m3u thành công!')
  
