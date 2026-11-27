import pg_compat
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
import sqlite3
import uuid
import random
import hashlib
import os
import csv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from cashfree_service import create_cashfree_order
import firebase_admin
from firebase_admin import credentials, messaging

# Firebase Admin Setup
try:
    cred = credentials.Certificate("firebase_credentials.json")
except Exception as fb_err:
    print("Firebase init skipped:", fb_err)
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Firebase app init skipped:", e)

class TokenRequest(BaseModel):
    user_id: str
    fcm_token: str

app = FastAPI(title="OreDial Vault API")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Serve Proof Images
os.makedirs("proof_uploads", exist_ok=True)
app.mount("/proofs", StaticFiles(directory="proof_uploads"), name="proofs")

# ================= FOMO MESSAGES (PREMIUM B2B WITH EMOJIS) =================
FOMO_MESSAGES = [
    "🚀 Growth doesn't wait! You have {credits} premium credits 💳 ready to unlock high-value B2B contacts 🏢. Connect with your next big client 🤝 in the next {days} days ⏳.",
    "💼 Turn connections into revenue 💸. Your OreDial vault 🏦 has {credits} credits waiting. Unlock 100% verified vendors today! ✅ (Valid for {days} days 📅).",
    "📈 Ready to scale? 🚀 Put your {credits} credits to work today 💼. Expand your business network 🌐 before they expire in {days} days ⏰.",
    "🎯 Your next high-ticket deal 💰 is just a tap away 👆. Use your {credits} credits to access exclusive business owners 👔. (Validity: {days} days ⏳).",
    "🤝 Smart businesses act fast ⚡. You have {credits} premium credits 💳 to build new B2B relationships 📈. Tap to explore today! 🔍 (Expires in {days} days 🔔).",
    "🔔 Fresh B2B opportunities just landed! 🛬 Use your {credits} credits to connect with newly verified buyers today 🤝. (Credits valid for {days} days 📅).",
    "💎 Quality leads = Higher conversions 📈. Tap into OreDial’s premium FSSAI-verified database 📜 with your {credits} credits 🪙. Available for {days} more days ⏳.",
    "👑 Exclusive access activated 🔓. Use your {credits} credits to unlock 'Golden Tag' 🌟 premium vendors today 🏬. (Don't miss out, valid for {days} days ⏰).",
    "📊 Stay ahead of the market 🏃‍♂️💨. Your competitors are searching for these vendors 🕵️‍♂️. Claim them first 🥇 with your {credits} credits! ({days} days left ⏳).",
    "🌐 The market is highly active today 📈. Your {credits} unused credits 💳 give you a direct line 📞 to verified founders 👔. (Valid for {days} days 📅).",
    "☕ Morning Strategy: Start your day 🌅 by unlocking a new business relationship 🤝. You have {credits} credits available 🪙 for the next {days} days ⏰.",
    "⚡ Maximize your OreDial advantage 🚀. Your {credits} credits are waiting to be converted into real business growth 📈. Put them to work in the next {days} days! ⏳",
    "🧠 Your business growth is in your hands 🤲. You have the data 📊, you have {credits} credits 💳. Close your next deal today 🤝. (Expires in {days} days ⏰).",
    "📋 Account Update: Your premium lead access is active ✅. {credits} credits 🪙 are ready to boost your sales pipeline 🚀. Make your move within {days} days! ⏳",
    "🏆 Top vendors are waiting for your call 📞. Don't leave your {credits} credits unused 💸. Tap here 👆 to lock your premium leads before the next {days} days ⏳."
]

# ================= DATA MODELS =================
class OrderRequest(BaseModel): amount: float; customer_phone: str; customer_email: str
class UnlockRequest(BaseModel): user_id: int; lead_id: int
class FlagRequest(BaseModel): user_id: int; lead_id: int; reason: str  
class PaymentSuccessRequest(BaseModel): user_id: int; credits_to_add: int
class ResolveFlagRequest(BaseModel): lead_id: int; user_id: int; action: str  
class SignupInitRequest(BaseModel): identifier: str; password: str
class OtpVerifyRequest(BaseModel): identifier: str; otp: str
class LoginRequest(BaseModel): email: str; password: str
class ForgotPasswordRequest(BaseModel): identifier: str
class VerifyVendorRequest(BaseModel): lead_id: int; action: str
class HeartbeatRequest(BaseModel): phone: str

