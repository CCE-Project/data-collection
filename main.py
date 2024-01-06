import time
import json
import csv
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError


visited_articles = set()


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


# Get user data
def get_users_data(page):
    page.evaluate('window.scrollTo(0, document.body.scrollHeight);')

    # Activate comment section
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    page.wait_for_selector(button_class)
    button_element = page.locator(button_class)
    button_element.click()

    iframe_locator = page.frame_locator('iframe[id^="jacSandbox_"]')

    # Load all comments
    load_comments_loc = ".spcv_load-more-messages"
    page.set_default_timeout(10000)
    try:
        button = iframe_locator.locator(load_comments_loc)
        while button:
            button.click()
            button = iframe_locator.locator(load_comments_loc)
    except TimeoutError as e:
        print(e)

    # Parse users
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
            is_private = True
            print("its private")
        except Exception as e:
            print("its not private")
            is_private = False

        if not is_private:
            user = {}

            # Get user info
            nickname_locator = 'div[class*="src-components-TopMenu-TopMenu__username"]'
            username_locator = 'bdi'
            post_num_locator = 'div[class*="src-components-Navbar-Navbar__Label"]'
            likes_rec_locator = 'div[class*="src-components-DetailText-DetailText__DetailText"][data-testid="text"]'
            likes_rec = iframe_locator.locator(likes_rec_locator).text_content().split()[0]
            username = iframe_locator.locator(username_locator).text_content()
            nickname = iframe_locator.locator(nickname_locator).text_content()
            post_num = iframe_locator.locator(post_num_locator).text_content()
            user['likes'] = likes_rec
            user['username'] = username
            user['nickname'] = nickname
            user['post_num'] = post_num

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
            comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
            comment_section_elements = iframe_locator.locator(comment_section_locator).element_handles()
            user['comments_section'] = []
            for comment_section in comment_section_elements:
                source_article_locator = 'a[class*="src-components-FeedItem-styles__ExtractWrapper"]'
                type_comment_locator = 'a[class*="src-components-FeedItem-styles__MessageLink"]'
                comment_text_locator = 'div[class*="src-components-FeedItem-styles__TextWrapper"]'

                # Get source article data
                source_article = comment_section.query_selector(source_article_locator).get_attribute('href')
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

                user['comments_section'].append({'source_article': source_article_data, "comments": comments})
            users_objs.append(user)
            close_profile_button = iframe_locator.locator('button[title="Close the modal"]')
            close_profile_button.click()
        return users_objs


# Process each article by getting article and users data
def process_article(page, link, retries=90):
    for i in range(retries):
        try:
            page.goto(link, timeout=3000, wait_until="domcontentloaded")
            _article_data = get_article_data(page)
            user_data = get_users_data(page)
            page.close()
            return _article_data, user_data
        except Exception as e:
            print(e)


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
            for i in range(18):
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
                    article_data, users_data = process_article(current_page, item_link)
                    articles.append(article_data)
                    users.append(users_data)
        except Exception as e:
            print(e)

    context.close()

    articles_file = 'articles.csv'
    users_file = 'users.json'

    # Write the data to the articles file
    with open(articles_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = articles[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data in articles:
            writer.writerow(data)

    # Write the data to the users file
    with open(users_file, "w") as file:
        json.dump(users, file, indent=4)

    # Close the browser
    browser.close()
