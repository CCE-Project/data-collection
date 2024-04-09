import json
from playwright.async_api import async_playwright
import requests
from pymongo import MongoClient
import re
import asyncio
import certifi
import os
import html

script_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(script_dir, 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)
uri = config['mongodb_connection_string']
mongo_client = MongoClient(uri, w=1, tlsCAFile=certifi.where())
db = mongo_client['NLP-Cross-Cutting-Exposure']
visited_articles = set()
PAGE_RETRIES = 5


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


async def intercept_request(route, request, interception_complete, comments):
    print("interception")
    # Log the URL of the intercepted request
    i = 0
    while True:
        try:
            data = {
                "sort_by": "best",
                "offset": 25 * i,
                "count": 25,
                "message_id": None,
                "depth": 15,
                "child_count": 15
            }
            response = requests.post(request.url, json=data, headers=request.headers)
            r_json = response.json()
            users_in_convo = r_json['conversation']['users']
            if len(r_json['conversation']['comments']) == 0:
                break

            for comment in r_json['conversation']['comments']:
                author = users_in_convo[comment['user_id']]

                content_a = []
                for content in comment['content']:
                    if 'text' in content:
                        content_a.append(html.unescape(re.sub(r'<.*?>', '', content['text'])))
                    if 'originalUrl' in content:
                        content_a.append(content['originalUrl'])

                replies = []
                if len(comment['replies']) > 0:
                    replies = get_formatted_replies(users_in_convo, comment['replies'])

                comments.append({
                    'display_name': author['display_name'],
                    'user_name': author['user_name'],
                    'replies_count': comment['replies_count'],
                    'time_commented': comment['written_at'],
                    'content': content_a,
                    'rank': comment['rank'],
                    'replies': replies,
                    'id': comment['id'],
                    'conversation_id': r_json['conversation']['conversation_id']
                })
            i += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(e)
            i += 1

    interception_complete.set()
    await route.continue_()


def get_formatted_replies(users_in_convo, replies):
    r = []
    for reply in replies:
        author = users_in_convo[reply['user_id']]

        content_a = []
        for content in reply['content']:
            if 'text' in content:
                content_a.append(html.unescape(re.sub(r'<.*?>', '', content['text'])))
            if 'originalUrl' in content:
                content_a.append(content['originalUrl'])

        replies_a = []
        if len(reply['replies']) > 0:
            replies_a = get_formatted_replies(users_in_convo, reply['replies'])

        r.append({
            'display_name': author['display_name'],
            'user_name': author['user_name'],
            'replies_count': reply['replies_count'],
            'time_commented': reply['written_at'],
            'content': content_a,
            'rank': reply['rank'],
            'replies': replies_a,
            'id': reply['id']
        })

    return r


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


async def navigate_to_article(page, link):
    for i in range(0, PAGE_RETRIES):
        try:
            await page.goto(link, timeout=15000, wait_until="domcontentloaded")
            comments_button = await page.query_selector(
                '.link.caas-button.noborder.caas-tooltip.flickrComment.caas-comment.top')
            await comments_button.click(timeout=15000)
            await asyncio.sleep(15)
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

            interception_complete = asyncio.Event()
            comments = []
            await article_page.route("https://api-2-0.spot.im/v1.0.0/conversation/read",
                                     handler=lambda route, request: asyncio.create_task(intercept_request(route,
                                                                                                          request,
                                                                            interception_complete, comments)))

            await navigate_to_article(article_page, article_link)
            await interception_complete.wait()
            print("here")
            try:
                article_data = await get_article_data(article_page)
                article_data["comments"] = comments
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
    collection_articles = db['Articles']
    if section_articles.__len__() > 0:
        write_to_mongodb(collection_articles, section_articles, "url")


# Run the job
async def job():
    async with async_playwright() as p:
        await process_link("https://www.yahoo.com/election/", p)

        # tasks = [asyncio.create_task(process_link(link, p)) for link in links]
        # await asyncio.gather(*tasks)

        visited_articles.clear()


if __name__ == '__main__':
    asyncio.run(job())
