import json
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
from playwright.sync_api import Error
from pymongo import MongoClient
import re
import schedule
import time

with open('./config.json', 'r') as f:
    config = json.load(f)

uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, w=1)
db = mongo_client['NLP-Cross-Cutting-Exposure']

visited_articles = set()
visited_users = set()


# Get article data for whole page
def get_article_data(page):
    page.set_default_timeout(5000)
    json_selector = 'script[type="application/ld+json"]'
    json_content = page.inner_text(json_selector)
    data = json.loads(json_content)

    wafer_json_content = page.inner_text('.wafer-caas-data[type="application/json"]')
    data_wafer = json.loads(wafer_json_content)

    og_url = page.evaluate('(document.querySelector("meta[property=\'og:url\']") || {}).content')
    news_keywords = page.evaluate('(document.querySelector("meta[name=\'news_keywords\']") || {}).content')
    og_title = page.evaluate('(document.querySelector("meta[property=\'og:title\']") || {}).content')
    og_description = page.evaluate('(document.querySelector("meta[property=\'og:description\']") || {}).content')
    og_image = page.evaluate('(document.querySelector("meta[property=\'og:image\']") || {}).content')
    body = page.inner_text('.caas-body')
    min_read = page.inner_text('.caas-attr-mins-read')
    date_published = data.get("datePublished")
    date_modified = data.get("dateModified")
    authors = data.get('author')
    num_comments = data_wafer.get('commentsCount')

    news_outlet_link = data.get('provider').get('url')
    news_outlet_name = data.get('provider').get('name')

    return {
        "url": og_url,
        "keywords": news_keywords,
        "title": og_title,
        "description": og_description,
        "image_url": og_image,
        "body": body,
        "min_read": min_read,
        "date_published": date_published,
        "date_modified": date_modified,
        "authors": authors,
        "num_comments": num_comments,
        "outlet_link": news_outlet_link,
        "outlet_name": news_outlet_name
    }


# Get General User Info
def get_general_user_info(iframe_locator):
    # Get user info
    nickname_locator = 'div[class*="src-components-TopMenu-TopMenu__username"]'
    username_locator = 'bdi'
    post_num_locator = 'div[class*="src-components-Navbar-Navbar__Label"]'
    likes_rec_locator = 'div[class*="src-components-DetailText-DetailText__DetailText"][data-testid="text"]'
    likes_rec = iframe_locator.locator(likes_rec_locator)
    likes_rec.wait_for(state="attached")
    likes_rec = likes_rec.first.text_content().split()[0]

    username = iframe_locator.locator(username_locator)
    username.wait_for(state="attached")
    username = username.first.text_content()
    nickname = iframe_locator.locator(nickname_locator)
    nickname.wait_for(state="attached")
    nickname = nickname.first.text_content()
    post_num_string = iframe_locator.locator(post_num_locator)
    post_num_string.wait_for(state="attached")
    post_num_string = post_num_string.first.inner_text()
    match = re.search(r'\((.*?)\)', post_num_string)
    post_num = ""
    if match:
        post_num = match.group(1)
    else:
        post_num = post_num_string
    return likes_rec, username, nickname, post_num


# Scroll down to load more comments
def generate_more_comments(iframe_locator, _page):
    generated_enough = False
    last_comment_section_number = 0
    i = 0
    while not generated_enough:
        comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
        type_comment_locator = 'a[class*="src-components-FeedItem-styles__MessageLink"]'

        comment_section_elements = iframe_locator.locator(comment_section_locator).element_handles()
        last_comment_section = comment_section_elements[comment_section_elements.__len__() - 1]
        type_comment_elements = last_comment_section.query_selector_all(type_comment_locator)
        _type = type_comment_elements[type_comment_elements.__len__() - 1].inner_text()

        time_posted = ""
        if _type.startswith("Posted"):
            time_posted = _type.split("d", 1)[1].strip()
        if _type.startswith("Replied to"):
            x = _type.split(" ")
            res = x[1].replace('\xa0', ' ')
            time_posted = f'{res.split("o", 1)[1]} {x[2]} {x[3]}'.strip()

        if "2y ago" in time_posted:
            generated_enough = True
        elif comment_section_elements.__len__() == last_comment_section_number:
            generated_enough = True
        else:
            i += 1
            last_comment_section_number = comment_section_elements.__len__()
            for comment_section in comment_section_elements:
                comment_section.dispose()
            _page.mouse.wheel(0, 50000)
            time.sleep(1)

    _page.mouse.wheel(50000 * i, 0)


