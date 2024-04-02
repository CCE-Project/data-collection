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
REPLY_DEPTH = 15

uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, w=1, tlsCAFile=certifi.where())
db = mongo_client['NLP-Cross-Cutting-Exposure']

visited_articles = set()


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


# Find and open comments button
async def open_comments_button(_page):
    button_class = '.caas-button.view-cmts-cta.showCmtCount'
    button_element = _page.locator(button_class)
    await button_element.scroll_into_view_if_needed()
    await button_element.wait_for(state="attached")
    await button_element.first.click()


async def parse_threads(comment_threads, comments):
    i = 0
    for thread in comment_threads:
        try:
            root_comment_loc = ".components-MessageLayout-index__appearance-component"
            root_comment_element = await thread.query_selector(root_comment_loc)

            nick_name_loc = ".src-components-Username-index__button"
            nick_name_span = await root_comment_element.query_selector(nick_name_loc)
            nick_name = await nick_name_span.inner_text()

            comment_time_loc = 'time[data-spot-im-class="message-timestamp"]'
            comment_time_element = await root_comment_element.query_selector(comment_time_loc)
            time_commented = await comment_time_element.inner_text()

            comment_text_loc = "p"
            comment_text_element = await root_comment_element.query_selector(comment_text_loc)
            comment_text = await comment_text_element.inner_text()

            print(comment_text)

            likes = 0
            dislikes = 0
            votes_loc = ".components-MessageActions-components-VoteButtons-index__votesCounter"
            votes_elements = await root_comment_element.query_selector_all(votes_loc)
            j = 0
            for vote in votes_elements:
                if j == 0:
                    j += 1
                    likes = int((await vote.inner_text()))
                else:
                    dislikes = int((await vote.inner_text()))

            comments.append({
                "nick_name": nick_name,
                "time_commented_ago": time_commented,
                "likes": likes,
                "dislikes": dislikes,
                "text": comment_text,
                "replies": []
            })
            await parse_replies(thread, comments, [i])
        except Exception as e:
            print(e)
        thread.dispose()
        i += 1


async def parse_inner_replies(replies, comments, i):
    inner_i = 0
    for reply in replies:
        try:
            root_comment_loc = ".components-MessageLayout-index__appearance-component"
            root_comment_element = await reply.query_selector(root_comment_loc)

            nick_name_loc = ".src-components-Username-index__button"
            nick_name_span = await root_comment_element.query_selector(nick_name_loc)
            nick_name = await nick_name_span.inner_text()

            comment_time_loc = 'time[data-spot-im-class="message-timestamp"]'
            comment_time_element = await root_comment_element.query_selector(comment_time_loc)
            time_commented = await comment_time_element.inner_text()

            comment_text_loc = "p"
            comment_text_element = await root_comment_element.query_selector(comment_text_loc)
            comment_text = await comment_text_element.inner_text()

            print(comment_text)

            likes = 0
            dislikes = 0
            votes_loc = ".components-MessageActions-components-VoteButtons-index__votesCounter"
            votes_elements = await root_comment_element.query_selector_all(votes_loc)
            j = 0
            for vote in votes_elements:
                if j == 0:
                    j += 1
                    likes = int((await vote.inner_text()))
                else:
                    dislikes = int((await vote.inner_text()))

            temp = comments
            for ind in i:
                temp = temp[ind]['replies']

            temp.append(
                {
                    "nick_name": nick_name,
                    "time_commented_ago": time_commented,
                    "likes": likes,
                    "dislikes": dislikes,
                    "text": comment_text,
                    "replies": []
                }
            )

            await parse_replies(reply, comments, i.append(inner_i))
        except Exception as e:
            print(e)
        reply.dispose()
        inner_i += 1


async def parse_replies(thread_locator, comments, i):
    global REPLY_DEPTH
    try:
        if REPLY_DEPTH == 0:
            raise Exception("error")
        else:
            REPLY_DEPTH -= 1
            replies_loc = ".spcv_children-list"
            replies = thread_locator.locator(replies_loc)
            replies = await replies.locator("li").element_handles()
            await parse_inner_replies(replies, comments, i)
    except Exception as e:
        REPLY_DEPTH = 15
        print("No more replies in thread to parse")


async def parse_comments(_page, iframe_locator, comments):
    comments_list_loc = '.spcv_messages-list'
    comment_threads = iframe_locator.locator(comments_list_loc)
    print(comment_threads)
    comment_threads = await comment_threads.locator("li").element_handles()
    print(len(comment_threads))

    await parse_threads(comment_threads, comments)


# Get user data
async def get_article_comments(_page):
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
        button = iframe_locator.locator(load_comments_loc).first
        while button:
            await button.wait_for(state="attached")
            await button.click()
            button = iframe_locator.locator(load_comments_loc).first
    except Exception as e:
        print("Finished loading more users from comment section")

    load_replies_loc = ".spcv_showMoreRepliesText"
    print("Loading more replies")
    try:
        button = iframe_locator.locator(load_replies_loc).first
        while button:
            await button.wait_for(state="attached")
            await button.click()
            button = iframe_locator.locator(load_replies_loc).first
    except Exception as e:
        print("Finished loading more replies from comment section")

    comments = []
    await parse_comments(_page, iframe_locator, comments)
    return comments


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
async def scrape_section(link, p, section_articles):
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

            try:
                article_data = await get_article_data(article_page)
                comments_data = await get_article_comments(article_page)
                article_data["comments"] = comments_data
                if article_data is not None:
                    section_articles.append(article_data)
            except Exception as e:
                print(e)

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
    section_articles = []

    try:
        await scrape_section(link, p, section_articles)
    except Exception as e:
        print(e)

    # Write to MongoDB
    collection_articles = db['Reply-Network']
    if section_articles.__len__() > 0:
        write_to_mongodb(collection_articles, section_articles, "url")


# Run the job
async def job():
    async with async_playwright() as p:
        await process_link("https://www.yahoo.com/news/us/", p)

        # tasks = [asyncio.create_task(process_link(link, p)) for link in links]
        # await asyncio.gather(*tasks)

        visited_articles.clear()


if __name__ == '__main__':
    asyncio.run(job())
