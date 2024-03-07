import json
from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError
from playwright.async_api import Error
from pymongo import MongoClient
import re
import asyncio
import certifi
import os

script_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(script_dir, 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

PAGE_RETRIES = 5

uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, w=1, tlsCAFile=certifi.where())
db = mongo_client['NLP-Cross-Cutting-Exposure']

visited_articles = set()
visited_users = set()


# Get article data for whole page
async def get_article_data(page):
    try:
        json_selector = 'script[type="application/ld+json"]'
        json_content = await page.inner_text(json_selector)
        data = json.loads(json_content)

        wafer_json_content = await page.inner_text('.wafer-caas-data[type="application/json"]')
        data_wafer = json.loads(wafer_json_content)

        og_url = await page.evaluate('(document.querySelector("meta[property=\'og:url\']") || {}).content')
        news_keywords = await page.evaluate('(document.querySelector("meta[name=\'news_keywords\']") || {}).content')
        og_title = await page.evaluate('(document.querySelector("meta[property=\'og:title\']") || {}).content')
        og_description = await page.evaluate(
            '(document.querySelector("meta[property=\'og:description\']") || {}).content')
        og_image = await page.evaluate('(document.querySelector("meta[property=\'og:image\']") || {}).content')
        body = await page.inner_text('.caas-body')
        min_read = await page.inner_text('.caas-attr-mins-read')
        date_published = data.get("datePublished")
        date_modified = data.get("dateModified")
        authors = data.get('author')
        num_comments = data_wafer.get('commentsCount')

        news_outlet_link = data.get('provider').get('url')
        news_outlet_name = data.get('provider').get('name')

        script_content = page.locator('//*[@id="atomic"]/body/script[4]')
        await script_content.wait_for(state="attached")
        await page.evaluate(await script_content.text_content())
        category_label = await page.evaluate('() => window.YAHOO.context.meta.categoryLabel')

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
        print("Failed to get article data")
        return None


# Get General User Info
async def get_general_user_info(iframe_locator):
    # Get user info
    nickname_locator = 'div[class*="src-components-TopMenu-TopMenu__username"]'
    username_locator = 'bdi'
    post_num_locator = 'div[class*="src-components-Navbar-Navbar__Label"]'
    likes_rec_locator = 'div[class*="src-components-DetailText-DetailText__DetailText"][data-testid="text"]'
    likes_rec = iframe_locator.locator(likes_rec_locator)
    await likes_rec.wait_for(state="attached")
    likes_rec = await likes_rec.first.text_content()
    likes_rec = likes_rec.split()[0]

    username = iframe_locator.locator(username_locator)
    await username.wait_for(state="attached")
    username = await username.first.text_content()
    nickname = iframe_locator.locator(nickname_locator)
    await nickname.wait_for(state="attached")
    nickname = await nickname.first.text_content()
    post_num_string = iframe_locator.locator(post_num_locator)
    await post_num_string.wait_for(state="attached")
    post_num_string = await post_num_string.first.inner_text()
    match = re.search(r'\((.*?)\)', post_num_string)
    post_num = ""
    if match:
        post_num = match.group(1)
    else:
        post_num = post_num_string
    return likes_rec, username, nickname, post_num


# Scroll down to load more comments
async def generate_more_comments(iframe_locator, _page):
    print("Scrolling down to load more comments from user")
    try:
        generated_enough = False
        i = 0
        last_number_comments = 0
        while not generated_enough:
            comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
            comment_section_elements = await iframe_locator.locator(comment_section_locator).element_handles()

            if comment_section_elements.__len__() >= 600:
                generated_enough = True
            elif last_number_comments == comment_section_elements.__len__():
                generated_enough = True
            else:
                i += 1
                for comment_section in comment_section_elements:
                    await comment_section.dispose()
                await _page.mouse.wheel(0, 50000)
                last_number_comments = comment_section_elements.__len__()
                await asyncio.sleep(1)

        await _page.mouse.wheel(50000 * i, 0)
    except Exception as e:
        print("Scrolling for more comments on user profile exception")
    print("Finished scroll for more comments on user page")


