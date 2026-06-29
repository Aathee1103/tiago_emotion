import os
import requests
import csv
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Configuration
LOG_FILE = "heart_rate.csv"

def get_valid_credentials():
    if not os.path.exists('token.json'):
        print("❌ Error: token.json not found.")
        return None
    creds = Credentials.from_authorized_user_file('token.json')
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return creds

def get_heart_rate_range(date_str, start_time, end_time):
    """
    date_str: "YYYY-MM-DD"
    start_time/end_time: "HH:MM"
    """
    creds = get_valid_credentials()
    if not creds: return

    # Helper: Convert provided Date + Time to UTC
    def to_utc(d_str, t_str):
        dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)

    utc_start = to_utc(date_str, start_time)
    utc_end = to_utc(date_str, end_time)

    url = "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints"
    time_filter = f"heart_rate.sample_time.physical_time >= \"{utc_start.isoformat().replace('+00:00', 'Z')}\" AND heart_rate.sample_time.physical_time < \"{utc_end.isoformat().replace('+00:00', 'Z')}\""
    
    # 1. Fetch ALL data using pagination
    params = {"filter": time_filter, "pageSize": "100"}
    headers = {"Authorization": f"Bearer {creds.token}"}
    
    all_data = []
    while True:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"❌ API Error {res.status_code}: {res.text}")
            return
        
        json_res = res.json()
        data = json_res.get("dataPoints", [])
        all_data.extend(data)
        
        page_token = json_res.get("nextPageToken")
        if not page_token:
            break
        params["pageToken"] = page_token

    if not all_data:
        print(f"⚠️ No data found on {date_str} between {start_time} and {end_time}.")
        return

    # 2. Prepare existing entries to prevent duplicates
    existing_timestamps = set()
    if os.path.isfile(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row: existing_timestamps.add(row[0])

    # 3. Write data to CSV
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp (Local)", "BPM"])
        
        print(f"\n📊 SAVING DATA ({date_str} {start_time} - {end_time}) TO {LOG_FILE}:")
        
        count = 0
        for p in reversed(all_data):
            bpm = p.get("heartRate", {}).get("beatsPerMinute")
            ts_raw = p.get("heartRate", {}).get("sampleTime", {}).get("physicalTime")
            
            ts_utc = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
            ts_local = ts_utc.astimezone(timezone(timedelta(hours=2))).strftime('%Y-%m-%d %H:%M:%S')
            
            if ts_local not in existing_timestamps:
                writer.writerow([ts_local, bpm])
                print(f" ↳ {ts_local} : {bpm} BPM")
                count += 1
                
        print(f"✅ Added {count} new entries.")

if __name__ == '__main__':
    # Usage: Date, Start Time, End Time
    get_heart_rate_range("2026-06-24", "14:54", "14:57")