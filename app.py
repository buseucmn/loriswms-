import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, date 
import streamlit as st
st.set_page_config(layout="wide")
import shutil
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# ---------- DB Helpers (kalıcı kayıt) ----------
DB_PATH = "data/loris.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        # Ürünler (sen zaten kullanıyorsun; gerekirse kolon isimlerini kendi şemanla eşleştir)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT,
            cost REAL,
            price REAL,
            shelf_price REAL,
            stock_in REAL DEFAULT 0,
            stock_out REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Ürün yükleme geçmişi (opsiyonel)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Stok ham verisi (kümülatif)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            product_name TEXT,
            movement TEXT,          -- 'in' / 'out'
            quantity REAL,
            note TEXT,
            current_stock REAL,
            uploaded_at TEXT,
            batch_id TEXT
        )
        """)

        # Satış ham verisi (kümülatif)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            customer TEXT,
            product_name TEXT,
            piece INTEGER,
            sale_price REAL,
            total_cash REAL,
            total_card REAL,
            general_total REAL,
            cost REAL,
            total_cost REAL,
            payment_type TEXT,
            uploaded_at TEXT,
            batch_id TEXT
        )
        """)

        conn.commit()
def ensure_daily_backup():
    """
    data/loris.db -> backups/loris_YYYYMMDD.db
    Günlük tek kopya. Sessiz çalışır.
    """
    try:
        db = Path(DB_PATH)
        if not db.exists():
            return  # DB yoksa sessizce geç

        bdir = Path("backups")
        bdir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        target = bdir / f"loris_{today}.db"

        if not target.exists():
            shutil.copy2(db, target)
            # hiçbir mesaj gösterme (sessiz)
    except Exception:
        # Sessiz: burada kullanıcıya bir şey göstermiyoruz.
        # İstersen ileride logging ekleriz.
        pass
# Uygulama açılırken mutlaka çalışsın
init_db()
ensure_daily_backup()
# ---------- Kayıt Fonksiyonları ----------
def save_stock_rows(df_stock: pd.DataFrame, batch_id: str, filename: str = None):
    """df_stock (normalized) -> stock_raw'a ekler + upload_history kaydı."""
    if df_stock is None or df_stock.empty:
        return

    # Güvenli kolon seçimi
    cols = {c.lower(): c for c in df_stock.columns}
    def pick(name, default=None):
        return df_stock[cols[name]].copy() if name in cols else default

    to_save = pd.DataFrame({
        "date": pick("date", pd.NaT),
        "product_name": pick("product_name", ""),
        "movement": pick("movement", ""),
        "quantity": pick("quantity", 0),
        "note": pick("note", ""),
        "current_stock": pick("current_stock", 0),
    })
    to_save["uploaded_at"] = datetime.utcnow().isoformat()
    to_save["batch_id"] = batch_id

    with get_conn() as conn:
        to_save.to_sql("stock_raw", conn, if_exists="append", index=False)
        if filename:
            pd.DataFrame([{"filename": filename}]).to_sql("upload_history", conn, if_exists="append", index=False)

def save_sales_rows(df_sales: pd.DataFrame, batch_id: str, filename: str = None):
    """df_sales (normalized) -> sales_raw'a ekler + upload_history kaydı."""
    if df_sales is None or df_sales.empty:
        return

    cols = {c.lower(): c for c in df_sales.columns}
    def pick(name, default=None):
        return df_sales[cols[name]].copy() if name in cols else default

    to_save = pd.DataFrame({
        "date": pick("date", pd.NaT),
        "customer": pick("customer", ""),
        "product_name": pick("product_name", ""),
        "piece": pick("piece", 0),
        "sale_price": pick("sale_price", 0.0),
        "total_cash": pick("total_cash", 0.0),
        "total_card": pick("total_card", 0.0),
        "general_total": pick("general_total", 0.0),
        "cost": pick("cost", 0.0),
        "total_cost": pick("total_cost", 0.0),
        "payment_type": pick("payment_type", ""),
    })
    to_save["uploaded_at"] = datetime.utcnow().isoformat()
    to_save["batch_id"] = batch_id

    with get_conn() as conn:
        to_save.to_sql("sales_raw", conn, if_exists="append", index=False)
        if filename:
            pd.DataFrame([{"filename": filename}]).to_sql("upload_history", conn, if_exists="append", index=False)
# ---------- Mini çeviri yardımcı ----------
def T(tr_text, en_text):
    lang = st.session_state.get("lang", "Türkçe")
    return tr_text if lang == "Türkçe" else en_text
# === Language bootstrap & helper (GLOBAL) ===
if "lang" not in st.session_state:
    st.session_state.lang = "Türkçe"

def T(tr: str, en: str) -> str:
    """TR/EN döndüren küçük yardımcı."""
    return en if st.session_state.lang != "Türkçe" else tr
# --- Satışlar için kolon isimlerini normalize eden fonksiyon ---
def normalize(col):
    return (str(col).lower()
            .replace("ı", "i")
            .replace("ş", "s")
            .replace("ü", "u")
            .replace("ö", "o")
            .replace("ç", "c")
            .strip())

rename_map_sales = {
    "date": "date",
    "tarih": "date",

    "customer": "customer",
    "müşteri": "customer",
    "musteri": "customer",

    "product name": "product_name",
    "ürün adı": "product_name",
    "urun adi": "product_name",

    "current stock": "current_stock",  # sadece okunacak, hesaplamada kullanmıyoruz

    "sale price": "sale_price",
    "satış fiyatı": "sale_price",
    "satis fiyati": "sale_price",
    "price": "sale_price",

    "piece": "quantity",
    "adet": "quantity",

    "cash": "cash",
    "nakit": "cash",

    "card": "card",
    "kart": "card",

    "total cash": "total_cash",
    "total card": "total_card",

    "general total": "general_total",
    "genel toplam": "general_total",

    "cost": "cost",
    "alış fiyatı": "cost",
    "alis fiyati": "cost",

    "total cost": "total_cost",
    "toplam maliyet": "total_cost"
}

