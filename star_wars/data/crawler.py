import os
import re
import requests
import time
from bs4 import BeautifulSoup
import cloudscraper

BASE_URL = "https://starwars.fandom.com/ru/wiki/" # Base fandom wiki URL
TARGET_DIR = "data" # Download directory
MIN_TEXT_LENGTH = 40 # To exclude redundant headers
MAX_TEXT_LENGTH = 1000 # To exclude large technical paragraphs or auto generated data
SECONDS_SLEEP = 2

# Create original data directory
os.makedirs(TARGET_DIR, exist_ok=True)


# Fandom wiki page names
pages = [
    "Палпатин",
    "Дарт_Плэгас",
    "Энакин_Скайуокер",
    "Лея_Органа-Соло",
    "Хан_Соло",
    "Бен_Соло",
    "Рей_Скайуокер",
    "Сноук",
    "Эзра_Бриджер",
    "Сабин_Врен",
    "Дин_Джарин",
    "Бо-Катан_Крайз",
    "Дарт_Нихилус",
    "Дарт_Плэгас",
    "Гера_Синдулла",
    "Гранд-инквизитор",
    "Экзегол",
    "Асока_Тано",
    "Мейс_Винду",
    "Квай-Гон_Джинн",
    "Пло_Кун",
    "Дуку",
    "Гривус",
    "Сайфо-Диас",
    "Люк_Скайуокер",
    "Дарт_Мол",
    "Падме_Амидала",
    "Дарт_Тенебрус",
    "Йода",
    "Ки-Ади-Мунди",
    "Эйла_Секура",
    "Оби-Ван_Кеноби"
]


# Remove redundant spaces, links and citations
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)  # remove redundant spaces
    text = re.sub(r'\[\d+\]', '', text) # remove links
    text = re.sub(r'\[источник\?\]', '', text, flags=re.IGNORECASE)  # ← русская «[источник?]»
    text = re.sub(r'\[citation needed\]', '', text, flags=re.IGNORECASE) # remove citations
    text = re.sub(r'(Править|Edit)\s+', ' ', text)  # remove specific Wiki marks
    return text.strip()


# Extract only article text
def extract_main_content(soup):
    content_div = soup.find('div', class_='mw-parser-output')
    if not content_div:
        return ""

    # Remove all redundant content
    for elem in content_div.find_all(['table', 'div', 'aside', 'nav', 'ul', 'dl']):
        if len(elem.contents) == 0:
            continue

        classes = elem.get('class', [])
        if not classes:
            continue

        if any(c in classes for c in [
            'toc', 'sidebar', 'infobox', 'navbox', 'gallery',
            'mw-references-wrap', 'printfooter', 'catlinks', 'hatnote'
        ]):
            elem.decompose()

    # Remove all links
    for a in content_div.find_all('a'):
        a.unwrap()

    # Prepare final text
    paragraphs = []
    for p in content_div.find_all('p'):
        for br in p.find_all('br'):
            br.replace_with(' ')
        txt = clean_text(p.get_text())
        if MIN_TEXT_LENGTH <= len(txt) <= MAX_TEXT_LENGTH:
            paragraphs.append(txt)

    return '\n\n'.join(paragraphs)


# Download pages:
for page in pages:
    url = BASE_URL + page
    filename = re.sub(r'[<>:"/\\|?*]', '_', page) + ".txt"  # безопасное имя файла
    filepath = os.path.join(TARGET_DIR, filename)

    print(f"Downloading {page} to {filename}")

    try:

        scraper = cloudscraper.create_scraper(
                    browser={
                        "browser": "chrome",
                        "platform": "windows",
                    },)

        response = scraper.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Page title
        title_tag = soup.find('h1')
        title = clean_text(title_tag.get_text()) if title_tag else page.replace('_', ' ')

        # Main text
        main_text = extract_main_content(soup)
        if not main_text:
            main_text = clean_text(soup.get_text())

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Source: {url}\n# Title: {title}\n\n{main_text}")

        print(f"OK: {len(main_text)} characters saved")

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(SECONDS_SLEEP) # to not torture wiki

print("\ndone\n")
