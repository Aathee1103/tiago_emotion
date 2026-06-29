import os
import requests
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Configuration
LOG_FILE = "heart_rate.txt"

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
    creds = get_valid_credentials()
    if not creds: return

    # Convert provided Date + Time to UTC
    def to_utc(d_str, t_str):
        dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
        # Adjust 'hours=2' if your local time offset is different
        return dt.replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)

    utc_start = to_utc(date_str, start_time)
    utc_end = to_utc(date_str, end_time)

    url = "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints"
    time_filter = f"heart_rate.sample_time.physical_time >= \"{utc_start.isoformat().replace('+00:00', 'Z')}\" AND heart_rate.sample_time.physical_time < \"{utc_end.isoformat().replace('+00:00', 'Z')}\""
    
    # Fetch data
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
        if not page_token: break
        params["pageToken"] = page_token

    if not all_data:
        print(f"⚠️ No data found on {date_str} between {start_time} and {end_time}.")
        return

    # Load existing timestamps to avoid duplicates
    existing_timestamps = set()
    if os.path.isfile(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            for line in f:
                parts = line.split('\t')
                if len(parts) > 0: existing_timestamps.add(parts[0].strip())

    # Save to TXT
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if not file_exists:
            f.write("Timestamp (Local)\tBPM\n")
        
        print(f"\n📊 SAVING DATA TO {LOG_FILE}:")
        count = 0
        for p in reversed(all_data):
            bpm = p.get("heartRate", {}).get("beatsPerMinute")
            ts_raw = p.get("heartRate", {}).get("sampleTime", {}).get("physicalTime")
            
            ts_utc = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
            ts_local = ts_utc.astimezone(timezone(timedelta(hours=2))).strftime('%Y-%m-%d %H:%M:%S')
            
            if ts_local not in existing_timestamps:
                f.write(f"{ts_local}\t{bpm}\n")
                print(f" ↳ {ts_local} : {bpm} BPM")
                count += 1
        print(f"✅ Added {count} new entries.")

if __name__ == '__main__':
    # Usage: Date, Start Time, End Time
    get_heart_rate_range("2026-06-24", "14:54", "14:57")