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

    # Bắt tất cả các luồng phát .m3u8 thực tế từ network của trang web
    captured_streams = {}

    def handle_request(request):
      url = request.url
      if '.m3u8' in url or 'pull.' in url:
        # Lưu lại link m3u8 theo dạng domain hoặc query
        captured_streams['active_m3u8'] = url

    page.on('request', handle_request)

    try:
      print('Đang truy cập trang chủ sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=30000
      )
      page.wait_for_timeout(8000)  # Chờ trang render dữ liệu động hoàn toàn

      # Tìm tất cả các liên kết dẫn đến trang xem trực tiếp trận đấu
      match_links = page.locator('a[href*="/truc-tiep/"]').all()
      unique_urls = set()
      for link in match_links:
        href = link.get_attribute('href')
        if href:
          full_url = (
              f'https://sutbongtve.cc{href}'
              if href.startswith('/')
              else href
          )
          unique_urls.add(full_url)

      print(f'Tìm thấy {len(unique_urls)} trận đấu đang phát trực tiếp.')

      # Nếu không quét được link trực tiếp, quét toàn bộ card giao diện
      if not unique_urls:
        cards = page.locator('div[class*="match"], div[class*="game"]').all()
        for card in cards:
          try:
            txt = card.inner_text()
            if 'vs' in txt.lower():
              link_el = card.locator('a').first
              if link_el.count() > 0:
                h = link_el.get_attribute('href')
                if h:
                  unique_urls.add(
                      f'https://sutbongtve.cc{h}'
                      if h.startswith('/')
                      else h
                  )
          except Exception:
            continue

      # Duyệt qua từng trang chi tiết trận đấu để bóc tách thông tin chuẩn xác
      for match_url in list(unique_urls)[:20]:
        try:
          print(f'Đang phân tích trận: {match_url}')
          detail_page = context.new_page()
          detail_page.goto(
              match_url, wait_until='domcontentloaded', timeout=15000
          )
          detail_page.wait_for_timeout(4000)

          # Lấy tiêu đề trang (thường chứa tên 2 đội, ví dụ: "Deportivo Pasto vs Alianza...")
          title_text = detail_page.title()
          home, away = 'Đội Nhà', 'Đội Khách'

          if 'vs' in title_text.lower():
            parts = re.split(r'\s+vs\s+|-', title_text, flags=re.IGNORECASE)
            if len(parts) >= 2:
              home = clean_text(parts[0])
              away = clean_text(parts[1])

          # Lấy logo đội bóng từ trang chi tiết
          img_el = detail_page.locator('img').first
          logo = (
              img_el.get_attribute('src')
              if img_el.count() > 0
              else 'https://sutbongtve.cc/wp-content/uploads/2026/08/logo-subongtv-vin.png'
          )
          if logo and logo.startswith('/'):
            logo = f'https://sutbongtve.cc{logo}'

          # Lấy danh sách tên các BLV (THOMAS, ZIDANE, BLV TAP, MESSI...)
          blv_elements = detail_page.locator(
              'button, div[class*="blv"], div[class*="tab"], span[class*="name"]'
          ).all()
          blv_names = []

          for el in blv_elements:
            t = clean_text(el.inner_text())
            if (
                t
                and len(t) < 25
                and (
                    'blv' in t.lower()
                    or t.isupper()
                    or t
                    in [
                        'THOMAS',
                        'ZIDANE',
                        'TAP',
                        'RICKHANTER',
                        'ROSI',
                        'KAN',
                        'ALEX',
                        'COCA',
                        'HUCK',
                        'PEANUT',
                        'CUỘI',
                        'VIP',
                        'HEHE',
                        'CÒ',
                        'RYO',
                        'LOGAN',
                        'MESSI',
                        'ĐỐM',
                        'TOMIA',
                        'YONE',
                        'XO',
                    ]
                )
            ):
              if (
                  t
                  not in [
                      'CHAT',
                      'THỐNG KÊ',
                      'ĐỘI HÌNH',
                      'DIỄN BIẾN',
                      'BẢNG XẾP HẠNG',
                  ]
                  and t not in blv_names
              ):
                blv_names.append(t)

          if not blv_names:
            blv_names = ['BLV Sút Bóng']

          now_vn = datetime.now(TZ_VN)
          time_str = now_vn.strftime('%H:%M')
          date_str = now_vn.strftime('%d/%m')

          # Lấy link stream m3u8 thực tế nếu bắt được, nếu không dùng match_url
          stream_link = captured_streams.get('active_m3u8', match_url)

          for blv in blv_names:
            channels_data.append({
                'home': home,
                'away': away,
                'time': time_str,
                'date': date_str,
                'blv': blv,
                'logo': logo,
                'url': stream_link,
            })

          detail_page.close()
        except Exception as e:
          print(f'Lỗi quét trang chi tiết {match_url}: {e}')

    except Exception as e:
      print(f'Lỗi tổng quan: {e}')
    finally:
      browser.close()

  return channels_data


def generate_m3u(channels):
  m3u_lines = ['#EXTM3U x-tvg-url=""']
  if not channels:
    print('Không thu thập được kênh nào.')
    return '\n'.join(m3u_lines)

  print(f'Đang tổng hợp {len(channels)} luồng phát...')
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
  print(f'Tổng số luồng phát hợp lệ: {len(data)}')
  content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(content)

  print('Đã ghi thành công file playlist.m3u!')
  
