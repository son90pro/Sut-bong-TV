from datetime import datetime
import re
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def clean_text(text):
  if not text:
    return ''
  return re.sub(r'\s+', ' ', str(text)).strip()


def scrape_sutbong_playlist():
  channels_data = []

  with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True, args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 800},
    )
    page = context.new_page()

    # Bắt trực tiếp link luồng m3u8 từ network request
    active_m3u8_links = {}

    def handle_request(request):
      url = request.url
      if '.m3u8' in url or 'pull.' in url:
        active_m3u8_links['url'] = url

    page.on('request', handle_request)

    try:
      print('Đang mở trang chủ sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=30000
      )
      page.wait_for_timeout(8000)

      # Quét các khối trận đấu cụ thể trên trang chủ
      match_cards = page.locator('div[class*="match"], div[class*="game"]').all()
      match_items = []

      for card in match_cards:
        try:
          txt = card.inner_text()
          if 'vs' in txt.lower():
            link_el = card.locator('a[href*="/truc-tiep/"]').first
            if link_el.count() > 0:
              href = link_el.get_attribute('href')
              full_url = (
                  f'https://sutbongtve.cc{href}'
                  if href.startswith('/')
                  else href
              )
              if full_url not in match_items:
                match_items.append(full_url)
        except Exception:
          continue

      print(
          f'Tìm thấy {len(match_items)} trận đấu. Đang trích xuất chi tiết...'
      )

      # Nếu không quét được qua card, lấy các đường dẫn trực tiếp từ trang
      if not match_items:
        links = page.locator('a[href*="/truc-tiep/"]').all()
        for l in links:
          h = l.get_attribute('href')
          if h:
            u = f'https://sutbongtve.cc{h}' if h.startswith('/') else h
            if u not in match_items:
              match_items.append(u)

      # Duyệt qua từng trang chi tiết trận đấu
      for match_url in match_items[:25]:
        try:
          detail_page = context.new_page()
          detail_page.goto(
              match_url, wait_until='domcontentloaded', timeout=15000
          )
          detail_page.wait_for_timeout(4000)

          # Lấy tiêu đề trang chính xác để tách tên 2 đội
          title = detail_page.title()
          home, away = 'Đội Nhà', 'Đội Khách'

          clean_title = re.sub(
              r'Sutbong TV.*?-|Xem trực tiếp.*?-', '', title, flags=re.IGNORECASE
          )
          if 'vs' in clean_title.lower():
            parts = re.split(
                r'\s+vs\s+|\s+-\s+', clean_title, flags=re.IGNORECASE
            )
            if len(parts) >= 2:
              home = clean_text(parts[0])
              away = clean_text(parts[1])

          # Lấy logo chuẩn
          img_el = detail_page.locator('img').first
          logo = (
              img_el.get_attribute('src')
              if img_el.count() > 0
              else 'https://sutbongtve.cc/wp-content/uploads/2026/08/logo-subongtv-vin-1024x576.png'
          )
          if logo and logo.startswith('/'):
            logo = f'https://sutbongtve.cc{logo}'

          # Lấy danh sách BLV thực tế đang hiển thị trên các nút bấm của trận này
          blv_buttons = detail_page.locator(
              'button, div[class*="blv"], div[class*="tab"]'
          ).all()
          blv_names = []

          for btn in blv_buttons:
            b_text = clean_text(btn.inner_text())
            if (
                b_text
                and len(b_text) < 20
                and b_text
                not in [
                    'CHAT',
                    'THỐNG KÊ',
                    'ĐỘI HÌNH',
                    'DIỄN BIẾN',
                    'BẢNG XẾP HẠNG',
                ]
            ):
              if b_text not in blv_names:
                blv_names.append(b_text)

          if not blv_names:
            blv_names = ['BLV Sút Bóng']

          now_vn = datetime.now(TZ_VN)
          time_str = now_vn.strftime('%H:%M')
          date_str = now_vn.strftime('%d/%m')

          # Lấy link m3u8 thực tế hoặc fallback về url chi tiết
          stream_url = active_m3u8_links.get('url', match_url)

          for blv in blv_names:
            channels_data.append({
                'home': home,
                'away': away,
                'time': time_str,
                'date': date_str,
                'blv': blv,
                'logo': logo,
                'url': stream_url,
            })

          detail_page.close()
        except Exception as e:
          print(f'Lỗi phân tích trận đấu: {e}')

    except Exception as e:
      print(f'Lỗi tổng quan: {e}')
    finally:
      browser.close()

  return channels_data


def generate_m3u(channels):
  m3u_lines = ['#EXTM3U x-tvg-url=""']
  if not channels:
    print('Không có kênh nào được tạo.')
    return '\n'.join(m3u_lines)

  print(f'Tổng hợp thành công {len(channels)} luồng phát...')
  seen = set()

  for ch in channels:
    home = ch['home']
    away = ch['away']
    blv = ch['blv']

    key = f'{home}-{away}-{blv}'
    if key in seen:
      continue
    seen.add(key)

    title = f"{ch['time']} {ch['date']} ⚽ {home} vs {away} ({blv}) [FHD]"
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="Sút Bóng TV",{title}'
    )
    m3u_lines.append(ch['url'])

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  data = scrape_sutbong_playlist()
  content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(content)

  print('Đã ghi file playlist.m3u hoàn tất!')
  
