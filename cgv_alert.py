import os
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
DB_FILE = "loaded_movies.txt"

def send_slack_message_with_image(new_movies_data):
    if not SLACK_WEBHOOK_URL:
        print("⚠️ 슬랙 웹훅 URL이 설정되지 않았습니다.")
        return

    items = list(new_movies_data.items())
    chunk_size = 20 
    
    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        blocks = []
        
        if i == 0:
            blocks.extend([
                {"type": "header", "text": {"type": "plain_text", "text": "🎬 [CGV 신규 예매 오픈 알림]", "emoji": True}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "지금 앱이나 웹에서 새로운 영화들의 예매가 오픈되었습니다! 🍿"}},
                {"type": "divider"}
            ])
            
        for title, img_url in chunk:
            movie_text = f"*{title}*"
            
            if img_url:
                # 💡 [수정 1] 이모지 대신 명확한 텍스트 문구를 넣어 모바일 슬랙의 주소 노출 버그를 해결합니다.
                movie_text += f"\n<{img_url}|🔍 크게 보기>"
                
            movie_section = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": movie_text}
            }
            
            if img_url:
                movie_section["accessory"] = {
                    "type": "image",
                    "image_url": img_url,
                    "alt_text": f"{title} 포스터"
                }
                
            blocks.append(movie_section)
            blocks.append({"type": "divider"})

        # 메시지의 제일 마지막 묶음을 전송할 때 맨 밑에 통합 예매 링크 추가
        if i + chunk_size >= len(items):
            # 💡 [수정 2] cgvapp:// 대신 https:// 주소를 사용하여 슬랙 차단 에러를 해결합니다.
            # 이 주소는 스마트폰에 CGV 앱이 있으면 자동으로 앱을 열어줍니다.
            cgv_app_link = "https://m.cgv.co.kr"
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"▶️ *<{cgv_app_link}|CGV 앱 켜서 바로 예매하기>* 🎫"}
            })

        payload = {
            "blocks": blocks,
            "unfurl_links": False,  
            "unfurl_media": False   
        }
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        
        if response.status_code != 200:
            print(f"슬랙 전송 실패: {response.text}")
        else:
            print(f"슬랙 메시지 전송 성공! ({i+1}~{min(i+len(chunk), len(items))}번째 영화)")
            
        time.sleep(1.5)

def click_visible_element(driver, xpath, step_name):
    print(f"🔍 '{step_name}' 클릭 시도 중...")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    elements = driver.find_elements(By.XPATH, xpath)
    
    for elem in elements:
        if elem.is_displayed():
            driver.execute_script("arguments[0].click();", elem)
            print(f"  ✅ '{step_name}' 클릭 완료")
            return True
    raise Exception(f"화면에서 '{step_name}' 요소를 찾을 수 없습니다.")

