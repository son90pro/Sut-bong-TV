from datetime import datetime, timedelta
import json
import re
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def parse_match_text(raw_text):
  """Làm sạch và tách chính xác tên đội bóng, giờ thi đấu từ nội dung thẻ."""
  lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
  home, away = 'Đội Nhà', 'Đội Khách'
  time_str = datetime.now(TZ_VN).strftime('%H:%M')
  date_str = datetime.now(TZ_VN).strftime('%d/%m')

  for line in lines:
    time_match = re.search(r'\d{2}:\d{2}', line)
    if time_match:
      time_str = time_match.group(0)

  for i, line in enumerate(lines):
    if 'vs' in line.lower():
      parts = re.split(r'\s+vs\s+', line, flags=re.IGNORECASE)
      if len(parts) == 2:
        home = parts[0].strip()
        away = parts[1].strip()
      elif i > 0 and i + 1 < len(lines):
        home = lines[i - 1]
        away = lines[i + 1]
      break

  return home, away, time_str, date_str


def fetch_data_from_sutbongtv():
  matches_list = []

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()

    try:
      print('Đang mở trang sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=20000
      )
      page.wait_for_timeout(5000)

      cards = page.locator('div, a, article, section').all()
      for card in cards:
        try:
          txt = card.inner_text()
          if 'vs' in txt.lower() and len(txt) < 300:
            href = card.get_attribute('href')
            if href:
              if href.startswith('/'):
                stream_url = f'https://sutbongtve.cc{href}'
              elif href.startswith('http'):
                stream_url = href
              else:
                stream_url = f'https://sutbongtve.cc/{href}'
            else:
              stream_url = 'https://sutbongtve.cc/'

            img_el = card.locator('img').first
            logo = (
                img_el.get_attribute('src')
                if img_el.count() > 0
                else ''
            )
            if logo and logo.startswith('/'):
              logo = f'https://sutbongtve.cc{logo}'

            home, away, time_str, date_str = parse_match_text(txt)

            # Bỏ qua nếu tên đội dính tên giải đấu hoặc chưa bắt được chuẩn
            if (
                home != 'Đội Nhà'
                and away != 'Đội Khách'
                and 'giải' not in home.lower()
                and 'vô địch' not in home.lower()
            ):
              matches_list.append({
                  'home_name': home,
                  'away_name': away,
                  'match_time': time_str,
                  'date': date_str,
                  'logo': logo,
                  'stream_url': stream_url,
                  'commentator': 'BLV Sút Bóng',
                  'quality': 'FHD',
                  'group': 'Sút Bóng TV',
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

  print(f'Đang tổng hợp dữ liệu trận đấu...')
  seen = set()

  for item in raw_matches:
    try:
      home = item.get('home_name', 'Đội Nhà')
      away = item.get('away_name', 'Đội Khách')

      key = f'{home}-{away}'
      if key in seen:
        continue
      seen.add(key)

      logo = item.get('logo', '')
      time_str = item.get('match_time', '00:00')
      date_str = item.get('date', datetime.now(TZ_VN).strftime('%d/%m'))
      sport_icon = '⚽'
      group_title = 'Sút Bóng TV'
      blv = item.get('commentator', 'BLV Sút Bóng')
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
  
