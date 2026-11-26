# W3Schools C++ Çevrimdışı Rehber ve Derleyici

W3Schools C++ eğitim içeriğinin tamamını, diyagramlarını ve **"Try it Yourself »"** kod editörünü internet bağlantısı olmadan kullanmanızı sağlayan masaüstü uygulamasıdır.

## Kullanım Seçenekleri

### 1. Masaüstü Uygulaması ve Canlı C++ Derleyici (Önerilen)
1. Sağ üstteki **Code -> Download ZIP** seçeneğiyle projeyi indirin ve klasöre çıkartın.
2. **`Baslat.bat`** dosyasına çift tıklayın.
   - İlk çalıştırmada gerekli Python arayüz kütüphanesi (`pywebview`) otomatik kurulur.
   - Kod örneklerindeki **Run ❯** butonunun çalışması için bilgisayarınızda **MinGW / MSYS2 (`g++`)** kurulu olmalıdır.

Önemli Not: İndirdiğiniz .zip dosyasına sağ tıklayıp Özellikler → Engellemeyi Kaldır → Tamam dedikten sonra klasöre çıkartın ve Baslat.bat dosyasını çalıştırın. Windows yine de .bat dosyasını engellerse klasör içinde terminali açıp python uygulama.py komutuyla uygulamayı doğrudan başlatabilirsiniz.

### 2. Sadece Okuma Modu (Kurulumsuz)
Python veya derleyici kurmadan yalnızca dersleri okumak için klasördeki **`index.html`** dosyasına çift tıklayarak herhangi bir web tarayıcısında açabilirsiniz.

## İçeriği Güncelleme (İsteğe Bağlı)
W3Schools üzerindeki güncel dersleri yeniden çekip `index.html` dosyasını sıfırdan üretmek için:
```bash
pip install -r requirements.txt
python indir.py
```
