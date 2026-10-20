from datetime import datetime
import json
import re
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def parse_timestamp(ts):
  """Quy đổi thời gian trận đấu sang giờ Việt Nam."""
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


def fetch_matches_and_m3u8():
  extracted_channels = []

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

    # Bắt tất cả các luồng phát .m3u8 phát ra trong mạng (network)
    captured_m3u8 = []

    def handle_request(request):
      url = request.url
      if '.m3u8' in url or 'pull.' in url:
        captured_m3u8.append(url)

    page.on('request', handle_request)

    try:
      print('Đang truy cập trang chủ sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=25000
      )
      page.wait_for_timeout(5000)

      # 1. Thu thập dữ liệu trận đấu và danh sách BLV từ DOM / API
      match_cards = page.locator(
          'div[class*="match"], div[class*="game"], a[href*="truc-tiep"]'
      ).all()
      match_links = []

      for card in match_cards:
        try:
          txt = card.inner_text()
          if 'vs' in txt.lower() and len(txt) < 300:
            href = card.get_attribute('href')
            if href:
              full_url = (
                  f'https://sutbongtve.cc{href}'
                  if href.startswith('/')
                  else href
              )
              if full_url not in match_links:
                match_links.append(full_url)
        except Exception:
          continue

      print(f'Tìm thấy {len(match_links)} trang trận đấu chi tiết.')

      # 2. Duyệt qua các trận đấu đang phát để bóc tách từng BLV & link .m3u8 trực tiếp
      for match_url in match_links[:15]:  # Giới hạn lấy các trận hot đang/sắp diễn ra
        try:
          print(f'Đang quét luồng phát trận: {match_url}')
          captured_m3u8.clear()
          detail_page = context.new_page()
          detail_page.on('request', handle_request)

          detail_page.goto(
              match_url, wait_until='domcontentloaded', timeout=15000
          )
          detail_page.wait_for_timeout(4000)

          # Lấy tên hai đội
          page_title = detail_page.title()
          title_parts = re.split(r'vs|-', page_title, flags=re.IGNORECASE)
          home_team = title_parts[0].strip() if len(title_parts) > 0 else 'Đội A'
          away_team = title_parts[1].strip() if len(title_parts) > 1 else 'Đội B'

          # Lấy danh sách các nút BLV (THOMAS, BLV TAP, ZIDANE...)
          blv_elements = detail_page.locator(
              'button, div[class*="blv"], div[class*="tab"], div[class*="btn"]'
          ).all()
          blv_names = []

          for el in blv_elements:
            t = el.inner_text().strip()
            if t and len(t) < 20 and ('blv' in t.lower() or t.isupper()):
              if t not in blv_names and t not in ['CHAT', 'THỐNG KÊ', 'ĐỘI HÌNH', 'DIỄN BIẾN']:
                blv_names.append(t)

          if not blv_names:
            blv_names = ['Sút Bóng TV']

          # Nếu tìm thấy link .m3u8 thực tế từ network
          valid_m3u8 = [u for u in captured_m3u8 if '.m3u8' in u]

          for idx, blv in enumerate(blv_names):
            stream_url = (
                valid_m3u8[idx]
                if idx < len(valid_m3u8)
                else (valid_m3u8[0] if valid_m3u8 else match_url)
            )

            now_vn = datetime.now(TZ_VN)
            extracted_channels.append({
                'home_team': home_team,
                'away_team': away_team,
                'match_time': now_vn.strftime('%H:%M'),
                'date': now_vn.strftime('%d/%m'),
                'blv': blv,
                'quality': 'FHD',
                'stream_url': stream_url,
                'logo': 'https://sutbongtve.cc/favicon.ico',
            })

          detail_page.close()
        except Exception as e:
          print(f'Lỗi quét trang chi tiết: {e}')

    except Exception as e:
      print(f'Lỗi tổng quan: {e}')
    finally:
      browser.close()

  return extracted_channels


def generate_m3u(channels):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not channels:
    print('Không có luồng phát nào được bóc tách.')
    return '\n'.join(m3u_lines)

  print(f'Đang tạo danh sách M3U cho {len(channels)} luồng BLV...')

  for ch in channels:
    home = ch.get('home_team', 'Đội A')
    away = ch.get('away_team', 'Đội B')
    time_str = ch.get('match_time', '00:00')
    date_str = ch.get('date', '20/10')
    blv = ch.get('blv', 'Sút Bóng TV')
    quality = ch.get('quality', 'FHD')
    logo = ch.get('logo', '')
    url = ch.get('stream_url', '')

    # Định dạng hiển thị chuẩn theo yêu cầu:
    # 09:00 20/10 ⚽ Escorpiones Belen vs Puntarenas FC (THOMAS) [FHD]
    title_display = f'{time_str} {date_str} ⚽ {home} vs {away} ({blv}) [{quality}]'

    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{logo}" group-title="Sút Bóng TV",{title_display}'
    )
    m3u_lines.append(url)

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  channels = fetch_matches_and_m3u8()
  m3u_content = generate_m3u(channels)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã cập nhật file playlist.m3u chứa link video m3u8 trực tiếp!')
  
