import streamlit as st
import pandas as pd
from datetime import datetime
import re
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ==========================================
# 1. KONFIGURASI HALAMAN & STATE
# ==========================================
st.set_page_config(page_title="Rekapitulasi Pengadaan", page_icon="📊", layout="wide")

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

# Inisialisasi counter untuk mereset form dinamis tanpa st.form
if "form_reset_counter" not in st.session_state:
    st.session_state.form_reset_counter = 0

# ==========================================
# 2. KONFIGURASI DATABASE (SQLAlchemy)
# ==========================================
Base = declarative_base()

class Pengadaan(Base):
    __tablename__ = 'rekap_pengadaan'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tahun_anggaran = Column(Integer, default=2026) # Kolom baru untuk Tahun Anggaran
    tanggal = Column(DateTime, default=datetime.now)
    nama_pengadaan = Column(String(255))
    jenis_pajak = Column(String(100))
    punya_npwp = Column(Boolean)
    bruto = Column(Float)
    dpp = Column(Float)
    ppn = Column(Float)
    pph = Column(Float)
    netto = Column(Float)
    keterangan = Column(String(255))

# Konfigurasi engine database
engine = create_engine('sqlite:///rekap_pengadaan.db', connect_args={'check_same_thread': False})

# Migrasi otomatis: Tambahkan kolom tahun_anggaran jika belum ada di database lama
# Default di-set 2026 agar isian lama otomatis menjadi tahun anggaran 2026
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE rekap_pengadaan ADD COLUMN tahun_anggaran INTEGER DEFAULT 2026;"))
except Exception:
    pass # Mengabaikan error jika kolom sudah ada

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ==========================================
# 3. FUNGSI BANTU & ENGINE PAJAK
# ==========================================
def parse_number(val):
    if isinstance(val, (int, float)):
        return int(val)
    cleaned = re.sub(r'\D', '', str(val))
    return int(cleaned) if cleaned else 0

def format_rupiah(angka):
    # Menggunakan standar ribuan titik (UI Dashboard)
    return f"{int(angka):,}".replace(",", ".")

def format_indo_csv(val):
    """Memformat angka dengan standar Indonesia: '.' untuk ribuan, ',' untuk desimal (CSV Export)"""
    if pd.isna(val): return ""
    s = f"{float(val):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if s.endswith(",00"):
        s = s[:-3] # Hapus desimal kosong jika nilai bulat bulat
    return s

def get_display_pajak(pajak_str, punya_npwp):
    """Memfilter tampilan tarif pajak sesuai status NPWP"""
    if "1.5% / 3%" in pajak_str:
        return pajak_str.replace("1.5% / 3%", "1.5%" if punya_npwp else "3%")
    if "2% / 4%" in pajak_str:
        return pajak_str.replace("2% / 4%", "2%" if punya_npwp else "4%")
    return pajak_str

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
        kat_engine = "Bebas"
        pph_rate = 0.0
    elif "Manual" in kategori_pajak:
        kat_engine = "Lainnya"
        pph_rate = manual_rate / 100.0

    if kat_engine == "Bebas":
        return bruto, 0, 0, bruto

    # Logika Batas Pemungutan Bendahara
    if bruto <= batas_pemungutan:
        dpp = bruto
        ppn = 0
        if kat_engine == "Barang":
            pph = 0
        else:
            pph = dpp * pph_rate
    else:
        dpp = bruto / (1 + ppn_rate)
        ppn = dpp * ppn_rate
        pph = dpp * pph_rate
        
    netto = bruto - ppn - pph
    return dpp, ppn, pph, netto

opsi_pajak_list = [
    "Barang (PPh 22) - 1.5% / 3%",
    "Jasa (PPh 23) - 2% / 4%",
    "Sewa Tanah/Bangunan (PPh 4 ayat 2) - 10%",
    "Pelaksanaan Konstruksi: Kecil/Perseorangan - 1.75%",
    "Pelaksanaan Konstruksi: Menengah/Besar/Spesialis - 2.65%",
    "Pelaksanaan Konstruksi: Tidak Memiliki SBU/SKK - 4.00%",
    "Konsultansi Konstruksi: Memiliki SBU/SKK - 3.50%",
    "Konsultansi Konstruksi: Tidak Memiliki SBU/SKK - 6.00%",
    "Pekerjaan Konstruksi Terintegrasi: Memiliki SBU - 2.65%",
    "Pekerjaan Konstruksi Terintegrasi: Tidak Memiliki SBU - 4.00%",
    "Bebas Pajak / Non-Objek",
    "Input Manual / Lainnya"
]