# Load read more comments
async def load_read_more_comments(iframe_locator):
    read_more_locator = 'a[class*="src-components-FeedItem-styles__ShowMoreButton"]'
    try:
        read_more_buttons = await iframe_locator.locator(read_more_locator).element_handles()
        while read_more_buttons:
            for read_more in read_more_buttons:
                await read_more.wait_for_element_state("stable")
                await read_more.click()
                await read_more.dispose()
            read_more_buttons = await iframe_locator.locator(read_more_locator).element_handles()
    except Error as e:
        print("Finished loading all sections")


# Get Comment Section data with source article and comments
async def parse_comment_sections(iframe_locator, _page, browser):
    comment_section_locator = 'div[class*="src-components-FeedItem-styles__IndexWrapper"]'
    comment_section_elements = await iframe_locator.locator(comment_section_locator).element_handles()
    comments_section = []
    for comment_section in comment_section_elements:
        source_article_locator = 'a[class*="src-components-FeedItem-styles__ExtractWrapper"]'
        type_comment_locator = 'a[class*="src-components-FeedItem-styles__MessageLink"]'
        comment_text_locator = 'div[class*="src-components-FeedItem-styles__TextWrapper"]'

        # Get source article data
        source_article = await comment_section.query_selector(source_article_locator)
        source_article = await source_article.get_attribute('href')

        if "news.yahoo.com" not in source_article:
            await comment_section.dispose()
            continue
        source_article_page = await create_new_page(browser)
        try:
            await navigate_to_page(source_article_page, source_article)
            source_article_data = await get_article_data(source_article_page)
            if source_article_data is None:
                raise Exception("Source article data is None")
            await source_article_page.close()
            print("Got source article data")
        except Exception as e:
            await source_article_page.close()
            await comment_section.dispose()
            print("Finished parsing comments section")
            continue

        # Parse each comment and type
        comments = []
        type_comment_elements = await comment_section.query_selector_all(type_comment_locator)
        comment_text_elements = await comment_section.query_selector_all(comment_text_locator)
        await comment_section.dispose()
        if type_comment_elements.__len__() == comment_text_elements.__len__():
            for index in range(type_comment_elements.__len__()):
                _type = await type_comment_elements[index].inner_text()
                comment_text = await comment_text_elements[index].inner_text()
                time_posted = ""
                if _type.startswith("Posted"):
                    time_posted = _type.split("d", 1)[1].strip()
                    _type = "Posted"
                if _type.startswith("Replied to"):
                    x = _type.split(" ")
                    res = x[1].replace('\xa0', ' ')
                    time_posted = f'{res.split("o", 1)[1]} {x[2]} {x[3]}'.strip().split()
                    time_posted = ' '.join(time_posted[1:])
                    print(time_posted)
                    _, rest_of_string = _type.split("o", 1)
                    _type = f"Replied to {rest_of_string}".split()
                    _type = " ".join(_type[:3])

                print(comment_text)
                comments.append({"comment_text": comment_text, "type": _type, "last_posted": time_posted})

            comments_section.append({'source_article': source_article_data, "comments": comments})

    return comments_section


async def close_user_profile(_iframe_locator, _page):
    try:
        close_profile_button = _iframe_locator.locator('button[title="Close the modal"]')
        await close_profile_button.scroll_into_view_if_needed()
        await close_profile_button.wait_for(state="attached")
        await close_profile_button.click()
        return True
    except Exception as e:
        print("Failed to close profile")
        return False


