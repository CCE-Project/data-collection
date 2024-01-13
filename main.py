import time
import json
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
from pymongo import MongoClient

with open('./config.json', 'r') as f:
    config = json.load(f)

uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, serverSelectionTimeoutMS=60000, w=1)
db = mongo_client['NLP-Cross-Cutting-Exposure']

visited_articles = set()
visited_users = set()


# Get article data for whole page
def get_article_data(page):
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


# Get article data for users comment section
def get_source_article_data(page):
    json_selector = 'script[type="application/ld+json"]'
    json_content = page.inner_text(json_selector)
    data = json.loads(json_content)

    news_outlet_link = data.get('provider').get('url')
    news_outlet_name = data.get('provider').get('name')
    og_title = data.get('headline')

    return {
        "title": og_title,
        'outlet_link': news_outlet_link,
        'outlet_name': news_outlet_name
    }


# Get General User Info
def get_general_user_info(iframe_locator):
    # Get user info
    nickname_locator = 'div[class*="src-components-TopMenu-TopMenu__username"]'
    username_locator = 'bdi'
    post_num_locator = 'div[class*="src-components-Navbar-Navbar__Label"]'
    likes_rec_locator = 'div[class*="src-components-DetailText-DetailText__DetailText"][data-testid="text"]'
    likes_rec = iframe_locator.locator(likes_rec_locator).text_content().split()[0]
    username = iframe_locator.locator(username_locator).text_content()
    nickname = iframe_locator.locator(nickname_locator).text_content()
    post_num = iframe_locator.locator(post_num_locator).text_content()
    return likes_rec, username, nickname, post_num


# Get Comment Section data with source article and comments
def parse_comment_sections(iframe_locator):
    comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
    comment_section_elements = iframe_locator.locator(comment_section_locator).element_handles()
    comments_section = []
    for comment_section in comment_section_elements:
        source_article_locator = 'a[class*="src-components-FeedItem-styles__ExtractWrapper"]'
        type_comment_locator = 'a[class*="src-components-FeedItem-styles__MessageLink"]'
        comment_text_locator = 'div[class*="src-components-FeedItem-styles__TextWrapper"]'

        # Get source article data
        source_article = comment_section.query_selector(source_article_locator).get_attribute('href')

        if "finance.yahoo.com" in source_article:
            continue
        source_article_page = context.new_page()
        source_article_page.goto(source_article, timeout=3000, wait_until="domcontentloaded")
        source_article_data = get_source_article_data(source_article_page)
        source_article_page.close()

        # Parse each comment and type
        comments = []
        type_comment_elements = comment_section.query_selector_all(type_comment_locator)
        comment_text_elements = comment_section.query_selector_all(comment_text_locator)
        comment_section.dispose()
        for index in range(type_comment_elements.__len__()):
            _type = type_comment_elements[index].inner_text()
            comment_text = comment_text_elements[index].inner_text()
            if _type.startswith("Posted"):
                _type = "Posted"
            if _type.startswith("Replied to"):
                _, rest_of_string = _type.split("o", 1)
                _type = f"Replied to {rest_of_string}".split()
                _type = " ".join(_type[:3])
            comments.append({"comment_text": comment_text, "type": _type})
            print(comment_text)

        comments_section.append({'source_article': source_article_data, "comments": comments})

    return comments_section


# Parse Users
def parse_users(iframe_locator):
    users_objs = []
    profile_locator = 'button[data-spot-im-class="user-info-username"]'
    profile_buttons = iframe_locator.locator(profile_locator).element_handles()
    for profile_button in profile_buttons:
        profile_button.click()
        profile_button.dispose()
        is_private = False

        # Private profile check
        private_profile_loc = 'div[class*="src-views-Profile-index__PrivateProfile"]'
        try:
            private = iframe_locator.locator(private_profile_loc)
            if private.inner_text().__contains__("private mode"):
                is_private = True
                print("its private")
            else:
                is_private = False
        except Exception as e:
            print("its not private")
            is_private = False

        if not is_private:
            # Get General User Info
            user = dict()
            user['likes'], user['username'], user['nickname'], user['post_num'] = get_general_user_info(iframe_locator)

            if user['username'] not in visited_users:

                # Load Read More Comments
                read_more_locator = 'a[class*="src-components-FeedItem-styles__ShowMoreButton"]'
                try:
                    read_more_buttons = iframe_locator.locator(read_more_locator).element_handles()
                    while read_more_buttons:
                        for read_more in read_more_buttons:
                            read_more.click()
                            read_more.dispose()
                        read_more_buttons = iframe_locator.locator(read_more_locator).element_handles()
                except TimeoutError as e:
                    print(e)

                # Parse comments under a single source article
                user['comments_section'] = parse_comment_sections(iframe_locator)
                users_objs.append(user)
                visited_users.add(user['username'])
        close_profile_button = iframe_locator.locator('button[title="Close the modal"]')
        close_profile_button.click()

    return users_objs


# Get user data
def get_users_data(page):
    # Activate comment section
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    page.wait_for_selector(button_class)
    button_element = page.locator(button_class)
    button_element.click()

    iframe_locator = page.frame_locator('iframe[id^="jacSandbox_"]')

    # Load all comments
    load_comments_loc = ".spcv_load-more-messages"
    page.set_default_timeout(5000)
    try:
        button = iframe_locator.locator(load_comments_loc)
        while button:
            button.click()
            button = iframe_locator.locator(load_comments_loc)
    except TimeoutError as e:
        print(e)

    return parse_users(iframe_locator)


# Process each article by getting article and users data
def process_article(page, link, retries=3):
    for i in range(retries):
        try:
            page.goto(link, timeout=3000, wait_until="domcontentloaded")
            _article_data = get_article_data(page)
            user_data = get_users_data(page)
            return _article_data, user_data
        except Exception as e:
            print(e)


# Write array to MongoDB
def write_to_mongodb(_collection, _array, id_field):
    ids = [item[id_field] for item in _array]
    duplicate_docs = _collection.find({id_field: {'$in': ids}})
    duplicate_urls = set(dupe_doc[id_field] for dupe_doc in duplicate_docs)
    docs_to_insert = [item for item in _array if item[id_field] not in duplicate_urls]
    if docs_to_insert:
        _collection.insert_many(docs_to_insert)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
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

                category = json.loads(stream_item.get_attribute('data-i13n-cfg'))['categoryLabel']
                item_link = stream_item.query_selector('a').get_attribute('href')

                if 'news.yahoo.com' not in item_link:
                    item_link = 'https://news.yahoo.com' + item_link
                if item_link not in visited_articles and item_link.__contains__('.html'):
                    visited_articles.add(item_link)
                    current_page = context.new_page()
                    article_data, users_data = process_article(current_page, item_link)

                    article_data['category'] = category

                    articles.append(article_data)
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
    write_to_mongodb(collection_articles, articles, "url")
    write_to_mongodb(collection_users, users, "username")


