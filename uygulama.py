import os
import sys
import glob
import shutil
import tempfile
import subprocess
import webview


def kaynak_yolu(dosya_adi: str) -> str:
    """PyInstaller (.exe) ve normal Python (.py) çalıştırma yollarını çözer."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, dosya_adi)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), dosya_adi)


def gpp_bul() -> str | None:
    """Sistem PATH'inde veya Windows'taki yaygın MinGW/MSYS2 klasörlerinde g++.exe arar."""
    yol = shutil.which("g++")
    if yol:
        return yol

    olasi_desenler = [
        r"C:\msys64\ucrt64\bin\g++.exe",
        r"C:\msys64\mingw64\bin\g++.exe",
        r"C:\msys64\mingw32\bin\g++.exe",
        r"C:\MinGW\bin\g++.exe",
        r"C:\TDM-GCC-64\bin\g++.exe",
        r"C:\Program Files\CodeBlocks\MinGW\bin\g++.exe",
        r"C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\g++.exe",
        r"C:\winlibs*\mingw64\bin\g++.exe",
        os.path.expanduser(r"~\scoop\apps\gcc\current\bin\g++.exe"),
        os.path.expanduser(r"~\scoop\apps\mingw\current\bin\g++.exe"),
    ]
    for desen in olasi_desenler:
        eslesenler = glob.glob(desen)
        if eslesenler and os.path.isfile(eslesenler[0]):
            return eslesenler[0]
    return None


def cikti_coz(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "cp1254", "cp857"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class Api:
    def run_cpp(self, code: str, stdin_data: str = "") -> dict:
        gpp_exe = gpp_bul()
        if not gpp_exe:
            return {
                "ok": False,
                "output": (
                    "Hata: Bilgisayarda 'g++' C++ derleyicisi bulunamadı.\n"
                    "MSYS2 / MinGW kuruluysa bin klasörünü Windows PATH ortam değişkenine ekleyin."
                ),
            }

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        gpp_dir = os.path.dirname(gpp_exe)
        env["PATH"] = gpp_dir + os.pathsep + env.get("PATH", "")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                cpp_file = os.path.join(tmpdir, "main.cpp")
                exe_file = os.path.join(tmpdir, "main.exe")

                with open(cpp_file, "w", encoding="utf-8") as f:
                    f.write(code)

                compile_proc = subprocess.run(
                    [gpp_exe, "-std=c++17", cpp_file, "-o", exe_file],
                    capture_output=True,
                    env=env,
                    timeout=15,
                    creationflags=creation_flags,
                )

                if compile_proc.returncode != 0:
                    err_text = cikti_coz(compile_proc.stderr) or cikti_coz(compile_proc.stdout)
                    return {
                        "ok": False,
                        "output": f"Derleme Hatası:\n{err_text.strip()}",
                    }

                run_proc = subprocess.run(
                    [exe_file],
                    input=(stdin_data or "").encode("utf-8"),
                    capture_output=True,
                    env=env,
                    timeout=10,
                    creationflags=creation_flags,
                )

                stdout_text = cikti_coz(run_proc.stdout)
                stderr_text = cikti_coz(run_proc.stderr)
                birlesik = stdout_text
                if stderr_text:
                    birlesik = f"{stdout_text}\n{stderr_text}".strip()

                return {
                    "ok": run_proc.returncode == 0,
                    "output": birlesik if birlesik else "(Program çıktı üretmeden tamamlandı)",
                }

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "output": "Hata: Program 10 saniyeden uzun sürdüğü için durduruldu (sonsuz döngü veya eksik cin girdisi olabilir).",
            }
        except Exception as e:
            return {"ok": False, "output": f"Beklenmeyen Hata: {e}"}


if __name__ == "__main__":
    html_dosyasi = kaynak_yolu("index.html")
    if not os.path.exists(html_dosyasi):
        raise FileNotFoundError(f"index.html bulunamadı: {html_dosyasi}")

    api = Api()
    webview.create_window(
        "W3Schools C++ Tam Çevrimdışı Rehber",
        url=html_dosyasi,
        width=1280,
        height=820,
        js_api=api,
    )
    webview.start()