def format_angka_ribuan(key):
    val = st.session_state[key]
    cleaned = re.sub(r'\D', '', str(val))
    if cleaned:
        st.session_state[key] = f"{int(cleaned):,}"
    else:
        st.session_state[key] = "0"

# ==========================================
# 4. SISTEM LOGIN
# ==========================================
def login_screen():
    st.markdown("<h2 style='text-align: center;'>🔐 Login Sistem Rekapitulasi Pengadaan</h2>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            # Tambahan input untuk Tahun Anggaran
            tahun_sekarang = datetime.now().year
            daftar_tahun = [tahun_sekarang - 1, tahun_sekarang, tahun_sekarang + 1]
            if 2026 not in daftar_tahun:
                daftar_tahun.append(2026)
            daftar_tahun.sort()
            
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
# 5. DASHBOARD UTAMA
# ==========================================
def main_dashboard():
    # -----------------------------------------------------
    # INJEKSI CSS - Diperbaiki untuk tooltip dan layout tombol
    # -----------------------------------------------------
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        div[data-testid="column"] { padding-bottom: 0px !important; overflow: visible !important; }
        p { margin-bottom: 0.1rem !important; font-size: 0.95rem; }
        
        /* Modifikasi untuk mencegah tooltip terpotong */
        .stTooltipIcon { position: relative; z-index: 9999; }
        div[data-testid="stTooltipContent"] {
            width: max-content !important;
            max-width: 350px !important;
            white-space: normal !important;
            z-index: 99999 !important;
        }
        
        /* Tombol lebih compact */
        .stButton > button {
            padding: 4px 8px !important;
            height: auto !important;
            min-height: 32px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    session = SessionLocal()
    
    if st.session_state.show_toast:
        st.toast(st.session_state.show_toast)
        st.session_state.show_toast = None

    c_title, c_logout = st.columns([4, 1])
    with c_title:
        st.title(f"📊 Dashboard Rekapitulasi (TA {st.session_state.tahun_anggaran})")
        st.write("Pencatatan nilai kuitansi, PPN, dan PPh dengan fitur otomatis.")
    with c_logout:
        if st.button("Keluar (Logout)", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.tahun_anggaran = None
            st.rerun()

    st.divider()

    # --- SECTION 1: TAMBAH DATA ---
    st.subheader("📝 Tambah Data Pengadaan Baru")
    
    col1, col2 = st.columns(2)
    counter = st.session_state.form_reset_counter
    
    with col1:
        nama_pengadaan = st.text_input("Nama Pengadaan / Uraian Kuitansi", key=f"form_nama_{counter}")
        
        key_bruto = f"form_bruto_{counter}"
        if key_bruto not in st.session_state:
            st.session_state[key_bruto] = "0"
            
        input_bruto = st.text_input("Nilai Pengadaan (Bruto)", 
                                    key=key_bruto, 
                                    on_change=format_angka_ribuan, 
                                    args=(key_bruto,),
                                    help="Ketik angka lalu tekan Tab atau klik di luar kotak untuk memunculkan pemisah ribuan")
        
        punya_npwp = st.checkbox("Punya NPWP", value=True, key=f"form_npwp_{counter}")
    
    with col2:
        jenis_pajak = st.selectbox("Klasifikasi Pajak", opsi_pajak_list, key=f"form_pajak_{counter}")
        
        manual_rate = 0.0
        if jenis_pajak == "Input Manual / Lainnya":
            manual_rate = st.number_input("Masukkan Persentase PPh (%)", min_value=0.0, step=0.1, value=2.0, key=f"form_manual_{counter}")
            
        keterangan = st.text_input("Keterangan Tambahan (Opsional)", key=f"form_ket_{counter}")
        
    submit_data = st.button("Hitung & Simpan ke Database", use_container_width=True, type="primary")

    if submit_data:
        nilai_bruto = parse_number(input_bruto)
        
        if not nama_pengadaan:
            st.error("Nama pengadaan tidak boleh kosong!")
        elif nilai_bruto <= 0:
            st.error("Nilai pengadaan harus lebih dari Rp 0!")
        else:
            dpp, ppn, pph, netto = hitung_pajak(nilai_bruto, jenis_pajak, punya_npwp, manual_rate)
            pajak_tersimpan = f"Manual ({manual_rate}%)" if jenis_pajak == "Input Manual / Lainnya" else jenis_pajak
            
            data_baru = Pengadaan(
                tahun_anggaran=st.session_state.tahun_anggaran,
                nama_pengadaan=nama_pengadaan,
                jenis_pajak=pajak_tersimpan,
                punya_npwp=punya_npwp,
                bruto=nilai_bruto,
                dpp=dpp,
                ppn=ppn,
                pph=pph,
                netto=netto,
                keterangan=keterangan
            )
            session.add(data_baru)
            session.commit()
            
            st.session_state.show_toast = f"✅ Berhasil menambahkan: {nama_pengadaan}"
            st.session_state.form_reset_counter += 1
            st.rerun()

    st.divider()

    # Query data difilter berdasarkan Tahun Anggaran aktif
    semua_data = session.query(Pengadaan).filter(Pengadaan.tahun_anggaran == st.session_state.tahun_anggaran).order_by(Pengadaan.id.asc()).all()

    # --- SECTION 2: RINGKASAN ANGGARAN ---
    st.subheader(f"📈 Ringkasan Anggaran TA {st.session_state.tahun_anggaran}")
    if semua_data:
        total_bruto = sum(d.bruto for d in semua_data)
        total_ppn = sum(d.ppn for d in semua_data)
        total_pph = sum(d.pph for d in semua_data)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Kuitansi (Bruto)", f"Rp {format_rupiah(total_bruto)}")
        m2.metric("Total PPN Dipungut", f"Rp {format_rupiah(total_ppn)}")
        m3.metric("Total PPh Dipungut", f"Rp {format_rupiah(total_pph)}")
        m4.metric("Total Transaksi", f"{len(semua_data)} Berkas")
    else:
        st.info("Belum ada data untuk diringkas pada tahun anggaran ini.")

    st.divider()

    # --- SECTION 3: TABEL & INLINE EDIT ---
    st.subheader("📑 Tabel Rekapitulasi & Edit Data")
    
    if semua_data:
        # Penyesuaian rasio agar kolom aksi (h12) lebih lebar dan tombol tidak terjepit
        h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12 = st.columns([0.5, 1.1, 1.5, 1.6, 0.7, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.6])
        h1.markdown("**ID**")
        h2.markdown("**Tanggal**")
        h3.markdown("**Nama**")
        h4.markdown("**Pajak**")
        h5.markdown("**NPWP**")
        h6.markdown("**Bruto**")
        h7.markdown("**DPP**")
        h8.markdown("**PPN**")
        h9.markdown("**PPh**")
        h10.markdown("**Netto**")
        h11.markdown("**Ket**")
        h12.markdown("**Aksi**")
        
        st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 2px solid #ccc;'>", unsafe_allow_html=True)

        for baris in semua_data:
            if st.session_state.edit_id == baris.id:
                with st.container():
                    with st.form(key=f"form_edit_{baris.id}"):
                        st.markdown(f"**✏️ Mengedit Data ID: {baris.id}**")
                        e_col1, e_col2, e_col3, e_col4 = st.columns(4)
                        
                        edit_nama = e_col1.text_input("Nama Pengadaan", value=baris.nama_pengadaan)
                        edit_bruto_str = e_col2.text_input("Nilai Bruto", value=f"{int(baris.bruto):,}")
                        edit_npwp = e_col3.checkbox("Punya NPWP", value=baris.punya_npwp)
                        edit_ket = e_col4.text_input("Keterangan", value=baris.keterangan)
                        
                        e_col5, e_col6 = st.columns([2, 1])
                        
                        idx_pajak = 0
                        manual_rate_val = 2.0
                        
                        if "Manual" in baris.jenis_pajak:
                            idx_pajak = len(opsi_pajak_list) - 1
                            match = re.search(r'\d+\.\d+|\d+', baris.jenis_pajak)
                            if match:
                                manual_rate_val = float(match.group())
                        elif baris.jenis_pajak in opsi_pajak_list:
                            idx_pajak = opsi_pajak_list.index(baris.jenis_pajak)
                            
                        edit_pajak = e_col5.selectbox("Klasifikasi Pajak", opsi_pajak_list, index=idx_pajak)
                        
                        edit_manual_rate = 0.0
                        if edit_pajak == "Input Manual / Lainnya":
                            edit_manual_rate = e_col6.number_input("Rate PPh (%)", value=manual_rate_val, step=0.1)
                        
                        col_btn1, col_btn2 = st.columns([1, 4])
                        simpan_perubahan = col_btn1.form_submit_button("💾 Simpan", type="primary")
                        batal_edit = col_btn2.form_submit_button("❌ Batal")
                        
                        if batal_edit:
                            st.session_state.edit_id = None
                            st.rerun()
                            
                        if simpan_perubahan:
                            val_bruto = parse_number(edit_bruto_str)
                            if not edit_nama or val_bruto <= 0:
                                st.error("Nama tidak boleh kosong dan nilai bruto harus > 0")
                            else:
                                dpp_b, ppn_b, pph_b, netto_b = hitung_pajak(val_bruto, edit_pajak, edit_npwp, edit_manual_rate)
                                pajak_tersimpan = f"Manual ({edit_manual_rate}%)" if edit_pajak == "Input Manual / Lainnya" else edit_pajak
                                
                                row_to_update = session.query(Pengadaan).filter_by(id=baris.id).first()
                                row_to_update.nama_pengadaan = edit_nama
                                row_to_update.jenis_pajak = pajak_tersimpan
                                row_to_update.punya_npwp = edit_npwp
                                row_to_update.bruto = val_bruto
                                row_to_update.dpp = dpp_b
                                row_to_update.ppn = ppn_b
                                row_to_update.pph = pph_b
                                row_to_update.netto = netto_b
                                row_to_update.keterangan = edit_ket
                                
                                session.commit()
                                st.session_state.edit_id = None
                                st.session_state.show_toast = f"💾 Perubahan pada ID {baris.id} berhasil disimpan!"
                                st.rerun()
                st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            else:
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = st.columns([0.5, 1.1, 1.5, 1.6, 0.7, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.6])
                c1.write(baris.id)
                c2.write(baris.tanggal.strftime("%d/%m/%y"))
                c3.write(baris.nama_pengadaan)
                c4.caption(get_display_pajak(baris.jenis_pajak, baris.punya_npwp))
                c5.write("✅" if baris.punya_npwp else "❌")
                c6.write(format_rupiah(baris.bruto))
                c7.write(format_rupiah(baris.dpp))
                c8.write(format_rupiah(baris.ppn))
                c9.write(format_rupiah(baris.pph))
                c10.write(format_rupiah(baris.netto))
                c11.caption(baris.keterangan if baris.keterangan else "-")
                
                # Logika Tampilan Kolom Aksi yang dirapikan
                with c12:
                    if st.session_state.confirm_del_id == baris.id:
                        # Tampilan saat konfirmasi hapus dipencet (tombol Yakin/Batal dibuat bersebelahan)
                        st.caption("Yakin Hapus?")
                        cyes, cno = st.columns(2)
                        if cyes.button("✅", key=f"yes_del_{baris.id}", help="Konfirmasi Hapus Data"):
                            row_to_delete = session.query(Pengadaan).filter_by(id=baris.id).first()
                            session.delete(row_to_delete)
                            session.commit()
                            st.session_state.confirm_del_id = None
                            st.session_state.show_toast = f"🗑️ Data ID {baris.id} berhasil dihapus!"
                            st.rerun()
                        if cno.button("❌", key=f"no_del_{baris.id}", help="Batal Hapus"):
                            st.session_state.confirm_del_id = None
                            st.rerun()
                    else:
                        # Tampilan standar (Edit / Delete)
                        col_aksi1, col_aksi2 = st.columns(2)
                        with col_aksi1:
                            if st.button("✏️", key=f"btn_edit_{baris.id}", help="Edit Data", use_container_width=True):
                                st.session_state.edit_id = baris.id
                                st.session_state.confirm_del_id = None
                                st.rerun()
                        with col_aksi2:
                            if st.button("🗑️", key=f"btn_del_{baris.id}", help="Hapus Data", use_container_width=True):
                                st.session_state.confirm_del_id = baris.id
                                st.rerun()
                
                st.markdown("<hr style='margin: 0.3em 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                
        # Fitur Download ke CSV (Hanya untuk Tahun Anggaran Aktif)
        df_download = pd.read_sql(session.query(Pengadaan).filter(Pengadaan.tahun_anggaran == st.session_state.tahun_anggaran).statement, session.bind)
        df_download['jenis_pajak'] = df_download.apply(lambda row: get_display_pajak(row['jenis_pajak'], row['punya_npwp']), axis=1)
        df_download['punya_npwp'] = df_download['punya_npwp'].map({True: 'Ya', False: 'Tidak'})
        df_download['tanggal'] = pd.to_datetime(df_download['tanggal']).dt.strftime('%d/%m/%Y %H:%M')
        
        kolom_angka = ['bruto', 'dpp', 'ppn', 'pph', 'netto']
        for col in kolom_angka:
            df_download[col] = df_download[col].apply(format_indo_csv)
            
        csv = df_download.to_csv(index=False, sep=';').encode('utf-8')
        
        st.download_button(
            label=f"📥 Unduh Data TA {st.session_state.tahun_anggaran} (CSV Excel)",
            data=csv,
            file_name=f"Rekap_Pengadaan_TA{st.session_state.tahun_anggaran}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Tabel kosong. Silakan isi data pada form di atas.")

    session.close()

# ==========================================
# 6. ROUTING APLIKASI
# ==========================================
if st.session_state.logged_in:
    main_dashboard()
else:
    login_screen()