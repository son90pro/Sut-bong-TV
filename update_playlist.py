from datetime import datetime, timedelta
import json
import re
import pytz
import requests

# Cấu hình múi giờ Việt Nam
TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')

# Header giả lập trình duyệt để không bị chặn
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://sutbongtve.cc/',
    'Origin': 'https://sutbongtve.cc',
    'Accept': 'application/json, text/plain, */*',
}


def get_sport_icon(sport_type):
  """Trả về icon theo môn thể thao."""
  sport = str(sport_type).lower()
  if 'basket' in sport or 'rổ' in sport:
    return '🏀'
  elif 'tennis' in sport or 'vợt' in sport:
    return '🎾'
  elif 'volley' in sport or 'chuyền' in sport:
    return '🏐'
  elif 'badminton' in sport or 'cầu lông' in sport:
    return '🏸'
  return '⚽'  # Mặc định là bóng đá


def fetch_matches():
  matches = []
  # Các API endpoint phổ biến của hệ thống sutbongtve / rainbowbridge
  api_urls = [
      'https://api.rainbowbridge.fit/api/matches',
      'https://sutbongtve.cc/api/matches',
      'https://sutbongtve.cc/json/matches.json',
  ]

  session = requests.Session()
  session.headers.update(HEADERS)

  # Thử gọi API lấy danh sách trận đấu
  for url in api_urls:
    try:
      res = session.get(url, timeout=10)
      if res.status_code == 200:
        data = res.json()
        if isinstance(data, list):
          matches = data
          break
        elif isinstance(data, dict) and 'data' in data:
          matches = data['data']
          break
    except Exception:
      continue

  # Nếu không lấy được qua API trực tiếp, cào dữ liệu từ trang chủ HTML
  if not matches:
    try:
      res = session.get('https://sutbongtve.cc/', timeout=10)
      if res.status_code == 200:
        # Tìm dữ liệu JSON nhúng trong thẻ script
        match_json = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', res.text
        )
        if match_json:
          json_data = json.loads(match_json.group(1))
          matches = json_data.get('matches', [])
    except Exception as e:
      print(f'Lỗi cào dữ liệu HTML: {e}')

  return matches


def build_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  # Ngày hôm nay và ngày mai theo giờ VN
  now_vn = datetime.now(TZ_VN)
  today_date = now_vn.date()
  tomorrow_date = today_date + timedelta(days=1)

  for match in matches:
    try:
      # Lấy thời gian trận đấu (chuyển sang UTC+7)
      match_time_raw = match.get('match_time') or match.get('start_time')
      if isinstance(match_time_raw, (int, float)):
        # Nếu là timestamp
        dt_utc = datetime.fromtimestamp(match_time_raw, tz=pytz.utc)
        dt_vn = dt_utc.astimezone(TZ_VN)
      elif isinstance(match_time_raw, str):
        dt_vn = datetime.strptime(
            match_time_raw[:19], '%Y-%m-%d %H:%M:%S'
        ).replace(tzinfo=TZ_VN)
      else:
        dt_vn = now_vn

      # Lọc chỉ lấy các trận hôm nay và ngày mai
      if dt_vn.date() not in [today_date, tomorrow_date]:
        continue

      time_str = dt_vn.strftime('%H:%M')
      date_str = dt_vn.strftime('%d/%m')

      # Thông tin đội bóng
      home_team = (
          match.get('home_team')
          or match.get('home_name')
          or match.get('home', {}).get('name', 'Đội nhà')
      )
      away_team = (
          match.get('away_team')
          or match.get('away_name')
          or match.get('away', {}).get('name', 'Đội khách')
      )

      # Logo đội bóng (ưu tiên logo đội nhà)
      logo = (
          match.get('home_logo')
          or match.get('home', {}).get('logo')
          or match.get('logo', '')
      )

      # Icon môn thể thao
      sport_icon = get_sport_icon(match.get('sport_type', 'football'))

      # Nhóm kênh (Nhà đài)
      group_title = (
          match.get('channel_name')
          or match.get('tournament_name')
          or 'Sút Bóng TV'
      )

      # Danh sách luồng phát (Streams)
      links = match.get('links') or match.get('play_urls') or []

      if not links and 'stream_url' in match:
        links = [{
            'url': match['stream_url'],
            'blv': match.get('commentator', 'BLV'),
            'quality': 'HD',
        }]

      for index, link in enumerate(links, 1):
        stream_url = (
            link.get('url') if isinstance(link, dict) else link
        )
        if not stream_url:
          continue

        blv = (
            link.get('blv')
            or link.get('commentator')
            or match.get('commentator')
            or 'BLV'
        )
        quality = (
            link.get('quality')
            or link.get('resolution')
            or f'HD{index if index > 1 else ""}'
        )

        # Định dạng tiêu đề giống mẫu: 06:00 20/10 ⚽ Corinthians - SP vs Vitória - BA (Gà Siêu Nhí) [hls]
        title_display = f'{time_str} {date_str} {sport_icon} {home_team} vs {away_team} ({blv}) [{quality}]'

        # Ghi dòng EXTINF
        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}"'
            f' group-title="{group_title}",{title_display}'
        )
        m3u_lines.append(stream_url)

    except Exception as e:
      print(f'Lỗi xử lý trận đấu: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  print('Đang lấy danh sách trận đấu từ sutbongtve.cc...')
  matches = fetch_matches()
  print(f'Tìm thấy {len(matches)} trận đấu.')

  m3u_content = build_m3u(matches)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã ghi thành công vào file playlist.m3u!')
    
