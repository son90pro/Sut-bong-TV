from datetime import datetime, timedelta
import json
import re
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


def parse_timestamp(ts):
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


def fetch_data_from_sutbongtv():
  matches_list = []

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Android 16; Mobile; rv:157.0) Gecko/157.0'
            ' Firefox/157.0'
        ),
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()

    # Bắt tất cả các phản hồi API JSON từ trang web trả về
    def handle_response(response):
      try:
        url = response.url.lower()
        if (
            'api' in url
            or 'match' in url
            or 'list' in url
            or 'track' in url
            or 'json' in url
        ):
          if (
              response.status == 200
              and 'json' in response.headers.get('content-type', '').lower()
          ):
            res_json = response.json()
            if isinstance(res_json, list):
              matches_list.extend(res_json)
            elif isinstance(res_json, dict):
              arr = (
                  res_json.get('data')
                  or res_json.get('matches')
                  or res_json.get('list')
              )
              if isinstance(arr, list):
                matches_list.extend(arr)
      except Exception:
        pass

    page.on('response', handle_response)

    try:
      print('Đang mở trang sutbongtve.cc...')
      # Sử dụng domcontentloaded để không bị timeout chờ network
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=20000
      )
      page.wait_for_timeout(4000)  # Chờ các thành phần JavaScript khởi tạo

      # Cào dữ liệu trực tiếp từ các thẻ trên HTML nếu trang hiển thị danh sách trận đấu dạng DOM
      cards = page.locator(
          'div, a, li'
      ).all()  # Hoặc quét các phần tử chứa thông tin trận đấu
      for card in cards:
        try:
          txt = card.inner_text()
          if 'vs' in txt.lower() and len(txt) < 200:
            # Trích xuất cơ bản tên các đội nếu tìm thấy cấu trúc text trận đấu
            lines = [
                l.strip() for l in txt.split('\n') if l.strip() != ''
            ]
            if len(lines) >= 2:
              matches_list.append({
                  'home_name': lines[0],
                  'away_name': (
                      lines[1] if 'vs' not in lines[1].lower() else 'Đội Khách'
                  ),
                  'match_time': datetime.now(TZ_VN).strftime('%H:%M'),
                  'stream_url': page.url,
                  'commentator': 'Gà Vàng',
                  'quality': 'FHD',
              })
        except Exception:
          continue

    except Exception as e:
      print(f'Lỗi khi duyệt trang: {e}')
    finally:
      browser.close()

  return matches_list


def generate_m3u(raw_matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not raw_matches:
    print('Không có dữ liệu trận đấu nào được trích xuất.')
    return '\n'.join(m3u_lines)

  print(f'Đang tổng hợp {len(raw_matches)} mục...')
  seen = set()

  for item in raw_matches:
    try:
      home = item.get('home_name', item.get('home_team', 'Đội Nhà'))
      away = item.get('away_name', item.get('away_team', 'Đội Khách'))
      if home == away or 'Đội Nhà' in home:
        continue

      key = f'{home}-{away}'
      if key in seen:
        continue
      seen.add(key)

      logo = item.get('logo', '')
      time_str, date_str = parse_timestamp(
          item.get('match_time', datetime.now(TZ_VN))
      )
      sport_icon = get_sport_icon(item.get('sport', 'football'))
      group_title = item.get('tournament_name', 'Sút Bóng TV')
      blv = item.get('commentator', 'BLV')
      quality = item.get('quality', 'FHD')
      s_url = item.get('stream_url', 'https://sutbongtve.cc')

      title_display = (
          f'{time_str} {date_str} {sport_icon} {home} vs {away} ({blv})'
          f' [{quality}]'
      )

      m3u_lines.append(
          f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_title}",'
          f'{title_display}'
      )
      m3u_lines.append(s_url)
    except Exception as e:
      print(f'Lỗi định dạng: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  matches = fetch_data_from_sutbongtv()
  m3u_content = generate_m3u(matches)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)
  print('Đã cập nhật file playlist.m3u thành công!')
  
