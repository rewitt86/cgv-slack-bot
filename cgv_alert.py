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
    """슬랙 '블록 키트'를 사용하여 이미지와 텍스트를 함께 전송"""
    if not SLACK_WEBHOOK_URL:
        print("⚠️ 슬랙 웹훅 URL이 설정되지 않았습니다.")
        return

    # 슬랙 메시지의 헤더 부분 조립
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🎬 [CGV 신규 예매 오픈 알림]",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "지금 앱이나 웹에서 아래 영화의 예매가 가능합니다! 🍿"
            }
        },
        {"type": "divider"}
    ]

    # 새로 추가된 영화들을 반복하며 슬랙 블록에 추가
    for title, img_url in new_movies_data.items():
        movie_section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*\n<https://www.cgv.co.kr|👉 예매하러 가기>"
            }
        }
        
        # 포스터 이미지 주소가 존재하면 블록 우측에 이미지 부착 (accessory)
        if img_url:
            movie_section["accessory"] = {
                "type": "image",
                "image_url": img_url,
                "alt_text": f"{title} 포스터"
            }
            
        blocks.append(movie_section)
        blocks.append({"type": "divider"})

    # 조립된 블록 페이로드 전송
    payload = {"blocks": blocks}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    
    if response.status_code != 200:
        print(f"슬랙 전송 실패: {response.text}")

def get_current_movies():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument('--window-size=1920,1080') # 가상 브라우저 화면 크기 키우기
    options.add_argument('--start-maximized')

    driver = webdriver.Chrome(options=options)
    
    # 기존에는 집합(set)을 썼지만, 이번엔 제목과 이미지를 같이 저장하기 위해 딕셔너리(dict) 사용
    current_movies = {}
    
    try:
        url = "https://cgv.co.kr/cnm/cgvChart/movieChart?tabParam=123"
        driver.get(url)
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul, li, [class*='chart']"))
        )
        time.sleep(3)
        
        movie_cards = driver.find_elements(By.CSS_SELECTOR, "li, [class*='item'], [class*='box']")
        for card in movie_cards:
            if "예매" in card.text:
                title_selectors = [".movie-name", ".txt-title", ".title", "strong", "h3"]
                title = ""
                
                # 1. 제목 찾기
                for selector in title_selectors:
                    elements = card.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        temp_title = elements[0].text.strip()
                        if temp_title and not any(word in temp_title for word in ["현재", "순위", "차트", "예매율", "개봉", "상영"]):
                            title = temp_title
                            break
                
                # 2. 제목이 찾아졌다면 이미지 URL 찾기
                if title:
                    img_url = ""
                    try:
                        img_elem = card.find_element(By.CSS_SELECTOR, "img")
                        img_url = img_elem.get_attribute("src")
                    except:
                        pass # 이미지가 없으면 빈 문자열 처리
                        
                    current_movies[title] = img_url

    except Exception as e:
        print(f"크롤링 에러: {e}")
    finally:
        driver.quit()
        
    return current_movies

def main():
    current_dict = get_current_movies()
    if not current_dict:
        print("❌ 수집된 영화가 없습니다.")
        return

    past_set = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            past_set = set(line.strip() for line in f if line.strip())

    # 어제 목록과 비교해서 새로 추가된 '영화 제목'들만 필터링
    current_titles = set(current_dict.keys())
    new_movie_titles = current_titles - past_set

    if new_movie_titles:
        # 새로 추가된 영화들의 {제목: 이미지URL} 데이터만 뽑아냄
        new_movies_data = {title: current_dict[title] for title in new_movie_titles}
        
        print(f"새로운 영화 {len(new_movies_data)}건 발견! 슬랙으로 전송합니다.")
        send_slack_message_with_image(new_movies_data)
    else:
        print("새로 추가된 영화가 없습니다.")

    # 오늘 보았던 영화 제목들을 파일에 기록 (내일 비교용)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        for title in sorted(current_titles):
            f.write(f"{title}\n")

if __name__ == "__main__":
    main()
