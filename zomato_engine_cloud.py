import os
import re
import time
import random
import psycopg2
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("psql "):
    DATABASE_URL = DATABASE_URL[5:].strip()
DATABASE_URL = DATABASE_URL.strip("'\"")
ZONES_PER_RUN = 2   # Har worker ek run me 2 zones scrape karega
MAX_THREADS = 3     # Zomato rate-limit se bachne ke liye 3 safe threads

def normalize_name(name):
    if not name:
        return ""
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def check_whatsapp_status(phone_number):
    clean_num = re.sub(r'[^0-9]', '', str(phone_number))
    if len(clean_num) >= 10:
        last_10 = clean_num[-10:]
        if last_10[0] in ['6', '7', '8', '9']:
            return True, last_10
    return False, str(phone_number)

def extract_deep_details(lead_item):
    b_name = lead_item["business_name"]
    restaurant_url = lead_item["restaurant_url"]
    fallback_map = lead_item["fallback_map"]

    data = {
        "phone": "Not Available", "fssai": "Not Available",
        "map_url": "Not Available", "dining_rating": "N/A",
        "delivery_rating": "N/A", "photo_url": "Not Available"
    }

    if not restaurant_url:
        return b_name, data, fallback_map

    try:
        time.sleep(random.uniform(1.0, 2.2))
        res = cffi_requests.get(restaurant_url, impersonate="chrome120", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')

        # LAYER 1: ZOMATO HIDDEN JSON
        next_data = soup.find('script', id='__NEXT_DATA__')
        if next_data and next_data.string:
            try:
                json_str = next_data.string
                phone_matches = re.findall(r'"phoneStr"\s*:\s*"([^"]+)"', json_str)
                if phone_matches:
                    clean_phones = [p.replace('+', '').replace('-', '').strip() for p in phone_matches]
                    data["phone"] = ", ".join(list(set(clean_phones)))

                fssai_matches = re.findall(r'"fssai"\s*:\s*\{.*?"licenseText"\s*:\s*"([^"]+)"', json_str)
                if fssai_matches:
                    data["fssai"] = re.sub(r'[^0-9]', '', fssai_matches[0])
                else:
                    raw_fssai = re.findall(r'[12]\d{13}', json_str)
                    valid_fssai = [f for f in raw_fssai if f != "16666666666666"]
                    if valid_fssai:
                        data["fssai"] = valid_fssai[0]

                lat_match = re.search(r'"latitude"\s*:\s*"([^"]+)"', json_str)
                lon_match = re.search(r'"longitude"\s*:\s*"([^"]+)"', json_str)
                if lat_match and lon_match:
                    data["map_url"] = f"https://www.google.com/maps/dir/?api=1&destination={lat_match.group(1)},{lon_match.group(1)}"

                photo_match = re.search(r'"thumb"\s*:\s*\[\s*\{\s*"url"\s*:\s*"([^"]+)"', json_str)
                if photo_match:
                    data["photo_url"] = photo_match.group(1).replace("\\/", "/")

                rating_match = re.findall(r'"rating_text"\s*:\s*"([^"]+)"', json_str)
                if len(rating_match) >= 1:
                    data["dining_rating"] = rating_match[0]
                if len(rating_match) >= 2:
                    data["delivery_rating"] = rating_match[1]
            except Exception:
                pass

        # LAYER 2: HTML FALLBACK
        if data["phone"] == "Not Available" or "7515979971" in data["phone"]:
            phone_elements = soup.find_all('a', href=lambda href: href and href.startswith('tel:'))
            if phone_elements:
                phones = list(set([el['href'].replace('tel:', '').replace('+', '').strip() for el in phone_elements]))
                data["phone"] = ", ".join(phones)

        if data["map_url"] == "Not Available":
            map_element = soup.find('a', href=lambda href: href and 'google.com/maps' in href)
            if map_element:
                data["map_url"] = map_element['href']

        if data["photo_url"] == "Not Available":
            meta_img = soup.find('meta', property='og:image')
            if meta_img and meta_img.get('content'):
                data["photo_url"] = meta_img['content']

    except Exception:
        pass

    # THE PURIFIER
    if "7515979971" in data["phone"]:
        data["phone"] = "Not Available"
    if data["fssai"] == "16666666666666":
        data["fssai"] = "Not Available"

    return b_name, data, fallback_map

def get_zone_html_with_scroll(url):
    """Headless Firefox Auto-Scroll with Smart Stop"""
    html_content = ""
    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
            )
            page = context.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

            last_height = page.evaluate("document.body.scrollHeight")
            no_change_count = 0

            for _ in range(35):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2.2)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 2:
                        break
                else:
                    no_change_count = 0
                last_height = new_height

            html_content = page.content()
            browser.close()
    except Exception as e:
        print(f"⚠️ Playwright Scrolling error on {url}: {e}")
    return html_content

