import pandas as pd
import streamlit as st

# CSV dosyasının adı
CSV_DOSYA_ADI = 'servis.csv'

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="Servis Güzergahı Arama Motoru", layout="wide")
st.title("🚌 Şirket Servis Güzergahı Arama Motoru")
st.markdown("---")

# --- 2. VERİ YÜKLEME VE TÜRKÇE KARAKTER ÇÖZÜMÜ ---

df = None # DataFrame'i başlangıçta boş tanımlıyoruz

try:
    # 1. Deneme: UTF-8 Kodlaması
    df = pd.read_csv(
        CSV_DOSYA_ADI,
        encoding='utf-8',
        sep=';' # Veri önizlemenize göre ayırıcı (delimiter) noktalı virgül (;) olmalı.
    )
    st.success(f"'{CSV_DOSYA_ADI}' dosyası **UTF-8** kodlaması ile başarıyla yüklendi.")

except UnicodeDecodeError:
    # 2. Deneme: Windows Türkçe (windows-1254) Kodlaması
    try:
        df = pd.read_csv(
            CSV_DOSYA_ADI,
            encoding='windows-1254',
            sep=';'
        )
        st.warning(f"'{CSV_DOSYA_ADI}' dosyası **Windows-1254** kodlaması ile yüklendi.")
    except Exception as e:
        st.error(f"Hata: Dosya okunurken kritik bir sorun oluştu: {e}")

except FileNotFoundError:
    st.error(f"Hata: **'{CSV_DOSYA_ADI}'** bulunamadı. Lütfen dosyanın aynı klasörde olduğundan emin olun.")

# --- 3. ARAMA MOTORU FONKSİYONLARI ---

if df is not None:
    # Sütun adlarını düzenliyoruz (veri önizlemesine göre)
    df.columns = ["Hedef Adres", "Servis Plakası", "Şoför Adı", "Şoför Telefonu"] + list(df.columns[4:])
    
    # Kullanıcı girişi için ana bölüm
    st.header("🔍 Adres Arama")
    
    # Adres girişi ve arama butonu
    col1, col2 = st.columns([3, 1])
    with col1:
        arama_metni = st.text_input(
            "Gitmeyi planladığınız adresin bir kısmını yazın (Örn: Turgut, Özal)",
            key="arama_metni"
        )
    with col2:
        # Arama butonu, Streamlit'te metin girişi değiştiğinde otomatik çalıştığı için bu butonu sadece görsel bir onay için kullanabiliriz.
        # Ya da formu zorlayıp sadece butona basınca çalıştırmalıyız. Biz şimdilik direkt girişe bağlı çalışalım.
        st.markdown("<br>", unsafe_allow_html=True) # Text input'ın hizasına gelmesi için boşluk
        arama_butonu = st.button("Servisleri Ara")
        
    # Arama butonu veya metin girişi doluysa filtrelemeyi yap
    if arama_metni:
        # **Filtreleme Mantığı (Türkçe Karakter Uyumlu Kısmi Eşleşme):**
        # 1. Metni küçük harfe çevir.
        # 2. 'Hedef Adres' sütununda bu metni içeren satırları bul.
        #    'case=False' ile büyük/küçük harf duyarlılığını kaldırır.
        
        # NOT: Python'da 'İ' ve 'i', 'Ş' ve 'ş' gibi dönüşümler otomatik çalışır.
        # Bu nedenle, sadece .str.lower() kullanmak genellikle yeterlidir.
        
        filtreli_df = df[
            df['Hedef Adres'].astype(str).str.contains(arama_metni, case=False, na=False)
        ]

        if filtreli_df.empty:
            st.info(f"'{arama_metni}' ifadesine uyan bir adres bulunamadı.")
        else:
            st.subheader(f"✅ '{arama_metni}' ile Eşleşen Adresler ve Servisler")
            
            # **Gruplandırma ve Çoklu Servis Görüntüleme:**
            # Aynı adrese giden birden fazla servisi listelemek için grupluyoruz.
            sonuclar = filtreli_df.groupby('Hedef Adres').agg(
                servis_plakalari=('Servis Plakası', lambda x: list(x.unique())) # Tekil plakaları listeler
            ).reset_index()

            # Her adresi ve ona giden servisleri listele
            for index, row in sonuclar.iterrows():
                adres = row['Hedef Adres']
                plakalar = ", ".join(row['servis_plakalari'])
                
                # Expand (Açılır Kapanır) ile detayları gösteriyoruz.
                with st.expander(f"📍 **{adres}** - Giden Servis Plakaları: **{plakalar}**"):
                    
                    # Bu adrese giden tüm servis kayıtlarını bul
                    adres_servisleri = filtreli_df[filtreli_df['Hedef Adres'] == adres][
                        ['Servis Plakası', 'Şoför Adı', 'Şoför Telefonu']
                    ].drop_duplicates() # Yinelenen servis-şoför ikililerini kaldır

                    # Kullanıcının seçebileceği liste
                    st.markdown("**Detayını görmek istediğiniz servisi seçin:**")
                    
                    # Servis Plakasına göre seçim kutusu
                    secilen_plaka = st.selectbox(
                        "Servis Plakası Seçimi",
                        adres_servisleri['Servis Plakası'].unique(),
                        key=f"select_{adres}_{index}" # Her selectbox'ın benzersiz bir anahtarı olmalı
                    )
                    
                    # Seçilen servisin detaylarını göster
                    if secilen_plaka:
                        detay = adres_servisleri[adres_servisleri['Servis Plakası'] == secilen_plaka].iloc[0]
                        
                        st.markdown(f"""
                        <div style="padding: 10px; border: 1px solid #1abc9c; border-radius: 5px;">
                            **Seçilen Servis Detayları**<br>
                            **Plaka:** `{detay['Servis Plakası']}`<br>
                            **Şoför Adı:** `{detay['Şoför Adı']}`<br>
                            **Şoför Telefonu:** `{detay['Şoför Telefonu']}`
                        </div>
                        """, unsafe_allow_html=True)

    elif not arama_metni and arama_butonu:
        st.warning("Lütfen bir adres girmek için metin kutusunu kullanın.")

# --- 4. ALT BİLGİ (Opsiyonel) ---
st.sidebar.markdown("---")
st.sidebar.info("Uygulama, 'servis.csv' dosyası üzerindeki verilere göre çalışmaktadır.")