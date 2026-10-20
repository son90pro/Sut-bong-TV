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
  """Chuyển timestamp/thời gian sang định dạng giờ VN."""
  try:
    if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
      ts_val = float(ts)
      if ts_val > 1e11:  # milliseconds
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
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()

    # Chặn các request API để bắt dữ liệu trận đấu gốc từ Server
    def handle_response(response):
      try:
        url = response.url.lower()
        if (
            'api' in url
            or 'match' in url
            or 'list' in url
            or 'schedule' in url
            or 'json' in url
        ):
          if (
              response.status == 200
              and 'json' in response.headers.get('content-type', '').lower()
          ):
            res_json = response.json()
            # Bóc tách danh sách trận đấu từ response API
            data_arr = None
            if isinstance(res_json, list):
              data_arr = res_json
            elif isinstance(res_json, dict):
              data_arr = (
                  res_json.get('data')
                  or res_json.get('matches')
                  or res_json.get('list')
                  or res_json.get('rows')
              )

            if isinstance(data_arr, list) and len(data_arr) > 0:
              for item in data_arr:
                if isinstance(item, dict) and (
                    'home' in item
                    or 'home_name' in item
                    or 'home_team' in item
                    or 'title' in item
                ):
                  matches_list.append(item)
      except Exception:
        pass

    page.on('response', handle_response)

    try:
      print('Đang mở trang sutbongtve.cc...')
      page.goto(
          'https://sutbongtve.cc/', wait_until='networkidle', timeout=30000
      )
      page.wait_for_timeout(6000)  # Chờ JS render xong

      # Nếu chưa bắt được qua API Response, cào dữ liệu nhúng trong thẻ script
      if not matches_list:
        content = page.content()
        # Tìm JSON state nhúng trong trang
        script_matches = re.findall(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});', content, re.DOTALL
        )
        if script_matches:
          st_json = json.loads(script_matches[0])
          found_list = st_json.get('matches') or st_json.get('list') or []
          if isinstance(found_list, list):
            matches_list.extend(found_list)

    except Exception as e:
      print(f'Lỗi khi truy cập trang web: {e}')
    finally:
      browser.close()

  return matches_list


def generate_m3u(raw_matches):
  m3u_lines = ['#EXTM3U x-tvg-url=""']

  if not raw_matches:
    print('CẢNH BÁO: Không lấy được danh sách trận đấu thực tế!')
    return '\n'.join(m3u_lines)

  print(f'Bắt đầu xử lý {len(raw_matches)} trận đấu...')

  for item in raw_matches:
    try:
      # 1. Tên 2 đội bóng
      home = (
          item.get('home_name')
          or item.get('home_team')
          or (
              item.get('home', {}).get('name')
              if isinstance(item.get('home'), dict)
              else item.get('home')
          )
          or 'Đội Nhà'
      )
      away = (
          item.get('away_name')
          or item.get('away_team')
          or (
              item.get('away', {}).get('name')
              if isinstance(item.get('away'), dict)
              else item.get('away')
          )
          or 'Đội Khách'
      )

      # 2. Logo đội bóng (ưu tiên logo đội nhà)
      logo = (
          item.get('home_logo')
          or (
              item.get('home', {}).get('logo')
              if isinstance(item.get('home'), dict)
              else ''
          )
          or item.get('logo')
          or item.get('poster')
          or ''
      )

      # 3. Giờ và ngày thi đấu (Múi giờ VN)
      match_time_raw = (
          item.get('match_time')
          or item.get('start_time')
          or item.get('time')
          or item.get('time_start')
      )
      time_str, date_str = parse_timestamp(match_time_raw)

      # 4. Icon môn thể thao
      sport_type = item.get('sport_type') or item.get('sport') or 'football'
      sport_icon = get_sport_icon(sport_type)

      # 5. Tên nhóm/Tab (Sút Bóng TV / Gà Vàng 33 TV)
      group_title = (
          item.get('channel_name')
          or item.get('tournament_name')
          or item.get('league_name')
          or 'Sút Bóng TV'
      )

      # 6. Luồng phát & Bình luận viên
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
            or item.get('url')
            or 'https://sutbongtve.cc'
        )
        blv = item.get('commentator') or item.get('blv') or 'BLV'
        quality = item.get('quality') or 'FHD'
        links = [{'url': stream_url, 'blv': blv, 'quality': quality}]

      for idx, link in enumerate(links, 1):
        if isinstance(link, dict):
          s_url = (
              link.get('url')
              or link.get('play_url')
              or link.get('m3u8')
              or link.get('flv')
          )
          s_blv = (
              link.get('blv')
              or link.get('commentator')
              or item.get('commentator')
              or 'BLV'
          )
          s_quality = (
              link.get('quality')
              or link.get('name')
              or (f'HD{idx}' if idx > 1 else 'FHD')
          )
        else:
          s_url = str(link)
          s_blv = item.get('commentator') or 'BLV'
          s_quality = f'HD{idx}' if idx > 1 else 'FHD'

        if not s_url or not s_url.startswith('http'):
          continue

        # Định dạng dòng tiêu đề chuẩn hình mẫu:
        # 06:00 20/10 ⚽ Corinthians - SP vs Vitória - BA (Gà Siêu Nhí) [hls]
        title_display = f'{time_str} {date_str} {sport_icon} {home} vs {away} ({s_blv}) [{s_quality}]'

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}"'
            f' group-title="{group_title}",{title_display}'
        )
        m3u_lines.append(s_url)

    except Exception as e:
      print(f'Lỗi dòng trận đấu: {e}')

  return '\n'.join(m3u_lines)


if __name__ == '__main__':
  matches = fetch_data_from_sutbongtv()
  print(f'Thu thập thành công {len(matches)} trận đấu thật!')

  m3u_content = generate_m3u(matches)

  with open('playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(m3u_content)

  print('Đã ghi dữ liệu chuẩn vào playlist.m3u!')
  
