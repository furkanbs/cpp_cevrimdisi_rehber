import os
import re
import sys
import io
import glob
import math
import shutil
import tempfile
import subprocess
import contextlib
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


def wsl_ile_calistir(code: str, stdin_data: str, creation_flags: int) -> dict | None:
    """Windows .exe engellendiğinde bilgisayarda WSL varsa Linux g++ üzerinden çalıştırır."""
    wsl_exe = shutil.which("wsl")
    if not wsl_exe:
        return None
    try:
        yaz = subprocess.run(
            [wsl_exe, "bash", "-c", "cat > /tmp/w3cpp_main.cpp && g++ -std=c++17 /tmp/w3cpp_main.cpp -o /tmp/w3cpp_main"],
            input=code.encode("utf-8"),
            capture_output=True,
            timeout=15,
            creationflags=creation_flags,
        )
        if yaz.returncode != 0:
            return None

        calistir = subprocess.run(
            [wsl_exe, "/tmp/w3cpp_main"],
            input=(stdin_data or "").encode("utf-8"),
            capture_output=True,
            timeout=10,
            creationflags=creation_flags,
        )
        out = cikti_coz(calistir.stdout)
        err = cikti_coz(calistir.stderr)
        birlesik = f"{out}\n{err}".strip() if err else out
        return {
            "ok": calistir.returncode == 0,
            "output": birlesik if birlesik else "(Program çıktı üretmeden tamamlandı)",
        }
    except Exception:
        return None


class CppContainer(list):
    """C++ vector ve string yardımcı metotlarını destekleyen liste sınıfı."""
    def push_back(self, val):
        self.append(val)

    def pop_back(self):
        if self:
            self.pop()

    def size(self):
        return len(self)

    def length(self):
        return len(self)

    def empty(self):
        return len(self) == 0

    def at(self, idx):
        return self[idx]

    def front(self):
        return self[0]

    def back(self):
        return self[-1]


class CppPtr:
    """Temel C++ pointer (& ve *) simülasyonu."""
    def __init__(self, scope, name):
        self._scope = scope
        self._name = name

    @property
    def val(self):
        return self._scope[self._name]

    @val.setter
    def val(self, v):
        self._scope[self._name] = v

    def __str__(self):
        return f"0x{abs(hash(self._name)) & 0xFFFFFFFF:08x}"


def _dis_parantez_bol(ifade: str, ayirici: str) -> list[str]:
    """Tırnak ve parantez dışındaki ayırıcılara göre ifadeyi böler."""
    parcalar, buf = [], []
    derinlik = 0
    tirnak = None
    i = 0
    while i < len(ifade):
        ch = ifade[i]
        if tirnak:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(ifade):
                i += 1
                buf.append(ifade[i])
            elif ch == tirnak:
                tirnak = None
        else:
            if ch in ('"', "'"):
                tirnak = ch
                buf.append(ch)
            elif ch in "([{":
                derinlik += 1
                buf.append(ch)
            elif ch in ")]}":
                derinlik = max(0, derinlik - 1)
                buf.append(ch)
            elif derinlik == 0 and ifade.startswith(ayirici, i):
                parcalar.append("".join(buf).strip())
                buf = []
                i += len(ayirici) - 1
            else:
                buf.append(ch)
        i += 1
    if buf:
        parcalar.append("".join(buf).strip())
    return parcalar