# Get Comment Section data with source article and comments
def parse_comment_sections(iframe_locator, context, _page):
    try:
        generate_more_comments(iframe_locator, _page)
    except Exception as e:
        print(e)

    comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
    comment_section_elements = iframe_locator.locator(comment_section_locator).element_handles()
    comments_section = []
    for comment_section in comment_section_elements:
        source_article_locator = 'a[class*="src-components-FeedItem-styles__ExtractWrapper"]'
        type_comment_locator = 'a[class*="src-components-FeedItem-styles__MessageLink"]'
        comment_text_locator = 'div[class*="src-components-FeedItem-styles__TextWrapper"]'

        # Get source article data
        source_article = comment_section.query_selector(source_article_locator).get_attribute('href')

        if "news.yahoo.com" not in source_article:
            comment_section.dispose()
            continue
        source_article_page = context.new_page()
        try:
            source_article_page.goto(source_article, timeout=3000, wait_until="domcontentloaded")
            source_article_data = get_article_data(source_article_page)
            source_article_page.close()
        except Exception as e:
            print(e)
            print("error in parsing comments section")
            comment_section.dispose()
            source_article_page.close()
            continue

        # Parse each comment and type
        comments = []
        type_comment_elements = comment_section.query_selector_all(type_comment_locator)
        comment_text_elements = comment_section.query_selector_all(comment_text_locator)
        comment_section.dispose()
        if type_comment_elements.__len__() == comment_text_elements.__len__():
            for index in range(type_comment_elements.__len__()):
                _type = type_comment_elements[index].inner_text()
                comment_text = comment_text_elements[index].inner_text()
                time_posted = ""
                if _type.startswith("Posted"):
                    time_posted = _type.split("d", 1)[1].strip()
                    _type = "Posted"
                if _type.startswith("Replied to"):
                    x = _type.split(" ")
                    res = x[1].replace('\xa0', ' ')
                    time_posted = f'{res.split("o", 1)[1]} {x[2]} {x[3]}'.strip()
                    _, rest_of_string = _type.split("o", 1)
                    _type = f"Replied to {rest_of_string}".split()
                    _type = " ".join(_type[:3])

                print(time_posted)
                print(_type)
                comments.append({"comment_text": comment_text, "type": _type, "last_posted": time_posted})

            comments_section.append({'source_article': source_article_data, "comments": comments})

    return comments_section


def close_user_profile(_iframe_locator, _page):
    try:
        close_profile_button = _iframe_locator.locator('button[title="Close the modal"]').element_handle()
        close_profile_button.click()
        close_profile_button.dispose()
    except Exception as e:
        print("failed to close profile")


# Parse Users
def parse_users(iframe_locator, context, _page):
    users_objs = []
    profile_locator = 'button[data-spot-im-class="user-info-username"]'
    profile_buttons = iframe_locator.locator(profile_locator).element_handles()
    for profile_button in profile_buttons:
        profile_button.wait_for_element_state("stable")
        profile_button.click()
        profile_button.dispose()

        # Get General User Info
        user = dict()

        try:
            user['likes'], user['username'], user['nickname'], user['post_num'] = get_general_user_info(iframe_locator)
        except Error as e:
            print("problem retrieving user data")
            close_user_profile(iframe_locator, _page)
            continue

        if user['username'] not in visited_users:

            # Load Read More Comments
            read_more_locator = 'a[class*="src-components-FeedItem-styles__ShowMoreButton"]'
            try:
                read_more_buttons = iframe_locator.locator(read_more_locator).element_handles()
                while read_more_buttons:
                    for read_more in read_more_buttons:
                        read_more.wait_for_element_state("stable")
                        read_more.click()
                        read_more.dispose()
                    read_more_buttons = iframe_locator.locator(read_more_locator).element_handles()
            except Error as e:
                print("Read more not found")

            # Parse comments under a single source article
            try:
                user['comments_section'] = parse_comment_sections(iframe_locator, context, _page)
            except Exception as e:
                print("problem with parsing comment section")
                close_user_profile(iframe_locator, _page)
                continue

            users_objs.append(user)
            visited_users.add(user['username'])
        close_user_profile(iframe_locator, _page)

    return users_objs


