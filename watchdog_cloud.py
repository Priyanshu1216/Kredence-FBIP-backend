import os
import time
import random
import psycopg2
from curl_cffi import requests as cffi_requests
from ddgs import DDGS
from concurrent.futures import ThreadPoolExecutor, as_completed

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("psql "):
    DATABASE_URL = DATABASE_URL[5:].strip()
DATABASE_URL = DATABASE_URL.strip("'\"")

VERIFY_BATCH_SIZE = 180   # Har run me 180 leads verify hongi (~4-5 mins)
MAX_WORKERS = 5

CLOSED_MARKERS = [
    "permanently closed",
    "temporarily closed",
    "does not exist",
    "page not found",
    "we couldn't find the page"
]

def find_zomato_url(business_name, city):
    try:
        query = f'site:zomato.com "{business_name}" "{city}"'
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                href = r.get("href", "")
                if "zomato.com/" in href and "/restaurants" not in href:
                    return href.split("?")[0]
    except Exception:
        pass
    return ""

def verify_lead_on_zomato(lead):
    lead_id, b_name, city, zomato_url = lead
    time.sleep(random.uniform(0.5, 1.5))

    target_url = zomato_url or find_zomato_url(b_name, city)
    if not target_url:
        return lead_id, b_name, "keep", ""

    try:
        res = cffi_requests.get(target_url, impersonate="chrome120", timeout=15)
        if res.status_code == 404:
            return lead_id, b_name, "delete", target_url

        if res.status_code == 200:
            page_lower = res.text.lower()
            for marker in CLOSED_MARKERS:
                if marker in page_lower:
                    return lead_id, b_name, "delete", target_url
            return lead_id, b_name, "keep", target_url

    except Exception:
        pass

    return lead_id, b_name, "keep", target_url

def run_watchdog():
    if not DATABASE_URL:
        print("❌ DATABASE_URL missing hai!")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS zomato_url VARCHAR,
        ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """)
    conn.commit()

    # 1. Self-Healing: Reset stuck 'processing' zones & leads (> 2 hours)
    cur.execute("""
        UPDATE zones
        SET status = 'pending', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'processing'
          AND updated_at < CURRENT_TIMESTAMP - INTERVAL '2 hours';
    """)
    stuck_zones = cur.rowcount

    cur.execute("""
        UPDATE leads
        SET status = 'raw', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'processing'
          AND updated_at < CURRENT_TIMESTAMP - INTERVAL '2 hours';
    """)
    stuck_leads = cur.rowcount
    conn.commit()
    print(f"🛠️ Self-Healing: {stuck_zones} stuck zones aur {stuck_leads} stuck leads reset hui.")

    # 2. 48-Hr Zomato Live Verification & Closed-Lead Cleanup
    cur.execute("""
        SELECT id, business_name, city, COALESCE(zomato_url, '')
        FROM leads
        WHERE last_verified_at IS NULL
           OR last_verified_at < CURRENT_TIMESTAMP - INTERVAL '48 hours'
        ORDER BY last_verified_at ASC NULLS FIRST
        LIMIT %s;
    """, (VERIFY_BATCH_SIZE,))
    leads_to_check = cur.fetchall()

    deleted_count = 0
    verified_count = 0

    if leads_to_check:
        print(f"🔍 {len(leads_to_check)} leads ka 48-hr Zomato live status check shuru...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(verify_lead_on_zomato, l) for l in leads_to_check]
            for future in as_completed(futures):
                try:
                    lead_id, b_name, action, resolved_url = future.result()
                    if action == "delete":
                        cur.execute("DELETE FROM leads WHERE id = %s;", (lead_id,))
                        deleted_count += 1
                        print(f"🗑️ Deleted (Closed on Zomato): {b_name[:30]}")
                    else:
                        cur.execute("""
                            UPDATE leads
                            SET last_verified_at = CURRENT_TIMESTAMP,
                                zomato_url = COALESCE(NULLIF(%s, ''), zomato_url)
                            WHERE id = %s;
                        """, (resolved_url, lead_id))
                        verified_count += 1
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Verify error: {e}")
                    conn.rollback()

    print(f"✅ Verification Done: {verified_count} active retained | {deleted_count} closed leads deleted.")

    # 3. 48-Hour Full Zone Re-Scan Trigger
    cur.execute("SELECT COUNT(*) FROM zones WHERE status != 'completed';")
    remaining_zones = cur.fetchone()[0]

    if remaining_zones == 0:
        cur.execute("""
            SELECT COUNT(*) FROM zones
            WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '48 hours';
        """)
        ready_for_rescan = cur.fetchone()[0]
        if ready_for_rescan > 0:
            cur.execute("""
                UPDATE zones
                SET status = 'pending', leads_found = 0, updated_at = CURRENT_TIMESTAMP;
            """)
            conn.commit()
            print("🔄 48-Hr Cycle Complete! Saari cities ke saare zones dubara scan ke liye 'pending' kar diye gaye hain.")

    cur.execute("SELECT status, COUNT(*) FROM zones GROUP BY status;")
    print("📊 ZONES:", cur.fetchall())
    cur.execute("SELECT status, COUNT(*) FROM leads GROUP BY status;")
    print("📊 LEADS:", cur.fetchall())

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_watchdog()