def _cpp_ifade_donustur(expr: str) -> str:
    """Tek satırlık C++ ifadesini Python ifadesine çevirir."""
    expr = expr.strip()
    parcalar = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', expr)
    sonuc = []
    tipler = r"(?:unsigned\s+|signed\s+|long\s+|short\s+|const\s+)*(?:int|double|float|char|string|bool|auto)"

    for idx, p in enumerate(parcalar):
        if idx % 2 == 1:
            sonuc.append(p)
            continue
        s = p
        s = re.sub(r"\(\s*" + tipler + r"\s*\)", "", s)
        s = re.sub(r"\btrue\b", "True", s)
        s = re.sub(r"\bfalse\b", "False", s)
        s = re.sub(r"\b(nullptr|NULL)\b", "None", s)
        s = s.replace("&&", " and ").replace("||", " or ")
        s = re.sub(r"(?<![=!<>])!(?!=)", " not ", s)
        s = re.sub(r"\b([A-Za-z_]\w*)\.(?:length|size)\(\)", r"len(\1)", s)
        s = re.sub(r"\b([A-Za-z_]\w*)\.at\(([^)]+)\)", r"\1[\2]", s)
        s = re.sub(r"\b([A-Za-z_]\w*)\.append\(([^)]+)\)", r"(\1 + \2)", s)
        s = re.sub(r"&([A-Za-z_]\w*)", r"_cpp_ref(locals(), '\1')", s)
        s = re.sub(r"(?<![\w\)\]\"'])\*([A-Za-z_]\w*)", r"\1.val", s)
        sonuc.append(s)

    birlesik = "".join(sonuc).strip()
    ternary = re.match(r"^(.+?)\?(.+?):(.+)$", birlesik)
    if ternary and "?" not in ternary.group(1):
        kosul, dogru, yanlis = ternary.groups()
        return f"({dogru.strip()} if {kosul.strip()} else {yanlis.strip()})"
    return birlesik


