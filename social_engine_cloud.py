import os
import re
import time
import random
import requests
import urllib3
import psycopg2
from bs4 import BeautifulSoup
from ddgs import DDGS
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATABASE_URL = os.environ.get("DATABASE_URL")
BATCH_SIZE = 120   # Per runner 120 leads (~5-6 mins)
MAX_WORKERS = 4    # 4 threads per runner

JUNK_KEYWORDS = [
    '/p/', '/reel/', '/explore/', '/tags/', '/stories/', '/locations/',
    '/groups/', '/events/', '/marketplace/', '/pages/', '/posts/', '/dir/',
    'zomato', 'swiggy', 'dineout', 'magicpin', 'justdial', 'tripadvisor', 'eazydiner'
]

def is_clean_profile(url, platform):
    url = url.lower()
    if platform not in url:
        return False
    for junk in JUNK_KEYWORDS:
        if junk in url:
            return False
    return True

def verify_username_authenticity(business_name, url):
    try:
        clean_url = url.split('?')[0].strip('/')
        username = clean_url.split('/')[-1].replace('_', '').replace('.', '').lower()
        clean_b_name = re.sub(r'[^a-z0-9]', '', business_name.lower())

        if clean_b_name in username or username in clean_b_name:
            return True

        return SequenceMatcher(None, clean_b_name, username).ratio() > 0.55
    except Exception:
        return False

def search_bing_html(query):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
    links = []
    try:
        res = requests.get(url, headers=headers, timeout=8, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'http' in href and 'bing.com' not in href and 'microsoft.com' not in href:
                links.append(href)
    except Exception:
        pass
    return links

def scrape_website_for_socials(url, business_name):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=6, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')

        insta, fb = "Not Available", "Not Available"
        for a_tag in soup.find_all('a', href=True):
            link = a_tag.get('href', '').lower()
            if "instagram.com" in link and is_clean_profile(link, "instagram.com"):
                if verify_username_authenticity(business_name, link):
                    insta = a_tag['href']
            elif "facebook.com" in link and is_clean_profile(link, "facebook.com"):
                if verify_username_authenticity(business_name, link):
                    fb = a_tag['href']
        return insta, fb
    except Exception:
        return "Not Available", "Not Available"

def get_1000_percent_real_links(b_name, city, platform):
    query = f'"{b_name}" {city} official {platform} restaurant OR cafe'
    platform_domain = f"{platform}.com"

    urls = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            urls = [res.get('href', '') for res in results]
    except Exception:
        urls = []

    if not urls:
        urls = search_bing_html(query)

    for link in urls:
        if is_clean_profile(link, platform_domain):
            if verify_username_authenticity(b_name, link):
                return link.split('?')[0].strip('/')

    return "Not Available"

def enrich_single_lead(lead):
    lead_id, b_name, city = lead
    final_insta, final_fb = "Not Available", "Not Available"

    # LAYER 1: Official Website Hunt
    try:
        website_query = f"{b_name} {city} official website restaurant"
        website_url = ""
        try:
            time.sleep(random.uniform(0.4, 1.0))
            with DDGS() as ddgs:
                results = list(ddgs.text(website_query, max_results=1))
                if results:
                    website_url = results[0].get('href', '')
        except Exception:
            website_url = ""

        if not website_url:
            urls = search_bing_html(website_query)
            if urls:
                website_url = urls[0]

        blacklist = [
            "zomato", "swiggy", "dineout", "magicpin", "eazydiner",
            "justdial", "instagram", "facebook", "youtube"
        ]
        if website_url and not any(blocked in website_url.lower() for blocked in blacklist):
            final_insta, final_fb = scrape_website_for_socials(website_url, b_name)
    except Exception:
        pass

    # LAYER 2: Direct Social Search
    if final_insta == "Not Available":
        time.sleep(random.uniform(0.7, 1.4))
        final_insta = get_1000_percent_real_links(b_name, city, "instagram")

    if final_fb == "Not Available":
        time.sleep(random.uniform(0.7, 1.4))
        final_fb = get_1000_percent_real_links(b_name, city, "facebook")

    return lead_id, b_name, final_insta, final_fb

def run_cloud_enricher():
    if not DATABASE_URL:
        print("❌ DATABASE_URL environment variable missing hai!")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Atomic Batch Claim: 5 parallel runners aapas me kabhi nahi takrayenge
    cur.execute("""
        WITH claimed AS (
            SELECT id
            FROM leads
            WHERE status = 'raw'
            ORDER BY id ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE leads
        SET status = 'processing', updated_at = CURRENT_TIMESTAMP
        FROM claimed
        WHERE leads.id = claimed.id
        RETURNING leads.id, leads.business_name, leads.city;
    """, (BATCH_SIZE,))
    leads = cur.fetchall()
    conn.commit()

    if not leads:
        print("🎉 Koi bhi 'raw' lead pending nahi hai! Sab enriched hain.")
        cur.close()
        conn.close()
        return

    print(f"🚀 {len(leads)} unique leads lock ho gayi hain. {MAX_WORKERS} workers start...")

    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(enrich_single_lead, lead) for lead in leads]
        for future in as_completed(futures):
            try:
                lead_id, b_name, insta, fb = future.result()
                cur.execute("""
                    UPDATE leads
                    SET instagram = %s,
                        facebook = %s,
                        status = 'enriched',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (insta, fb, lead_id))
                conn.commit()
                completed += 1
                print(f"[{completed}/{len(leads)}] ✅ {b_name[:25]} | IG: {'Yes' if insta != 'Not Available' else 'No'} | FB: {'Yes' if fb != 'Not Available' else 'No'}")
            except Exception as e:
                print(f"⚠️ Update error: {e}")
                conn.rollback()

    cur.close()
    conn.close()
    print(f"\n🎯 Batch complete! {completed} leads cloud DB me 'enriched' mark ho gayi.")

if __name__ == "__main__":
    run_cloud_enricher()