from datetime import datetime, timedelta
import json
import re
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def parse_timestamp(ts):
  """Chuyển đổi timestamp/chuỗi giờ sang giờ Việt Nam (UTC+7)."""
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


def fetch_matches_with_aes_decryption():
  raw_matches = []

  with sync_playwright() as p:
    # Mở Chromium với Flag bỏ qua CORS để nhận luồng giải mã AES
    browser = p.chromium.launch(
        headless=True, args=['--disable-web-security', '--no-sandbox']
    )
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()

    # Bắt tất cả response JSON sau khi trình duyệt đã giải mã AES thành công
    def handle_response(response):
      try:
        url = response.url.lower()
        if (
            'aes-pull' in url
            or 'wp-json' in url
            or 'match' in url
            or 'sport' in url
        ):
          if (
              response.status == 200
              and 'json' in response.headers.get('content-type', '').lower()
          ):
            res_data = response.json()
            if isinstance(res_data, list):
              raw_matches.extend(res_data)
            elif isinstance(res_data, dict):
              arr = (
                  res_data.get('data')
                  or res_data.get('matches')
                  or res_data.get('list')
                  or res_data.get('rows')
              )
              if isinstance(arr, list):
                raw_matches.extend(arr)
      except Exception:
        pass

    page.on('response', handle_response)

    try:
      print('Đang mở sutbongtve.cc và kích hoạt giải mã AES...')
      # Dùng commit/domcontentloaded để không bị timeout
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=25000
      )
      page.wait_for_timeout(7000)  # Chờ JS chạy giải mã AES và render DOM

      # Nếu response mạng chưa bắt đủ, trích xuất dữ liệu từ DOM đã render hoàn chỉnh
      if not raw_matches:
        print('Bóc tách dữ liệu trực tiếp từ DOM đã giải mã...')
        cards = page.locator(
            'div[class*="match"], div[class*="game"], div[class*="soco"]'
        ).all()
        for card in cards:
          try:
            txt = card.inner_text()
            if 'vs' in txt.lower() and len(txt) < 300:
              lines = [l.strip() for l in txt.split('\n') if l.strip()]
              imgs = card.locator('img').all()
              logo = (
                  imgs[0].get_attribute('src')
                  if imgs and len(imgs) > 0
                  else ''
              )

              # Lấy tên BLV từ card nếu có
              blv_match = re.search(r'BLV\s+[\w\s]+', txt, re.IGNORECASE)
              blv_name = blv_match.group(0) if blv_match else 'BLV Sút Bóng'

              raw_matches.append({
                  'home_name': lines[0] if len(lines) > 0 else 'Đội A',
                  'away_name': lines[2] if len(lines) > 2 else 'Đội B',
                  'match_time': datetime.now(TZ_VN).strftime('%H:%M'),
                  'logo': logo,
                  'stream_url': 'https://sutbongtve.cc/',
                  'commentator': blv_name,
                  'quality': 'FHD',
              })
          except Exception:
            continue

    except Exception as e:
      print(f'Lỗi Playwright: {e}')
    finally:
      browser.close()

  return raw_matches


def generate_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not matches:
    print('Không tìm thấy trận đấu nào.')
    return '\n'.join(m3u_lines)

  print(f'Đang bóc tách {len(matches)} trận đấu...')
  seen = set()

  for item in matches:
    try:
      if not isinstance(item, dict):
        continue

      home = (
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or item.get('home')
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else ''
          )
          or item.get('away')
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

        unique_key = f'{home}-{away}-{blv_name}'
        if unique_key in seen:
          continue
        seen.add(unique_key)

        # Định dạng chuẩn giao diện mẫu:
        # 06:00 20/10 ⚽ Corinthians vs Vitória (BLV Siêu Nhí) [FHD]
        title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({blv_name}) [{quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng'
            f' TV",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi xử lý mục: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  matches_data = fetch_matches_with_aes_decryption()
  m3u_content = generate_m3u(matches_data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã bóc tách thành công danh sách trận đấu thực tế vào playlist.m3u!')
  
