import json
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
from playwright.sync_api import Error
from pymongo import MongoClient
import re
import schedule
import time
import certifi
import csv

with open('./config.json', 'r') as f:
    config = json.load(f)

PAGE_RETRIES = 5

uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, w=1, tlsCAFile=certifi.where())
db = mongo_client['NLP-Cross-Cutting-Exposure']

visited_articles = set()
visited_users = set()


# Get article data for whole page
def get_article_data(page):
    try:
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

        script_content = page.locator('//*[@id="atomic"]/body/script[4]')
        script_content.wait_for(state="attached")
        page.evaluate(script_content.text_content())
        category_label = page.evaluate('() => window.YAHOO.context.meta.categoryLabel')

        print(og_title)
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
            "outlet_name": news_outlet_name,
            "category": category_label
        }
    except Exception as e:
        print(e)
        return None


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
    print("Scrolling down to load more comments from user")
    try:
        generated_enough = False
        i = 0
        last_number_comments = 0
        while not generated_enough:
            comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
            comment_section_elements = iframe_locator.locator(comment_section_locator).element_handles()

            if comment_section_elements.__len__() >= 300:
                generated_enough = True
            elif last_number_comments == comment_section_elements.__len__():
                generated_enough = True
            else:
                i += 1
                for comment_section in comment_section_elements:
                    comment_section.dispose()
                _page.mouse.wheel(0, 50000)
                last_number_comments = comment_section_elements.__len__()
                time.sleep(1)

        _page.mouse.wheel(50000 * i, 0)
    except Exception as e:
        print(e)
    print("Finished scroll for more comments on user page")


# Load read more comments
def load_read_more_comments(iframe_locator):
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
        print("Finished loading all sections")


# Get Comment Section data with source article and comments
def parse_comment_sections(iframe_locator, _page, browser):
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
        source_article_page = create_new_page(browser)
        try:
            navigate_to_page(source_article_page, source_article)
            source_article_data = get_article_data(source_article_page)
            if source_article_data is None:
                raise Exception("Source article data is None")
            source_article_page.close()
            print("Got source article data")
        except Exception as e:
            print(e)
            source_article_page.close()
            comment_section.dispose()
            print("Finished parsing comments section")
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

                print(comment_text)
                comments.append({"comment_text": comment_text, "type": _type, "last_posted": time_posted})

            comments_section.append({'source_article': source_article_data, "comments": comments})

    return comments_section


def close_user_profile(_iframe_locator, _page):
    try:
        close_profile_button = _iframe_locator.locator('button[title="Close the modal"]')
        close_profile_button.scroll_into_view_if_needed()
        close_profile_button.wait_for(state="attached")
        close_profile_button.click()
        return True
    except Exception as e:
        print(f"Failed to close profile")
        return False


# Parse Users
def parse_users(iframe_locator, _page, browser):
    users_objs = []
    profile_locator = 'button[data-spot-im-class="user-info-username"]'
    profile_buttons = iframe_locator.locator(profile_locator).element_handles()
    for profile_button in profile_buttons:
        try:
            profile_button.wait_for_element_state("stable")
            profile_button.click()

            # Get General User Info
            user = dict()

            try:
                user['likes'], user['username'], user['nickname'], user['post_num'] = get_general_user_info(
                    iframe_locator)
            except Error as e:
                print("Private profile skipping to next")
                profile_button.dispose()
                if close_user_profile(iframe_locator, _page):
                    print("finished scraping user")
                    continue
                else:
                    return users_objs

            if user['username'] not in visited_users:

                # Generate more comments by scrolling
                generate_more_comments(iframe_locator, _page)

                # Load Read More Comments
                load_read_more_comments(iframe_locator)

                # Parse comments under a single source article
                try:
                    user['comments_section'] = parse_comment_sections(iframe_locator, _page, browser)
                    print("parsing comment section finished")
                except Exception as e:
                    print("parsing comment section finished")
                    profile_button.dispose()
                    if close_user_profile(iframe_locator, _page):
                        print("finished scraping user")
                        continue
                    else:
                        return users_objs

                users_objs.append(user)
                visited_users.add(user['username'])
            profile_button.dispose()
            if close_user_profile(iframe_locator, _page):
                print("finished scraping user")
                continue
            else:
                return users_objs
        except Exception as e:
            print(e)
            break

    return users_objs