# Products tablosuna gerekli kolonları ekle (eksikse)
def ensure_product_columns():
    expected_cols = {
        "upload_id": "INTEGER",
        "product_name": "TEXT",
        "unit": "TEXT",
        "cost": "REAL DEFAULT 0",
        "price": "REAL DEFAULT 0",
        "shelf_price": "REAL DEFAULT 0",
        "stock_in": "INTEGER DEFAULT 0",
        "stock_out": "INTEGER DEFAULT 0",
        "notes": "TEXT"
    }
    with get_conn() as conn:
        cur = conn.cursor()
        # mevcut kolonları oku
        cur.execute("PRAGMA table_info(products)")
        existing = [row[1] for row in cur.fetchall()]
        # eksikleri ekle
        for col, coltype in expected_cols.items():
            if col not in existing:
                cur.execute(f"ALTER TABLE products ADD COLUMN {col} {coltype}")
        conn.commit()

ensure_product_columns()
# Upload history tablosunu oluştur
def ensure_upload_history():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
        """)
        conn.commit()

ensure_upload_history()

# --- Mini çeviri helper'ı (genel sözlük gelene kadar) ---
def L(tr, en):
    return tr if st.session_state.get("lang", "Türkçe") == "Türkçe" else en


# ---------- ÜRÜN YARDIMCI FONKSİYONLARI ----------

def list_products(search: str = "", include_inactive: bool = False) -> pd.DataFrame:
    q = """
    SELECT id, name AS "Ürün Adı", barcode AS "Barkod", price AS "Fiyat",
           stock AS "Stok", description AS "Açıklama", is_active AS "Aktif",
           created_at AS "Oluşturma", updated_at AS "Güncelleme"
    FROM products
    WHERE 1=1
    """
    params = []
    if not include_inactive:
        q += " AND is_active = 1"
    if search:
        q += " AND (LOWER(name) LIKE ? OR LOWER(IFNULL(barcode,'')) LIKE ?)"
        s = f"%{search.lower()}%"
        params += [s, s]
    q += " ORDER BY name ASC"
    with get_conn() as conn:
        df = pd.read_sql_query(q, conn, params=params)
    return df

def add_stock_move(product_id: int, change: int, reason: str = "manual", ref: str = None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO stock_moves (product_id, change, reason, ref, ts) VALUES (?,?,?,?,?)",
            (product_id, change, reason, ref, datetime.utcnow().isoformat())
        )
        conn.commit()

def add_product(name: str, barcode: str, price: float, stock: int, description: str):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO products (name, barcode, price, stock, description, is_active, created_at, updated_at)
            VALUES (?,?,?,?,?,1,?,?)
        """, (name.strip(), (barcode or None), float(price or 0), int(stock or 0), (description or "").strip(), now, now))
        pid = c.lastrowid
        conn.commit()
    if stock:
        add_stock_move(pid, int(stock), reason="initial")
    return pid

def update_product(pid: int, name: str, barcode: str, price: float, stock: int, description: str):
    # Mevcut stok ile yeni stok arasındaki farkı hareket olarak yaz
    with get_conn() as conn:
        c = conn.cursor()
        old = c.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
        old_stock = int(old[0]) if old else 0
        diff = int(stock) - old_stock
        now = datetime.utcnow().isoformat()
        c.execute("""
            UPDATE products
               SET name=?, barcode=?, price=?, stock=?, description=?, updated_at=?
             WHERE id=?
        """, (name.strip(), (barcode or None), float(price or 0), int(stock or 0), (description or "").strip(), now, pid))
        conn.commit()
    if diff != 0:
        add_stock_move(pid, diff, reason="manual_adjust")

def soft_delete_product(pid: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET is_active=0, updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), pid))
        conn.commit()

def restore_product(pid: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET is_active=1, updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), pid))
        conn.commit()

# ---------- EXCEL İÇE/DIŞA AKTARIM ----------

PRODUCTS_COL_MAP = {
    # bizde → onlardan gelebilecek olası isimler
    "name": ["name", "ürün adı", "urun adi", "ürün", "product", "product name"],
    "barcode": ["barcode", "barkod", "code", "sku"],
    "price": ["price", "fiyat", "satış fiyatı", "satis fiyati", "unit price"],
    "stock": ["stock", "stok", "quantity", "qty", "adet"],
    "description": ["description", "açıklama", "aciklama", "desc", "notes", "note"]
}

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c: str(c).strip().lower() for c in df.columns}
    df = df.rename(columns=cols)
    # duplicate/nan kolon temizliği
    df = df.loc[:, ~df.columns.str.contains(r"^unnamed|^nan$", case=False, na=False)]
    # hedef kolon isimlerini bul
    target = {}
    for target_col, candidates in PRODUCTS_COL_MAP.items():
        for cand in candidates:
            if cand in df.columns:
                target[target_col] = cand
                break
    # olmayanlara varsayılan kolon ekle
    for key in ["name","barcode","price","stock","description"]:
        if key not in target:
            df[key] = None
    # yalnızca hedef kolonları sırala
    out = pd.DataFrame({
        "name": df.get(target.get("name","name"), None),
        "barcode": df.get(target.get("barcode","barcode"), None),
        "price": df.get(target.get("price","price"), 0),
        "stock": df.get(target.get("stock","stock"), 0),
        "description": df.get(target.get("description","description"), None),
    })
    # tip dönüşümleri
    out["name"] = out["name"].astype(str).str.strip()
    out["barcode"] = out["barcode"].astype(str).str.strip().replace({"None": None, "nan": None})
    # fiyat: 1.234,56 → 1234.56
    out["price"] = (
        out["price"].astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    out["price"] = pd.to_numeric(out["price"], errors="coerce").fillna(0.0)
    out["stock"] = pd.to_numeric(out["stock"], errors="coerce").fillna(0).astype(int)
    out["description"] = out["description"].fillna("").astype(str).str.strip()
    # boş isimleri ele
    out = out[out["name"].str.len() > 0]
    return out.reset_index(drop=True)

def import_products_from_excel(file) -> pd.DataFrame:
    raw = pd.read_excel(file)
    norm = _normalize_columns(raw)
    results = []
    for _, r in norm.iterrows():
        try:
            pid = add_product(
                name=r["name"],
                barcode=(None if r["barcode"] in (None, "", "None", "nan") else r["barcode"]),
                price=float(r["price"]),
                stock=int(r["stock"]),
                description=r["description"]
            )
            results.append({"name": r["name"], "status": "OK", "id": pid})
        except sqlite3.IntegrityError as e:
            results.append({"name": r["name"], "status": f"SKIP (duplicate barcode)"})
        except Exception as e:
            results.append({"name": r["name"], "status": f"ERROR: {e}"})
    return pd.DataFrame(results)

def export_products_to_excel(include_inactive: bool = False) -> BytesIO:
    df = list_products(include_inactive=include_inactive)
    # Excel'e yaz
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)
    bio.seek(0)
    return bio


