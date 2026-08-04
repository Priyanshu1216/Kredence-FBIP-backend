
import requests
import csv

# 1. API Address (Seedha Render Cloud ka link daal diya hai)
BASE_URL = "http://127.0.0.1:8000"
# 2. Login karke Chabi (Token) nikalna
def get_admin_token():
    print("🔒 Logging into Kredence Bureau...")
    login_data = {
        "username": "admin@kredence.com", # Agar email alag banaya tha, toh yahan change kar lena
        "password": "12345678"            
    }
    response = requests.post(f"{BASE_URL}/api/v1/users/login", data=login_data)
    
    if response.status_code == 200:
        print("✅ Login Successful! Token received.")
        return response.json().get("access_token")
    else:
        print("❌ Login Failed! Check credentials.")
        return None

# 3. CSV File Padhna aur Data Daalna
def load_leads():
    token = get_admin_token()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}

    # YAHAN APNI CSV FILE KA NAAM LIKHNA HAI (Maine abhi 'data.csv' likha hai)
    csv_filename = "data.csv" 

    print(f"📂 Reading data from {csv_filename}...")
    
    try:
        # encoding="utf-8-sig" lagaya hai taaki excel file ke hidden characters error na dein
        with open(csv_filename, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            success_count = 0
            
            for row in reader:
                # Endpoint ko /api/v1/businesses/ update kar diya hai
                res = requests.post(f"{BASE_URL}/api/v1/businesses/", json=row, headers=headers)
                
                if res.status_code == 201 or res.status_code == 200:
                    success_count += 1
                    print(f"🟢 Business added: {row.get('email', 'Unknown')}")
                else:
                    print(f"🔴 Failed to add business: {res.text}")
                    
            print(f"🚀 Data Injection Complete! Successfully added {success_count} businesses.")
            
    except FileNotFoundError:
        print(f"⚠️ Error: '{csv_filename}' file nahi mili! CSV file ko VS Code ke left panel mein drag & drop karo.")

if __name__ == "__main__":
    load_leads()