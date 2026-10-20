from datetime import datetime
import re
from playwright.sync_api import sync_playwright
import pytz

TZ_VN = pytz.timezone('Asia/Ho_Chi_Minh')


def clean_text(text):
  if not text:
    return ''
  return re.sub(r'\s+', ' ', str(text)).strip()


def scrape_sutbong():
  matches_data = []
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

    try:
      print('Đang truy cập trang web sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='domcontentloaded', timeout=30000
      )
      # Chờ trang nạp hoàn tất các dữ liệu động
      page.wait_for_timeout(8000)

      # Tìm các khối phần tử chứa thông tin trận đấu trên trang
      match_cards = page.locator(
          'div.match-item, div.matches-item, div[class*="match"],'
          ' div[class*="game"], a[href*="truc-tiep"]'
      ).all()
      print(f'Tìm thấy {len(match_cards)} phần tử trên giao diện.')

      for card in match_cards:
        try:
          txt = card.inner_text()
          if 'vs' in txt.lower() or '-' in txt:
            lines = [clean_text(l) for l in txt.split('\n') if clean_text(l)]
            if len(lines) < 2:
              continue

            # Lấy đường dẫn link chi tiết trận đấu
            href = card.get_attribute('href')
            if not href:
              link_el = card.locator('a').first
              if link_el.count() > 0:
                href = link_el.get_attribute('href')

            stream_url = (
                f'https://sutbongtve.cc{href}'
                if href and href.startswith('/')
                else (
                    href
                    if href and href.startswith('http')
                    else 'https://sutbongtve.cc/'
                )
            )

            # Lấy logo đội bóng
            img_el = card.locator('img').first
            logo = img_el.get_attribute('src') if img_el.count() > 0 else ''
            if logo and logo.startswith('/'):
              logo = f'https://sutbongtve.cc{logo}'

            # Giờ và ngày thi đấu
            time_str = datetime.now(TZ_VN).strftime('%H:%M')
            date_str = datetime.now(TZ_VN).strftime('%d/%m')

            for line in lines:
              time_match = re.search(r'\d{2}:\d{2}', line)
              if time_match:
                time_str = time_match.group(0)

            # Phân tách tên 2 đội
            home, away = 'Đội Nhà', 'Đội Khách'
            for line in lines:
              if 'vs' in line.lower():
                parts = re.split(r'\s+vs\s+', line, flags=re.IGNORECASE)
                if len(parts) >= 2:
                  home = parts[0].strip()
                  away = parts[1].strip()
                break

            # Quét tên các BLV xuất hiện trong card trận đấu
            blv_list = []
            for line in lines:
              if 'blv' in line.lower() or any(
                  name in line.upper()
                  for name in [
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
                  ]
              ):
                blv_list.append(line)

            if not blv_list:
              blv_list = ['BLV Sút Bóng']

            for blv in blv_list:
              matches_data.append({
                  'home': home,
                  'away': away,
                  'time': time_str,
                  'date': date_str,
                  'logo': logo,
                  'blv': clean_text(blv),
                  'url': stream_url,
              })
        except Exception:
          continue

    except Exception as e:
      print(f'Lỗi cào dữ liệu: {e}')
    finally:
      browser.close()

  return matches_data


def generate_m3u(matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']
  if not matches:
    print('Không có trận đấu nào được tổng hợp.')
    return '\n'.join(m3u_lines)

  print(f'Đang ghi {len(matches)} luồng phát vào file...')
  seen = set()

  for m in matches:
    home = m['home']
    away = m['away']
    blv = m['blv']

    key = f'{home}-{away}-{blv}'
    if key in seen:
      continue
    seen.add(key)

    title = f"{m['time']} {m['date']} ⚽ {home} vs {away} ({blv}) [FHD]"
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{m["logo"]}" group-title="Sút Bóng TV",{title}'
    )
    m3u_lines.append(m['url'])

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  data = scrape_sutbong()
  print(f'Thu thập thành công {len(data)} mục.')
  content = generate_m3u(data)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(content)

  print('Đã ghi file playlist.m3u thành công!')
  