# Kullanıcı listesi (şimdilik sabit)
# Kullanıcı listesi (.env'den)
import os

def _env_user(user_key: str, pass_key: str, role: str):
    """ .env içinden kullanıcıyı okuyup sözlüğe dönüştürür """
    u = os.getenv(user_key, "").strip()
    p = os.getenv(pass_key, "").strip()
    if u and p:
        return {u: {"password": p, "role": role}}
    return {}

USERS = {}
# admin1 (varsa)
USERS.update(_env_user("ADMIN1_USER", "ADMIN1_PASS", "admin"))

# merve = personel
USERS.update(_env_user("MERVE_USER", "MERVE_PASS", "personel"))

# ali = admin
USERS.update(_env_user("ALI_USER", "ALI_PASS", "admin"))

# mehmet = admin
USERS.update(_env_user("MEHMET_USER", "MEHMET_PASS", "admin"))

# personel1 = personel
USERS.update(_env_user("PERSON1_USER", "PERSON1_PASS", "personel"))
# --- Session defaults (mutlaka tek kopya) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None
if "user" not in st.session_state:
    st.session_state.user = None
if "lang" not in st.session_state:
    st.session_state.lang = "Türkçe"
# Basit çeviri helper'ı
T = lambda tr, en: tr if st.session_state.get("lang", "Türkçe") == "Türkçe" else en
# Login ekranı
if not st.session_state.logged_in:
    st.title("🔐 LORISWMS — Pilot Login")

    # (Burada zaten dil seçiminiz var — bırakın)
    # Örn: st.session_state.lang -> "Türkçe" / "English"

    if st.session_state.lang == "Türkçe":
        with st.form("login_form_tr", clear_on_submit=False):
            username = st.text_input("Kullanıcı Adı", key="__login_user__")
            password = st.text_input("Şifre", type="password", key="__login_pass__")
            submitted_tr = st.form_submit_button("Giriş Yap")

        if submitted_tr:
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.role = USERS[username]["role"]
                st.session_state.user = username
                st.success(f"Giriş başarılı! Hoş geldin, {username}")
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre")
    else:
        with st.form("login_form_en", clear_on_submit=False):
            username = st.text_input("Username", key="__login_user__")
            password = st.text_input("Password", type="password", key="__login_pass__")
            submitted_en = st.form_submit_button("Login")

        if submitted_en:
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.role = USERS[username]["role"]
                st.session_state.user = username
                st.success(f"Login successful! Welcome, {username}")
                st.rerun()
            else:
                st.error("Invalid username or password")

    # 🔴 ÖNEMLİ: Giriş yapılmadıysa uygulamanın geri kalanını ÇİZME
    st.stop()