# ================= DATABASE SETUP & CRASH PREVENTION =================
def hash_password(password: str): return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, credits REAL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS unlocked_leads (
        user_id INTEGER, lead_id INTEGER, PRIMARY KEY (user_id, lead_id)
    )''')
    
    # Updated Core Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        business_name TEXT, phone TEXT, fssai_name TEXT, licence_no TEXT, 
        location TEXT, city TEXT, instagram TEXT, facebook TEXT, 
        is_golden_tag BOOLEAN, has_whatsapp BOOLEAN
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT, is_read BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Safely add any missing columns (Crash Prevention)
    safe_columns = {
        "status": "TEXT DEFAULT 'Active'",
        "category": "TEXT DEFAULT ''",
        "proof_url": "TEXT DEFAULT ''",
        "is_self_listed": "BOOLEAN DEFAULT 0",
        "last_heartbeat": "DATETIME",
        "fssai_name": "TEXT DEFAULT ''",
        "licence_no": "TEXT DEFAULT ''",
        "instagram": "TEXT DEFAULT ''",
        "facebook": "TEXT DEFAULT ''",
        "has_whatsapp": "BOOLEAN DEFAULT 0"
    }
    for col, col_type in safe_columns.items():
        try: cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_type}")
        except: pass

    try: cursor.execute("ALTER TABLE users ADD COLUMN credit_expiry DATETIME")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN fcm_token TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN session_token TEXT DEFAULT ''")
    except: pass

    # Dummy Admin Setup
    cursor.execute("SELECT * FROM users WHERE id=1")
    if not cursor.fetchone():
        dummy_pw = hash_password("admin123")
        future_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO users (id, email, password, credits, credit_expiry) VALUES (1, 'client@oredial.com', ?, 1111.0, ?)", (dummy_pw, future_date))

    conn.commit()
    conn.close()

init_db()

# ================= DYNAMIC PRICING ENGINE =================
def calculate_lead_price(has_whatsapp, instagram, facebook):
    cost = 1.5 # Base Strategy: Contact + Map + Business Name
    if has_whatsapp: 
        cost += 0.3
    
    ig = str(instagram).lower()
    if ig and ig not in ["n/a", "false", "not available", "none", ""]: 
        cost += 0.6
        
    fb = str(facebook).lower()
    if fb and fb not in ["n/a", "false", "not available", "none", ""]: 
        cost += 0.9
        
    return round(cost, 2)


# ================= THE 90-DAY FOMO ENGINE (WITH FIREBASE PUSH) =================
def run_fomo_engine():
    print(f"[{datetime.now()}] 🚀 FOMO Engine Started: Checking Expiries & Sending Pushes...")
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, credits, credit_expiry, fcm_token FROM users WHERE credits > 0 AND credit_expiry IS NOT NULL")
    users = cursor.fetchall()
    
    notifications_sent = 0
    for user in users:
        user_id, credits, expiry_str, fcm_token = user[0], user[1], user[2], user[3]
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        days_left = (expiry_date - datetime.now()).days
        
        if 0 < days_left <= 90:
            msg_template = random.choice(FOMO_MESSAGES)
            final_msg = msg_template.replace("{credits}", str(int(credits))).replace("{days}", str(days_left))
            
            cursor.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (user_id, final_msg))
            
            if fcm_token and len(fcm_token) > 10:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title="OreDial Alert 🚨",
                            body=final_msg
                        ),
                        token=fcm_token,
                    )
                    messaging.send(message)
                    print(f"📲 Push sent to User {user_id}")
                except Exception as e:
                    print(f"❌ Failed to push for User {user_id}: {str(e)}")
            
            notifications_sent += 1
            print(f"➡️ FOMO DB Alert logged for User {user_id}: {days_left} days left.")

    conn.commit()
    conn.close()
    print(f"✅ FOMO Engine Finished: {notifications_sent} users processed!")

# Start the Alarm Clock 
scheduler = BackgroundScheduler()
scheduler.add_job(run_fomo_engine, 'cron', hour=9, minute=30)
scheduler.start()

@app.post("/api/admin/trigger-fomo")
def trigger_fomo():
    run_fomo_engine()
    return {"status": "success", "message": "FOMO Engine triggered manually! Check terminal or DB."}

@app.get("/api/notifications/{user_id}")
def get_notifications(user_id: int):
    conn = pg_compat.connect("oredial.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,))
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"notifications": data}

# ================= FCM TOKEN SAVER =================
@app.post("/api/save-token")
async def save_token(req: TokenRequest):
    print(f"✅ Token received for User ID [{req.user_id}]: {req.fcm_token[:20]}...")
    
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET fcm_token = ? WHERE id = ?", (req.fcm_token, req.user_id))
    conn.commit()
    conn.close()
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title="🔔 OreDial Connected",
                body="Push notifications are now active. You'll receive credit expiry alerts here!"
            ),
            token=req.fcm_token,
        )
        messaging.send(message)
    except Exception as e:
        print("❌ Notification error:", e)

    return {"message": "Token saved in DB and connection tested!"}

# ================= VENDOR REGISTRATION & HEARTBEAT APIs =================
@app.post("/api/vendor/register")
async def register_vendor(
    business_name: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    phone: str = Form(...),
    fssai_number: str = Form(...),
    proof_file: UploadFile = File(...)
):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM leads WHERE phone=?", (phone,))
        if cursor.fetchone(): raise HTTPException(status_code=400, detail="Yeh number already registered hai.")

        os.makedirs("proof_uploads", exist_ok=True)
        file_ext = proof_file.filename.split(".")[-1]
        filename = f"{uuid.uuid4().hex[:8]}.{file_ext}"
        file_path = f"proof_uploads/{filename}"
        
        with open(file_path, "wb") as f: f.write(await proof_file.read())

        cursor.execute('''INSERT INTO leads 
            (business_name, category, location, city, is_golden_tag, status, phone, proof_url, is_self_listed, last_heartbeat, fssai_name)
            VALUES (?, ?, ?, 'Ghaziabad', 0, 'Pending Verification', ?, ?, 1, CURRENT_TIMESTAMP, ?)''',
            (business_name.title(), category, location, phone, file_path, fssai_number))
            
        conn.commit()
        return {"status": "success", "message": "Business Details submitted! Please wait for Admin Verification."}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail=str(e))
    finally: conn.close()

@app.post("/api/vendor/heartbeat")
def vendor_heartbeat(req: HeartbeatRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE leads SET last_heartbeat = CURRENT_TIMESTAMP, status='Active' WHERE phone=? AND is_self_listed=1", (req.phone,))
        if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Vendor not found or not self-listed.")
        conn.commit()
        return {"status": "success", "message": "Heartbeat updated! You are safe for the next 7 days."}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail="Error updating heartbeat.")
    finally: conn.close()

# ================= ADMIN PANEL APIs =================
@app.post("/api/flag-lead")
def flag_lead(req: FlagRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        new_status = f"Under Review: {req.reason}"
        cursor.execute("UPDATE leads SET status=? WHERE id=?", (new_status, req.lead_id))
        conn.commit()
        return {"status": "success", "message": "Issue reported! Admins will check within 24 hours."}
    except Exception: conn.rollback(); raise HTTPException(status_code=500, detail="System Error")
    finally: conn.close()

@app.get("/api/admin/flagged-leads")
def get_flagged_leads():
    conn = pg_compat.connect("oredial.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE status LIKE 'Under Review%' OR status = 'Pending Verification'")
    flagged_leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"flagged_leads": flagged_leads}

@app.post("/api/admin/resolve-flag")
def resolve_flag(req: ResolveFlagRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT has_whatsapp, instagram, facebook, status FROM leads WHERE id=?", (req.lead_id,))
        lead = cursor.fetchone()
        if not lead: raise HTTPException(status_code=404, detail="Lead nahi mili")
        
        hw, ig, fb, status = lead
        refund_amount = calculate_lead_price(hw, ig, fb) # Dynamic Refund
        
        if status == 'Pending Verification' and req.action == 'approve':
            cursor.execute("UPDATE leads SET status='Active', last_heartbeat=CURRENT_TIMESTAMP WHERE id=?", (req.lead_id,))
            message = "New Business Verified & Live in Market!"
        elif req.action == "refund" or req.action == "reject_vendor":
            cursor.execute("UPDATE users SET credits = credits + ? WHERE id=?", (refund_amount, req.user_id))
            cursor.execute("DELETE FROM leads WHERE id=?", (req.lead_id,))
            cursor.execute("DELETE FROM unlocked_leads WHERE lead_id=?", (req.lead_id,))
            message = "Lead Deleted permanently and credits refunded."
        else:
            cursor.execute("UPDATE leads SET status='Active' WHERE id=?", (req.lead_id,))
            message = "Complaint rejected. Lead is active again."
            
        conn.commit()
        return {"status": "success", "message": message}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail="Error in resolving flag")
    finally: conn.close()

# ================= DASHBOARD & LEAD APIs =================
@app.get("/api/dashboard/{user_id}")
def get_dashboard_data(user_id: int):
    conn = pg_compat.connect("oredial.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT credits FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if not user: 
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    cursor.execute("SELECT lead_id FROM unlocked_leads WHERE user_id=?", (user_id,))
    unlocked_ids = [row["lead_id"] for row in cursor.fetchall()]

    cursor.execute("SELECT id, business_name, phone, city, location, category, status, has_whatsapp, instagram, facebook, is_golden_tag FROM leads WHERE status IN ('enriched', 'Active', 'raw') ORDER BY (CASE WHEN status='enriched' THEN 0 ELSE 1 END), id DESC")
    leads_data = []
    
    for row in cursor.fetchall():
        lead = dict(row)
        is_unlocked = lead["id"] in unlocked_ids
        lead["is_unlocked"] = is_unlocked
        
        if not is_unlocked and lead.get("status", "Active") not in ("Active", "enriched", "raw"):
            continue

        lead["name"] = lead.get("business_name", "")
        lead["phone_number"] = lead.get("phone", "")
        lead["is_golden_tag"] = bool(lead.get("is_golden_tag", 0))
        lead["has_whatsapp"] = bool(lead.get("has_whatsapp", 0) or lead.get("phone", ""))
        
        # 🚀 Frontend UI Categories aur Icons Fix
        lead["category"] = lead.get("category", "Other")
        
        ig_val = str(lead.get("instagram", "")).lower()
        fb_val = str(lead.get("facebook", "")).lower()
        lead["has_ig"] = bool(ig_val and ig_val not in ["not available", "n/a", "false", "none", ""])
        lead["has_fb"] = bool(fb_val and fb_val not in ["not available", "n/a", "false", "none", ""])
        lead["instagram_url"] = lead.get("instagram", "")
        lead["facebook_url"] = lead.get("facebook", "")
        lead["map_url"] = lead.get("location", "")
        # Dynamic Cost injection for Frontend
        lead["credit_cost"] = calculate_lead_price(lead.get("has_whatsapp"), lead.get("instagram"), lead.get("facebook"))

        if not is_unlocked:
            if lead.get("phone_number"): 
                lead["phone_number"] = str(lead["phone_number"])[:5] + "XXXXX"
            if lead.get("name"):
                words = lead["name"].strip().split(" ")
                if len(words) > 1:
                    words[-1] = "***"
                    lead["name"] = " ".join(words)
                else:
                    half = max(1, len(lead["name"]) // 2)
                    lead["name"] = lead["name"][:half] + "***"
            city_name = lead.get("city", "Unknown City")
            lead["location"] = f"{city_name} (Address Hidden)"
            
        leads_data.append(lead)

    conn.close()
    return {"credits_left": user["credits"], "leads": leads_data}

@app.post("/api/unlock")
@limiter.limit("5/minute")
def unlock_lead(request: Request, req: UnlockRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM unlocked_leads WHERE user_id=? AND lead_id=?", (req.user_id, req.lead_id))
        if cursor.fetchone(): return {"status": "already_unlocked", "message": "Lead was already downloaded. 0 credits deducted."}

        cursor.execute("SELECT has_whatsapp, instagram, facebook FROM leads WHERE id=?", (req.lead_id,))
        lead_data = cursor.fetchone()
        if not lead_data: raise HTTPException(status_code=404, detail="Lead not found")
        
        hw, ig, fb = lead_data
        actual_cost = calculate_lead_price(hw, ig, fb) # 🚀 Dynamic Cost Deduction

        cursor.execute("SELECT credits FROM users WHERE id=?", (req.user_id,))
        user = cursor.fetchone()
        if not user or user[0] < actual_cost: raise HTTPException(status_code=400, detail="Not enough credits! Please top up.")

        cursor.execute("UPDATE users SET credits = credits - ? WHERE id=?", (actual_cost, req.user_id))
        cursor.execute("INSERT INTO unlocked_leads (user_id, lead_id) VALUES (?, ?)", (req.user_id, req.lead_id))

        cursor.execute("SELECT phone FROM leads WHERE id=?", (req.lead_id,))
        phone_row = cursor.fetchone()
        phone = phone_row[0] if phone_row else "NOT_FOUND"

        conn.commit()
        return {"status": "success", "message": f"Lead unlocked! {actual_cost} credits deducted.", "phone": phone}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail="System Error")
    finally: conn.close()

@app.delete("/api/vault/remove/{user_id}/{lead_id}")
def remove_from_vault(user_id: int, lead_id: int):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM unlocked_leads WHERE user_id=? AND lead_id=?", (user_id, lead_id))
        conn.commit()
        return {"status": "success", "message": "Lead permanently removed from your Vault."}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail="Error removing lead.")
    finally: conn.close()

# ================= SMART CATEGORIZATION ENGINE =================
def smart_categorize(business_name: str, raw_category: str = "") -> str:
    if raw_category and raw_category.strip() and raw_category.lower() not in ["other", "food business", "fssai", ""]:
        return raw_category.strip().title()

    name = business_name.lower().strip()
    restaurant_keywords = ["restaurant", "dhaba", "bhojnalaya", "rasoi", "mess", "caterers", "caterer", "kitchen", "dine", "dining", "palace", "garden", "family", "delight", "bite", "food joint", "hub", "point", "corner", "junction", "treat", "bar & restaurant"]
    cafe_keywords = ["cafe", "coffee", "espresso", "brew", "roasters", "burger", "pizza", "bakery", "bakers", "confectionery", "cake", "pastry", "rolls", "wraps", "momos", "fast food", "snack", "snacks", "shakes", "juice", "beverages", "tea", "chai", "pizzeria"]
    sweets_keywords = ["sweets", "mithai", "namkeen", "dairy", "milk", "kulfi", "ice cream", "halwai", "chat", "chaat", "panipuri", "gola", "bhandar", "misthan"]
    cloud_keywords = ["cloud", "delivery", "tiffin", "online", "ghost", "kitchenette", "home cooked", "homemade"]

    for kw in sweets_keywords:
        if kw in name: return "Sweets & Confectionery"
    for kw in cafe_keywords:
        if kw in name: return "Cafe & Fast Food"
    for kw in cloud_keywords:
        if kw in name: return "Cloud Kitchen & Tiffin"
    for kw in restaurant_keywords:
        if kw in name: return "Restaurant & Dining"
    if "food" in name or "eat" in name or "taste" in name or "palace" in name: return "Restaurant & Dining"
    return "Restaurant & Dining"

# ================= CSV BULK UPLOADER =================
@app.post("/api/admin/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    try:
        contents = await file.read()
        decoded = contents.decode("utf-8", errors="ignore")
        reader = csv.DictReader(decoded.splitlines())
        count = 0
        for row in reader:
            b_name = row.get("business_name") or row.get("name") or "Unknown"
            phone = row.get("contact") or row.get("phone") or "Not Available"
            fssai_name = row.get("fssai_name", "")
            lic_no = row.get("licence_no", "")
            loc = row.get("map_location") or row.get("location") or "Ghaziabad"
            city = row.get("city", "Ghaziabad")
            instagram = row.get("instagram", "")
            facebook = row.get("facebook", "")
            has_whatsapp = 1 if str(row.get("has_whatsapp", "0")).lower() in ["true", "1", "yes"] else 0
            raw_cat = row.get("category") or ""
            final_category = smart_categorize(b_name, raw_cat)

            cursor.execute('''INSERT INTO leads 
                (business_name, category, phone, fssai_name, licence_no, location, city, instagram, facebook, is_golden_tag, has_whatsapp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'Active')''',
                (b_name, final_category, phone, fssai_name, lic_no, loc, city, instagram, facebook, has_whatsapp))
            count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Boom! 🚀 {count} leads uploaded successfully!"}
    except Exception as e: conn.rollback(); raise HTTPException(status_code=500, detail=f"Upload Error: {str(e)}")
    finally: conn.close()
    
# ================= CASHFREE PAYMENTS =================
@app.post("/create-order")
def create_order(req: OrderRequest):
    order_id = f"ORDER_{uuid.uuid4().hex[:8].upper()}"
    customer_id = f"CUST_{uuid.uuid4().hex[:8].upper()}"
    try:
        response = create_cashfree_order(order_id=order_id, amount=req.amount, customer_id=customer_id, customer_phone=req.customer_phone, customer_email=req.customer_email)
        return response
    except Exception as e: raise HTTPException(status_code=500, detail=f"Payment Gateway Error: {str(e)}")

@app.post("/api/payment-success")
def payment_success(req: PaymentSuccessRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    new_expiry = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE users SET credits = credits + ?, credit_expiry = ? WHERE id = ?", (req.credits_to_add, new_expiry, req.user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"{req.credits_to_add} Credits added! Validity extended to 90 days."}

# ================= AUTHENTICATION APIs =================
otp_storage = {}
@app.post("/api/auth/signup-request")
def signup_request(req: SignupInitRequest):
    is_email = "@" in req.identifier and "." in req.identifier.split("@")[-1]
    is_phone = req.identifier.isdigit() and len(req.identifier) == 10
    if not is_email and not is_phone: raise HTTPException(status_code=400, detail="Please enter a valid Email or 10-digit Mobile Number.")
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=?", (req.identifier,))
    if cursor.fetchone(): conn.close(); raise HTTPException(status_code=400, detail="Yeh account already registered hai. Log in karo.")
    conn.close()
    generated_otp = str(random.randint(100000, 999999))
    otp_storage[req.identifier] = {"otp": generated_otp, "password": hash_password(req.password)}
    return {"status": "success", "message": "OTP sent.", "debug_otp": generated_otp}

@app.post("/api/auth/verify-otp")
def verify_otp(req: OtpVerifyRequest):
    record = otp_storage.get(req.identifier)
    if not record or record["otp"] != req.otp: raise HTTPException(status_code=400, detail="Invalid or expired OTP.")
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    expiry_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO users (email, password, credits, credit_expiry) VALUES (?, ?, ?, ?)", 
                   (req.identifier, record["password"], 5.0, expiry_date))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    del otp_storage[req.identifier]
    return {"status": "success", "user_id": user_id, "credits": 5.0}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    hashed_pw = hash_password(req.password)
    
    cursor.execute("SELECT id, credits FROM users WHERE email=? AND password=?", (req.email, hashed_pw))
    user = cursor.fetchone()
    
    if not user: 
        conn.close() 
        raise HTTPException(status_code=401, detail="Galat Email/Mobile ya Password!")
        
    new_token = str(uuid.uuid4())
    
    try:
        cursor.execute("UPDATE users SET session_token=? WHERE id=?", (new_token, user[0]))
        conn.commit()
    except Exception as e:
        print("Token save error:", e)
        
    conn.close()
    
    return {"status": "success", "user_id": user[0], "credits": user[1], "session_token": new_token}

@app.get("/api/city-counts")
def get_city_counts():
    conn = pg_compat.connect("oredial.db")
    cursor = conn.cursor()
    
    # Har city ke hisab se active leads count karo
    cursor.execute("SELECT city, COUNT(*) FROM leads WHERE status IN ('Active', 'enriched', 'raw') GROUP BY city")
    rows = cursor.fetchall()
    
    counts = {}
    noida_total = 0
    haryana_total = 0
    for r in rows:
        c = (r["city"] or "").strip() if isinstance(r, dict) else (r[0] or "").strip()
        cnt = int((r["count"] if isinstance(r, dict) else r[1]) or 0)
        cl = c.lower()
        if "noida" in cl:
            noida_total += cnt
        elif "ghaziabad" in cl:
            counts["Ghaziabad"] = counts.get("Ghaziabad", 0) + cnt
        elif "delhi" in cl:
            counts["Delhi"] = counts.get("Delhi", 0) + cnt
        elif "gurugram" in cl or "gurgaon" in cl:
            counts["Gurugram"] = counts.get("Gurugram", 0) + cnt
            haryana_total += cnt
        elif "meerut" in cl:
            counts["Meerut"] = counts.get("Meerut", 0) + cnt
        elif "faridabad" in cl or "haryana" in cl:
            haryana_total += cnt
        elif c:
            counts[c] = counts.get(c, 0) + cnt
    counts["Noida"] = noida_total
    counts["Noida / Greater Noida"] = noida_total
    counts["Haryana"] = haryana_total
        
    conn.close()
    return {"city_counts": counts}