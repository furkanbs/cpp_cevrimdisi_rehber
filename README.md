# W3Schools C++ Çevrimdışı Rehber ve Derleyici

W3Schools C++ eğitim içeriğinin tamamını, diyagramlarını ve **"Try it Yourself »"** kod editörünü internet bağlantısı olmadan kullanmanızı sağlayan masaüstü uygulamasıdır.

## Kurulum ve Kullanım

1. Sağ üstteki **Code -> Download ZIP** seçeneğiyle projeyi indirin ve klasöre çıkartın.
2. Klasör içinde terminali açıp gerekli kütüphaneyi ve çevrimdışı ders içeriklerini (`index.html`) bir kez indirin:
   ```bash
   pip install -r requirements.txt
   python indir.py
   ```
3. Ardından **`Baslat.bat`** dosyasına çift tıklayarak uygulamayı başlatın.

* **Windows `.bat` dosyasını engellerse:** İndirdiğiniz `.zip` dosyasına sağ tıklayıp **Özellikler → Engellemeyi Kaldır → Tamam** dedikten sonra klasöre çıkartın; yine açılmazsa klasör içinde terminali açıp `python uygulama.py` komutuyla başlatın.
* **C++ Kodlarını Çalıştırma:** Bilgisayarınızda **MinGW / MSYS2 (`g++`)** kuruluysa **Run ❯** butonu kodları gerçek C++ derleyicisiyle çalıştırır. `g++` kurulu değilse veya Windows Akıllı Uygulama Denetimi derlenen `.exe` dosyasını engellerse uygulama otomatik olarak dahili yedek motora geçer (üst çubuktaki **Yedek Çalıştır** butonunu da kullanabilirsiniz).
* **Sadece Tarayıcıda Okuma:** İlk kurulumda `index.html` oluşturulduktan sonra, masaüstü uygulamasını açmadan yalnızca dersleri okumak için klasördeki `index.html` dosyasına çift tıklayarak tarayıcıda açabilirsiniz.

## İçeriği Güncelleme (İsteğe Bağlı)

W3Schools üzerindeki güncel dersleri yeniden çekip `index.html` dosyasını sıfırdan üretmek için:
```bash
python indir.py
```

---
*Not: Eğitim içerikleri, anlatımlar ve diyagramların telif hakları W3Schools'a (`w3schools.com`) aittir. Bu proje yalnızca öğrencilerin çevrimdışı ortamda C++ çalışabilmesi için geliştirilmiş açık kaynaklı bir yardımcı araçtır.*