else:
    # --- Üst bilgi ---
    role = st.session_state.role or "admin"
    user = st.session_state.user or "admin1"
    st.sidebar.title(T(f"Merhaba, {user} ({role})", f"Hello, {user} ({role})"))

    # --- Dil seçimi (girişten sonra) ---
    st.sidebar.markdown("### 🌐 " + T("Dil / Language", "Language"))
    new_lang = st.sidebar.radio(
        "",
        ["Türkçe", "English"],
        index=0 if st.session_state.lang == "Türkçe" else 1,
        key="__lang_after__",
    )
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()

    st.sidebar.markdown("---")
    # Yedek butonu: SADECE admin görsün, personel görmesin
    if (st.session_state.role or "admin") == "admin":
        with st.sidebar.expander(T("Yönetici araçları", "Admin tools"), expanded=False):
            from pathlib import Path
            dbp = Path(DB_PATH)
            st.caption(T("Tam yedek indirme yalnızca yönetici içindir.", "Full backup is admin-only."))
            if dbp.exists():
                with open(dbp, "rb") as f:
                    st.download_button(
                        label=T("Veritabanı yedeğini indir", "Download database backup"),
                        data=f.read(),
                        file_name=f"loris_{datetime.now():%Y%m%d_%H%M%S}.db",
                        mime="application/octet-stream",
                        key="dl_db_prof",
                    )
            else:
                st.caption(T("Veritabanı bulunamadı", "No database found"))
    # else: personel için hiçbir şey göstermiyoruz
        
    # --- Rol bazlı menü (tek kod, T() ile çeviri) ---
    menu_items_admin = [
        T("Ürünler", "Products"),
        T("Stoklar", "Stocks"),
        T("Satışlar", "Sales"),
        T("Raporlar", "Reports"),
        T("Çıkış", "Logout"),
    ]
    menu_items_personel = [
        T("Stoklar", "Stocks"),
        T("Raporlar", "Reports"),
        T("Çıkış", "Logout"),
    ]

    menu = st.sidebar.radio(
        T("Menü", "Menu"),
        menu_items_admin if role == "admin" else menu_items_personel,
        key="__menu__",
    )

    # --- Çıkış ---
    if menu == T("Çıkış", "Logout"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.user = None
        st.rerun()


    # Menü içerikleri (şimdilik boş sayfalar)
    if menu == T("Ürünler", "Products"):
        st.header("📦 Ürünler")

     # --- Ürünleri listele ---
        st.subheader("📋 Ürün Listesi")
        search_term = st.text_input("🔍 Ürün adı ile ara")

        df = pd.read_sql("SELECT * FROM products", get_conn())
        if search_term:
            df = df[df["name"].str.contains(search_term, case=False, na=False)]


        if not df.empty:
            # Gri kolonları hesapla
            df["Stok"] = df["stock_in"] - df["stock_out"]
            df["Alış Toplam"] = df["Stok"] * df["cost"]
            df["Satış Toplam"] = df["Stok"] * df["price"]
            df["Raf Satış Toplam"] = df["Stok"] * df["shelf_price"]

            # 12 kolon sırası
            df = df[["name", "unit", "cost", "price", "shelf_price",
                    "stock_in", "stock_out", "Stok",
                    "Alış Toplam", "Satış Toplam", "Raf Satış Toplam", "notes"]]

            st.dataframe(df, use_container_width=True)

            # Excel export
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Ürünler")
            st.download_button("📤 Excel indir",
                            out.getvalue(),
                            file_name="urunler.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Henüz ürün yok.")

        # --- Excel'den ürün yükleme ---
        st.subheader("📥 Excel'den Yükle")
        file = st.file_uploader("Excel seç (.xls, .xlsx, .xlsm)", type=["xls", "xlsx", "xlsm"])
        if file:
            try:
                # Sadece "Ürünlerim" sheetini oku
                df_upload = pd.read_excel(file, sheet_name="Ürünlerim")

                # Kolon adlarını normalize et
                def normalize(col):
                    return (str(col)
                            .lower()
                            .replace("(", "")
                            .replace(")", "")
                            .replace("₺", "")
                            .replace("£", "")
                            .replace("$", "")
                            .replace(".", "")
                            .strip())

                rename_map = {
                    "product name": "name", "ürün adı": "name", "urun adi": "name",
                    "unit": "unit", "birim": "unit",
                    "cost": "cost", "maliyet": "cost",
                    "price": "price", "satış fiyatı": "price", "satis fiyati": "price",
                    "shelf price": "shelf_price", "shelf pric": "shelf_price", "raf fiyatı": "shelf_price",
                    "stok girişi": "stock_in", "stok girisi": "stock_in", "stock in": "stock_in",
                    "stok çıkışı": "stock_out", "stok cikisi": "stock_out", "stock out": "stock_out",
                    "notes": "notes", "not": "notes"
                }

                df_upload = df_upload.rename(
                    columns={c: rename_map.get(normalize(c), c) for c in df_upload.columns}
                )

                # Sadece bizim istediğimiz kolonlar varsa onları seç
                keep_cols = ["name", "unit", "cost", "price", "shelf_price",
                            "stock_in", "stock_out", "notes"]
                df_upload = df_upload[[c for c in df_upload.columns if c in df_upload.columns and c in keep_cols]]

                # Boş satırları at
                df_upload = df_upload.dropna(subset=["name"])
                df_upload = df_upload[df_upload["name"].astype(str).str.strip() != ""]

                # DB'ye ekle
                # DB'ye kaydet
                with get_conn() as conn:
                    # önce upload_history'ye kayıt ekle
                    cur = conn.cursor()
                    cur.execute("INSERT INTO upload_history (filename, uploaded_at) VALUES (?, ?)",
                                (file.name, datetime.utcnow().isoformat()))
                    upload_id = cur.lastrowid

                    # products tablosuna dosyadan gelen ürünleri yaz
                    df_upload["upload_id"] = upload_id  # yeni kolon ekle
                    df_upload.to_sql("products", conn, if_exists="append", index=False)

                    conn.commit()


                st.success("Excel'den ürünler yüklendi!")

            except Exception as e:
                st.error(f"Excel okunamadı: {e}")

        st.divider()
        # --- Manuel Ürün Ekle ---
        with st.expander("➕ Manuel Ürün Ekle"):
            with st.form("add_manual_product", clear_on_submit=True):
                col1, col2 = st.columns(2)
                name = col1.text_input("Ürün Adı")
                unit = col2.text_input("Birim")
                col3, col4, col5 = st.columns(3)
                cost = col3.number_input("Maliyet", 0.0, step=0.01)
                price = col4.number_input("Satış Fiyatı", 0.0, step=0.01)
                shelf_price = col5.number_input("Raf Fiyatı", 0.0, step=0.01)
                col6, col7 = st.columns(2)
                stock_in = col6.number_input("Stok Girişi", 0, step=1)
                stock_out = col7.number_input("Stok Çıkışı", 0, step=1)
                notes = st.text_area("Notlar")

                submitted = st.form_submit_button("Kaydet")
                if submitted:
                    with get_conn() as conn:
                        conn.execute("""
                            INSERT INTO products 
                            (name, unit, cost, price, shelf_price, stock_in, stock_out, notes, 
                            is_active, upload_id, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, ?, ?)
                        """, (name, unit, cost, price, shelf_price, stock_in, stock_out, notes,
                            datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
                        conn.commit()
                    st.success("Manuel ürün eklendi!")
                    st.rerun()
            # --- Manuel Ürün Sil ---
        with st.expander("🗑️ Manuel Ürün Sil"):
            df_all = pd.read_sql("SELECT id, name FROM products WHERE is_active=1 AND upload_id IS NULL", get_conn())
            if not df_all.empty:
                selected = st.selectbox("Silinecek ürünü seç:", df_all["name"])
                if st.button("Sil"):
                    with get_conn() as conn:
                        conn.execute("UPDATE products SET is_active=0 WHERE name=?", (selected,))
                        conn.commit()
                    st.warning(f"{selected} silindi (is_active=0).")
                    st.rerun()
            else:
                st.info("Silinecek manuel ürün yok.")

                # --- Yükleme Geçmişi ---
        st.subheader("📜 Yükleme Geçmişi")
        df_history = pd.read_sql("SELECT * FROM upload_history ORDER BY uploaded_at DESC", get_conn())

        if not df_history.empty:
            st.table(df_history)
        else:
            st.info("Henüz yükleme yapılmadı.")
            # --- Geçmişten tek dosya silme ---
        if not df_history.empty:
            selected_id = st.selectbox("Silmek istediğin yüklemeyi seç (ID):", df_history["id"].tolist())

            if st.button("✗ Seçili Yüklemeyi Sil "):
                with get_conn() as conn:
                    conn.execute("DELETE FROM products WHERE upload_id = ?", (selected_id,))
                    conn.execute("DELETE FROM upload_history WHERE id = ?", (selected_id,))
                    conn.commit()
                st.success(f"Yükleme ID {selected_id} ve ürünleri silindi!")
                st.rerun()
    
            # --- Excel'i sıfırla ---
        if st.button("🗑️ Excel verilerini sıfırla"):
            with get_conn() as conn:
                conn.execute("DELETE FROM products")
                conn.execute("DELETE FROM upload_history")
                conn.commit()
            st.warning("Tüm Excel verileri silindi!")
            st.rerun()
        st.divider()

    elif menu == T("Stoklar", "Stocks"):
        # Basit iki dilli helper (genel i18n’i en sonda yapacağız)
        T = (lambda tr, en: en if st.session_state.get("lang", "Türkçe") != "Türkçe" else tr)

        st.header(T("📦 Stoklar", "📦 Stocks"))

        # 0) Session state
        if "stock_df" not in st.session_state:
            st.session_state.stock_df = None
        if "stock_last_batch" not in st.session_state:
            st.session_state.stock_last_batch = None

        # 0.1) DB şemasını garanti et
        with get_conn() as conn:
            # 1) Tablonun varlığını garanti et (en güncel şema)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    product_name TEXT,
                    movement TEXT,
                    quantity REAL,
                    note TEXT,
                    current_stock REAL,
                    uploaded_at TEXT,
                    batch_id INTEGER
                )
            """)
            conn.commit()

            # 2) ŞEMA MİGRASYONU — eski kurulumlarda eksik kolonları ekle
            try:
                info = conn.execute("PRAGMA table_info(stock_raw)").fetchall()
                existing_cols = {row[1] for row in info}  # 0:cid, 1:name, 2:type...

                wanted = {
                    "uploaded_at": "TEXT",
                    "batch_id": "INTEGER",
                    "current_stock": "REAL",
                }
                for col, typ in wanted.items():
                    if col not in existing_cols:
                        conn.execute(f"ALTER TABLE stock_raw ADD COLUMN {col} {typ}")
                conn.commit()
            except Exception as e:
                # migrasyon hatası olursa sadece bilgi ver, akışı bozma
                st.warning(f"Şema güncelleme uyarısı: {e}")

        # 1) Excel'den yükle
        st.subheader(T("📥 Excel'den Yükle", "📥 Import from Excel"))
        file = st.file_uploader(
            T("Stok Excel seç (.xlsx, .xls, .xlsm)", "Choose stock Excel (.xlsx, .xls, .xlsm)"),
            type=["xlsx", "xls", "xlsm"],
            key="stock_upload_stable"
        )

        def _norm(s: str) -> str:
            return (str(s).lower()
                    .replace("ı","i").replace("ğ","g").replace("ş","s")
                    .replace("ö","o").replace("ü","u").replace("ç","c")
                    .strip())

        df_stock = None  # bu render'da kullanılacak tablo

        if file:
            try:
                # Sheet & başlık tespiti (A1/C5 fark etmez)
                raw_book = pd.read_excel(file, sheet_name=None, header=None)
                candidates = ["Stoklar", "Stok Hareketleri", "StokHareketleri", "Stocks", "Stock"]
                sheet_name = next((s for s in raw_book.keys()
                                if any(_norm(c) in _norm(s) for c in candidates)),
                                list(raw_book.keys())[0])
                raw = raw_book[sheet_name]

                # başlık satırı: ilk 60 satırda >=2 anahtar yakalanırsa
                keys = ["urun","ürün","product","adet","miktar","quantity","giris","giriş","cikis","çıkış","movement"]
                header_row = 0
                for i in range(min(60, len(raw))):
                    vals = [str(v).strip().lower() for v in list(raw.iloc[i, :])]
                    hit = sum(any(k in v for v in vals) for k in keys)
                    if hit >= 2:
                        header_row = i
                        break

                df = pd.read_excel(file, sheet_name=sheet_name, header=header_row)
                df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed|^nan$", case=False)]

                # kolon eşle
                rename_map = {}
                for c in df.columns:
                    cn = _norm(c)
                    if cn in ["tarih","date"]:
                        rename_map[c] = "date"
                    elif cn in ["urun adi","ürün adı","urun","product","product name"]:
                        rename_map[c] = "product_name"
                    elif cn in ["adet","miktar","qty","quantity","piece"]:
                        rename_map[c] = "quantity"
                    elif cn in ["giris / cikis","giriş / çıkış","giris","giriş","cikis","çıkış","movement","in/out","in - out"]:
                        rename_map[c] = "movement"
                    elif cn in ["aciklama","açıklama","note","notes","description","desc"]:
                        rename_map[c] = "note"
                df = df.rename(columns=rename_map)

                # çekirdek kolonlar
                for need in ["date","product_name","quantity","movement","note"]:
                    if need not in df.columns:
                        df[need] = pd.NA

                # tipler
                df["product_name"] = df["product_name"].astype(str).str.strip()
                df["quantity"] = (
                    df["quantity"].astype(str)
                    .str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                )
                df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(float)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

                # movement standardizasyonu
                mv = df["movement"].astype(str).str.lower()
                mv = mv.str.replace("giriş","in").str.replace("giris","in")
                mv = mv.str.replace("çıkış","out").str.replace("cikis","out")
                df["movement"] = mv.where(mv.isin(["in","out"]), "in")

                # işaretli miktar + kümülatif
                df["signed_qty"] = df.apply(lambda r: r["quantity"] if r["movement"]=="in" else -r["quantity"], axis=1)
                # ürün & tarih varsa sıralayıp No ekleyelim
                df = df.reset_index(drop=True)
                sort_cols = [c for c in ["product_name","date"] if c in df.columns]
                if sort_cols:
                    df = df.sort_values(by=sort_cols, kind="stable").reset_index(drop=True)
                df["current_stock"] = df.groupby("product_name")["signed_qty"].cumsum()
                # Görünüm için sıra numarası
                df.insert(0, T("Sıra","No"), range(1, len(df)+1))

                # ✅ KALICI KAYIT: hemen DB'ye yaz (batch_id ile)
                from datetime import datetime
                batch_id = int(datetime.utcnow().timestamp())
                to_save = df.rename(columns={T("Sıra","No"): "row_no"}).copy()
                # DB şemasına uygun kolon seti
                cols = {str(c).lower(): c for c in to_save.columns}
                def pick(name, default=None):
                    return to_save[cols[name]].copy() if name in cols else default

                persist = pd.DataFrame({
                    "date": pick("date", pd.NaT),
                    "product_name": pick("product_name",""),
                    "movement": pick("movement",""),
                    "quantity": pick("quantity",0.0),
                    "note": pick("note",""),
                    "current_stock": pick("current_stock",0.0),
                })
                persist["uploaded_at"] = datetime.utcnow().isoformat()
                persist["batch_id"] = batch_id

                with get_conn() as conn:
                    persist.to_sql("stock_raw", conn, if_exists="append", index=False)
                    ensure_daily_backup()
                # Session'a yaz (ekranda kalsın) + son batch
                st.session_state.stock_df = df
                st.session_state.stock_last_batch = batch_id

                st.success(T(f"Stok verisi yüklendi ve kaydedildi (Sayfa: {sheet_name}).",
                            f"Stock data loaded & saved (Sheet: {sheet_name})."))

                

            except Exception as e:
                st.error(T(f"Excel okunamadı: {e}", f"Failed to read Excel: {e}"))
                df_stock = None

        # 2) Uygulama yeniden başlasa bile DB'den geri yükle
        if df_stock is None:
            # Önce session’dan dene
            df_stock = st.session_state.stock_df

        if df_stock is None:
            # DB’den oku (son batch’i tercih et; yoksa tümünü)
            try:
                with get_conn() as conn:
                    df_db = pd.read_sql("SELECT date, product_name, movement, quantity, note, current_stock, uploaded_at, batch_id FROM stock_raw", conn)
                if not df_db.empty:
                    # Son batch’i bul
                    last_batch = df_db["batch_id"].dropna().astype("int64").max()
                    dfx = df_db[df_db["batch_id"] == last_batch] if pd.notna(last_batch) else df_db
                    # tipler
                    dfx["date"] = pd.to_datetime(dfx["date"], errors="coerce").dt.date
                    dfx["product_name"] = dfx["product_name"].astype(str)
                    dfx["movement"] = dfx["movement"].astype(str)
                    dfx["quantity"] = pd.to_numeric(dfx["quantity"], errors="coerce").fillna(0.0)
                    dfx["current_stock"] = pd.to_numeric(dfx["current_stock"], errors="coerce").fillna(0.0)
                    # görünüm No
                    dfx = dfx.reset_index(drop=True)
                    dfx.insert(0, T("Sıra","No"), range(1, len(dfx)+1))
                    st.session_state.stock_df = dfx
                    st.session_state.stock_last_batch = int(last_batch) if pd.notna(last_batch) else None
                    df_stock = dfx
                    st.info(T("Veri DB'den yüklendi.", "Data loaded from DB."))
            except Exception as e:
                st.error(T(f"DB okuma hatası: {e}", f"DB read error: {e}"))

        # 3) Filtreler
        st.subheader(T("🔎 Filtreler", "🔎 Filters"))
        colF1, colF2 = st.columns([2, 1])
        search_term = colF1.text_input(T("Ürün adı ara (Enter'a bas)", "Search product name (press Enter)"), value="")
        mv_pick = colF2.multiselect(
            T("Hareket tipi", "Movement type"),
            options=[T("Giriş","In"), T("Çıkış","Out")],
            default=[T("Giriş","In"), T("Çıkış","Out")]
        )

        def apply_filters(df):
            if df is None or df.empty:
                return df
            f = df.copy()
            if search_term:
                f = f[f["product_name"].astype(str).str.contains(search_term, case=False, na=False)]
            want = set()
            if T("Giriş","In") in mv_pick: want.add("in")
            if T("Çıkış","Out") in mv_pick: want.add("out")
            if want:
                f = f[f["movement"].isin(want)]
            return f

        df_view = apply_filters(df_stock)

        # 4) Görünüm + İndir
        st.subheader(T("🧾 Görünüm", "🧾 View"))
        if df_view is not None and not df_view.empty:
            first_col = "Sıra" if T("Sıra","No")=="Sıra" else "No"
            cols = [c for c in [first_col,"date","product_name","movement","quantity","current_stock","note"] if c in df_view.columns]
            show = df_view[cols].copy()
            show = show.rename(columns={
                "date": T("Tarih","Date"),
                "product_name": T("Ürün Adı","Product Name"),
                "movement": T("Hareket","Movement"),
                "quantity": T("Adet","Qty"),
                "current_stock": T("Güncel Stok","Current Stock"),
                "note": T("Açıklama","Note"),
            })
            st.dataframe(show, use_container_width=True)

            from io import BytesIO
            buff = BytesIO()
            with pd.ExcelWriter(buff, engine="openpyxl") as w:
                show.to_excel(w, index=False, sheet_name=T("Stok Hareketleri","Stock Movements"))
            st.download_button(
                T("📤 Excel indir (filtreli)","📤 Download Excel (filtered)"),
                buff.getvalue(),
                file_name=T("stok_hareketleri.xlsx","stock_movements.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info(T("Gösterilecek hareket yok.","No movements to show."))

        # 5) Temizleme seçenekleri
        with st.expander(T("🧹 Temizleme", "🧹 Cleanup")):
            cA, cB = st.columns(2)
            if cA.button(T("Geçici tabloyu temizle (ekran)","Clear temporary table (screen)")):
                st.session_state.stock_df = None
                st.info(T("Geçici tablo temizlendi. DB etkilenmedi.","Temporary table cleared. DB unaffected."))

            if cB.button(T("⚠️ Tüm stok kayıtlarını DB'den sil","⚠️ Delete ALL stock records from DB")):
                try:
                    with get_conn() as conn:
                        conn.execute("DELETE FROM stock_raw")
                        conn.commit()
                    st.session_state.stock_df = None
                    st.session_state.stock_last_batch = None
                    st.warning(T("Tüm stok kayıtları silindi.","All stock records deleted."))
                    st.rerun()
                except Exception as e:
                    st.error(T(f"Silme hatası: {e}", f"Delete error: {e}"))
   
    elif menu == T("Satışlar", "Sales"):
        # --- minik TR-EN yardımcı (sonradan global sözlüğe alacağız) ---
        T = (lambda tr, en: en if st.session_state.get("lang","Türkçe") != "Türkçe" else tr)

        # --- TL format (₺12.345,67) ---
        def tl(n):
            try:
                x = float(n)
                return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return ""

        # --- tabloyu garanti et + şema migrasyonu ---
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    customer TEXT,
                    product_name TEXT,
                    piece REAL,
                    sale_price REAL,
                    general_total REAL,
                    cost REAL,
                    total_cost REAL,
                    note TEXT,
                    uploaded_at TEXT,
                    batch_id INTEGER
                )
            """)
            # eksik kolonlar varsa ekle
            info = conn.execute("PRAGMA table_info(sales_raw)").fetchall()
            cols = {r[1] for r in info}
            want = {
                "customer":"TEXT","piece":"REAL","sale_price":"REAL","general_total":"REAL",
                "cost":"REAL","total_cost":"REAL","uploaded_at":"TEXT","batch_id":"INTEGER","note":"TEXT"
            }
            for c, typ in want.items():
                if c not in cols:
                    conn.execute(f"ALTER TABLE sales_raw ADD COLUMN {c} {typ}")
            conn.commit()

        st.header(T("💰 Satışlar", "💰 Sales"))

        # ========== 1) Excel'den yükle ==========
        st.subheader(T("📥 Excel'den Satış Yükle", "📥 Import Sales from Excel"))
        up = st.file_uploader(
            T("Satışlar Excel seç (.xlsx, .xls, .xlsm)", "Choose Sales Excel (.xlsx, .xls, .xlsm)"),
            type=["xlsx","xls","xlsm"],
            key="sales_upload_v2"
        )

        df_upload = None
        if up is not None:
            try:
                # esnek sayfa ve başlık bulucu
                wb = pd.read_excel(up, sheet_name=None, header=None)
                # aday isimler / değilse ilk sayfa
                candidates = ["satış", "satis", "sales", "satışlar", "satislar"]
                sheet = next((s for s in wb.keys() if any(c in str(s).lower() for c in candidates)), list(wb.keys())[0])
                raw = wb[sheet]

                # başlık satırı autodetect (ilk 50 satır)
                keys = ["date","tarih","customer","müşteri","urun","product","piece","adet","price","sale","genel","total"]
                header_row = 0
                for i in range(min(50, len(raw))):
                    vals = [str(v).strip().lower() for v in list(raw.iloc[i,:])]
                    if sum(any(k in v for k in keys) for v in vals) >= 2:
                        header_row = i
                        break

                df = pd.read_excel(up, sheet_name=sheet, header=header_row)
                # boş/unnamed kolonları at
                df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed|^nan$", case=False)]

                # normalize kol adları
                def norm(s:str)->str:
                    return (str(s).lower()
                            .replace("ı","i").replace("ğ","g").replace("ş","s").replace("ö","o").replace("ü","u").replace("ç","c")
                            .strip())

                rename = {}
                for c in df.columns:
                    cn = norm(c)
                    if cn in ["date","tarih"]:
                        rename[c] = "date"
                    elif cn in ["customer","musteri","müşteri"]:
                        rename[c] = "customer"
                    elif cn in ["product name","product","urun adi","urun adı","urun","ürün adi","ürün adı"]:
                        rename[c] = "product_name"
                    elif cn in ["piece","adet","miktar","qty","quantity"]:
                        rename[c] = "piece"
                    elif cn in ["sale price","saleprice","price","satis fiyati","satış fiyati","satis fiyatı","satış fiyatı","satis","satış"]:
                        rename[c] = "sale_price"
                    elif cn in ["general total","genel total","genel toplam","total","genel"]:
                        rename[c] = "general_total"
                    elif cn in ["cost","alis fiyati","alış fiyati","alis fiyatı","alış fiyatı","note"]:  # cost ile note çakışmasın
                        # 'note' özel eşleşecek aşağıda
                        pass
                    elif cn in ["total cost","toplam maliyet","total maliyet","maliyet toplam"]:
                        rename[c] = "total_cost"
                    elif cn in ["note","not","aciklama","açıklama","notes","desc","description"]:
                        rename[c] = "note"

                # 'cost' için daha açık eşleşme (üstte note ile karışmasın)
                for c in df.columns:
                    cn = norm(c)
                    if cn in ["cost","alis fiyati","alış fiyati","alis fiyatı","alış fiyatı"]:
                        rename[c] = "cost"

                df = df.rename(columns=rename)

                # eksik zorunlu kolonları oluştur
                for need in ["date","customer","product_name","piece","sale_price","general_total","cost","total_cost","note"]:
                    if need not in df.columns:
                        df[need] = pd.NA

                # sayı ayıklayıcı (₺, nokta/virgül vs)
                def to_num(x):
                    if pd.isna(x): return 0.0
                    s = str(x)
                    s = s.replace("₺","").replace("TL","").replace("TRY","").replace(" ","")
                    # binlik . / , normalize → nokta
                    s = s.replace(".", "").replace(",", ".")
                    try:
                        return float(s)
                    except:
                        return 0.0

                # tip dönüşümleri
                df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
                df["customer"] = df["customer"].astype(str).str.strip()
                df["product_name"] = df["product_name"].astype(str).str.strip()

                for col in ["piece","sale_price","general_total","cost","total_cost"]:
                    df[col] = df[col].apply(to_num)

                # eksik hesaplar:
                df.loc[(df["general_total"].isna()) | (df["general_total"]==0), "general_total"] = \
                    df["piece"] * df["sale_price"]
                df.loc[(df["total_cost"].isna()) | (df["total_cost"]==0), "total_cost"] = \
                    df["piece"] * df["cost"]

                # batch id ve kaydetme
                with get_conn() as conn:
                    cur = conn.execute("SELECT COALESCE(MAX(batch_id),0) FROM sales_raw")
                    next_batch = (cur.fetchone()[0] or 0) + 1
                    to_save = df[[
                        "date","customer","product_name","piece","sale_price",
                        "general_total","cost","total_cost","note"
                    ]].copy()
                    to_save["uploaded_at"] = datetime.utcnow().isoformat()
                    to_save["batch_id"] = next_batch
                    to_save.to_sql("sales_raw", conn, if_exists="append", index=False)
                    ensure_daily_backup()
                st.success(T("Satışlar yüklendi ve kaydedildi.", "Sales uploaded & saved."))
            except Exception as e:
                st.error(T(f"Excel okunamadı: {e}", f"Failed to read Excel: {e}"))
            else:
                # yükleme sonrası yeniden göster
                st.rerun()

       
        # ========== 3) Kümülatif Görünüm + Filtre + İndir ==========
        st.subheader(T("🧾 Satış Listesi (Kümülatif)", "🧾 Sales List (Cumulative)"))
        with get_conn() as conn:
            sales_df = pd.read_sql("""
                SELECT date, customer, product_name, piece, sale_price,
                    general_total, cost, total_cost, note, batch_id, uploaded_at
                FROM sales_raw
                ORDER BY batch_id DESC, id ASC
            """, conn)

        if sales_df.empty:
            st.info(T("Gösterilecek satış yok.", "No sales to show."))
        else:
            # filtreler
            colf1, colf2, colf3 = st.columns([2,1,1])
            q = colf1.text_input(T("Ürün adı ara (Enter'a bas)", "Search product (press Enter)"), "")
            # tarih filtreyi güvenli yap (tarih olmayan değerler varsa es geç)
            sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
            valid_dates = sales_df["date"].dropna()
            if not valid_dates.empty:
                dmin, dmax = valid_dates.min().date(), valid_dates.max().date()
                fd1, fd2 = colf2.date_input(T("Başlangıç", "Start"), dmin), colf3.date_input(T("Bitiş", "End"), dmax)
            else:
                fd1, fd2 = None, None

            view = sales_df.copy()
            if q:
                view = view[view["product_name"].str.contains(q, case=False, na=False)]
            if fd1 and fd2:
                view = view[(view["date"]>=pd.to_datetime(fd1)) & (view["date"]<=pd.to_datetime(fd2))]
            # gösterim
            show = view.copy()
            show["date"] = pd.to_datetime(show["date"]).dt.date
            for c in ["sale_price","general_total","cost","total_cost"]:
                show[c] = show[c].apply(tl)

            show = show.rename(columns={
                "date": T("Tarih","Date"),
                "customer": T("Müşteri","Customer"),
                "product_name": T("Ürün Adı","Product"),
                "piece": T("Adet","Piece"),
                "sale_price": T("Satış Fiyatı","Sale Price"),
                "general_total": T("Genel Toplam","General Total"),
                "cost": T("Maliyet","Cost"),
                "total_cost": T("Toplam Maliyet","Total Cost"),
                "note": T("Not","Note"),
                "batch_id": T("Parti","Batch"),
                "uploaded_at": T("Yüklenme","Uploaded"),
            })
            # excel sırası gibi 1..N numara
            show.insert(0, T("Sıra","No"), range(1, len(show)+1))

            st.dataframe(show, use_container_width=True)

            # indir (filtreli, sayısal kolonları sayı olarak da ekleyelim ikinci sayfada)
            buff = BytesIO()
            with pd.ExcelWriter(buff, engine="openpyxl") as w:
                show.to_excel(w, index=False, sheet_name=T("Görünüm","View"))
                # Sayısal ham veri:
                raw_out = view.rename(columns={
                    "date":"date","customer":"customer","product_name":"product_name","piece":"piece",
                    "sale_price":"sale_price","general_total":"general_total","cost":"cost","total_cost":"total_cost",
                    "note":"note","batch_id":"batch_id","uploaded_at":"uploaded_at"
                })
                raw_out.to_excel(w, index=False, sheet_name="raw")
            st.download_button(
                T("📤 Bu tabloyu indir", "📤 Download this table"),
                buff.getvalue(),
                file_name=T("satislar.xlsx","sales.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
             # ========== 2) Yükleme Geçmişi (kümülatif) ==========
        st.subheader(T("🗂️ Yükleme Geçmişi", "🗂️ Upload History"))
        with get_conn() as conn:
            hist = pd.read_sql("""
                SELECT batch_id,
                    MIN(uploaded_at) AS uploaded_at,
                    COUNT(*) AS rows,
                    SUM(general_total) AS sum_general,
                    SUM(total_cost) AS sum_cost
                FROM sales_raw
                GROUP BY batch_id
                ORDER BY batch_id DESC
            """, conn)

        if hist.empty:
            st.info(T("Henüz satış yüklenmedi.", "No uploads yet."))
        else:
            hist_show = hist.copy()
            hist_show["uploaded_at"] = pd.to_datetime(hist_show["uploaded_at"]).dt.tz_localize(None)
            hist_show["sum_general_fmt"] = hist_show["sum_general"].apply(tl)
            hist_show["sum_cost_fmt"] = hist_show["sum_cost"].apply(tl)
            hist_show = hist_show.rename(columns={
                "batch_id": T("Parti No","Batch ID"),
                "uploaded_at": T("Yüklenme Zamanı","Uploaded At"),
                "rows": T("Satır","Rows"),
                "sum_general_fmt": T("Genel Toplam","General Total"),
                "sum_cost_fmt": T("Toplam Maliyet","Total Cost"),
            })[[T("Parti No","Batch ID"), T("Yüklenme Zamanı","Uploaded At"),
                T("Satır","Rows"), T("Genel Toplam","General Total"), T("Toplam Maliyet","Total Cost")]]

            st.dataframe(hist_show, use_container_width=True)

            # Son yüklemeyi sil (revize etmek için)
            last_batch = int(hist["batch_id"].max())
            with st.expander(T("🗑️ Son Yüklemeyi Sil (Revize)", "🗑️ Delete Last Upload (Revise)")):
                st.caption(T("Sadece en son parti silinir. Tekrar doğru dosyayı yükleyebilirsiniz.",
                            "Only the last batch will be deleted. Then re-upload the corrected file."))
                if st.button(T(f"Son Partiyi Sil (#{last_batch})", f"Delete Last Batch (#{last_batch})")):
                    try:
                        with get_conn() as conn:
                            conn.execute("DELETE FROM sales_raw WHERE batch_id = ?", (last_batch,))
                            conn.commit()
                        st.success(T("Son parti silindi.", "Last batch deleted."))
                        st.rerun()
                    except Exception as e:
                        st.error(T(f"Silme hatası: {e}", f"Delete failed: {e}"))
    