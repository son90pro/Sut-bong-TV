from datetime import datetime
import json
import re
from curl_cffi import requests
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def clean_text(text):
  """Xóa tất cả các ký tự xuống dòng và khoảng trắng thừa."""
  if not text:
    return ''
  return re.sub(r'\s+', ' ', str(text)).strip()


def parse_timestamp(ts):
  """Chuyển đổi thời gian sang giờ Việt Nam (UTC+7)."""
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


def get_sport_icon(sport_type):
  s = str(sport_type).lower()
  if 'basket' in s or 'rổ' in s:
    return '🏀'
  elif 'tennis' in s or 'vợt' in s:
    return '🎾'
  elif 'volley' in s or 'chuyền' in s:
    return '🏐'
  elif 'badminton' in s or 'cầu lông' in s:
    return '🏸'
  return '⚽'


def fetch_matches():
  session = requests.Session(impersonate='chrome120')
  headers = {
      'Referer': 'https://sutbongtve.cc/',
      'Origin': 'https://sutbongtve.cc',
      'Accept': 'application/json, text/plain, */*',
  }

  raw_matches = []
  endpoints = [
      'https://sutbongtve.cc/wp-json/soco/v1/matches',
      'https://sutbongtve.cc/api/v1/matches',
      'https://api.rainbowbridge.fit/api/matches',
  ]

  for url in endpoints:
    try:
      res = session.get(url, headers=headers, timeout=10)
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

  if not raw_matches:
    try:
      res = session.get(
          'https://sutbongtve.cc/', headers=headers, timeout=12
      )
      if res.status_code == 200:
        html = res.text
        match_json = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL
        )
        if match_json:
          st = json.loads(match_json.group(1))
          raw_matches = (
              st.get('matches') or st.get('matchList') or st.get('list') or []
          )
    except Exception as e:
      print(f'Lỗi kết nối trang web: {e}')

  return raw_matches


def generate_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches:
    print('Không có dữ liệu trận đấu.')
    return '\n'.join(m3u_lines)

  seen = set()

  for item in matches:
    try:
      if not isinstance(item, dict):
        continue

      # Lấy tên hai đội và làm sạch
      home = clean_text(
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else ''
          )
      )
      away = clean_text(
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else ''
          )
      )

      # Bỏ qua dòng bị lỗi hoặc dính tên giải
      if (
          not home
          or not away
          or home == away
          or 'giải' in home.lower()
          or 'giải' in away.lower()
      ):
        continue

      # Logo chuẩn của đội nhà
      logo = item.get('home_logo') or item.get('logo') or ''
      if isinstance(item.get('home'), dict):
        logo = item.get('home', {}).get('logo') or logo
      if logo and logo.startswith('/'):
        logo = f'https://sutbongtve.cc{logo}'

      # Thời gian thi đấu thực tế
      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)
      sport_icon = get_sport_icon(item.get('sport_type', 'football'))

      # Xử lý danh sách luồng phát của các BLV
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
        blv_raw = item.get('commentator') or item.get('blv') or 'BLV Sút Bóng'
        links = [{'url': stream_url, 'blv': blv_raw, 'quality': 'FHD'}]

      for idx, link in enumerate(links, 1):
        if isinstance(link, dict):
          s_url = (
              link.get('url')
              or link.get('play_url')
              or link.get('m3u8')
              or link.get('link')
          )
          blv_str = (
              link.get('blv')
              or link.get('commentator')
              or link.get('name')
              or f'BLV {idx}'
          )
          quality = link.get('quality') or 'FHD'
        else:
          s_url = str(link)
          blv_str = f'BLV {idx}'
          quality = 'FHD'

        if not s_url:
          continue

        # Lọc danh sách BLV nếu bị lặp/xuống dòng
        blv_clean_list = [
            clean_text(b) for b in str(blv_str).split('\n') if clean_text(b)
        ]
        if not blv_clean_list:
          blv_clean_list = ['BLV Sút Bóng']

        for single_blv in blv_clean_list:
          unique_key = f'{home}-{away}-{single_blv}'
          if unique_key in seen:
            continue
          seen.add(unique_key)

          # Định dạng chuẩn không xuống dòng
          title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({single_blv}) [{quality}]'

          m3u_lines.append(
              f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
              f' TV",{title_display}'
          )
          m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi xử lý mục: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  data = fetch_matches()
  m3u_content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã ghi file playlist.m3u chuẩn thành công!')
  
