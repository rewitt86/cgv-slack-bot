import os
import time
import requests
from selenium import webdriver
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
    # 썸네일 방식이므로 한 번에 20개씩 보내도 안전합니다.
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
            # 1. 영화 제목 세팅
            movie_text = f"*{title}*"
            
            # 2. 이미지 URL이 있다면 제목 밑에 [크게 보기] 링크를 달아줍니다.
            if img_url:
                movie_text += f"\n<{(img_url)}|🔍 포스터 크게 보기>"
                
            movie_section = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": movie_text}
            }
            
            # 3. 우측 썸네일(Accessory) 디자인 유지
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
            # CGV 앱 호출용 딥링크 체계 (아이폰, 안드로이드 공용)
            # 만약 앱이 설치되어 있지 않다면 모바일 웹페이지로 자동 이동합니다.
            cgv_app_link = "cgvapp://m.cgv.co.kr"
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"▶️ *<{cgv_app_link}|CGV 앱 켜서 바로 예매하기>* 🎫"}
            })

        payload = {"blocks": blocks}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        
        if response.status_code != 200:
            print(f"슬랙 전송 실패: {response.text}")
        else:
            print(f"슬랙 메시지 전송 성공! ({i+1}~{min(i+len(chunk), len(items))}번째 영화)")
            
        time.sleep(1.5)

def get_current_movies():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    # 💡 [핵심 추가] 깃허브 서버의 가상 모니터 크기를 FHD로 강제 설정하여 모든 요소가 보이게 함
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    current_movies = {}
    
    try:
        url = "https://cgv.co.kr/cnm/cgvChart/movieChart?tabParam=123"
        print(f"[{time.strftime('%H:%M:%S')}] CGV 페이지 접속 중...")
        driver.get(url)
        
        # 💡 [핵심 추가] 깃허브 서버의 느린 속도를 감안하여 대기 시간을 20초로 증가
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul, li, [class*='chart']"))
        )
        print(f"[{time.strftime('%H:%M:%S')}] 기본 구조 로드 완료, 추가 데이터를 위해 스크롤을 진행합니다.")
        
        # 💡 [핵심 추가] 화면을 중간, 그리고 끝까지 2번 스크롤하여 지연된 이미지와 데이터를 강제 호출
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        movie_cards = driver.find_elements(By.CSS_SELECTOR, "li, [class*='item'], [class*='box']")
        print(f"[{time.strftime('%H:%M:%S')}] 총 {len(movie_cards)}개의 카드를 분석합니다.")
        
        for card in movie_cards:
            if "예매" in card.text:
                title_selectors = [".movie-name", ".txt-title", ".title", "strong", "h3"]
                title = ""
                
                for selector in title_selectors:
                    elements = card.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        temp_title = elements[0].text.strip()
                        if temp_title and not any(word in temp_title for word in ["현재", "순위", "차트", "예매율", "개봉", "상영"]):
                            title = temp_title
                            break
                
                if title:
                    img_url = ""
                    try:
                        img_elem = card.find_element(By.CSS_SELECTOR, "img")
                        img_url = img_elem.get_attribute("src")
                    except:
                        pass
                        
                    current_movies[title] = img_url

    except Exception as e:
        print(f"크롤링 에러: {e}")
    finally:
        driver.quit()
        
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
    new_movie_titles = current_titles - past_set

    if new_movie_titles:
        new_movies_data = {title: current_dict[title] for title in new_movie_titles}
        print(f"🎉 새로운 영화 {len(new_movies_data)}건 발견! 슬랙으로 전송합니다.")
        send_slack_message_with_image(new_movies_data)
    else:
        print("✅ 새로 추가된 영화가 없습니다.")

    with open(DB_FILE, "w", encoding="utf-8") as f:
        for title in sorted(current_titles):
            f.write(f"{title}\n")

if __name__ == "__main__":
    main()
