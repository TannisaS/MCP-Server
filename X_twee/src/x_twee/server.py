import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import mcp.types as types
from mcp.server import InitializationOptions
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Setup Google Sheets connection
def connect_to_google_sheet(sheet_url, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('C:/Users/KIIT/Desktop/KIIT/MCP/service_account.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(sheet_url).worksheet(sheet_name)
    return sheet

# Fetch tweets from Google Sheets
def fetch_tweets(sheet):
    tweets_to_post = []
    rows = sheet.get_all_records()
    for index, row in enumerate(rows):
        if row.get("Status", "").lower() != "posted":
            tweets_to_post.append({
                "content": row.get("Tweet Content", ""),
                "row_number": index + 2,
            })
    return tweets_to_post

# Post tweet using Selenium
def post_tweet(tweet_content):
    driver = webdriver.Chrome()  # Make sure you have ChromeDriver installed and in PATH
    driver.get("https://twitter.com/login")
    
    # Wait for page to load
    asyncio.sleep(5)
    
    username_field = driver.find_element(By.NAME, "text")
    username_field.send_keys("username")  # Replace with your Twitter username
    username_field.send_keys(Keys.RETURN)
    
    asyncio.sleep(5)  # Wait for password page
    
    password_field = driver.find_element(By.NAME, "password")
    password_field.send_keys("password")  # Replace with your Twitter password
    password_field.send_keys(Keys.RETURN)
    
    asyncio.sleep(5)  # Wait for login
    
    # Locate the tweet input field
    tweet_box = driver.find_element(By.XPATH, "//div[@aria-label='Tweet text']")
    tweet_box.send_keys(tweet_content)
    
    tweet_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButtonInline']")
    tweet_button.click()
    
    asyncio.sleep(5)  # Wait for tweet to post
    driver.quit()

# Update status in Google Sheet
def update_status(sheet, row_number):
    sheet.update_cell(row_number, sheet.find("Status").col, "Posted")

# MCP Server
server = Server("TweetScheduler")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="schedule-tweets",
            description="Fetch and post tweets from Google Sheets",
            inputSchema={
                "type": "object",
                "properties": {
                    "sheet_url": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
                "required": ["sheet_url", "sheet_name"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name != "schedule-tweets":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        raise ValueError("Missing arguments")

    sheet_url = arguments.get("sheet_url")
    sheet_name = arguments.get("sheet_name")

    sheet = connect_to_google_sheet(sheet_url, sheet_name)
    tweets = fetch_tweets(sheet)

    for tweet in tweets:
        post_tweet(tweet['content'])
        update_status(sheet, tweet['row_number'])

    return [
        types.TextContent(
            type="text",
            text=f"Processed {len(tweets)} tweets."
        )
    ]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="TweetScheduler",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