def run_cloud_zomato():
    if not DATABASE_URL:
        print("❌ DATABASE_URL missing hai!")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Ensure optional rating/photo columns exist in Neon leads table
    cur.execute("""
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS dining_rating VARCHAR,
        ADD COLUMN IF NOT EXISTS delivery_rating VARCHAR,
        ADD COLUMN IF NOT EXISTS photo_url VARCHAR;
    """)
    conn.commit()

    # Atomic Zone Lock: Parallel runners aapas me kabhi ek zone nahi uthayenge
    cur.execute("""
        WITH claimed AS (
            SELECT id
            FROM zones
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE zones
        SET status = 'processing', updated_at = CURRENT_TIMESTAMP
        FROM claimed
        WHERE zones.id = claimed.id
        RETURNING zones.id, zones.city, zones.base_url, zones.zone_slug;
    """, (ZONES_PER_RUN,))
    claimed_zones = cur.fetchall()
    conn.commit()

    if not claimed_zones:
        print("🎉 Saare zones complete ho chuke hain! Koi pending zone nahi bacha.")
        cur.close()
        conn.close()
        return

    # Existing businesses in memory for fast skip
    cur.execute("SELECT business_name FROM leads;")
    global_seen = {normalize_name(r[0]) for r in cur.fetchall() if r[0]}
    print(f"🛡️ Cloud Shield Active: {len(global_seen)} existing businesses loaded.")

    for zone_id, city, base_url, zone_slug in claimed_zones:
        page_url = f"https://www.zomato.com/{base_url}/{zone_slug}-restaurants"
        print(f"\n🌍 Scanning [{city}] -> {zone_slug.upper()} ...")

        raw_html = get_zone_html_with_scroll(page_url)
        if not raw_html:
            cur.execute("UPDATE zones SET status = 'pending' WHERE id = %s;", (zone_id,))
            conn.commit()
            continue

        soup = BeautifulSoup(raw_html, 'html.parser')
        scraped_leads = []
        local_seen = set()

        for item in soup.find_all('h4'):
            b_name = item.text.strip()
            if not b_name or len(b_name) < 3 or "Zomato" in b_name:
                continue

            norm_name = normalize_name(b_name)
            if norm_name in global_seen or norm_name in local_seen:
                continue
            local_seen.add(norm_name)

            parent_a = item.find_parent('a')
            res_url = ""
            if parent_a and 'href' in parent_a.attrs:
                href = parent_a['href'].split('?')[0]
                res_url = href if href.startswith("http") else "https://www.zomato.com" + href

            fallback_map = f"https://www.google.com/maps/search/{b_name.replace(' ', '+')}+{city.replace(' ', '+')}"
            scraped_leads.append({
                "business_name": b_name,
                "restaurant_url": res_url,
                "fallback_map": fallback_map
            })

        print(f"🎯 {len(scraped_leads)} naye restaurants mile {zone_slug} me. Deep extracting...")

        saved_in_zone = 0
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(extract_deep_details, lead) for lead in scraped_leads]
            for future in as_completed(futures):
                try:
                    b_name, deep_data, fallback_map = future.result()
                    has_wa, final_contact = check_whatsapp_status(deep_data["phone"])
                    final_map = deep_data["map_url"] if deep_data["map_url"] != "Not Available" else fallback_map
                    clean_lic = None if deep_data["fssai"] in ("Not Available", "", None) else deep_data["fssai"]

                    cur.execute("""
                        INSERT INTO leads (
                            business_name, phone, has_whatsapp, fssai_name, licence_no,
                            location, city, dining_rating, delivery_rating, photo_url, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'raw')
                        ON CONFLICT (licence_no) DO NOTHING;
                    """, (
                        b_name, final_contact, has_wa, b_name, clean_lic,
                        final_map, city, deep_data["dining_rating"], deep_data["delivery_rating"],
                        deep_data["photo_url"]
                    ))
                    conn.commit()
                    global_seen.add(normalize_name(b_name))
                    saved_in_zone += 1
                    print(f"✅ [{city}] {b_name[:20]} | 📞 {final_contact[:12]} | ⭐ {deep_data['dining_rating']}")
                except Exception as e:
                    print(f"⚠️ Insert error: {e}")
                    conn.rollback()

        cur.execute("""
            UPDATE zones
            SET status = 'completed', leads_found = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (saved_in_zone, zone_id))
        conn.commit()
        print(f"🏁 Zone {zone_slug} completed! ({saved_in_zone} new raw leads added)")
        time.sleep(random.uniform(3.0, 5.0))

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_cloud_zomato()