import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 깃허브 비밀번호(Secrets)에서 슬랙 주소를 안전하게 가져옵니다.
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
DB_FILE = "loaded_movies.txt"

def send_slack_message(text):
    if not SLACK_WEBHOOK_URL:
        print("⚠️ 슬랙 웹훅 URL이 설정되지 않았습니다.")
        return
    payload = {"text": text}
    requests.post(SLACK_WEBHOOK_URL, json=payload)

def get_current_movies():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 깃허브 서버에는 화면이 없으므로 필수
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    current_movies = set()
    
    try:
        url = "https://cgv.co.kr/cnm/cgvChart/movieChart?tabParam=123"
        driver.get(url)
        
        # 영화 데이터 로드 대기
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul, li, [class*='chart']"))
        )
        time.sleep(3)
        
        movie_cards = driver.find_elements(By.CSS_SELECTOR, "li, [class*='item'], [class*='box']")
        for card in movie_cards:
            if "예매" in card.text:
                title_selectors = [".movie-name", ".txt-title", ".title", "strong", "h3"]
                for selector in title_selectors:
                    elements = card.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        temp_title = elements[0].text.strip()
                        if temp_title and not any(word in temp_title for word in ["현재", "순위", "차트", "예매율", "개봉", "상영"]):
                            current_movies.add(temp_title)
                            break
    except Exception as e:
        print(f"크롤링 에러: {e}")
    finally:
        driver.quit()
        
    return current_movies

def main():
    current_set = get_current_movies()
    if not current_set:
        print("❌ 수집된 영화가 없습니다.")
        return

    past_set = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            past_set = set(line.strip() for line in f if line.strip())

    # 어제 목록과 비교해서 새로 추가된 영화 찾기
    new_movies = current_set - past_set

    if new_movies:
        message = "🎬 *[CGV 신규 예매 오픈 알림]*\n\n"
        for movie in sorted(new_movies):
            message += f"• *{movie}*\n"
        message += "\n지금 CGV 앱이나 웹에서 예매하세요! 🍿"
        send_slack_message(message)
        print("새로운 영화 슬랙 전송 완료!")
    else:
        print("새로 추가된 영화가 없습니다.")

    # 오늘 보았던 영화들을 파일에 기록 (내일 비교용)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        for movie in sorted(current_set):
            f.write(f"{movie}\n")

if __name__ == "__main__":
    main()