# Find and open comments button
def open_comments_button(_page, retries=5):
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    button_element = _page.locator(button_class)
    button_element.scroll_into_view_if_needed()
    button_element.wait_for(state="attached")
    button_element.first.click()


# Get user data
def get_users_data(_page, context):
    # Activate comment section
    try:
        open_comments_button(_page)
    except Exception as e:
        print("Could not find comment section")
        return []

    iframe_locator = _page.frame_locator('iframe[id^="jacSandbox_"]')
    _page.set_default_timeout(5000)
    # Load all comments
    load_comments_loc = ".spcv_load-more-messages"
    try:
        button = iframe_locator.locator(load_comments_loc)
        while button:
            button.wait_for(state="attached")
            button.click()
            button = iframe_locator.locator(load_comments_loc).first
    except TimeoutError as e:
        print(e)

    return parse_users(iframe_locator, context, _page)


# Process each article by getting article and users data
def process_article(_page, link, context, retries=3):
    for i in range(retries):
        try:
            _page.goto(link, timeout=3000, wait_until="domcontentloaded")
            _article_data = get_article_data(_page)
            user_data = get_users_data(_page, context)
            return _article_data, user_data
        except Exception as e:
            print(e)


# Write array to MongoDB
def write_to_mongodb(_collection, _array, id_field):
    try:
        ids = [item[id_field] for item in _array]
        duplicate_docs = _collection.find({id_field: {'$in': ids}})
        duplicate_urls = set(dupe_doc[id_field] for dupe_doc in duplicate_docs)
        docs_to_insert = [item for item in _array if item[id_field] not in duplicate_urls]
        if docs_to_insert:
            _collection.insert_many(docs_to_insert)
    except Exception as e:
        print(e)


# Run the job
def job():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36")
        articles = []
        users = []

        # Parse through the articles on the scrolling page
        # 'https://news.yahoo.com/tagged/donald-trump', 'https://news.yahoo.com/tagged/joe-biden'
        for start_link in ['https://news.yahoo.com/politics/']:
            try:
                page = context.new_page()
                page.goto(start_link, timeout=3000, wait_until="domcontentloaded")

                # Scroll to the bottom
                for i in range(10):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
                    time.sleep(0.5)

                # Parse through each article
                stream_items = page.query_selector_all('.stream-item')
                for stream_item in stream_items:
                    item_link = stream_item.query_selector('a').get_attribute('href')

                    if 'news.yahoo.com' not in item_link:
                        item_link = 'https://news.yahoo.com' + item_link
                    if item_link not in visited_articles and item_link.__contains__('.html'):
                        visited_articles.add(item_link)
                        current_page = context.new_page()
                        article_data, users_data = process_article(current_page, item_link, context)

                        category = json.loads(stream_item.get_attribute('data-i13n-cfg'))['categoryLabel']
                        article_data['category'] = category

                        if article_data is not None:
                            articles.append(article_data)
                        if users_data is not None:
                            users.extend(users_data)

                        current_page.close()
            except Exception as e:
                print(e)

        # Close resources
        context.close()
        browser.close()

        # Write to MongoDB
        collection_articles = db['Articles']
        collection_users = db['Users']
        if articles.__len__() > 0:
            write_to_mongodb(collection_articles, articles, "url")
        if users.__len__() > 0:
            write_to_mongodb(collection_users, users, "username")

        visited_articles.clear()
        visited_users.clear()


schedule.every().day.at("00:00").do(job)
while True:
    schedule.run_pending()
    time.sleep(1)