# Find and open comments button
def open_comments_button(_page):
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    button_element = _page.locator(button_class)
    button_element.scroll_into_view_if_needed()
    button_element.wait_for(state="attached")
    button_element.first.click()


# Get user data
def get_users_data(_page, browser):
    # Activate comment section
    try:
        open_comments_button(_page)
    except Exception as e:
        print("Could not find comment section skipping to next article")
        return []

    iframe_locator = _page.frame_locator('iframe[id^="jacSandbox_"]')
    # Load all comments
    load_comments_loc = ".spcv_load-more-messages"
    print("Loading more users")
    try:
        button = iframe_locator.locator(load_comments_loc)
        while button:
            button.wait_for(state="attached")
            button.click()
            button = iframe_locator.locator(load_comments_loc).first
    except TimeoutError as e:
        print("Finished loading more users from comment section")

    return parse_users(iframe_locator, _page, browser)


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


# Navigate to page
def navigate_to_page(page, link):
    for i in range(0, PAGE_RETRIES):
        try:
            page.goto(link, timeout=5000, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(e)


# Scrolls down to generate more articles
def generate_more_articles(page, link):
    duration = 30
    for i in range(duration):
        page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(1)


# Scrape Yahoo News section
def scrape_section(link, p):
    browser = create_new_browser(p)
    page = create_new_page(browser)

    navigate_to_page(page, link)
    generate_more_articles(page, link)

    section_article_data = []
    section_users_data = []

    stream_items = page.query_selector_all('.stream-item')
    for stream_item in stream_items:
        article_link = stream_item.query_selector('a').get_attribute('href')
        if 'news.yahoo.com' not in article_link and "https://" not in article_link:
            print(article_link)
            article_link = 'https://news.yahoo.com' + article_link
        if article_link not in visited_articles and article_link.__contains__(
                '.html') and 'news.yahoo.com' in article_link:
            visited_articles.add(article_link)
            article_page = create_new_page(browser)
            article_page.set_viewport_size({"width": 1600, "height": 1200})

            navigate_to_page(article_page, article_link)

            article_data = get_article_data(article_page)

            if article_data is not None:
                section_article_data.append(article_data)
                users_data = get_users_data(article_page, browser)
                if users_data is not None:
                    section_users_data.extend(users_data)

            article_page.close()

    page.close()
    browser.close()

    return section_article_data, section_users_data


# Create new page given browser
def create_new_page(browser):
    page = browser.new_page(ignore_https_errors=True,
                            user_agent="Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_10_3; en-US) "
                                       "Gecko/20100101 Firefox/55.8",
                            bypass_csp=True,
                            java_script_enabled=True,
                            service_workers="block",
                            reduced_motion="reduce")
    page.set_default_timeout(5000)
    return page


# Create new browser
def create_new_browser(p):
    browser = p.chromium.launch(headless=True)
    return browser


# Run the job
def job():
    with sync_playwright() as p:
        browser = create_new_browser(p)

        articles = []
        users = []

        landing_page = create_new_page(browser)
        navigate_to_page(landing_page, "https://news.yahoo.com/")
        nav_bar_elements = landing_page.query_selector_all('#ybar-navigation > div > ul > li')
        nav_bar_elements = nav_bar_elements[0:3] + nav_bar_elements[4:8]
        links = []

        for nav_bar_element in nav_bar_elements:
            link = nav_bar_element.query_selector("a").get_attribute('href')
            links.append(link)

        landing_page.close()
        browser.close()

        for link in links:
            section_articles, section_users = scrape_section(link, p)
            if section_articles is not None:
                articles.extend(section_articles)
                if section_users is not None:
                    users.extend(section_users)

        # Write to MongoDB
        collection_articles = db['Articles']
        collection_users = db['Users']

        if articles.__len__() > 0:
            write_to_mongodb(collection_articles, articles, "url")

        if users.__len__() > 0:
            write_to_mongodb(collection_users, users, "username")

        users.clear()
        articles.clear()
        visited_articles.clear()
        visited_users.clear()


# schedule.every().day.at("00:00").do(job)
# schedule.every().day.at("12:00").do(job)
# while True:
#     schedule.run_pending()
#     time.sleep(1)

if __name__ == '__main__':
    job()
