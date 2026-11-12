"""Şirket servis güzergahı arama uygulaması."""
from __future__ import annotations

import difflib
import html
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

KLASOR = Path(__file__).parent
# Önce Excel'e, bulunamazsa CSV'ye bakılır.
VERI_ADAYLARI = [KLASOR / "servis.xlsx", KLASOR / "servis.csv"]

st.set_page_config(page_title="Servis güzergahları", page_icon="🚌", layout="centered")

CSS = """
<style>
.block-container{max-width:820px;padding-top:2.5rem}
footer{visibility:hidden}
.kart{border:1px solid rgba(128,128,128,.32);border-radius:12px;padding:16px 18px 14px;margin:0 0 14px}
.kart .ust{display:flex;align-items:center;justify-content:space-between;gap:10px 16px;flex-wrap:wrap;margin-bottom:12px}
.kart .kimlik{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.plaka{display:inline-flex;border:2px solid #1b1b1b;border-radius:6px;overflow:hidden;background:#fff;color:#111;font-weight:700;font-size:1.05rem;letter-spacing:.05em;line-height:1}
.plaka .tr{background:#0a3a8f;color:#fff;font-size:.55rem;letter-spacing:0;padding:0 4px 3px;display:flex;align-items:flex-end}
.plaka .pn{padding:7px 11px 6px;white-space:nowrap}
.sofor{font-weight:600;font-size:1.05rem}
.tel{display:inline-block;padding:7px 14px;border-radius:8px;background:var(--primary-color,#0b6e4f);color:#fff !important;text-decoration:none !important;font-weight:600;white-space:nowrap}
.tel.pasif{background:rgba(128,128,128,.25);color:inherit !important}
.rota{margin:0;line-height:2;font-size:.97rem}
.rota .sn{font-size:.72rem;opacity:.55;margin-right:4px;font-weight:600}
.rota .ok{opacity:.4;margin:0 6px}
.rota mark{background:rgba(250,204,21,.4);color:inherit;border-radius:4px;padding:2px 4px}
</style>
"""

# ----------------------------------------------------------------------------
# Metin yardımcıları
# ----------------------------------------------------------------------------

# Python'un lower()/upper() fonksiyonları İ, I, ı, i harflerini Türkçe'ye uygun
# dönüştürmez ("İ".lower() iki karakter üretir). Arama için her şeyi ASCII'ye
# indirgiyoruz: böylece "ozal", "ÖZAL" ve "Özal" aynı şeydir.
_ASCII = str.maketrans(
    {"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
     "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c"}
)


def sadelestir(metin) -> str:
    """Arama anahtarı: küçük harf, ASCII, noktalama ve fazla boşluk yok."""
    if metin is None or (isinstance(metin, float) and pd.isna(metin)):
        return ""
    s = str(metin).translate(_ASCII).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tr_baslik(metin: str) -> str:
    """'HASAN ÖZCAN' -> 'Hasan Özcan' (Türkçe i/ı kurallarıyla)."""
    kelimeler = []
    for kelime in str(metin).split():
        kucuk = kelime.replace("İ", "i").replace("I", "ı").lower()
        ilk = {"i": "İ", "ı": "I"}.get(kucuk[0], kucuk[0].upper())
        kelimeler.append(ilk + kucuk[1:])
    return " ".join(kelimeler)


def plaka_duzelt(plaka: str) -> str:
    """'1 S 2539', '01S2539' -> '01 S 2539'."""
    s = re.sub(r"\s+", "", str(plaka)).upper()
    m = re.fullmatch(r"(\d{1,2})([A-ZÇĞİÖŞÜ]+)(\d+)", s)
    if not m:
        return str(plaka).strip()
    il, harf, no = m.groups()
    return f"{il.zfill(2)} {harf} {no}"


