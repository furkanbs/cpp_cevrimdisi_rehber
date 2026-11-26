import os
import re
import time
import json
import base64
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.w3schools.com/cpp/"
START_URL = urljoin(BASE_URL, "default.asp")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

IMG_CACHE = {}

def gorseli_gom(img_url: str) -> str:
    """Sayfadaki diyagramları Base64 olarak HTML içine gömer."""
    if img_url in IMG_CACHE:
        return IMG_CACHE[img_url]
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "image/png").split(";")[0]
        b64 = base64.b64encode(r.content).decode("ascii")
        data_uri = f"data:{ctype};base64,{b64}"
        IMG_CACHE[img_url] = data_uri
        return data_uri
    except Exception:
        IMG_CACHE[img_url] = ""
        return ""

def sol_menuyu_cek() -> list[dict]:
    """Sol menüdeki tüm ana kategorileri, dersleri ve ▼ alt menülerini eksiksiz toplar."""
    resp = requests.get(START_URL, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    menu_div = soup.find("div", id="leftmenuinnerinner")
    if not menu_div:
        raise RuntimeError("Sol menü bulunamadı.")

    kategoriler = []
    aktif_kat = {"kategori": "C++ TUTORIAL", "dersler": []}

    for eleman in menu_div.children:
        if not getattr(eleman, "name", None):
            continue

        if eleman.name == "h2":
            if aktif_kat["dersler"]:
                kategoriler.append(aktif_kat)
            aktif_kat = {"kategori": eleman.get_text(strip=True), "dersler": []}

        elif eleman.name == "a":
            href = eleman.get("href", "").strip()
            baslik = eleman.get_text(strip=True)
            if not href or href.startswith("javascript:") or "#" in href:
                continue
            tam_url = urljoin(BASE_URL, href)
            if "/cpp/" not in tam_url:
                continue
            aktif_kat["dersler"].append({
                "baslik": baslik,
                "url": tam_url,
                "alt_dersler": []
            })

        elif eleman.name == "div" and "tut_overview" in (eleman.get("class") or []):
            for sub_a in eleman.find_all("a"):
                sub_href = sub_a.get("href", "").strip()
                sub_baslik = sub_a.get_text(strip=True)
                if not sub_href or sub_href.startswith("javascript:") or "#" in sub_href:
                    continue
                sub_url = urljoin(BASE_URL, sub_href)
                if "/cpp/" not in sub_url:
                    continue

                if aktif_kat["dersler"]:
                    ust_ders = aktif_kat["dersler"][-1]
                    if sub_url != ust_ders["url"]:
                        ust_ders["alt_dersler"].append({
                            "baslik": sub_baslik,
                            "url": sub_url
                        })
                else:
                    aktif_kat["dersler"].append({
                        "baslik": sub_baslik,
                        "url": sub_url,
                        "alt_dersler": []
                    })

    if aktif_kat["dersler"]:
        kategoriler.append(aktif_kat)

    return kategoriler

def sayfa_icerigini_cek(url: str, bulunan_try_urlleri: set) -> str:
    """Ders sayfasının gövdesini temizler, Try butonlarının gerçek tam kod adreslerini bağlar."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    main_div = soup.find("div", id="main")
    if not main_div:
        return "<p>İçerik yüklenemedi.</p>"

    # 1) "Try it Yourself" bağlantılarını silinmeden önce yakalayıp özel butona çevir
    for a in main_div.find_all("a"):
        href = a.get("href", "").strip()
        text_lower = a.get_text(strip=True).lower()
        if (
            "try it yourself" in text_lower
            or "trycpp.asp" in href.lower()
            or "tryit.asp" in href.lower()
            or "showcpp.asp" in href.lower()
            or "filename=" in href.lower()
        ):
            try_url = urljoin(url, href)
            bulunan_try_urlleri.add(try_url)
            btn = soup.new_tag("button", **{"class": "try-btn", "data-try-url": try_url})
            btn.string = a.get_text(strip=True) or "Try it Yourself »"
            a.replace_with(btn)

    # 2) Reklamları, gereksiz butonları ve bannerları kaldır
    kaldirilacaklar = [
        ".nextprev", "#mainLeaderboard", "#midcontentadcontainer",
        "#user-profile-bottom-wrapper", "#mypagediv2", "#getdiploma",
        ".w3-btn", "script", "style", "iframe", "form"
    ]
    for secici in kaldirilacaklar:
        for tag in main_div.select(secici):
            tag.decompose()

    # 3) Sayfadaki kısa kod kutularını temiz <pre><code> formatına çevir
    for kod_kutusu in main_div.select("div.w3-code"):
        for br in kod_kutusu.find_all("br"):
            br.replace_with("\n")
        saf_kod = kod_kutusu.get_text()
        pre = soup.new_tag("pre")
        code = soup.new_tag("code")
        code.string = saf_kod.strip()
        pre.append(code)
        kod_kutusu.replace_with(pre)

    # 4) Görselleri çevrimdışı çalışacak şekilde göm
    for img in main_div.find_all("img"):
        src = img.get("src", "").strip()
        if src and not src.startswith("data:"):
            data_uri = gorseli_gom(urljoin(url, src))
            if data_uri:
                img["src"] = data_uri
            else:
                img.decompose()

    # 5) Ders içindeki diğer C++ sayfalarına giden linkleri uygulama içi geçişe çevir
    for a in main_div.find_all("a"):
        href = a.get("href", "").strip()
        if href and not href.startswith(("http://", "https://", "#", "javascript:")):
            hedef_url = urljoin(url, href).split("#")[0]
            if "/cpp/" in hedef_url:
                a["href"] = "#"
                a["onclick"] = f"openByUrl('{hedef_url}'); return false;"

    return str(main_div)

def tek_try_kodu_cek(try_url: str) -> tuple[str, str]:
    """trycpp.asp sayfasındaki #include ve int main() içeren tam C++ kodunu alır."""
    try:
        r = requests.get(try_url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        ta = soup.find("textarea", id="textareaCode") or soup.find("textarea")
        if ta:
            return try_url, ta.get_text().strip("\r\n")
    except Exception:
        pass
    return try_url, ""

def html_uygulamasi_olustur():
    print("W3Schools C++ sol menü yapısı taranıyor...")
    kategoriler = sol_menuyu_cek()

    sayfa_haritasi = {}
    sirali_sayfalar = []

    for kat in kategoriler:
        for ders in kat["dersler"]:
            if ders["url"] not in sayfa_haritasi:
                sayfa_haritasi[ders["url"]] = ders["baslik"]
                sirali_sayfalar.append((kat["kategori"], ders["baslik"], ders["url"]))
            for alt in ders["alt_dersler"]:
                if alt["url"] not in sayfa_haritasi:
                    sayfa_haritasi[alt["url"]] = alt["baslik"]
                    sirali_sayfalar.append((kat["kategori"], alt["baslik"], alt["url"]))

    toplam = len(sirali_sayfalar)
    print(f"Toplam {len(kategoriler)} ana kategori ve {toplam} ders sayfası bulundu.\n")

    icerikler = {}
    bulunan_try_urlleri = set()

    for idx, (kat_adi, baslik, url) in enumerate(sirali_sayfalar, start=1):
        print(f"[{idx}/{toplam}] {kat_adi} -> {baslik}")
        try:
            icerikler[url] = sayfa_icerigini_cek(url, bulunan_try_urlleri)
        except Exception as e:
            print(f"   Hata ({url}): {e}")
            icerikler[url] = f"<h1>{baslik}</h1><p>Sayfa indirilirken hata oluştu.</p>"
        time.sleep(0.15)

    print(f"\nToplam {len(bulunan_try_urlleri)} adet tam 'Try it Yourself' kodu indiriliyor...")
    try_codes = {}
    with ThreadPoolExecutor(max_workers=8) as havuz:
        gorevler = [havuz.submit(tek_try_kodu_cek, u) for u in bulunan_try_urlleri]
        for tamamlanan, gorev in enumerate(as_completed(gorevler), start=1):
            t_url, kod = gorev.result()
            if kod:
                try_codes[t_url] = kod
            if tamamlanan % 50 == 0 or tamamlanan == len(gorevler):
                print(f"   Try kodları: {tamamlanan}/{len(gorevler)}")

    veri_paketi = json.dumps({
        "kategoriler": kategoriler,
        "icerikler": icerikler,
        "tryCodes": try_codes,
        "sira": [u for _, _, u in sirali_sayfalar]
    }, ensure_ascii=False).replace("</", "<\\/")

    html_sablon = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>W3Schools C++ Tam Çevrimdışı Rehber</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: 'Segoe UI', Tahoma, sans-serif; display: flex; height: 100vh; background: #1d2a35; color: #e2e8f0; }
  #sidebar { width: 300px; background: #15202b; overflow-y: auto; border-right: 1px solid #38444d; padding: 12px; flex-shrink: 0; user-select: none; }
  #search { width: 100%; padding: 9px 12px; margin-bottom: 12px; border-radius: 6px; border: 1px solid #38444d; background: #1d2a35; color: #fff; font-size: 14px; outline: none; }
  #search:focus { border-color: #04aa6d; }
  .cat-title { font-size: 13px; font-weight: 800; color: #04aa6d; margin: 18px 0 6px; padding-left: 6px; text-transform: uppercase; letter-spacing: 0.6px; border-bottom: 1px solid #283541; padding-bottom: 4px; }
  .lesson-row { display: flex; align-items: center; }
  .lesson-btn { flex: 1; text-align: left; background: none; border: none; color: #ddd; padding: 7px 10px; border-radius: 5px; cursor: pointer; font-size: 14px; }
  .lesson-btn:hover, .sub-btn:hover { background: #283541; }
  .lesson-btn.active, .sub-btn.active { background: #04aa6d; color: #fff; font-weight: 600; }
  .toggle-btn { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 6px 8px; font-size: 11px; border-radius: 4px; }
  .toggle-btn:hover { background: #283541; color: #fff; }
  .sub-list { display: none; padding-left: 16px; border-left: 2px solid #283541; margin-left: 10px; }
  .sub-list.open { display: block; }
  .sub-btn { display: block; width: 100%; text-align: left; background: none; border: none; color: #cbd5e1; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; margin: 2px 0; }
  #main-area { flex: 1; overflow-y: auto; padding: 32px 48px; }
  #content { max-width: 960px; margin: 0 auto; line-height: 1.7; font-size: 15.5px; }
  #content h1 { font-size: 32px; margin-top: 0; color: #fff; border-bottom: 1px solid #38444d; padding-bottom: 10px; }
  #content h2 { font-size: 23px; margin-top: 28px; color: #f8fafc; }
  #content h3 { font-size: 18px; color: #e2e8f0; }
  #content a { color: #38bdf8; }
  .w3-example { background: #283541; padding: 16px; border-radius: 8px; margin: 18px 0; }
  .w3-note, .w3-panel { background: #263440; border-left: 4px solid #eab308; padding: 12px 16px; border-radius: 6px; margin: 16px 0; }
  pre { background: #0f172a; border-left: 4px solid #04aa6d; padding: 14px 16px; border-radius: 6px; overflow-x: auto; position: relative; margin: 12px 0 8px; }
  code { font-family: Consolas, 'Courier New', monospace; font-size: 14px; color: #f8f8f2; }
  p code, li code, td code { background: #283541; padding: 2px 6px; border-radius: 4px; color: #fda4af; }
  .copy-btn { position: absolute; top: 8px; right: 8px; background: #334155; color: #fff; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  .copy-btn:hover { background: #475569; }
  .try-btn { display: inline-block; background: #04aa6d; color: #fff; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: 600; margin-top: 6px; margin-bottom: 6px; }
  .try-btn:hover { background: #059862; }
  table { border-collapse: collapse; width: 100%; margin: 18px 0; background: #15202b; }
  th, td { border: 1px solid #38444d; padding: 10px 12px; text-align: left; }
  th { background: #0f172a; color: #04aa6d; }
  tr:nth-child(even) { background: #1a2632; }
  img { max-width: 100%; height: auto; border-radius: 6px; background: #fff; padding: 6px; }
  .nav-bar { display: flex; justify-content: space-between; margin-top: 36px; padding-top: 18px; border-top: 1px solid #38444d; max-width: 960px; margin-left: auto; margin-right: auto; }
  .nav-btn { background: #04aa6d; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; }
  .nav-btn:disabled { background: #38444d; color: #94a3b8; cursor: not-allowed; }

  #try-modal { display: none; position: fixed; inset: 0; background: #0f172a; z-index: 9999; flex-direction: column; }
  #try-modal.open { display: flex; }
  .try-header { display: flex; align-items: center; justify-content: space-between; background: #15202b; padding: 10px 18px; border-bottom: 1px solid #38444d; }
  .try-actions { display: flex; gap: 10px; align-items: center; }
  .try-run-btn { background: #04aa6d; color: #fff; border: none; padding: 8px 20px; border-radius: 5px; font-size: 14px; font-weight: 700; cursor: pointer; }
  .try-run-btn:hover { background: #059862; }
  .try-reset-btn, .try-close-btn { background: #334155; color: #fff; border: none; padding: 8px 14px; border-radius: 5px; font-size: 13px; cursor: pointer; }
  .try-close-btn { background: #dc2626; }
  .try-body { display: flex; flex: 1; overflow: hidden; }
  .try-pane { flex: 1; display: flex; flex-direction: column; border-right: 1px solid #38444d; }
  .try-pane:last-child { border-right: none; }
  .try-pane-title { background: #1e293b; color: #94a3b8; font-size: 12px; font-weight: 700; padding: 6px 14px; text-transform: uppercase; letter-spacing: 0.5px; }
  #try-editor { flex: 1; width: 100%; background: #0b1120; color: #f8fafc; border: none; padding: 16px; font-family: Consolas, 'Courier New', monospace; font-size: 15px; line-height: 1.55; resize: none; outline: none; tab-size: 2; }
  #try-stdin { height: 70px; width: 100%; background: #15202b; color: #e2e8f0; border: none; border-top: 1px solid #38444d; padding: 10px 14px; font-family: Consolas, monospace; font-size: 13px; resize: none; outline: none; }
  #try-output { flex: 1; margin: 0; padding: 16px; background: #000000; color: #4ade80; font-family: Consolas, 'Courier New', monospace; font-size: 14.5px; overflow: auto; white-space: pre-wrap; border: none; border-radius: 0; }
</style>
</head>
<body>
<div id="sidebar">
  <input type="text" id="search" placeholder="Konu ara (ör. Pointers, Vector, Class)...">
  <div id="menu"></div>
</div>
<div id="main-area">
  <div id="content"></div>
  <div class="nav-bar">
    <button class="nav-btn" id="prev-btn">❮ Önceki Konu</button>
    <button class="nav-btn" id="next-btn">Sonraki Konu ❯</button>
  </div>
</div>

<div id="try-modal">
  <div class="try-header">
    <div class="try-actions">
      <button class="try-run-btn" id="try-run">Run ❯</button>
      <button class="try-reset-btn" id="try-reset">Sıfırla</button>
    </div>
    <span style="color:#94a3b8; font-size:13px;">W3Schools C++ Çevrimdışı Derleyici</span>
    <button class="try-close-btn" id="try-close">✕ Kapat</button>
  </div>
  <div class="try-body">
    <div class="try-pane">
      <div class="try-pane-title">C++ Kodu (Düzenlenebilir)</div>
      <textarea id="try-editor" spellcheck="false"></textarea>
      <div class="try-pane-title">Program Girdisi (cin kullanıyorsa buraya yaz)</div>
      <textarea id="try-stdin" placeholder="Örn: 25"></textarea>
    </div>
    <div class="try-pane">
      <div class="try-pane-title">Çıktı (Result)</div>
      <pre id="try-output">Çalıştırmak için sol üstteki "Run ❯" butonuna basın...</pre>
    </div>
  </div>
</div>

<script id="app-data" type="application/json">__VERI_PAKETI__</script>
<script>
const APP_DATA = JSON.parse(document.getElementById('app-data').textContent);
const menuEl = document.getElementById('menu');
const contentEl = document.getElementById('content');
const mainArea = document.getElementById('main-area');
const searchEl = document.getElementById('search');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');

const tryModal = document.getElementById('try-modal');
const tryEditor = document.getElementById('try-editor');
const tryStdin = document.getElementById('try-stdin');
const tryOutput = document.getElementById('try-output');
let originalCode = '';
let currentUrl = (APP_DATA.sira && APP_DATA.sira.length > 0) ? APP_DATA.sira[0] : '';

function autoWrapCpp(snippet) {
  if (!snippet) return '';
  if (/\bmain\s*\(/.test(snippet)) return snippet;
  const indented = snippet.split('\n').map(l => '  ' + l).join('\n');
  return '#include <iostream>\n#include <string>\n#include <cmath>\nusing namespace std;\n\nint main() {\n' + indented + '\n  return 0;\n}';
}

function openTryIt(tryUrl, fallback) {
  const fullCode = (tryUrl && APP_DATA.tryCodes && APP_DATA.tryCodes[tryUrl])
    ? APP_DATA.tryCodes[tryUrl]
    : autoWrapCpp(fallback);
  originalCode = fullCode;
  tryEditor.value = fullCode;
  tryStdin.value = '';
  tryOutput.style.color = '#94a3b8';
  tryOutput.textContent = 'Çalıştırmak için "Run ❯" butonuna basın...';
  tryModal.classList.add('open');
}

document.getElementById('try-close').onclick = () => tryModal.classList.remove('open');
document.getElementById('try-reset').onclick = () => { tryEditor.value = originalCode; };

tryEditor.addEventListener('keydown', e => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const s = tryEditor.selectionStart;
    const end = tryEditor.selectionEnd;
    tryEditor.value = tryEditor.value.substring(0, s) + '  ' + tryEditor.value.substring(end);
    tryEditor.selectionStart = tryEditor.selectionEnd = s + 2;
  }
});

document.getElementById('try-run').onclick = async () => {
  const code = tryEditor.value;
  const stdinVal = tryStdin.value;
  tryOutput.style.color = '#eab308';
  tryOutput.textContent = 'Derleniyor ve çalıştırılıyor...';

  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.run_cpp(code, stdinVal);
      tryOutput.style.color = res.ok ? '#4ade80' : '#f87171';
      tryOutput.textContent = res.output || '(Program çıktı üretmeden tamamlandı)';
    } catch (err) {
      tryOutput.style.color = '#f87171';
      tryOutput.textContent = 'Hata: ' + err;
    }
  } else {
    tryOutput.style.color = '#f87171';
    tryOutput.textContent = 'Kod çalıştırma özelliği yalnızca CPP_Rehber.exe masaüstü uygulamasında aktiftir.';
  }
};

function renderMenu(filter = '') {
  menuEl.innerHTML = '';
  const q = filter.toLowerCase().trim();

  APP_DATA.kategoriler.forEach(cat => {
    const catDiv = document.createElement('div');
    let hasVisible = false;

    const h = document.createElement('div');
    h.className = 'cat-title';
    h.textContent = cat.kategori;
    catDiv.appendChild(h);

    cat.dersler.forEach(ders => {
      const mainMatch = ders.baslik.toLowerCase().includes(q);
      const matchedSubs = ders.alt_dersler.filter(s => s.baslik.toLowerCase().includes(q));
      if (q && !mainMatch && matchedSubs.length === 0) return;
      hasVisible = true;

      const row = document.createElement('div');
      row.className = 'lesson-row';

      const btn = document.createElement('button');
      btn.className = 'lesson-btn';
      btn.dataset.url = ders.url;
      btn.textContent = ders.baslik;
      btn.onclick = () => openByUrl(ders.url);
      row.appendChild(btn);

      if (ders.alt_dersler.length > 0) {
        const subList = document.createElement('div');
        subList.className = 'sub-list' + (q ? ' open' : '');

        const toggle = document.createElement('button');
        toggle.className = 'toggle-btn';
        toggle.textContent = '▼';
        toggle.onclick = (e) => {
          e.stopPropagation();
          subList.classList.toggle('open');
        };
        row.appendChild(toggle);
        catDiv.appendChild(row);

        const subsToRender = q ? matchedSubs : ders.alt_dersler;
        subsToRender.forEach(sub => {
          const sBtn = document.createElement('button');
          sBtn.className = 'sub-btn';
          sBtn.dataset.url = sub.url;
          sBtn.textContent = sub.baslik;
          sBtn.onclick = () => openByUrl(sub.url);
          subList.appendChild(sBtn);
        });
        catDiv.appendChild(subList);
      } else {
        catDiv.appendChild(row);
      }
    });

    if (hasVisible) menuEl.appendChild(catDiv);
  });
  highlightActive();
}

function highlightActive() {
  document.querySelectorAll('.lesson-btn, .sub-btn').forEach(b => {
    const isMatch = b.dataset.url === currentUrl;
    b.classList.toggle('active', isMatch);
    if (isMatch) {
      const parentSub = b.closest('.sub-list');
      if (parentSub) parentSub.classList.add('open');
      b.scrollIntoView({ block: 'nearest' });
    }
  });
}

function openByUrl(url) {
  if (!APP_DATA.icerikler[url]) return;
  currentUrl = url;
  contentEl.innerHTML = APP_DATA.icerikler[url];
  mainArea.scrollTop = 0;

  contentEl.querySelectorAll('.try-btn').forEach(btn => {
    const tryUrl = btn.dataset.tryUrl;
    let fallback = '';
    const parentEx = btn.closest('.w3-example');
    if (parentEx && parentEx.querySelector('pre code')) {
      fallback = parentEx.querySelector('pre code').innerText;
    }
    btn.onclick = () => openTryIt(tryUrl, fallback);
  });

  contentEl.querySelectorAll('pre').forEach(pre => {
    const codeText = pre.querySelector('code').innerText;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Kopyala';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(codeText);
      copyBtn.textContent = 'Kopyalandı!';
      setTimeout(() => copyBtn.textContent = 'Kopyala', 1500);
    };
    pre.appendChild(copyBtn);

    const nextEl = pre.nextElementSibling;
    const parentEx = pre.closest('.w3-example');
    const hasTry = (nextEl && nextEl.classList.contains('try-btn')) ||
                   (parentEx && parentEx.querySelector('.try-btn'));
    if (!hasTry) {
      const tryBtn = document.createElement('button');
      tryBtn.className = 'try-btn';
      tryBtn.textContent = 'Try it Yourself »';
      tryBtn.onclick = () => openTryIt('', codeText);
      pre.insertAdjacentElement('afterend', tryBtn);
    }
  });

  const idx = APP_DATA.sira.indexOf(url);
  prevBtn.disabled = idx <= 0;
  nextBtn.disabled = idx === -1 || idx >= APP_DATA.sira.length - 1;
  prevBtn.onclick = () => { if (idx > 0) openByUrl(APP_DATA.sira[idx - 1]); };
  nextBtn.onclick = () => { if (idx < APP_DATA.sira.length - 1) openByUrl(APP_DATA.sira[idx + 1]); };

  highlightActive();
}

searchEl.addEventListener('input', e => renderMenu(e.target.value));
renderMenu();
if (currentUrl) openByUrl(currentUrl);
</script>
</body>
</html>"""

    html_sablon = html_sablon.replace("__VERI_PAKETI__", veri_paketi)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_sablon)
    print(f"\nBitti! 'index.html' {len(try_codes)} adet tam Try koduyla oluşturuldu.")

if __name__ == "__main__":
    html_uygulamasi_olustur()