def yedek_cpp_calistir(code: str, stdin_data: str = "", uyari_ekle: bool = True) -> dict:
    """Windows .exe engellendiğinde ek dosya oluşturmadan C++ kodunu dahili olarak çalıştırır."""
    temiz = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    temiz = re.sub(r"//.*", "", temiz)
    temiz = re.sub(r"^\s*#.*$", "", temiz, flags=re.M)
    temiz = re.sub(r"^\s*using\s+namespace\s+\w+\s*;\s*$", "", temiz, flags=re.M)

    # Blokları satır bazlı ayrıştır
    hazir = (
        temiz.replace("{", "\n{\n")
        .replace("}", "\n}\n")
        .replace(";", ";\n")
    )
    ham_satirlar = [s.strip() for s in hazir.splitlines() if s.strip()]

    # for (a; b; c) parantez içindeki noktalı virgülleri geri birleştir
    satirlar = []
    i = 0
    while i < len(ham_satirlar):
        s = ham_satirlar[i]
        if re.match(r"^for\s*\(", s) and s.count("(") > s.count(")"):
            birlesik = s
            while i + 1 < len(ham_satirlar) and birlesik.count("(") > birlesik.count(")"):
                i += 1
                birlesik += " " + ham_satirlar[i]
            satirlar.append(birlesik)
        else:
            satirlar.append(s)
        i += 1

    py_kod = [
        "def _cpp_print(*vals):",
        "    for v in vals:",
        "        if isinstance(v, bool):",
        "            print('1' if v else '0', end='')",
        "        else:",
        "            print(v, end='')",
        "",
        "_cin_tokens = iter(_STDIN_RAW.split())",
        "_cin_lines = iter(_STDIN_RAW.splitlines())",
        "def _cpp_cin():",
        "    try:",
        "        return next(_cin_tokens)",
        "    except StopIteration:",
        "        return ''",
        "",
        "def _cpp_getline():",
        "    try:",
        "        return next(_cin_lines)",
        "    except StopIteration:",
        "        return ''",
        "",
        "def _cpp_cast_cin(tok, mevcut):",
        "    if isinstance(mevcut, bool): return tok.lower() in ('1', 'true')",
        "    if isinstance(mevcut, int): return int(float(tok)) if tok else 0",
        "    if isinstance(mevcut, float): return float(tok) if tok else 0.0",
        "    return tok",
        "",
        "def _cpp_ref(scope, name): return CppPtr(scope, name)",
        "",
    ]

    girinti = 0
    blok_yigini = []  # ('func'|'if'|'while'|'for'|'switch'|'struct', ekstra)
    tipler_re = r"(?:unsigned\s+|signed\s+|long\s+|short\s+|const\s+)*(?:int|double|float|char|string|bool|auto|void)"

    def ekle(satir: str):
        py_kod.append("    " * girinti + satir)

    idx = 0
    while idx < len(satirlar):
        s = satirlar[idx]

        if s == "{":
            girinti += 1
            idx += 1
            continue

        if s == "}":
            if blok_yigini:
                tur, ekstra = blok_yigini.pop()
                if tur == "for" and ekstra:
                    ekle(ekstra)
                elif tur == "do":
                    girinti = max(0, girinti - 1)
                    if idx + 1 < len(satirlar) and satirlar[idx + 1].startswith("while"):
                        m_do = re.match(r"^while\s*\((.+)\)\s*;?$", satirlar[idx + 1])
                        if m_do:
                            ekle(f"    if not ({_cpp_ifade_donustur(m_do.group(1))}): break")
                            idx += 2
                            continue
                    idx += 1
                    continue
            girinti = max(0, girinti - 1)
            if idx + 1 < len(satirlar) and satirlar[idx + 1] == ";":
                idx += 1
            idx += 1
            continue

        if s in ("public:", "private:", "protected:", ";"):
            idx += 1
            continue

        # Fonksiyon tanımı: int main() veya int topla(int a, int b)
        m_fn = re.match(r"^(" + tipler_re + r")\s+([A-Za-z_]\w*)\s*\(([^)]*)\)$", s)
        if m_fn:
            _, fn_adi, params_str = m_fn.groups()
            params = []
            if params_str.strip():
                for p in params_str.split(","):
                    p_temiz = p.strip().split("=")[0].strip()
                    p_adi = re.findall(r"[A-Za-z_]\w*", p_temiz)[-1]
                    if "=" in p:
                        varsayilan = _cpp_ifade_donustur(p.split("=", 1)[1])
                        params.append(f"{p_adi}={varsayilan}")
                    else:
                        params.append(p_adi)
            ekle(f"def {fn_adi}({', '.join(params)}):")
            blok_yigini.append(("func", None))
            idx += 1
            continue

        # struct / class tanımı
        m_cls = re.match(r"^(?:struct|class)\s+([A-Za-z_]\w*)$", s)
        if m_cls:
            ekle(f"class {m_cls.group(1)}:")
            blok_yigini.append(("struct", None))
            idx += 1
            continue

        # if / else if / else
        m_elif = re.match(r"^else\s+if\s*\((.+)\)$", s)
        if m_elif:
            ekle(f"elif {_cpp_ifade_donustur(m_elif.group(1))}:")
            blok_yigini.append(("if", None))
            idx += 1
            continue

        m_if = re.match(r"^if\s*\((.+)\)$", s)
        if m_if:
            ekle(f"if {_cpp_ifade_donustur(m_if.group(1))}:")
            blok_yigini.append(("if", None))
            idx += 1
            continue

        if s == "else":
            ekle("else:")
            blok_yigini.append(("if", None))
            idx += 1
            continue

        # while döngüsü
        m_while = re.match(r"^while\s*\((.+)\)$", s)
        if m_while:
            ekle(f"while {_cpp_ifade_donustur(m_while.group(1))}:")
            blok_yigini.append(("while", None))
            idx += 1
            continue

        # do { ... } while (...)
        if s == "do":
            ekle("while True:")
            blok_yigini.append(("do", None))
            idx += 1
            continue

        # for döngüsü (klasik ve range-based)
        m_for = re.match(r"^for\s*\((.+)\)$", s)
        if m_for:
            ic = m_for.group(1).strip()
            if ";" in ic:
                bas, kosul, adim = [x.strip() for x in ic.split(";", 2)]
                bas_temiz = re.sub(r"^" + tipler_re + r"\s+", "", bas)
                if bas_temiz:
                    ekle(_cpp_ifade_donustur(bas_temiz))
                kosul_py = _cpp_ifade_donustur(kosul) if kosul else "True"
                adim_py = ""
                if adim:
                    adim_py = re.sub(r"^(\+\+)?([A-Za-z_]\w*)(\+\+)?$", r"\2 += 1", adim)
                    adim_py = re.sub(r"^(--)?([A-Za-z_]\w*)(--)?$", r"\2 -= 1", adim_py)
                    if adim_py == adim:
                        adim_py = _cpp_ifade_donustur(adim)
                ekle(f"while {kosul_py}:")
                blok_yigini.append(("for", adim_py))
            elif ":" in ic:
                sol, sag = ic.split(":", 1)
                deg = re.findall(r"[A-Za-z_]\w*", sol)[-1]
                ekle(f"for {deg} in {_cpp_ifade_donustur(sag)}:")
                blok_yigini.append(("while", None))
            idx += 1
            continue

        # switch / case / default
        m_sw = re.match(r"^switch\s*\((.+)\)$", s)
        if m_sw:
            ekle(f"_sw_val = {_cpp_ifade_donustur(m_sw.group(1))}")
            blok_yigini.append(("switch", True))
            idx += 1
            continue

        m_case = re.match(r"^case\s+(.+):$", s)
        if m_case:
            ilk_mi = blok_yigini and blok_yigini[-1][0] == "switch" and blok_yigini[-1][1]
            if ilk_mi:
                ekle(f"if _sw_val == {_cpp_ifade_donustur(m_case.group(1))}:")
                blok_yigini[-1] = ("switch", False)
            else:
                girinti = max(0, girinti - 1)
                ekle(f"elif _sw_val == {_cpp_ifade_donustur(m_case.group(1))}:")
            girinti += 1
            idx += 1
            continue

        if s == "default:":
            girinti = max(0, girinti - 1)
            ekle("else:")
            girinti += 1
            idx += 1
            continue

        # Noktalı virgülle biten ifadeler
        komut = s[:-1].strip() if s.endswith(";") else s

        if komut == "break":
            if not (blok_yigini and blok_yigini[-1][0] == "switch"):
                ekle("break")
            idx += 1
            continue

        if komut == "continue":
            if blok_yigini and blok_yigini[-1][0] == "for" and blok_yigini[-1][1]:
                ekle(blok_yigini[-1][1])
            ekle("continue")
            idx += 1
            continue

        m_ret = re.match(r"^return(?:\s+(.+))?$", komut)
        if m_ret:
            ekle(f"return {_cpp_ifade_donustur(m_ret.group(1))}" if m_ret.group(1) else "return")
            idx += 1
            continue

        # cout << ...
        if re.match(r"^(?:std::)?cout\s*<<", komut):
            kisimlar = _dis_parantez_bol(re.sub(r"^(?:std::)?cout\s*<<", "", komut), "<<")
            donusenler = []
            for k in kisimlar:
                if k in ("endl", "std::endl"):
                    donusenler.append("'\\n'")
                else:
                    donusenler.append(_cpp_ifade_donustur(k))
            ekle(f"_cpp_print({', '.join(donusenler)})")
            idx += 1
            continue

        # cin >> ...
        if re.match(r"^(?:std::)?cin\s*>>", komut):
            degiskenler = _dis_parantez_bol(re.sub(r"^(?:std::)?cin\s*>>", "", komut), ">>")
            for d in degiskenler:
                ekle(f"{d} = _cpp_cast_cin(_cpp_cin(), {d})")
            idx += 1
            continue

        # getline(cin, degisken)
        m_gl = re.match(r"^(?:std::)?getline\s*\(\s*(?:std::)?cin\s*,\s*([A-Za-z_]\w*)\s*\)$", komut)
        if m_gl:
            ekle(f"{m_gl.group(1)} = _cpp_getline()")
            idx += 1
            continue

        # vector<tip> ad = {...}
        m_vec = re.match(r"^(?:std::)?vector\s*<[^>]+>\s*([A-Za-z_]\w*)(?:\s*=\s*\{(.*)\})?$", komut)
        if m_vec:
            ad, icerik = m_vec.groups()
            if icerik is not None:
                elemanlar = [_cpp_ifade_donustur(e) for e in _dis_parantez_bol(icerik, ",") if e]
                ekle(f"{ad} = CppContainer([{', '.join(elemanlar)}])")
            else:
                ekle(f"{ad} = CppContainer()")
            idx += 1
            continue

        # Dizi tanımı: int nums[4] = {1, 2, 3, 4}; veya int nums[4];
        m_arr = re.match(r"^" + tipler_re + r"\s+([A-Za-z_]\w*)\s*\[([^\]]*)\](?:\s*=\s*\{(.*)\})?$", komut)
        if m_arr:
            ad, boyut, icerik = m_arr.groups()
            if icerik is not None:
                elemanlar = [_cpp_ifade_donustur(e) for e in _dis_parantez_bol(icerik, ",") if e]
                ekle(f"{ad} = CppContainer([{', '.join(elemanlar)}])")
            else:
                b = _cpp_ifade_donustur(boyut) if boyut.strip() else "0"
                ekle(f"{ad} = CppContainer([0] * ({b}))")
            idx += 1
            continue

        # Değişken tanımları: int x = 5, y = 6; veya string &meal = food;
        m_decl = re.match(r"^(" + tipler_re + r")(?:\s*[\*&])?\s+(.+)$", komut)
        if m_decl and "(" not in komut.split("=")[0]:
            tip_adi, geri_kalan = m_decl.groups()
            varsayilan = "''" if "string" in tip_adi else ("False" if "bool" in tip_adi else "0")
            for parca in _dis_parantez_bol(geri_kalan, ","):
                parca = parca.lstrip("*& ").strip()
                if "=" in parca:
                    sol, sag = parca.split("=", 1)
                    sol = sol.lstrip("*& ").strip()
                    ekle(f"{sol} = {_cpp_ifade_donustur(sag)}")
                else:
                    ekle(f"{parca} = {varsayilan}")
            idx += 1
            continue

        # Pointer üzerinden değer değiştirme: *ptr = "Hamburger";
        m_ptr_set = re.match(r"^\*([A-Za-z_]\w*)\s*=\s*(.+)$", komut)
        if m_ptr_set:
            ekle(f"{m_ptr_set.group(1)}.val = {_cpp_ifade_donustur(m_ptr_set.group(2))}")
            idx += 1
            continue

        # i++ / ++i / i-- / --i
        m_inc = re.match(r"^(?:\+\+([A-Za-z_]\w*)|([A-Za-z_]\w*)\+\+)$", komut)
        if m_inc:
            deg = m_inc.group(1) or m_inc.group(2)
            ekle(f"{deg} += 1")
            idx += 1
            continue

        m_dec = re.match(r"^(?:--([A-Za-z_]\w*)|([A-Za-z_]\w*)--)$", komut)
        if m_dec:
            deg = m_dec.group(1) or m_dec.group(2)
            ekle(f"{deg} -= 1")
            idx += 1
            continue

        # Genel atama veya fonksiyon çağrısı
        ekle(_cpp_ifade_donustur(komut))
        idx += 1

    py_kod.append("")
    py_kod.append("if 'main' in globals():")
    py_kod.append("    main()")

    tam_script = "\n".join(py_kod)
    stdout_buf = io.StringIO()
    ortam = {
        "_STDIN_RAW": stdin_data or "",
        "CppContainer": CppContainer,
        "CppPtr": CppPtr,
        "max": max,
        "min": min,
        "abs": abs,
        "round": round,
        "pow": pow,
        "sqrt": math.sqrt,
        "log": math.log,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    try:
        with contextlib.redirect_stdout(stdout_buf):
            exec(tam_script, ortam)
        cikti = stdout_buf.getvalue()
        baslik = "[Yedek Motor ile Çalıştırıldı — Windows .exe engeli aşıldı]\n\n" if uyari_ekle else ""
        return {
            "ok": True,
            "output": baslik + (cikti if cikti else "(Program çıktı üretmeden tamamlandı)"),
        }
    except Exception as e:
        return {
            "ok": False,
            "output": (
                f"Yedek Motor Çalıştırma Hatası: {e}\n\n"
                "Not: Çok gelişmiş C++ özellikleri için yerel g++ derleyicisi gerekir."
            ),
        }


class Api:
    def run_cpp(self, code: str, stdin_data: str = "") -> dict:
        gpp_exe = gpp_bul()
        if not gpp_exe:
            return yedek_cpp_calistir(code, stdin_data, uyari_ekle=True)

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

                try:
                    run_proc = subprocess.run(
                        [exe_file],
                        input=(stdin_data or "").encode("utf-8"),
                        capture_output=True,
                        env=env,
                        timeout=10,
                        creationflags=creation_flags,
                    )
                except OSError as os_err:
                    if getattr(os_err, "winerror", None) == 4551:
                        wsl_sonuc = wsl_ile_calistir(code, stdin_data, creation_flags)
                        if wsl_sonuc is not None:
                            return wsl_sonuc
                        return yedek_cpp_calistir(code, stdin_data, uyari_ekle=True)
                    raise

                stdout_text = cikti_coz(run_proc.stdout)
                stderr_text = cikti_coz(run_proc.stderr)
                birlesik = f"{stdout_text}\n{stderr_text}".strip() if stderr_text else stdout_text

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

    def run_cpp_backup(self, code: str, stdin_data: str = "") -> dict:
        """Kullanıcı 'Yedek Çalıştır' butonuna bastığında doğrudan dahili motoru kullanır."""
        return yedek_cpp_calistir(code, stdin_data, uyari_ekle=False)


def arayuze_yedek_butonu_ekle(window):
    """Mevcut index.html dosyasını değiştirmeden üst çubuğa Yedek Çalıştır butonu ekler."""
    js = """
    (function() {
        const actions = document.querySelector('.try-actions');
        const runBtn = document.getElementById('try-run');
        if (!actions || !runBtn || document.getElementById('try-run-backup')) return;

        const backupBtn = document.createElement('button');
        backupBtn.id = 'try-run-backup';
        backupBtn.className = 'try-reset-btn';
        backupBtn.style.background = '#2563eb';
        backupBtn.style.fontWeight = '600';
        backupBtn.title = 'Windows .exe engeli olan sistemler için dahili yedek çalıştırıcı';
        backupBtn.textContent = 'Yedek Çalıştır';

        backupBtn.onclick = async () => {
            const editor = document.getElementById('try-editor');
            const stdinEl = document.getElementById('try-stdin');
            const outputEl = document.getElementById('try-output');
            outputEl.style.color = '#eab308';
            outputEl.textContent = 'Yedek motorda çalıştırılıyor...';
            try {
                const res = await window.pywebview.api.run_cpp_backup(editor.value, stdinEl.value);
                outputEl.style.color = res.ok ? '#4ade80' : '#f87171';
                outputEl.textContent = res.output;
            } catch (err) {
                outputEl.style.color = '#f87171';
                outputEl.textContent = 'Hata: ' + err;
            }
        };

        runBtn.insertAdjacentElement('afterend', backupBtn);
    })();
    """
    window.evaluate_js(js)


if __name__ == "__main__":
    html_dosyasi = kaynak_yolu("index.html")
    if not os.path.exists(html_dosyasi):
        raise FileNotFoundError(f"index.html bulunamadı: {html_dosyasi}")

    api = Api()
    pencere = webview.create_window(
        "W3Schools C++ Tam Çevrimdışı Rehber",
        url=html_dosyasi,
        width=1280,
        height=820,
        js_api=api,
    )
    webview.start(arayuze_yedek_butonu_ekle, pencere)