def get_current_movies():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # 💡 깃허브 액션 환경 필수 옵션 (활성화 됨)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    prefs = {
        'profile.default_content_setting_values.geolocation': 2,
        'profile.default_content_setting_values.notifications': 2,
        'profile.managed_default_content_settings.images': 1
    }
    options.add_experimental_option('prefs', prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    current_movies = {}
    
    try:
        url = "https://cgv.co.kr/cnm/movieBook"
        print(f"[{time.strftime('%H:%M:%S')}] CGV 예매 다이렉트 페이지 접속 중...")
        driver.get(url)
        time.sleep(3)

        try:
            driver.switch_to.alert.dismiss()
        except:
            pass

        click_visible_element(driver, "//*[contains(text(), '극장을 선택해 주세요')]", "극장을 선택해 주세요")
        time.sleep(1.5)
        click_visible_element(driver, "//*[normalize-space(text())='경기'] | //*[contains(text(), '경기')]", "경기 지역")
        time.sleep(1.5)
        click_visible_element(driver, "//*[normalize-space(text())='오리'] | //*[contains(text(), '오리')]", "오리 극장")
        time.sleep(4) 

        print("\n📅 브라우저 내부에서 전체 활성 날짜 스캔 중...")
        valid_date_texts = driver.execute_script("""
            let results = [];
            let dates = document.querySelectorAll('button[class*="dayScroll_scrollItem"]');
            for(let el of dates) {
                if(!el.textContent) continue;
                let txt = el.textContent.replace(/\\n/g, ' ').trim();
                if(/^(오늘|내일|월|화|수|목|금|토|일)\\s*\\d+$/.test(txt)) {
                    if(!results.includes(txt)) {
                        results.push(txt);
                    }
                }
            }
            return results;
        """)
        
        print(f"✅ 총 {len(valid_date_texts)}일의 스케줄 탭을 발견했습니다.")

        for date_text in valid_date_texts:
            print(f"\n▶️ [{date_text}] 스케줄 선택 및 파싱...")
            
            driver.execute_script(f"""
                let dates = document.querySelectorAll('button[class*="dayScroll_scrollItem"]');
                for(let el of dates) {{
                    if(!el.textContent) continue;
                    let txt = el.textContent.replace(/\\n/g, ' ').trim();
                    if(txt === '{date_text}') {{
                        el.click();
                        break;
                    }}
                }}
            """)
            time.sleep(2.5) 
            
            # JS 주입으로 제목과 고화질 포스터 동시 수집
            movies_on_this_date = driver.execute_script("""
                let results = [];
                let accordions = document.querySelectorAll('[class*="accordion_container"]');
                
                accordions.forEach(acc => {
                    let titleEl = acc.querySelector('.title2, [class*="screenInfo_title"]');
                    if (!titleEl) return;
                    let title = titleEl.textContent.trim();
                    title = title.replace(/(12|15|18|청불|ALL|전체|관람가)+$/g, '').trim();

                    let imgEl = acc.querySelector('img[class*="screenInfo_poster"]');
                    let imgUrl = imgEl ? imgEl.src : "";
                    
                    // 고화질 원본 포스터로 치환
                    if (imgUrl) {
                        imgUrl = imgUrl.replace(/_\\d+\\.jpg/i, '_1000.jpg');
                    }

                    let seatSpans = acc.querySelectorAll('[class*="screenInfo_status"]');
                    let hasSeats = false;
                    
                    seatSpans.forEach(span => {
                        let txt = span.textContent.replace(/\\s+/g, ''); 
                        let match = txt.match(/(\\d+)\\//); 
                        if (!match) match = txt.match(/(\\d+)석/);
                        
                        if (match && parseInt(match[1]) > 0) {
                            hasSeats = true;
                        }
                    });

                    if (hasSeats) {
                        let isDuplicate = results.some(item => item.title === title);
                        if (!isDuplicate) {
                            results.push({ title: title, img_url: imgUrl });
                        }
                    }
                });
                return results;
            """)
            
            if movies_on_this_date:
                for item in movies_on_this_date:
                    movie_title = item['title']
                    movie_img = item['img_url']
                    
                    if movie_title not in current_movies:
                        current_movies[movie_title] = movie_img
                        print(f"    🍿 [예매가능] {movie_title}")

    except Exception as e:
        print(f"❌ 크롤링 도중 예외 발생: {e}")
    finally:
        driver.quit()
        print("\n🔒 크롬 브라우저를 종료했습니다.")
        
    return current_movies

def main():
    current_dict = get_current_movies()
    if not current_dict:
        print("❌ 수집된 영화가 없습니다. 스크립트를 종료합니다.")
        return

    past_set = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            past_set = set(line.strip() for line in f if line.strip())

    current_titles = set(current_dict.keys())
    
    # 💡 [핵심] 기존에 저장된 영화 목록(past_set)과 방금 긁어온 목록(current_titles)을 비교하여, 
    # 오직 '새로 추가된 영화(new_movie_titles)'만 골라냅니다.
    new_movie_titles = current_titles - past_set

    if new_movie_titles:
        new_movies_data = {title: current_dict[title] for title in new_movie_titles}
        print(f"🎉 새로운 영화 {len(new_movies_data)}건 발견! 슬랙으로 전송합니다.")
        send_slack_message_with_image(new_movies_data)
    else:
        print("✅ 새로 추가된 예매 가능 영화가 없습니다.")

    # 차후 비교를 위해 영화 '제목'만 파일에 저장해 둡니다.
    with open(DB_FILE, "w", encoding="utf-8") as f:
        for title in sorted(current_titles):
            f.write(f"{title}\n")

if __name__ == "__main__":
    main()