# Parse Users
async def parse_users(iframe_locator, _page, browser):
    users_objs = []
    profile_locator = 'button[data-spot-im-class="user-info-username"]'
    profile_buttons = await iframe_locator.locator(profile_locator).element_handles()
    for profile_button in profile_buttons:
        try:
            await profile_button.wait_for_element_state("stable")
            await profile_button.click()

            # Get General User Info
            user = dict()

            try:
                user['likes'], user['username'], user['nickname'], user['post_num'] = await get_general_user_info(
                    iframe_locator)
            except Error as e:
                print("Private profile skipping to next")
                await profile_button.dispose()
                close = await close_user_profile(iframe_locator, _page)
                if close:
                    print("finished scraping user")
                    continue
                else:
                    return users_objs

            if user['username'] not in visited_users:

                # Generate more comments by scrolling
                await generate_more_comments(iframe_locator, _page)

                # Load Read More Comments
                await load_read_more_comments(iframe_locator)

                # Parse comments under a single source article
                try:
                    user['comments_section'] = await parse_comment_sections(iframe_locator, _page, browser)
                    print("parsing comment section finished")
                except Exception as e:
                    print("parsing comment section finished")
                    await profile_button.dispose()
                    close = await close_user_profile(iframe_locator, _page)
                    if close:
                        print("finished scraping user")
                        continue
                    else:
                        return users_objs

                users_objs.append(user)
                visited_users.add(user['username'])
            await profile_button.dispose()
            close = await close_user_profile(iframe_locator, _page)
            if close:
                print("finished scraping user")
                continue
            else:
                return users_objs
        except Exception as e:
            print(e)
            break

    return users_objs


# Find and open comments button
async def open_comments_button(_page):
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    button_element = _page.locator(button_class)
    await button_element.scroll_into_view_if_needed()
    await button_element.wait_for(state="attached")
    await button_element.first.click()


# Get user data
async def get_users_data(_page, browser):
    # Activate comment section
    try:
        await open_comments_button(_page)
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
            await button.wait_for(state="attached")
            await button.click()
            button = iframe_locator.locator(load_comments_loc).first
    except TimeoutError as e:
        print("Finished loading more users from comment section")

    res = await parse_users(iframe_locator, _page, browser)
    return res


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
async def navigate_to_page(page, link):
    for i in range(0, PAGE_RETRIES):
        try:
            await page.goto(link, timeout=15000, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            await asyncio.sleep(1)


# Scrolls down to generate more articles
async def generate_more_articles(page, link):
    duration = 30
    for i in range(duration):
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
        await asyncio.sleep(1)


# Scrape Yahoo News section
async def scrape_section(link, p, section_users):
    browser = await create_new_browser(p)
    page = await create_new_page(browser)

    await navigate_to_page(page, link)
    await generate_more_articles(page, link)

    stream_items = await page.query_selector_all('.stream-item')
    for stream_item in stream_items:
        article_link = await stream_item.query_selector('a')
        article_link = await article_link.get_attribute('href')
        if 'news.yahoo.com' not in article_link and "https://" not in article_link:
            print(article_link)
            article_link = 'https://news.yahoo.com' + article_link
        if article_link not in visited_articles and article_link.__contains__(
                '.html') and 'news.yahoo.com' in article_link:
            visited_articles.add(article_link)
            article_page = await create_new_page(browser)
            await article_page.set_viewport_size({"width": 1600, "height": 1200})

            await navigate_to_page(article_page, article_link)

            users_data = None
            try:
                users_data = await get_users_data(article_page, browser)
            except Exception as e:
                print(e)
            if users_data is not None:
                section_users.extend(users_data)

            await article_page.close()
            print("finished article")

    await page.close()
    await browser.close()
    print("finished section")


# Create new page given browser
async def create_new_page(browser):
    page = await browser.new_page(ignore_https_errors=True,
                                  user_agent="Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_10_3; en-US) "
                                             "Gecko/20100101 Firefox/55.8",
                                  bypass_csp=True,
                                  java_script_enabled=True,
                                  service_workers="block",
                                  reduced_motion="reduce")
    page.set_default_timeout(15000)
    return page


# Create new browser
async def create_new_browser(p):
    browser = await p.firefox.launch(headless=True)
    return browser


async def process_link(link, p):
    section_users = []

    try:
        await scrape_section(link, p, section_users)
    except Exception as e:
        print(e)

    # Write to MongoDB
    collection_users = db['Users']
    if section_users.__len__() > 0:
        write_to_mongodb(collection_users, section_users, "username")


# Run the job
async def job():
    async with async_playwright() as p:

        link = "https://news.yahoo.com/"

        await process_link(link, p)

        # tasks = [asyncio.create_task(process_link(link, p)) for link in links]
        # await asyncio.gather(*tasks)

        visited_articles.clear()
        visited_users.clear()


if __name__ == '__main__':
    asyncio.run(job())
