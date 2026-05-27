import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. KONFIGURASI HALAMAN & STATE
# ==========================================
st.set_page_config(page_title="Rekapitulasi Pengadaan", page_icon="📊", layout="wide")

# --- INJEKSI KODE VERIFIKASI GOOGLE SEARCH CONSOLE ---
components.html(
    """
    <script>
        var meta = document.createElement('meta');
        meta.name = "google-site-verification";
        meta.content = "fFqVc0Wnb7VnRAEsJqMmMZJSJntLgJVkMmLU9K59uYQ";
        document.getElementsByTagName('head')[0].appendChild(meta);
    </script>
    """,
    height=0,
    width=0
)
# -----------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "tahun_anggaran" not in st.session_state:
    st.session_state.tahun_anggaran = None
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "confirm_del_id" not in st.session_state:
    st.session_state.confirm_del_id = None
if "show_toast" not in st.session_state:
    st.session_state.show_toast = None
if "form_reset_counter" not in st.session_state:
    st.session_state.form_reset_counter = 0

# ==========================================
# 2. INJEKSI CSS (DESAIN MINIMALIS, ELEGAN & PERBAIKAN)
# ==========================================
st.markdown("""
    <style>
    /* Latar belakang aplikasi yang bersih */
    .stApp { background-color: #f8fafc; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 98%; }
    
    /* --------------------------------------------------------------------- */
    /* PERBAIKAN TOAST NOTIFICATION (KOTAK PESAN) AGAR LEBAR & MULTILINE     */
    /* --------------------------------------------------------------------- */
    div[data-testid="stToast"] {
        min-width: 350px !important;
        width: max-content !important;
        max-width: 500px !important;
        padding: 16px !important;
        z-index: 999999 !important;
    }
    div[data-testid="stToast"] span, 
    div[data-testid="stToast"] p,
    div[data-testid="stToast"] div {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow: visible !important;
        line-height: 1.4 !important;
    }
    /* --------------------------------------------------------------------- */

    /* --------------------------------------------------------------------- */
    /* SOLUSI HOVERING TEXT TERPOTONG (AGRESIF KE SEMUA PARENT CONTAINER)    */
    /* --------------------------------------------------------------------- */
    div[data-testid="stHorizontalBlock"],
    div[data-testid="stVerticalBlock"],
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="column"],
    div[data-testid="stBlock"] { 
        padding-bottom: 0px !important; 
        overflow: visible !important; 
    }
    
    /* Target ke komponen portal tooltip (BaseWeb) yang digunakan Streamlit */
    div[data-baseweb="tooltip"],
    div[data-baseweb="popover"],
    div[data-baseweb="popper"] {
        z-index: 9999999 !important;
        overflow: visible !important;
    }

    /* Format Kotak Teks Melayang (Tooltip Hover) agar Luas, Rapi, dan Elegan */
    div[data-testid="stTooltipContent"] { 
        width: max-content !important; 
        min-width: 80px !important;
        max-width: 300px !important;
        white-space: normal !important; 
        word-wrap: break-word !important;
        overflow: visible !important;
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
        z-index: 9999999 !important;
        text-align: center !important;
        font-size: 0.85rem !important;
    }
    /* --------------------------------------------------------------------- */
    
    /* Styling Card/Wadah Kontainer Kontrol */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        padding: 12px;
    }
    
    /* Modifikasi Indikator Anggaran */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 12px 18px;
        border-radius: 6px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        border-left: 4px solid #0f172a;
    }
    
    p { margin-bottom: 0.1rem !important; font-size: 0.95rem; }
    .stButton > button { padding: 4px 8px !important; height: auto !important; min-height: 32px !important; border-radius: 4px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. KONFIGURASI DATABASE GOOGLE SHEETS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_NAME = "Sheet1"

COLS = [
    "id", "tahun_anggaran", "tanggal", "nama_pengadaan", "jenis_pajak", "punya_npwp", 
    "bruto", "dpp", "ppn", "pph", "netto", "keterangan",
    "no_kontrak", "tgl_kontrak", "no_bast", "tgl_bast", "tgl_kuitansi"
]

def get_data():
    try:
        df = conn.read(worksheet=SHEET_NAME, ttl=0)
        df = df.dropna(how="all")
        
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame(columns=COLS)
            
        for col in COLS:
            if col not in df.columns:
                df[col] = ""
                
        df = df[COLS]
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        df['tahun_anggaran'] = pd.to_numeric(df['tahun_anggaran'], errors='coerce').fillna(2026).astype(int)
        
        df['punya_npwp'] = df['punya_npwp'].map({
            True: True, False: False, 'TRUE': True, 'FALSE': False,
            'True': True, 'False': False, '1': True, '0': False,
            1: True, 0: False, 'Ya': True, 'Tidak': False, 'YA': True
        }).fillna(True).astype(bool)
        
        for col in ['bruto', 'dpp', 'ppn', 'pph', 'netto']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        kolom_teks = ['nama_pengadaan', 'jenis_pajak', 'keterangan', 'no_kontrak', 'tgl_kontrak', 'no_bast', 'tgl_bast', 'tgl_kuitansi']
        for col in kolom_teks:
            df[col] = df[col].astype(str).replace('nan', '').replace('None', '')
            
        return df
    except Exception as e:
        return pd.DataFrame(columns=COLS)

def save_data(df):
    conn.update(worksheet=SHEET_NAME, data=df)
    st.cache_data.clear()

def parse_date(date_str):
    try:
        if pd.isna(date_str) or not date_str or str(date_str).strip() == "":
            return None
        return datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d").date()
    except:
        return None

def singkatin_teks(teks, maks_karakter=75):
    """Fungsi pembantu untuk membatasi panjang teks pada notifikasi toast"""
    return teks if len(teks) <= maks_karakter else f"{teks[:maks_karakter]}..."

# ==========================================
# 4. ENGINE PERHITUNGAN PAJAK
# ==========================================
def parse_number(val):
    if isinstance(val, (int, float)): return int(val)
    cleaned = re.sub(r'\D', '', str(val))
    return int(cleaned) if cleaned else 0

def format_rupiah(angka):
    return f"{int(angka):,}".replace(",", ".")

def format_indo_csv(val):
    if pd.isna(val): return ""
    s = f"{float(val):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if s.endswith(",00"): s = s[:-3]
    return s

def get_display_pajak(pajak_str, punya_npwp):
    if "1.5% / 3%" in pajak_str: return pajak_str.replace("1.5% / 3%", "1.5%" if pph_rate_is_npwp(pajak_str, punya_npwp) else "3%")
    if "2% / 4%" in pajak_str: return pajak_str.replace("2% / 4%", "2%" if pph_rate_is_npwp(pajak_str, punya_npwp) else "4%")
    return pajak_str

def pph_rate_is_npwp(pajak_str, punya_npwp):
    return punya_npwp

def hitung_pajak(bruto, kategori_pajak, punya_npwp, manual_rate=0.0):
    ppn_rate = 0.11
    batas_pemungutan = 2000000
    kat_engine = "Lainnya"
    pph_rate = 0.0

    if "Barang" in kategori_pajak:
        kat_engine = "Barang"
        pph_rate = 0.015 if punya_npwp else 0.030
    elif "Jasa" in kategori_pajak:
        kat_engine = "Jasa"
        pph_rate = 0.020 if punya_npwp else 0.040
    elif "Sewa" in kategori_pajak:
        kat_engine = "Sewa"
        pph_rate = 0.100
    elif "1.75%" in kategori_pajak:
        kat_engine = "Konstruksi"
        pph_rate = 0.0175
    elif "2.65%" in kategori_pajak:
        kat_engine = "Konstruksi"
        pph_rate = 0.0265
    elif "3.50%" in kategori_pajak:
        kat_engine = "Konstruksi"
        pph_rate = 0.0350
    elif "4.00%" in kategori_pajak:
        kat_engine = "Konstruksi"
        pph_rate = 0.0400
    elif "6.00%" in kategori_pajak:
        kat_engine = "Konstruksi"
        pph_rate = 0.0600
    elif "Bebas Pajak" in kategori_pajak:
        return bruto, 0, 0, bruto
    elif "Manual" in kategori_pajak:
        kat_engine = "Lainnya"
        pph_rate = manual_rate / 100.0

    if bruto <= batas_pemungutan:
        dpp = bruto
        ppn = 0
        pph = 0 if kat_engine == "Barang" else dpp * pph_rate
    else:
        dpp = bruto / (1 + ppn_rate)
        ppn = dpp * ppn_rate
        pph = dpp * pph_rate
        
    netto = bruto - ppn - pph
    return dpp, ppn, pph, netto

opsi_pajak_list = [
    "Barang (PPh 22) - 1.5% / 3%", "Jasa (PPh 23) - 2% / 4%", "Sewa Tanah/Bangunan (PPh 4 ayat 2) - 10%",
    "Pelaksanaan Konstruksi: Kecil/Perseorangan - 1.75%", "Pelaksanaan Konstruksi: Menengah/Besar/Spesialis - 2.65%",
    "Pelaksanaan Konstruksi: Tidak Memiliki SBU/SKK - 4.00%", "Konsultansi Konstruksi: Memiliki SBU/SKK - 3.50%",
    "Konsultansi Konstruksi: Tidak Memiliki SBU/SKK - 6.00%", "Pekerjaan Konstruksi Terintegrasi: Memiliki SBU - 2.65%",
    "Pekerjaan Konstruksi Terintegrasi: Tidak Memiliki SBU - 4.00%", "Bebas Pajak / Non-Objek", "Input Manual / Lainnya"
]

def format_angka_ribuan(key):
    val = st.session_state[key]
    cleaned = re.sub(r'\D', '', str(val))
    st.session_state[key] = f"{int(cleaned):,}" if cleaned else "0"

# ==========================================
# 5. SISTEM LOGIN
# ==========================================
def login_screen():
    st.markdown("<h2 style='text-align: center; color: #0f172a;'>🔐 Login Sistem Rekapitulasi Pengadaan</h2>", unsafe_allow_html=True)
    st.write("---")
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            tahun_sekarang = datetime.now().year
            daftar_tahun = sorted(list(set([tahun_sekarang - 1, tahun_sekarang, tahun_sekarang + 1, 2026])))
            pilihan_tahun = st.selectbox("Tahun Anggaran", daftar_tahun, index=daftar_tahun.index(2026))
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Masuk", use_container_width=True)
            
            if submit_login:
                if username == "admin" and password == "ppk123":
                    st.session_state.logged_in = True
                    st.session_state.tahun_anggaran = pilihan_tahun
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")

# ==========================================
# 6. DASHBOARD UTAMA
# ==========================================
def main_dashboard():
    if st.session_state.show_toast:
        st.toast(st.session_state.show_toast)
        st.session_state.show_toast = None

    df_utama = get_data()

    c_title, c_logout = st.columns([4, 1])
    with c_title:
        st.title(f"📊 Dashboard Rekapitulasi (TA {st.session_state.tahun_anggaran})")
        st.write("Pencatatan nilai kuitansi, PPN, dan PPh tersinkronisasi terpusat dengan Google Sheets.")
    with c_logout:
        if st.button("Keluar (Logout)", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.tahun_anggaran = None
            st.rerun()

    st.divider()

    # --- INPUT FORM DATA BARU ---
    st.subheader("📝 Tambah Data Pengadaan Baru")
    
    col1, col2 = st.columns(2)
    counter = st.session_state.form_reset_counter
    
    with col1:
        nama_pengadaan = st.text_input("Nama Pengadaan / Uraian Kuitansi", key=f"form_nama_{counter}")
        key_bruto = f"form_bruto_{counter}"
        if key_bruto not in st.session_state: st.session_state[key_bruto] = "0"
        input_bruto = st.text_input("Nilai Pengadaan (Bruto)", key=key_bruto, on_change=format_angka_ribuan, args=(key_bruto,))
        punya_npwp = st.checkbox("Punya NPWP", value=True, key=f"form_npwp_{counter}")
    
    with col2:
        jenis_pajak = st.selectbox("Klasifikasi Pajak", opsi_pajak_list, key=f"form_pajak_{counter}")
        manual_rate = st.number_input("Masukkan Persentase PPh (%)", min_value=0.0, step=0.1, value=2.0, key=f"form_manual_{counter}") if jenis_pajak == "Input Manual / Lainnya" else 0.0
        keterangan = st.text_input("Keterangan Tambahan (Opsional)", key=f"form_ket_{counter}")
        
    # --- INPUT TAMBAHAN (KONTRAK & BAST) ---
    with st.expander("📄 Detail Dokumen Tambahan (Kontrak, BAST, & Nota)"):
        c_dok1, c_dok2, c_dok3 = st.columns([1, 1, 1])
        with c_dok1:
            no_kontrak = st.text_input("Nomor Kontrak (Opsional)", key=f"form_nokontrak_{counter}")
            tgl_kontrak = st.date_input("Tanggal Kontrak (Opsional)", value=None, key=f"form_tglkontrak_{counter}")
        with c_dok2:
            no_bast = st.text_input("Nomor BAST (Opsional)", key=f"form_nobast_{counter}")
            tgl_bast = st.date_input("Tanggal BAST (Opsional)", value=None, key=f"form_tglbast_{counter}")
        with c_dok3:
            tgl_kuitansi = st.date_input("Tanggal Kuitansi / Nota", value=datetime.now().date(), key=f"form_tglkuitansi_{counter}")

    if st.button("Hitung & Simpan ke Database", use_container_width=True, type="primary"):
        nilai_bruto = parse_number(input_bruto)
        if not nama_pengadaan: 
            st.error("Nama pengadaan tidak boleh kosong!")
        elif nilai_bruto <= 0: 
            st.error("Nilai pengadaan harus lebih dari Rp 0!")
        else:
            dpp, ppn, pph, netto = hitung_pajak(nilai_bruto, jenis_pajak, punya_npwp, manual_rate)
            pajak_tersimpan = f"Manual ({manual_rate}%)" if jenis_pajak == "Input Manual / Lainnya" else jenis_pajak
            
            new_id = 1 if df_utama.empty else int(df_utama['id'].max()) + 1
            waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            data_baru = pd.DataFrame([{
                "id": new_id, "tahun_anggaran": st.session_state.tahun_anggaran, "tanggal": waktu_sekarang,
                "nama_pengadaan": nama_pengadaan, "jenis_pajak": pajak_tersimpan, "punya_npwp": bool(punya_npwp),
                "bruto": nilai_bruto, "dpp": dpp, "ppn": ppn, "pph": pph, "netto": netto, "keterangan": keterangan,
                "no_kontrak": no_kontrak, "tgl_kontrak": str(tgl_kontrak) if tgl_kontrak else "",
                "no_bast": no_bast, "tgl_bast": str(tgl_bast) if tgl_bast else "",
                "tgl_kuitansi": str(tgl_kuitansi) if tgl_kuitansi else ""
            }])
            
            df_update = pd.concat([df_utama, data_baru], ignore_index=True)
            save_data(df_update)
            
            # FORMAT TOAST BARU: Dibatasi dengan singkatin_teks jika terlalu panjang dan di-support oleh CSS baru
            nama_rapi = singkatin_teks(nama_pengadaan)
            st.session_state.show_toast = f"✅ Berhasil menambahkan:\n{nama_rapi}"
            st.session_state.form_reset_counter += 1
            st.rerun()

    st.divider()

    df_filter = df_utama[df_utama['tahun_anggaran'] == st.session_state.tahun_anggaran]

    # --- RINGKASAN METRIC ---
    st.subheader(f"📈 Ringkasan Anggaran TA {st.session_state.tahun_anggaran}")
    if not df_filter.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Kuitansi (Bruto)", f"Rp {format_rupiah(df_filter['bruto'].sum())}")
        m2.metric("Total PPN Dipungut", f"Rp {format_rupiah(df_filter['ppn'].sum())}")
        m3.metric("Total PPh Dipungut", f"Rp {format_rupiah(df_filter['pph'].sum())}")
        m4.metric("Total Transaksi", f"{len(df_filter)} Berkas")
    else:
        st.info("Belum ada data untuk diringkas pada tahun anggaran ini.")

    st.divider()

    # --- VIEW & INLINE EDIT TABLE ---
    st.subheader("📑 Tabel Rekapitulasi & Edit Data")
    if not df_filter.empty:
        # Penambahan Header Kolom Untuk Kontrak & BAST
        h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14 = st.columns([0.4, 0.9, 1.4, 1.1, 1.1, 1.4, 0.6, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 1.3])
        header_labels = ["ID", "Tgl Kuitansi", "Nama", "Kontrak", "BAST", "Pajak", "NPWP", "Bruto", "DPP", "PPN", "PPh", "Netto", "Ket", "Aksi"]
        for col, label in zip([h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14], header_labels):
            col.markdown(f"**{label}**")
        st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 2px solid #ccc;'>", unsafe_allow_html=True)

        for _, row in df_filter.iterrows():
            if st.session_state.edit_id == row['id']:
                with st.container():
                    with st.form(key=f"form_edit_{row['id']}"):
                        st.markdown(f"**✏️ Mengedit Data ID: {row['id']}**")
                        e_col1, e_col2, e_col3, e_col4 = st.columns(4)
                        
                        edit_nama = e_col1.text_input("Nama Pengadaan", value=str(row['nama_pengadaan']))
                        edit_bruto_str = e_col2.text_input("Nilai Bruto", value=f"{int(row['bruto']):,}")
                        edit_npwp = e_col3.checkbox("Punya NPWP", value=bool(row['punya_npwp']))
                        edit_ket = e_col4.text_input("Keterangan", value=str(row['keterangan']))
                        
                        e_col5, e_col6 = st.columns([2, 1])
                        
                        idx_pajak, manual_rate_val = 0, 2.0
                        if "Manual" in str(row['jenis_pajak']):
                            idx_pajak = len(opsi_pajak_list) - 1
                            match = re.search(r'\d+\.\d+|\d+', str(row['jenis_pajak']))
                            if match: manual_rate_val = float(match.group())
                        elif row['jenis_pajak'] in opsi_pajak_list:
                            idx_pajak = opsi_pajak_list.index(row['jenis_pajak'])
                            
                        edit_pajak = e_col5.selectbox("Klasifikasi Pajak", opsi_pajak_list, index=idx_pajak)
                        edit_manual_rate = e_col6.number_input("Rate PPh (%)", value=manual_rate_val, step=0.1) if edit_pajak == "Input Manual / Lainnya" else 0.0
                        
                        # --- EDIT FORM: DOKUMEN TAMBAHAN ---
                        st.markdown("**📄 Informasi Dokumen Tambahan**")
                        e_doc1, e_doc2, e_doc3 = st.columns([1, 1, 1])
                        edit_no_kontrak = e_doc1.text_input("No Kontrak", value=str(row.get('no_kontrak', '')))
                        edit_tgl_kontrak = e_doc1.date_input("Tgl Kontrak", value=parse_date(row.get('tgl_kontrak', '')))
                        edit_no_bast = e_doc2.text_input("No BAST", value=str(row.get('no_bast', '')))
                        edit_tgl_bast = e_doc2.date_input("Tgl BAST", value=parse_date(row.get('tgl_bast', '')))
                        edit_tgl_kuitansi = e_doc3.date_input("Tgl Kuitansi", value=parse_date(row.get('tgl_kuitansi', '')) or datetime.now().date())
                        
                        col_btn1, col_btn2 = st.columns([1, 4])
                        if col_btn1.form_submit_button("💾 Simpan", type="primary"):
                            val_bruto = parse_number(edit_bruto_str)
                            if not edit_nama or val_bruto <= 0:
                                st.error("Nama tidak boleh kosong dan nilai bruto harus > 0")
                            else:
                                dpp_b, ppn_b, pph_b, netto_b = hitung_pajak(val_bruto, edit_pajak, edit_npwp, edit_manual_rate)
                                pajak_tersimpan = f"Manual ({edit_manual_rate}%)" if edit_pajak == "Input Manual / Lainnya" else edit_pajak
                                
                                idx_utama = df_utama.index[df_utama['id'] == row['id']].tolist()[0]
                                df_utama.at[idx_utama, 'nama_pengadaan'] = edit_nama
                                df_utama.at[idx_utama, 'jenis_pajak'] = pajak_tersimpan
                                df_utama.at[idx_utama, 'punya_npwp'] = bool(edit_npwp)
                                df_utama.at[idx_utama, 'bruto'] = val_bruto
                                df_utama.at[idx_utama, 'dpp'] = dpp_b
                                df_utama.at[idx_utama, 'ppn'] = ppn_b
                                df_utama.at[idx_utama, 'pph'] = pph_b
                                df_utama.at[idx_utama, 'netto'] = netto_b
                                df_utama.at[idx_utama, 'keterangan'] = edit_ket
                                
                                df_utama.at[idx_utama, 'no_kontrak'] = edit_no_kontrak
                                df_utama.at[idx_utama, 'tgl_kontrak'] = str(edit_tgl_kontrak) if edit_tgl_kontrak else ""
                                df_utama.at[idx_utama, 'no_bast'] = edit_no_bast
                                df_utama.at[idx_utama, 'tgl_bast'] = str(edit_tgl_bast) if edit_tgl_bast else ""
                                df_utama.at[idx_utama, 'tgl_kuitansi'] = str(edit_tgl_kuitansi) if edit_tgl_kuitansi else ""
                                
                                save_data(df_utama)
                                st.session_state.edit_id = None
                                st.session_state.show_toast = f"💾 Perubahan pada ID {row['id']} berhasil disimpan!"
                                st.rerun()
                                
                        if col_btn2.form_submit_button("❌ Batal"):
                            st.session_state.edit_id = None
                            st.rerun()
                st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            else:
                # Kolom penampil telah di sesuaikan proporsi rasio agar menampilkan Kontrak & BAST
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12, c13, c14 = st.columns([0.4, 0.9, 1.4, 1.1, 1.1, 1.4, 0.6, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 1.3])
                
                tgl_val = row.get('tgl_kuitansi', '')
                if not tgl_val or str(tgl_val).strip() == "":
                    tgl_val = row['tanggal']
                    
                try: tgl_display = pd.to_datetime(tgl_val).strftime("%d/%m/%y")
                except: tgl_display = str(tgl_val)[:10]

                c1.write(row['id'])
                c2.write(tgl_display)
                c3.write(row['nama_pengadaan'])
                
                # --- Format Tampilan Kolom Baru (Kontrak) ---
                no_k = str(row.get('no_kontrak', '')).strip()
                tgl_k = str(row.get('tgl_kontrak', '')).strip()
                try: 
                    tgl_k_disp = pd.to_datetime(tgl_k).strftime("%d/%m/%y") if tgl_k else ""
                except: tgl_k_disp = tgl_k
                txt_kontrak = f"{no_k}" + (f" ({tgl_k_disp})" if tgl_k_disp else "")
                c4.caption(txt_kontrak if txt_kontrak.strip() else "-")
                
                # --- Format Tampilan Kolom Baru (BAST) ---
                no_b = str(row.get('no_bast', '')).strip()
                tgl_b = str(row.get('tgl_bast', '')).strip()
                try: 
                    tgl_b_disp = pd.to_datetime(tgl_b).strftime("%d/%m/%y") if tgl_b else ""
                except: tgl_b_disp = tgl_b
                txt_bast = f"{no_b}" + (f" ({tgl_b_disp})" if tgl_b_disp else "")
                c5.caption(txt_bast if txt_bast.strip() else "-")

                c6.caption(get_display_pajak(str(row['jenis_pajak']), bool(row['punya_npwp'])))
                c7.write("✅" if bool(row['punya_npwp']) else "❌")
                c8.write(format_rupiah(row['bruto']))
                c9.write(format_rupiah(row['dpp']))
                c10.write(format_rupiah(row['ppn']))
                c11.write(format_rupiah(row['pph']))
                c12.write(format_rupiah(row['netto']))
                c13.caption(str(row['keterangan']) if str(row['keterangan']).strip() else "-")
                
                with c14:
                    if st.session_state.confirm_del_id == row['id']:
                        st.caption("Yakin Hapus?")
                        cyes, cno = st.columns(2)
                        if cyes.button("✅", key=f"yes_del_{row['id']}"):
                            df_utama = df_utama[df_utama['id'] != row['id']]
                            save_data(df_utama)
                            st.session_state.confirm_del_id = None
                            st.session_state.show_toast = f"🗑️ Data ID {row['id']} berhasil dihapus!"
                            st.rerun()
                        if cno.button("❌", key=f"no_del_{row['id']}"):
                            st.session_state.confirm_del_id = None
                            st.rerun()
                    else:
                        col_aksi1, col_aksi2 = st.columns(2)
                        if col_aksi1.button("✏️", key=f"btn_edit_{row['id']}", use_container_width=True, help="Edit Data"):
                            st.session_state.edit_id = row['id']
                            st.session_state.confirm_del_id = None
                            st.rerun()
                        if col_aksi2.button("🗑️", key=f"btn_del_{row['id']}", use_container_width=True, help="Hapus Data"):
                            st.session_state.confirm_del_id = row['id']
                            st.rerun()
                st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                
        # Fitur Export CSV
        df_download = df_filter.copy()
        df_download['jenis_pajak'] = df_download.apply(lambda r: get_display_pajak(str(r['jenis_pajak']), bool(r['punya_npwp'])), axis=1)
        df_download['punya_npwp'] = df_download['punya_npwp'].map({True: 'Ya', False: 'Tidak'})
        try: df_download['tanggal'] = pd.to_datetime(df_download['tanggal']).dt.strftime('%d/%m/%Y %H:%M')
        except: pass
        
        for col in ['bruto', 'dpp', 'ppn', 'pph', 'netto']:
            df_download[col] = df_download[col].apply(format_indo_csv)
            
        csv = df_download.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button(
            label=f"📥 Unduh Data TA {st.session_state.tahun_anggaran} (CSV Excel)", data=csv,
            file_name=f"Rekap_Pengadaan_TA{st.session_state.tahun_anggaran}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Tabel kosong. Silakan isi data pada form di atas.")

# ==========================================
# 7. ROUTING RUNNER APLIKASI
# ==========================================
if st.session_state.logged_in: 
    main_dashboard()
else: 
    login_screen()
