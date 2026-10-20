from datetime import datetime, timedelta
import json
import re
from bs4 import BeautifulSoup
from curl_cffi import requests
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


def parse_timestamp(ts):
  """Quy đổi thời gian trận đấu sang múi giờ Việt Nam UTC+7."""
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


def fetch_matches_data():
  matches = []
  session = requests.Session(impersonate='chrome120')

  headers = {
      'Referer': 'https://sutbongtve.cc/',
      'Origin': 'https://sutbongtve.cc',
      'Accept': 'application/json, text/plain, */*',
  }

  # 1. Gọi trực tiếp API nội bộ của trang web
  api_urls = [
      'https://sutbongtve.cc/api/v1/matches',
      'https://sutbongtve.cc/api/matches',
      'https://sutbongtve.cc/json/matches.json',
  ]

  for url in api_urls:
    try:
      res = session.get(url, headers=headers, timeout=10)
      if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and len(data) > 0:
          matches = data
          break
        elif isinstance(data, dict):
          arr = (
              data.get('data') or data.get('matches') or data.get('list') or []
          )
          if isinstance(arr, list) and len(arr) > 0:
            matches = arr
            break
    except Exception:
      continue

  # 2. Nếu API không mở, cào HTML bằng Impersonate Fingerprint
  if not matches:
    try:
      res = session.get('https://sutbongtve.cc/', headers=headers, timeout=12)
      if res.status_code == 200:
        html = res.text
        # Quét state JSON nhúng sẵn trong script
        script_data = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL
        )
        if script_data:
          st = json.loads(script_data.group(1))
          matches = (
              st.get('matches') or st.get('matchList') or st.get('list') or []
          )

        # Nếu không có state JSON, bóc tách bằng BeautifulSoup
        if not matches:
          soup = BeautifulSoup(html, 'html.parser')
          cards = soup.select(
              'div[class*="match"], div[class*="game"], a[href*="truc-tiep"]'
          )
          for card in cards:
            text = card.get_text(separator=' ', strip=True)
            if 'vs' in text.lower():
              imgs = card.find_all('img')
              logo = imgs[0]['src'] if imgs and 'src' in imgs[0].attrs else ''
              matches.append({
                  'raw_text': text,
                  'logo': logo,
                  'home_name': 'Đội A',
                  'away_name': 'Đội B',
                  'match_time': datetime.now(TZ_VN).strftime('%H:%M'),
                  'stream_url': 'https://sutbongtve.cc/',
              })
    except Exception as e:
      print(f'Lỗi cào HTML: {e}')

  return matches


def generate_m3u(matches_data):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches_data:
    print('Không tìm thấy dữ liệu từ Sút Bóng TV.')
    return '\n'.join(m3u_lines)

  print(f'Thu thập thành công {len(matches_data)} mục.')
  seen = set()

  for item in matches_data:
    try:
      home = (
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or 'Đội A'
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else ''
          )
          or 'Đội B'
      )

      if not home or not away or home == away:
        continue

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

      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)

      sport_type = item.get('sport_type') or item.get('sport') or 'football'
      sport_icon = get_sport_icon(sport_type)

      # Bóc tách danh sách các BLV (THOMAS, BLV TAP, ZIDANE...)
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
        blv = item.get('commentator') or item.get('blv') or 'BLV'
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

        key = f'{home}-{away}-{blv_name}'
        if key in seen:
          continue
        seen.add(key)

        title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({blv_name}) [{quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
            f' TV",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi định dạng: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  data = fetch_matches_data()
  m3u_content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã ghi file playlist.m3u thành công!')
    