def telefon_duzelt(tel: str) -> str:
    """'532 648 69 73' -> '0532 648 69 73'. Tanınmayan biçim olduğu gibi kalır."""
    rakam = re.sub(r"\D", "", str(tel))
    if len(rakam) == 12 and rakam.startswith("90"):
        rakam = "0" + rakam[2:]
    if len(rakam) == 10:
        rakam = "0" + rakam
    if len(rakam) != 11:
        return str(tel).strip()
    return f"{rakam[:4]} {rakam[4:7]} {rakam[7:9]} {rakam[9:]}"


def telefon_linki(tel: str) -> str:
    """Telefonda tek dokunuşla aramak için '+905326486973' biçimi."""
    rakam = re.sub(r"\D", "", tel)
    return f"+90{rakam[1:]}" if len(rakam) == 11 else ""


def en_sik(seri: pd.Series) -> str:
    return seri.mode().iat[0]


# ----------------------------------------------------------------------------
# Veri
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def veri_yukle(yol: str, degisim_zamani: float) -> pd.DataFrame:
    """Dosyayı okur ve temizler. Dosya değişince önbellek kendiliğinden yenilenir."""
    p = Path(yol)
    if p.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        ham = pd.read_excel(p, dtype=str)
    else:
        ham = None
        for kodlama in ("utf-8-sig", "cp1254"):  # cp1254 = Windows Türkçe
            try:
                ham = pd.read_csv(p, sep=";", encoding=kodlama, dtype=str)
                break
            except UnicodeDecodeError:
                continue
        if ham is None:
            raise ValueError("CSV dosyasının karakter kodlaması anlaşılamadı.")

    df = ham.iloc[:, :4].copy()
    df.columns = ["adres", "plaka", "sofor", "tel"]
    for sutun in df.columns:
        df[sutun] = (
            df[sutun].fillna("").astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    df = df[(df["adres"] != "") & (df["plaka"] != "")].reset_index(drop=True)

    df["plaka"] = df["plaka"].map(plaka_duzelt)
    df["sofor"] = df["sofor"].map(tr_baslik)
    df["tel"] = df["tel"].map(telefon_duzelt)
    # Aynı servisin satırlarında farklı yazılmış isim/telefon varsa en sık geçeni al.
    for sutun in ("sofor", "tel"):
        df[sutun] = df.groupby("plaka")[sutun].transform(en_sik)

    df["sira"] = df.groupby("plaka").cumcount() + 1  # Excel'deki sıra = durak sırası
    df["_adres"] = df["adres"].map(sadelestir)
    df["_hepsi"] = (
        df["adres"] + " " + df["plaka"] + " " + df["plaka"].str.replace(" ", "") + " " + df["sofor"]
    ).map(sadelestir)
    return df


# ----------------------------------------------------------------------------
# Görünüm
# ----------------------------------------------------------------------------

def kart_html(grup: pd.DataFrame, vurgulu: set[int]) -> str:
    """Bir servisin kartı. Tek satır HTML: Markdown girintiyi kod bloğu sanmasın."""
    ilk = grup.iloc[0]
    duraklar = []
    for sira, adres in zip(grup["sira"], grup["adres"]):
        icerik = f'<span class="sn">{sira}</span>{html.escape(adres)}'
        duraklar.append(f"<mark>{icerik}</mark>" if sira in vurgulu else icerik)
    rota = '<span class="ok">›</span>'.join(duraklar)

    link = telefon_linki(ilk["tel"])
    if link:
        tel = f'<a class="tel" href="tel:{link}">Ara: {html.escape(ilk["tel"])}</a>'
    else:
        tel = f'<span class="tel pasif">{html.escape(ilk["tel"] or "Telefon yok")}</span>'

    return (
        '<div class="kart"><div class="ust"><div class="kimlik">'
        f'<span class="plaka"><span class="tr">TR</span><span class="pn">{html.escape(ilk["plaka"])}</span></span>'
        f'<span class="sofor">{html.escape(ilk["sofor"])}</span></div>{tel}</div>'
        f'<p class="rota">{rota}</p></div>'
    )


def sorgu_ata(deger: str) -> None:
    st.session_state["sorgu"] = deger


def oneri_uret(df: pd.DataFrame, tokenlar: list[str]) -> str | None:
    """Yazım hatası için 'bunu mu demek istediniz' önerisi."""
    sozluk = sorted({w for s in pd.concat([df["_adres"], df["sofor"].map(sadelestir)]) for w in s.split() if len(w) > 2})
    yeni, degisti = [], False
    for t in tokenlar:
        if df["_hepsi"].str.contains(t, regex=False).any():
            yeni.append(t)
            continue
        yakin = difflib.get_close_matches(t, sozluk, n=1, cutoff=0.7)
        yeni.append(yakin[0] if yakin else t)
        degisti = degisti or bool(yakin)
    return " ".join(yeni) if degisti else None


# ----------------------------------------------------------------------------
# Sayfa
# ----------------------------------------------------------------------------

st.markdown(CSS, unsafe_allow_html=True)

dosya = next((p for p in VERI_ADAYLARI if p.exists()), None)
if dosya is None:
    st.error("Veri dosyası bulunamadı. `servis.xlsx` dosyasını app.py ile aynı klasöre koyun.")
    st.stop()
try:
    df = veri_yukle(str(dosya), dosya.stat().st_mtime)
except Exception as hata:
    st.error(f"`{dosya.name}` okunamadı: {hata}")
    st.stop()

st.title("Servis güzergahları")
st.caption(f"{df['plaka'].nunique()} servis kayıtlı. Durak, plaka veya şoför adıyla arayabilirsiniz.")

ara_sekme, tum_sekme = st.tabs(["Ara", "Tüm servisler"])

with ara_sekme:
    sorgu = st.text_input(
        "Ara",
        key="sorgu",
        placeholder="Durak, plaka veya şoför adı (ör. Kozan, Özal, 1884)",
        label_visibility="collapsed",
    )
    tokenlar = sadelestir(sorgu).split()

    if not tokenlar:
        st.caption("Çok servisin uğradığı duraklar")
        sik = (
            df.groupby("_adres")
            .agg(ad=("adres", "first"), n=("plaka", "nunique"))
            .sort_values("n", ascending=False, kind="stable")
            .head(4)
        )
        for kolon, ad in zip(st.columns(len(sik)), sik["ad"]):
            kolon.button(ad, on_click=sorgu_ata, args=(ad,))
    else:
        # Her kelime satırın adresinde, plakasında veya şoför adında geçmeli.
        maske = pd.Series(True, index=df.index)
        for t in tokenlar:
            maske &= df["_hepsi"].str.contains(t, regex=False)

        if not maske.any():
            st.info(f"“{sorgu}” için sonuç yok.")
            oneri = oneri_uret(df, tokenlar)
            if oneri:
                st.button(f"Bunu mu demek istediniz: {oneri}", on_click=sorgu_ata, args=(oneri,))
            else:
                st.caption("Daha az kelimeyle veya adın bir bölümüyle deneyin.")
        else:
            # Sarı vurgu: adresinde aranan kelime geçen duraklar.
            vurgu = maske & df["_adres"].map(lambda a: any(t in a for t in tokenlar if len(t) > 1))
            vurgu_sayisi = vurgu.groupby(df["plaka"]).sum()
            plakalar = sorted(df.loc[maske, "plaka"].unique(), key=lambda p: (-vurgu_sayisi[p], p))
            st.caption(f"{len(plakalar)} servis bulundu")
            for plaka in plakalar:
                grup = df[df["plaka"] == plaka]
                st.markdown(kart_html(grup, set(grup.loc[vurgu[grup.index], "sira"])), unsafe_allow_html=True)

with tum_sekme:
    for plaka in df["plaka"].unique():  # Excel'deki sırayla
        st.markdown(kart_html(df[df["plaka"] == plaka], set()), unsafe_allow_html=True)

st.caption(f"Veri kaynağı: {dosya.name}")
