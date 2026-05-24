import streamlit as st
import pandas as pd
from datetime import datetime
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. KONFIGURASI HALAMAN & STATE
# ==========================================
st.set_page_config(page_title="Dashboard PPK - Rekap Pengadaan", page_icon="📑", layout="wide")

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
# 2. INJEKSI CSS (MINIMALIS & ELEGAN)
# ==========================================
st.markdown("""
    <style>
    /* Latar belakang aplikasi lebih bersih */
    .stApp { background-color: #f8fafc; }
    /* Mempersempit padding atas */
    .block-container { padding-top: 2rem; max-width: 96%; }
    
    /* Styling Card untuk Container */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 0.75rem;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        padding: 0.5rem;
    }
    
    /* Mempercantik Metric (Ringkasan Anggaran) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        border-left: 4px solid #0f172a;
    }
    
    /* Tabel Baris Header */
    .table-header { font-weight: 600; color: #475569; font-size: 0.9rem; padding-bottom: 0.5rem; border-bottom: 2px solid #cbd5e1; }
    /* Teks Tabel Data */
    p { margin-bottom: 0.2rem !important; font-size: 0.95rem; color: #334155; }
    
    /* Modifikasi Tombol */
    .stButton > button {
        border-radius: 0.4rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }
    /* Mencegah tooltip terpotong */
    .stTooltipIcon { position: relative; z-index: 9999; }
    div[data-testid="stTooltipContent"] { width: max-content !important; max-width: 350px !important; white-space: normal !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. KONEKSI GOOGLE SHEETS & FUNGSI BANTU
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_NAME = "Sheet1"
COLS = ["id", "tahun_anggaran", "tanggal", "nama_pengadaan", "jenis_pajak", "punya_npwp", "bruto", "dpp", "ppn", "pph", "netto", "keterangan"]

def safe_parse_bool(val):
    """Fungsi tangguh untuk membaca boolean dari GSheets"""
    if isinstance(val, bool): return val
    if pd.isna(val): return False
    return str(val).strip().upper() in ['TRUE', '1', 'YA', 'Y', 'YES', 'T']

def get_data():
    try:
        df = conn.read(worksheet=SHEET_NAME, usecols=list(range(len(COLS))), ttl=0)
        df = df.dropna(how="all")
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame(columns=COLS)
        
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        df['tahun_anggaran'] = pd.to_numeric(df['tahun_anggaran'], errors='coerce').fillna(2026).astype(int)
        df['punya_npwp'] = df['punya_npwp'].apply(safe_parse_bool) # PERBAIKAN BUG NPWP
        
        for col in ['bruto', 'dpp', 'ppn', 'pph', 'netto']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        return df
    except Exception as e:
        return pd.DataFrame(columns=COLS)

def save_data(df):
    conn.update(worksheet=SHEET_NAME, data=df)
    st.cache_data.clear()

def parse_number(val):
    if isinstance(val, (int, float)): return int(val)
    cleaned = re.sub(r'\D', '', str(val))
    return int(cleaned) if cleaned else 0

def format_rupiah(angka):
    return f"{int(angka):,}".replace(",", ".")

def format_indo_csv(val):
    if pd.isna(val): return ""
    s = f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-3] if s.endswith(",00") else s

def get_display_pajak(pajak_str, punya_npwp):
    if "1.5% / 3%" in pajak_str: return pajak_str.replace("1.5% / 3%", "1.5%" if punya_npwp else "3%")
    if "2% / 4%" in pajak_str: return pajak_str.replace("2% / 4%", "2%" if punya_npwp else "4%")
    return pajak_str

def hitung_pajak(bruto, kategori_pajak, punya_npwp, manual_rate=0.0):
    ppn_rate, batas_pemungutan = 0.11, 2000000
    kat_engine, pph_rate = "Lainnya", 0.0

    if "Barang" in kategori_pajak: kat_engine, pph_rate = "Barang", 0.015 if punya_npwp else 0.030
    elif "Jasa" in kategori_pajak: kat_engine, pph_rate = "Jasa", 0.020 if punya_npwp else 0.040
    elif "Sewa" in kategori_pajak: kat_engine, pph_rate = "Sewa", 0.100
    elif "1.75%" in kategori_pajak: kat_engine, pph_rate = "Konstruksi", 0.0175
    elif "2.65%" in kategori_pajak: kat_engine, pph_rate = "Konstruksi", 0.0265
    elif "3.50%" in kategori_pajak: kat_engine, pph_rate = "Konstruksi", 0.0350
    elif "4.00%" in kategori_pajak: kat_engine, pph_rate = "Konstruksi", 0.0400
    elif "6.00%" in kategori_pajak: kat_engine, pph_rate = "Konstruksi", 0.0600
    elif "Bebas Pajak" in kategori_pajak: return bruto, 0, 0, bruto
    elif "Manual" in kategori_pajak: kat_engine, pph_rate = "Lainnya", manual_rate / 100.0

    if bruto <= batas_pemungutan:
        dpp, ppn = bruto, 0
        pph = 0 if kat_engine == "Barang" else dpp * pph_rate
    else:
        dpp = bruto / (1 + ppn_rate)
        ppn, pph = dpp * ppn_rate, dpp * pph_rate
        
    return dpp, ppn, pph, bruto - ppn - pph

opsi_pajak_list = [
    "Barang (PPh 22) - 1.5% / 3%", "Jasa (PPh 23) - 2% / 4%", "Sewa Tanah/Bangunan (PPh 4 ayat 2) - 10%",
    "Pelaksanaan Konstruksi: Kecil/Perseorangan - 1.75%", "Pelaksanaan Konstruksi: Menengah/Besar/Spesialis - 2.65%",
    "Pelaksanaan Konstruksi: Tidak Memiliki SBU/SKK - 4.00%", "Konsultansi Konstruksi: Memiliki SBU/SKK - 3.50%",
    "Konsultansi Konstruksi: Tidak Memiliki SBU/SKK - 6.00%", "Pekerjaan Konstruksi Terintegrasi: Memiliki SBU - 2.65%",
    "Pekerjaan Konstruksi Terintegrasi: Tidak Memiliki SBU - 4.00%", "Bebas Pajak / Non-Objek", "Input Manual / Lainnya"
]

def format_angka_ribuan(key):
    cleaned = re.sub(r'\D', '', str(st.session_state[key]))
    st.session_state[key] = f"{int(cleaned):,}" if cleaned else "0"

# ==========================================
# 4. SISTEM LOGIN
# ==========================================
def login_screen():
    _, col2, _ = st.columns([1.5, 2, 1.5])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #0f172a;'>🔐 Portal PPK</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #64748b;'>Sistem Rekapitulasi Pengadaan Barang & Jasa</p>", unsafe_allow_html=True)
            st.divider()
            with st.form("login_form"):
                tahun_sekarang = datetime.now().year
                daftar_tahun = sorted(list(set([tahun_sekarang - 1, tahun_sekarang, tahun_sekarang + 1, 2026])))
                pilihan_tahun = st.selectbox("Tahun Anggaran", daftar_tahun, index=daftar_tahun.index(2026))
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit_login = st.form_submit_button("Masuk", use_container_width=True, type="primary")
                
                if submit_login:
                    if username == "admin" and password == "ppk123":
                        st.session_state.logged_in = True
                        st.session_state.tahun_anggaran = pilihan_tahun
                        st.rerun()
                    else:
                        st.error("Kredensial tidak sah!")

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================
def main_dashboard():
    if st.session_state.show_toast:
        st.toast(st.session_state.show_toast)
        st.session_state.show_toast = None

    df_utama = get_data()

    # HEADER DASHBOARD
    c_title, c_logout = st.columns([5, 1])
    with c_title:
        st.markdown(f"<h2 style='color: #0f172a; margin-bottom: 0;'>Papan Kendali Pengadaan</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #64748b; font-size: 1.1rem;'>Tahun Anggaran {st.session_state.tahun_anggaran} | Dokumen Tersinkronisasi ✅</p>", unsafe_allow_html=True)
    with c_logout:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Keluar", use_container_width=True):
            st.session_state.logged_in, st.session_state.tahun_anggaran = False, None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SECTION 1: FORM TAMBAH DATA (CARD) ---
    with st.container(border=True):
        st.markdown("<h4 style='color: #1e293b; margin-top:0;'>📝 Entri Dokumen Kuitansi</h4>", unsafe_allow_html=True)
        st.write("") # spacing
        col1, col2 = st.columns(2)
        counter = st.session_state.form_reset_counter
        
        with col1:
            nama_pengadaan = st.text_input("Uraian Pekerjaan / Kuitansi", key=f"form_nama_{counter}")
            key_bruto = f"form_bruto_{counter}"
            if key_bruto not in st.session_state: st.session_state[key_bruto] = "0"
            input_bruto = st.text_input("Nilai Kontrak/Kuitansi (Bruto)", key=key_bruto, on_change=format_angka_ribuan, args=(key_bruto,))
            punya_npwp = st.checkbox("Penyedia Memiliki NPWP", value=True, key=f"form_npwp_{counter}")
        
        with col2:
            jenis_pajak = st.selectbox("Klasifikasi Pemungutan Pajak", opsi_pajak_list, key=f"form_pajak_{counter}")
            manual_rate = st.number_input("Rate PPh Manual (%)", min_value=0.0, step=0.1, value=2.0, key=f"form_manual_{counter}") if jenis_pajak == "Input Manual / Lainnya" else 0.0
            keterangan = st.text_input("Keterangan Tambahan", key=f"form_ket_{counter}", placeholder="Opsional...")
            
        st.write("")
        if st.button("➕ Hitung & Simpan ke Database", use_container_width=True, type="primary"):
            nilai_bruto = parse_number(input_bruto)
            if not nama_pengadaan: st.error("Uraian Pekerjaan wajib diisi!")
            elif nilai_bruto <= 0: st.error("Nilai Kontrak harus lebih dari Rp 0!")
            else:
                dpp, ppn, pph, netto = hitung_pajak(nilai_bruto, jenis_pajak, punya_npwp, manual_rate)
                pajak_tersimpan = f"Manual ({manual_rate}%)" if jenis_pajak == "Input Manual / Lainnya" else jenis_pajak
                
                new_id = 1 if df_utama.empty else int(df_utama['id'].max()) + 1
                waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                data_baru = pd.DataFrame([{
                    "id": new_id, "tahun_anggaran": st.session_state.tahun_anggaran, "tanggal": waktu_sekarang,
                    "nama_pengadaan": nama_pengadaan, "jenis_pajak": pajak_tersimpan, "punya_npwp": bool(punya_npwp),
                    "bruto": nilai_bruto, "dpp": dpp, "ppn": ppn, "pph": pph, "netto": netto, "keterangan": keterangan
                }])
                df_update = pd.concat([df_utama, data_baru], ignore_index=True)
                save_data(df_update)
                st.session_state.show_toast = f"✅ Berkas sah: {nama_pengadaan} tersimpan!"
                st.session_state.form_reset_counter += 1
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SECTION 2: RINGKASAN ANGGARAN ---
    df_filter = df_utama[df_utama['tahun_anggaran'] == st.session_state.tahun_anggaran]
    st.markdown("<h4 style='color: #1e293b;'>📈 Ringkasan Penyerapan</h4>", unsafe_allow_html=True)
    
    if not df_filter.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Nilai Kuitansi (Bruto)", f"Rp {format_rupiah(df_filter['bruto'].sum())}")
        m2.metric("Total PPN Dipungut", f"Rp {format_rupiah(df_filter['ppn'].sum())}")
        m3.metric("Total PPh Dipungut", f"Rp {format_rupiah(df_filter['pph'].sum())}")
        m4.metric("Total Berkas Diterbitkan", f"{len(df_filter)} Dokumen")
    else:
        st.info("Belum ada data kuitansi yang diterbitkan pada tahun anggaran ini.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SECTION 3: TABEL & INLINE EDIT ---
    st.markdown("<h4 style='color: #1e293b;'>📑 Buku Pembantu Pajak & Pengadaan</h4>", unsafe_allow_html=True)
    
    with st.container(border=True):
        if not df_filter.empty:
            # HEADER TABEL
            h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12 = st.columns([0.5, 1.1, 1.6, 1.5, 0.7, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4])
            labels = ["ID", "Tanggal", "Uraian Pekerjaan", "Pemungutan", "NPWP", "Bruto", "DPP", "PPN", "PPh", "Netto", "Ket", "Aksi"]
            for col, label in zip([h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12], labels):
                col.markdown(f"<div class='table-header'>{label}</div>", unsafe_allow_html=True)
            
            st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

            # ISI TABEL
            for _, row in df_filter.iterrows():
                if st.session_state.edit_id == row['id']:
                    # TAMPILAN EDIT BERUPA KOTAK FOKUS
                    with st.container(border=True):
                        with st.form(key=f"form_edit_{row['id']}"):
                            st.markdown(f"**✏️ Revisi Dokumen ID: {row['id']}**")
                            e_col1, e_col2, e_col3, e_col4 = st.columns(4)
                            edit_nama = e_col1.text_input("Uraian Pekerjaan", value=str(row['nama_pengadaan']))
                            edit_bruto_str = e_col2.text_input("Nilai Kontrak", value=f"{int(row['bruto']):,}")
                            edit_npwp = e_col3.checkbox("Penyedia Punya NPWP", value=bool(row['punya_npwp']))
                            edit_ket = e_col4.text_input("Keterangan", value=str(row['keterangan']) if pd.notna(row['keterangan']) else "")
                            
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
                            
                            col_btn1, col_btn2 = st.columns([1, 4])
                            if col_btn1.form_submit_button("💾 Update", type="primary"):
                                val_bruto = parse_number(edit_bruto_str)
                                if not edit_nama or val_bruto <= 0: st.error("Uraian tidak boleh kosong & nilai harus > 0")
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
                                    
                                    save_data(df_utama)
                                    st.session_state.edit_id = None
                                    st.session_state.show_toast = f"💾 Perubahan ID {row['id']} sah tersimpan!"
                                    st.rerun()
                                    
                            if col_btn2.form_submit_button("❌ Batal"):
                                st.session_state.edit_id = None
                                st.rerun()
                else:
                    # TAMPILAN BARIS STANDAR
                    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = st.columns([0.5, 1.1, 1.6, 1.5, 0.7, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4])
                    try: tgl_display = pd.to_datetime(row['tanggal']).strftime("%d/%m/%y")
                    except: tgl_display = str(row['tanggal'])[:10]

                    c1.write(f"**{row['id']}**")
                    c2.caption(tgl_display)
                    c3.write(row['nama_pengadaan'])
                    c4.caption(get_display_pajak(str(row['jenis_pajak']), bool(row['punya_npwp'])))
                    c5.write("✔️" if row['punya_npwp'] else "➖")
                    c6.write(format_rupiah(row['bruto']))
                    c7.write(format_rupiah(row['dpp']))
                    c8.write(format_rupiah(row['ppn']))
                    c9.write(format_rupiah(row['pph']))
                    c10.write(format_rupiah(row['netto']))
                    c11.caption(str(row['keterangan']) if pd.notna(row['keterangan']) and str(row['keterangan']).strip() else "-")
                    
                    with c12:
                        if st.session_state.confirm_del_id == row['id']:
                            st.caption("Hapus?")
                            cyes, cno = st.columns(2)
                            if cyes.button("✅", key=f"yes_{row['id']}"):
                                df_utama = df_utama[df_utama['id'] != row['id']]
                                save_data(df_utama)
                                st.session_state.confirm_del_id = None
                                st.session_state.show_toast = f"🗑️ Berkas ID {row['id']} dihapus."
                                st.rerun()
                            if cno.button("❌", key=f"no_{row['id']}"):
                                st.session_state.confirm_del_id = None
                                st.rerun()
                        else:
                            col_aksi1, col_aksi2 = st.columns(2)
                            if col_aksi1.button("✏️", key=f"edit_{row['id']}", help="Edit Data"):
                                st.session_state.edit_id, st.session_state.confirm_del_id = row['id'], None
                                st.rerun()
                            if col_aksi2.button("🗑️", key=f"del_{row['id']}", help="Hapus"):
                                st.session_state.confirm_del_id = row['id']
                                st.rerun()
                    st.markdown("<hr style='margin: 0.2rem 0; border: none; border-bottom: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
            # FITUR UNDUH
            df_download = df_filter.copy()
            df_download['jenis_pajak'] = df_download.apply(lambda r: get_display_pajak(str(r['jenis_pajak']), bool(r['punya_npwp'])), axis=1)
            df_download['punya_npwp'] = df_download['punya_npwp'].map({True: 'Ya', False: 'Tidak'})
            try: df_download['tanggal'] = pd.to_datetime(df_download['tanggal']).dt.strftime('%d/%m/%Y %H:%M')
            except: pass
            
            for col in ['bruto', 'dpp', 'ppn', 'pph', 'netto']: df_download[col] = df_download[col].apply(format_indo_csv)
            csv = df_download.to_csv(index=False, sep=';').encode('utf-8')
            
            st.download_button(
                label=f"📥 Unduh Laporan TA {st.session_state.tahun_anggaran} (CSV Excel)", data=csv,
                file_name=f"Rekap_Pengadaan_PPK_TA{st.session_state.tahun_anggaran}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv", type="secondary"
            )
        else:
            st.info("Tabel kosong. Silakan entri dokumen pada form di atas.")

# ==========================================
# 6. ROUTING APLIKASI
# ==========================================
if st.session_state.logged_in: main_dashboard()
else: login_screen()
