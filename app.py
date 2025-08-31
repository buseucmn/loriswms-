import streamlit as st
import sqlite3, pandas as pd, numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import matplotlib.pyplot as plt
import re, uuid, os, shutil

# =========================
#  CONFIG & GLOBALS
# =========================
st.set_page_config(page_title="Loris WMS – Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>#MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}</style>""", unsafe_allow_html=True)

# ---- i18n ----
LANGS = ["tr","en"]
if "lang" not in st.session_state: st.session_state.lang = "tr"
def t(key):
    TR = {
        # menu / common
        "title": "📦 Loris WMS – Pro",
        "menu_products": "Ürünler",
        "menu_moves": "Stok Hareketleri",
        "menu_sales": "Satışlar",
        "menu_reports": "Raporlar",
        "menu_imports": "İçe Aktarım Geçmişi",
        "logout": "Çıkış Yap",
        "settings": "Ayarlar",
        "allow_negative": "Negatif stoğa izin ver",
        "language": "Dil / Language",
        "login": "Giriş",
        "username": "Kullanıcı Adı",
        "password": "Şifre",
        "login_btn": "Giriş Yap",
        "login_err": "Hatalı kullanıcı adı/şifre",

        # products
        "products_header": "Ürünler (Önizleme → Kaydet)",
        "upload_products": "📂 Ürün Excel (Depo.xlsm/Ürünlerim)",
        "preview_info": "Önizleme gösteriliyor; 'Kaydet' demeden veritabanına yazılmaz.",
        "save": "💾 Kaydet",
        "delete_preview": "🗑️ Sil (Önizleme)",
        "products_updated": "Ürünler güncellendi ✅ Güncellenen:{u} | Yeni:{c} | İlk stok girişi:{s}",
        "products_summary": "Ürün Özeti",
        "search": "Ara",
        "choose_cols": "Gösterilecek kolonlar",
        "download_excel": "⬇️ Excel indir",

        # moves
        "moves_header": "Stok Hareketleri",
        "start_date": "Başlangıç",
        "end_date": "Bitiş",

        # sales
        "sales_header": "Satışlar (Önizleme → Kaydet / Sil / Undo)",
        "upload_sales": "📂 Satış Excel (Satışlar/Sales)",
        "auto_open_note": "Son yüklenen dosya otomatik açıldı.",
        "preview_note": "Önizleme – tabloyu kontrol et. 'Kaydet' ile DB'ye yazılır.",
        "save_db": "💾 Kaydet (DB'ye işle)",
        "undo_last": "↩️ Undo (Son satış importu)",
        "saved_ok": "✅ Kaydedildi",
        "blocked_neg": "{n} satır NEGATİF stok nedeniyle engellendi (Ayarlar'dan izin verebilirsin).",
        "bad_rows": "{n} satır ürün/adet/fiyat eksik olduğu için atlandı.",
        "sales_archive": "📚 Önceden yüklenen satış dosyaları",
        "file_select": "Dosya seç",
        "preview_again": "📄 Önizle (tekrar)",
        "reprocess": "♻️ Bu dosyayı yeniden işle (Kaydet)",
        "delete_files": "🧹 Seçili dosyaları sil (Arşivden)",
        "trash_mgr": "🗑️ Çöp kutusu",
        "restore_sel": "⤴️ Seçiliyi geri getir",
        "empty_trash": "🔥 Çöp kutusunu boşalt",
        "preview_delete": "🗑️ Sil (Önizleme)",

        # imports
        "imports_header": "İçe Aktarım Geçmişi",
        "imports_download": "⬇️ Excel indir (Geçmiş)",
        "imports_select": "Seç ve Geri Al",
        "imports_undo": "↩️ Seçili importu geri al",
        "imports_done": "Geri alındı: {x}",

        # reports
        "reports_header": "Raporlar",
        "stock_report": "Stok Durumu",
        "download_stock": "⬇️ Excel indir (Stok)",
        "top_pie": "En Çok Satan Ürünler (Pasta)",
        "branch_bar": "Şube Bazlı Stok (Bar)",
        "daily_sales_profit": "Günlük Satış & Kârlılık",
    }
    EN = {
        "title": "📦 Loris WMS – Pro",
        "menu_products": "Products",
        "menu_moves": "Stock Movements",
        "menu_sales": "Sales",
        "menu_reports": "Reports",
        "menu_imports": "Import History",
        "logout": "Log out",
        "settings": "Settings",
        "allow_negative": "Allow negative stock",
        "language": "Language",
        "login": "Login",
        "username": "Username",
        "password": "Password",
        "login_btn": "Sign in",
        "login_err": "Wrong username or password",

        "products_header": "Products (Preview → Save)",
        "upload_products": "📂 Products Excel (Depo.xlsm/Ürünlerim)",
        "preview_info": "Preview only; DB is not changed until you click Save.",
        "save": "💾 Save",
        "delete_preview": "🗑️ Delete (Preview)",
        "products_updated": "Products updated ✅ Updated:{u} | New:{c} | Initial stock entries:{s}",
        "products_summary": "Products Summary",
        "search": "Search",
        "choose_cols": "Visible columns",
        "download_excel": "⬇️ Download Excel",

        "moves_header": "Stock Movements",
        "start_date": "Start",
        "end_date": "End",

        "sales_header": "Sales (Preview → Save / Delete / Undo)",
        "upload_sales": "📂 Sales Excel (Satışlar/Sales)",
        "auto_open_note": "Auto-opened the last uploaded file.",
        "preview_note": "Preview – review table. Click 'Save' to write to DB.",
        "save_db": "💾 Save (write to DB)",
        "undo_last": "↩️ Undo (Last sales import)",
        "saved_ok": "✅ Saved",
        "blocked_neg": "{n} rows blocked due to NEGATIVE stock (toggle in Settings).",
        "bad_rows": "{n} rows skipped due to missing product/qty/price.",
        "sales_archive": "📚 Previously uploaded sales files",
        "file_select": "Select file",
        "preview_again": "📄 Preview again",
        "reprocess": "♻️ Re-process this file (Save)",
        "delete_files": "🧹 Delete selected files (Archive)",
        "trash_mgr": "🗑️ Trash",
        "restore_sel": "⤴️ Restore selected",
        "empty_trash": "🔥 Empty trash",
        "preview_delete": "🗑️ Delete (Preview)",

        "imports_header": "Import History",
        "imports_download": "⬇️ Download Excel (History)",
        "imports_select": "Select & Undo",
        "imports_undo": "↩️ Undo selected import",
        "imports_done": "Undone: {x}",

        "reports_header": "Reports",
        "stock_report": "Stock Status",
        "download_stock": "⬇️ Download Excel (Stock)",
        "top_pie": "Top Sellers (Pie)",
        "branch_bar": "Stock by Branch (Bar)",
        "daily_sales_profit": "Daily Sales & Profit",
    }
    return (TR if st.session_state.lang=="tr" else EN).get(key, key)

# Column display translations (no underscores)
COLMAP_TR = {
    "Product Name":"Ürün Adı","Unit":"Birim","Cost":"Alış Fiyatı","Price":"Satış Fiyatı","Shelf Price":"Raf Fiyatı",
    "Stock":"Stok","Current Stock":"Mevcut Stok","Date":"Tarih","Customer":"Müşteri","Sale Price":"Satış Fiyatı",
    "Cash":"Nakit","Card":"Kart","Piece":"Adet","Total Cash":"Nakit Toplam","Total Card":"Kart Toplam",
    "General Total":"Genel Toplam","Note":"Note","Column1":"Column1","Payment_Type":"Ödeme Türü",
    "Urun_Adi":"Ürün Adı","Birim":"Birim","Alış_Fiyatı":"Alış Fiyatı","Satış_Fiyatı":"Satış Fiyatı","Raf_Fiyatı":"Raf Fiyatı",
    "Stok_Giriş":"Stok Giriş","Stok_Çıkış":"Stok Çıkış","Mevcut_Stok":"Mevcut Stok","Alış_Toplam":"Alış Toplam",
    "Satış_Toplam":"Satış Toplam","Raf_Satış_Toplam":"Raf Satış Toplam","Ürün":"Ürün","Hareket_Tipi":"Hareket Tipi",
    "Miktar":"Miktar","Notlar":"Notlar","Şube":"Şube","Toplam_Stok":"Toplam Stok"
}
COLMAP_EN = {
    "Product Name":"Product Name","Unit":"Unit","Cost":"Cost","Price":"Price","Shelf Price":"Shelf Price",
    "Stock":"Stock","Current Stock":"Current Stock","Date":"Date","Customer":"Customer","Sale Price":"Sale Price",
    "Cash":"Cash","Card":"Card","Piece":"Piece","Total Cash":"Total Cash","Total Card":"Total Card",
    "General Total":"General Total","Note":"Note","Column1":"Column1","Payment_Type":"Payment Type",
    "Urun_Adi":"Product","Birim":"Unit","Alış_Fiyatı":"Cost","Satış_Fiyatı":"Price","Raf_Fiyatı":"Shelf Price",
    "Stok_Giriş":"In","Stok_Çıkış":"Out","Mevcut_Stok":"Current Stock","Alış_Toplam":"Total Cost",
    "Satış_Toplam":"Total Price","Raf_Satış_Toplam":"Total Shelf","Ürün":"Product","Hareket_Tipi":"Move Type",
    "Miktar":"Qty","Notlar":"Notes","Şube":"Branch","Toplam_Stok":"Running Stock"
}
def localize_df(df: pd.DataFrame) -> pd.DataFrame:
    mapper = COLMAP_TR if st.session_state.lang=="tr" else COLMAP_EN
    return df.rename(columns={c: mapper.get(c, c).replace("_"," ") for c in df.columns})

# ---- Settings in sidebar ----
with st.sidebar.expander(t("settings"), True):
    if "allow_negative" not in st.session_state: st.session_state.allow_negative = False
    st.session_state.allow_negative = st.checkbox(t("allow_negative"), value=st.session_state.allow_negative)
    st.session_state.lang = st.selectbox(t("language"), LANGS, index=LANGS.index(st.session_state.lang))

# ---- Login (with Enter support via form submit) ----
USERS = {"admin":"1234","personel":"0000"}
if "logged_in" not in st.session_state: st.session_state.logged_in=False
def do_login(user, pwd):
    if user in USERS and USERS[user]==pwd:
        st.session_state.logged_in=True
        st.session_state.user=user
    else:
        st.session_state.login_error = t("login_err")

if not st.session_state.logged_in:
    st.sidebar.subheader("🔐 "+t("login"))
    with st.sidebar.form("login_form"):
        u = st.text_input(t("username"))
        p = st.text_input(t("password"), type="password")
        submitted = st.form_submit_button(t("login_btn"))
    if submitted: do_login(u,p)
    if st.session_state.get("login_error"): st.sidebar.error(st.session_state.login_error)
    st.stop()

# =========================
#  DB & SCHEMA
# =========================
conn = sqlite3.connect("test.db", check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE, unit TEXT, cost REAL, price REAL, shelf_price REAL
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS movements(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER, date TEXT, type TEXT CHECK(type IN('IN','OUT')),
  quantity REAL, note TEXT, branch TEXT, import_id TEXT,
  FOREIGN KEY(product_id) REFERENCES products(id)
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer TEXT, date TEXT, status TEXT, payment_type TEXT CHECK(payment_type IN('Cash','Card','')),
  import_id TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS order_lines(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER, product_id INTEGER, quantity REAL, unit_price REAL, unit_cost REAL DEFAULT 0,
  import_id TEXT,
  FOREIGN KEY(order_id) REFERENCES orders(id),
  FOREIGN KEY(product_id) REFERENCES products(id)
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS imports(
  id TEXT PRIMARY KEY, kind TEXT, filename TEXT, ts TEXT
)""")
def ensure_column(table, col, decl):
    have=[r[1] for r in cur.execute(f"PRAGMA table_info('{table}')")]
    if col not in have: cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
ensure_column("movements","import_id","TEXT")
ensure_column("orders","import_id","TEXT")
ensure_column("order_lines","import_id","TEXT")
conn.commit()

# =========================
#  Helpers
# =========================
UPLOAD_DIR = Path("Uploads"); TRASH_DIR = Path("Uploads/_trash")
for p in [UPLOAD_DIR/"sales", UPLOAD_DIR/"products", TRASH_DIR/"sales", TRASH_DIR/"products"]:
    p.mkdir(parents=True, exist_ok=True)

def nk(s:str)->str:
    if s is None: return ""
    s=str(s).strip().lower()
    s=s.translate(str.maketrans("çğıöşüı ", "cgiosui_"))
    s=re.sub(r"[^a-z0-9_]", "", s)
    return re.sub(r"_+","_",s)

CANON = {
    "date":"Date","tarih":"Date","customer":"Customer","musteri":"Customer",
    "productname":"Product Name","urunadi":"Product Name","urun_ad":"Product Name","urun":"Product Name","product":"Product Name",
    "unit":"Unit","birim":"Unit","cost":"Cost","maliyet":"Cost","alis_fiyati":"Cost","alisfiyati":"Cost",
    "price":"Price","satisfiyati":"Price","satisfiyat":"Price","shelfprice":"Shelf Price","raf_fiyati":"Shelf Price",
    "raffiyati":"Shelf Price","stock":"Stock","stok":"Stock","mevcut_stok":"Stock",
    "currentstock":"Current Stock","saleprice":"Sale Price","birimfiyat":"Sale Price","fiyat":"Sale Price",
    "cash":"Cash","nakit":"Cash","card":"Card","kart":"Card","pos":"Card",
    "piece":"Piece","adet":"Piece","miktar":"Piece","quantity":"Piece",
    "totalcash":"Total Cash","total_card":"Total Card","totalcard":"Total Card",
    "generaltotal":"General Total","geneltoplam":"General Total","note":"Note","not":"Note","column1":"Column1"
}
REQ_SALES=["Date","Customer","Product Name","Piece","Sale Price","Cash","Card","Note","Column1"]
REQ_PROD=["Product Name","Unit","Cost","Price","Shelf Price","Stock"]

def normalize_columns(df: pd.DataFrame)->pd.DataFrame:
    mapping={}
    for c in df.columns:
        k=nk(c)
        if k in CANON: mapping[c]=CANON[k]
    return df.rename(columns=mapping)

def manual_mapper(df: pd.DataFrame, required: list, key:str):
    st.warning("Kolon eşlemesi gerekiyor." if st.session_state.lang=="tr" else "Column mapping required.")
    candidates=list(df.columns)
    mapping={}
    cols=st.columns(2)
    for i,need in enumerate(required):
        with cols[i%2]:
            mapping[need]=st.selectbox(f"→ {need}", ["(seç)"]+candidates, index=0, key=f"map_{key}_{need}")
    if st.button("Eşlemeyi Uygula" if st.session_state.lang=="tr" else "Apply Mapping", key=f"apply_{key}"):
        chosen={need:m for need,m in mapping.items() if m and m!="(seç)"}
        if len(chosen)>=2:
            df2=pd.DataFrame()
            for need,src in chosen.items(): df2[need]=df[src]
            st.success("Eşleme uygulandı." if st.session_state.lang=="tr" else "Mapping applied.")
            return df2
        st.error("En az 2 kolon eşle." if st.session_state.lang=="tr" else "Map at least 2 columns.")
    return None

def save_upload(uploaded_file, kind:str)->Path:
    ts=datetime.now().strftime("%Y%m%d-%H%M%S")
    safe=re.sub(r"[^A-Za-z0-9_.-]+","_", uploaded_file.name)
    path=UPLOAD_DIR/kind/f"{ts}__{safe}"
    with open(path,"wb") as f: f.write(uploaded_file.getbuffer())
    return path

def df_to_excel_bytes(df: pd.DataFrame, sheet="Sheet1")->bytes:
    buf=BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name=sheet)
    return buf.getvalue()

def mini_archive(kind:str, sheets:list, required_cols:list, limit:int=3):
    """Show a tiny expander with last N uploaded files for given kind ('sales'/'products')."""
    try:
        files = sorted((UPLOAD_DIR/kind).glob("*"))
        files = files[-limit:]
        if not files:
            return
        title = "📂 Son 3 yükleme (mini)" if st.session_state.get("lang","tr")=="tr" else "📂 Last 3 uploads (mini)"
        with st.expander(title, expanded=False):
            for p in files:
                c1,c2,c3 = st.columns([8,1,1])
                with c1:
                    st.caption(p.name)
                with c2:
                    if st.button("📄", key=f"mini_prev_{kind}_{p.name}"):
                        try:
                            dfv = smart_read(p, sheets, required_cols)
                            st.dataframe(localize_df(dfv.head(10)), use_container_width=True)
                        except Exception as e:
                            st.error(str(e))
                with c3:
                    if st.button("🗑️", key=f"mini_del_{kind}_{p.name}"):
                        try:
                            dst = TRASH_DIR/kind/p.name
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(p), str(dst))
                        except Exception as e:
                            st.error(str(e))
                        st.rerun()
    except Exception as e:
        st.error(str(e))

def parse_number(x):
    if pd.isna(x): return None
    s=str(x).strip()
    if s=="": return None
    s=s.replace("TL","").replace("₺","").replace("$","").replace("€","").strip()
    if re.search(r",\d{1,2}$", s) and s.count(",")==1:
        s=s.replace(".","").replace(",",".")
    else:
        if s.count(".")>1 and "," not in s: s=s.replace(".","")
        s=s.replace(",","")
    try: return float(s)
    except: return None

def numberize(df: pd.DataFrame, cols)->pd.DataFrame:
    for c in cols:
        if c in df.columns: df[c]=df[c].apply(parse_number).fillna(0.0)
    return df

def drop_empty_rows(df: pd.DataFrame, keys:list)->pd.DataFrame:
    keys=[c for c in keys if c in df.columns]
    if not keys: return df.iloc[0:0]
    mask=pd.Series(False, index=df.index)
    for c in keys:
        mask |= (~df[c].astype(str).str.strip().isin(["","0","0.0","nan"]))
    return df[mask]

def smart_read(path, sheets, required):
    """
    Excel dosyasını açar, doğru sheet'i bulur, başlık satırını otomatik tespit eder.
    """
    xls = pd.ExcelFile(path)

    # Sheet seçimi (Sales / Satışlar vs.)
    target_sheet = None
    for name in xls.sheet_names:
        if any(s.lower() in name.lower() for s in sheets):
            target_sheet = name
            break
    if target_sheet is None:
        target_sheet = xls.sheet_names[0]

    # Önizleme ile başlık satırını bul
    preview = pd.read_excel(xls, sheet_name=target_sheet, header=None, nrows=10)
    header_row = None
    for i, row in preview.iterrows():
        values = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        found = sum(any(req.lower() in v for v in values) for req in required)
        if found >= 2:
            header_row = i
            break
    if header_row is None:
        raise ValueError("Satışlar sheet'inde başlık satırı bulunamadı")

    # Artık doğru başlıkla oku
    df = pd.read_excel(xls, sheet_name=target_sheet, header=header_row)

    # Kolon adlarını normalize et
    df.columns = [str(c).strip() for c in df.columns]

    return df

    # fallback
    df=pd.read_excel(xls)
    return normalize_columns(df)

def get_current_stock(pid:int)->float:
    val=conn.execute("""
      SELECT COALESCE(SUM(CASE WHEN type='IN' THEN quantity ELSE -quantity END),0)
      FROM movements WHERE product_id=?""",(pid,)).fetchone()
    return float(val[0]) if val and val[0] is not None else 0.0

# =========================
#  UI – MENU
# =========================
st.title(t("title"))
if st.sidebar.button(t("logout")):
    st.session_state.logged_in=False; st.rerun()

menu_admin=[t("menu_products"), t("menu_moves"), t("menu_sales"), t("menu_reports"), t("menu_imports")]
menu_user=[t("menu_moves"), t("menu_reports")]
choice=st.sidebar.radio("Menü", menu_admin if st.session_state.user=="admin" else menu_user)

# =========================
#  PRODUCTS
# =========================
if choice==t("menu_products"):
    st.header(t("products_header"))
    up = st.file_uploader(t("upload_products"), type=["xls","xlsx","xlsm"], key="prod_up")
    if up:
        st.info(t("preview_info"))
        path = save_upload(up, "products")
        dfp = smart_read(path, ["Ürünlerim","Ürünler","Products"], REQ_PROD)

        if len(set(REQ_PROD) & set(dfp.columns)) < 3:
            manual = manual_mapper(dfp, REQ_PROD, "products")
            if manual is not None: dfp = manual

        dfp = numberize(dfp, ["Cost","Price","Shelf Price","Stock"])
        st.dataframe(localize_df(dfp), use_container_width=True)

        col1,col2 = st.columns([1,1])
        if col1.button(t("save"), key="prod_save"):
            updated=created=stocked=0
            for _, r in dfp.iterrows():
                name=str(r.get("Product Name","")).strip()
                if not name: continue
                unit=str(r.get("Unit","Adet")).strip()
                cost=float(r.get("Cost",0)); price=float(r.get("Price",0)); shelf=float(r.get("Shelf Price",0))
                init=float(r.get("Stock",0))
                cur.execute("SELECT id FROM products WHERE name=?", (name,))
                row=cur.fetchone()
                if row:
                    pid=row[0]
                    cur.execute("UPDATE products SET unit=?,cost=?,price=?,shelf_price=? WHERE id=?",
                                (unit,cost,price,shelf,pid))
                    updated+=1
                else:
                    cur.execute("INSERT INTO products(name,unit,cost,price,shelf_price) VALUES(?,?,?,?,?)",
                                (name,unit,cost,price,shelf))
                    pid=cur.lastrowid; created+=1
                if init:
                    imp_id=str(uuid.uuid4())
                    cur.execute("INSERT INTO movements(product_id,date,type,quantity,note,branch,import_id) VALUES(?,?,?,?,?,?,?)",
                                (pid, str(date.today()), "IN", init, "Initial stock (Excel)", "Main Warehouse", imp_id))
                    cur.execute("INSERT INTO imports(id,kind,filename,ts) VALUES(?,?,?,?)",
                                (imp_id,"products", path.name, datetime.now().isoformat(timespec="seconds")))
                    stocked+=1
            conn.commit()
            st.success(t("products_updated").format(u=updated,c=created,s=stocked))
        if col2.button(t("delete_preview"), key="prod_del"):
            try: os.remove(path)
            except: pass
            st.rerun()

    st.subheader(t("products_summary"))
    search = st.text_input(t("search"))
    q = """
    SELECT p.id,
           p.name AS Ürün_Adı, p.unit AS Birim, p.cost AS Alış_Fiyatı, p.price AS Satış_Fiyatı, p.shelf_price AS Raf_Fiyatı,
           IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='IN'),0)  AS Stok_Giriş,
           IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='OUT'),0) AS Stok_Çıkış,
           (IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='IN'),0) -
            IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='OUT'),0)) AS Mevcut_Stok,
           ((IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='IN'),0) -
             IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='OUT'),0)) * p.cost)        AS Alış_Toplam,
           ((IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='IN'),0) -
             IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='OUT'),0)) * p.price)       AS Satış_Toplam,
           ((IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='IN'),0) -
             IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id=p.id AND m.type='OUT'),0)) * p.shelf_price) AS Raf_Satış_Toplam
    FROM products p ORDER BY p.name
    """
    dfp2 = pd.read_sql(q, conn)
    if search: dfp2 = dfp2[dfp2["Ürün_Adı"].str.contains(search, case=False, na=False)]
    cols_all=list(dfp2.columns)
    show_cols=st.multiselect(t("choose_cols"), cols_all, default=cols_all, key="prod_cols")
    st.dataframe(localize_df(dfp2[show_cols]), use_container_width=True)
    st.download_button(t("download_excel"), df_to_excel_bytes(dfp2[show_cols], "Products"),
                       file_name="products_report.xlsx")

# =========================
#  MOVEMENTS
# =========================
elif choice==t("menu_moves"):
    st.header(t("moves_header"))
    date_from = st.date_input(t("start_date"), value=date(2024,1,1))
    date_to   = st.date_input(t("end_date"), value=date.today())
    df = pd.read_sql("""
      SELECT m.id, p.name AS Ürün, m.date AS Tarih, m.type AS Hareket_Tipi, m.quantity AS Miktar, m.note AS Notlar, m.branch AS Şube
      FROM movements m JOIN products p ON p.id=m.product_id
      ORDER BY m.date DESC, m.id DESC
    """, conn)
    df["Tarih"] = pd.to_datetime(df["Tarih"], errors="coerce", dayfirst=True)
    df = df[(df["Tarih"]>=pd.to_datetime(date_from)) & (df["Tarih"]<=pd.to_datetime(date_to))]
    cols_all=list(df.columns)
    show_cols=st.multiselect(t("choose_cols"), cols_all, default=cols_all, key="mov_cols")
    st.dataframe(localize_df(df[show_cols]), use_container_width=True)
    st.download_button(t("download_excel"), df_to_excel_bytes(df[show_cols], "Movements"), file_name="movements.xlsx")

# =========================
#  SALES
# =========================

    # Mini archive (last uploads)
    try:
        mini_archive("products", ["Ürünlerim","Ürünler","Products"], REQ_PROD, limit=3)
    except Exception:
        pass
elif choice==t("menu_sales"):
    st.header(t("sales_header"))

    # 1) Auto open last uploaded file preview (if exists and no new upload yet)
    sales_dir = UPLOAD_DIR/"sales"
    uploaded_files = sorted(sales_dir.glob("*"))
    last_file = uploaded_files[-1] if uploaded_files else None

    # Upload area
    up = st.file_uploader(t("upload_sales"), type=["xls","xlsx","xlsm"], key="sales_up")
    preview_df=None; current_path=None

    # If new upload, use it; else use last file if exists
    if up:
        current_path = save_upload(up, "sales")
    elif last_file:
        current_path = last_file
        st.info(t("auto_open_note"))

    if current_path:
        df = smart_read(current_path, ["Sales","Satışlar","Satislar","SATISLAR"], REQ_SALES)
        if len(set(REQ_SALES) & set(df.columns)) < 3:
            manual = manual_mapper(df, REQ_SALES, "sales")
            if manual is not None: df = manual

        df = drop_empty_rows(df, ["Product Name","Piece","Sale Price"])
        df = numberize(df, ["Piece","Sale Price","Note","Column1"])

        # NOTE & COLUMN1: preserve if present; else fill
        products_df = pd.read_sql("SELECT id,name,cost FROM products", conn)
        id_map = dict(zip(products_df["name"], products_df["id"]))
        cost_map = dict(zip(products_df["name"], products_df["cost"]))
        df["Note"] = df.apply(lambda r: (r["Note"] if float(r["Note"])>0 else cost_map.get(str(r.get("Product Name","")).strip(),0.0)), axis=1)
        df["Column1"] = df.apply(lambda r: (r["Column1"] if float(r["Column1"])>0 else r["Note"]*r["Piece"]), axis=1)

        # Payment rule
        def detect_payment(r):
            cash_txt=str(r.get("Cash","")).strip()
            return "Cash" if cash_txt not in ["","0","0.0","nan"] else "Card"
        df["Payment_Type"]=df.apply(detect_payment, axis=1)

        preview_df=df.copy()
        st.caption(f"Current file: {Path(current_path).name}")
        st.info(t("preview_note"))
        st.dataframe(localize_df(preview_df), use_container_width=True)

        c1,c2,c3 = st.columns([1,1,1])

        if c1.button(t("save_db"), key="sales_save"):
            imp_id=str(uuid.uuid4())
            cur.execute("INSERT INTO imports(id,kind,filename,ts) VALUES(?,?,?,?)",
                        (imp_id,"sales", Path(current_path).name, datetime.now().isoformat(timespec="seconds")))
            blocked=bad=0
            for _, r in preview_df.iterrows():
                name=str(r.get("Product Name","")).strip()
                piece=float(r.get("Piece",0)); price=float(r.get("Sale Price",0))
                if not name or piece<=0 or price<=0:
                    bad+=1; continue
                row=cur.execute("SELECT id,cost FROM products WHERE name=?",(name,)).fetchone()
                if row: pid=row[0]; cost_val=float(row[1])
                else:
                    pid=None; cost_val=float(r["Note"])
                    cur.execute("INSERT INTO products(name,unit,cost,price,shelf_price) VALUES(?,?,?,?,?)",
                                (name,"Adet",cost_val,price,price))
                    pid=cur.lastrowid
                stock_before=get_current_stock(pid)
                if (stock_before - piece) < 0 and not st.session_state.allow_negative:
                    blocked+=1; continue
                d=pd.to_datetime(r.get("Date"), errors="coerce")
                date_str=d.date().isoformat() if not pd.isna(d) else str(date.today())
                cur.execute("INSERT INTO orders(customer,date,status,payment_type,import_id) VALUES(?,?,?,?,?)",
                            (str(r.get("Customer","")), date_str, "Completed", r["Payment_Type"], imp_id))
                oid=cur.lastrowid
                cur.execute("INSERT INTO order_lines(order_id,product_id,quantity,unit_price,unit_cost,import_id) VALUES(?,?,?,?,?,?)",
                            (oid,pid,piece,price,float(r["Note"]),imp_id))
                cur.execute("INSERT INTO movements(product_id,date,type,quantity,note,branch,import_id) VALUES(?,?,?,?,?,?,?)",
                            (pid,date_str,"OUT",piece,"Sale Excel Upload","Main Warehouse",imp_id))
            conn.commit()
            st.success(t("saved_ok"))
            if blocked>0: st.warning(t("blocked_neg").format(n=blocked))
            if bad>0: st.info(t("bad_rows").format(n=bad))

        if c2.button(t("preview_delete"), key="sales_del"):
            # move to trash instead of permanent delete
            TRASH_DIR.mkdir(parents=True, exist_ok=True)
            dst = TRASH_DIR/"sales"/Path(current_path).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try: shutil.move(str(current_path), str(dst))
            except Exception: pass
            st.rerun()

        if c3.button(t("undo_last"), key="sales_undo"):
            row=cur.execute("SELECT id FROM imports WHERE kind='sales' ORDER BY ts DESC LIMIT 1").fetchone()
            if row:
                last=row[0]
                cur.execute("DELETE FROM order_lines WHERE import_id=?", (last,))
                cur.execute("DELETE FROM movements   WHERE import_id=?", (last,))
                cur.execute("DELETE FROM orders      WHERE import_id=?", (last,))
                cur.execute("DELETE FROM imports     WHERE id=?", (last,))
                conn.commit()
                st.success(f"Undo: {last}")
            else:
                st.info("Geri alınacak satış importu yok." if st.session_state.lang=="tr" else "No sales import to undo.")

    # Archive manager
    
    # Mini archive (last uploads)
    try:
        mini_archive("sales", ["Sales","Satışlar","Satislar","SATISLAR"], REQ_SALES, limit=3)
    except Exception:
        pass
    st.subheader(t("sales_archive"))
    sales_files = sorted((UPLOAD_DIR/"sales").glob("*"))
    names = [p.name for p in sales_files]
    if names:
        sel = st.selectbox(t("file_select"), names, index=len(names)-1)
        colA,colB,colC = st.columns(3)
        if colA.button(t("preview_again")):
            dfv = smart_read(UPLOAD_DIR/"sales"/sel, ["Sales","Satışlar","Satislar","SATISLAR"], REQ_SALES)
            st.dataframe(localize_df(dfv.head(30)), use_container_width=True)
        if colB.button(t("reprocess")):
            # just set as current by touching its mtime
            path = UPLOAD_DIR/"sales"/sel
            os.utime(path, None)
            st.rerun()
        if colC.button(t("delete_files")):
            path = UPLOAD_DIR/"sales"/sel
            dst  = TRASH_DIR/"sales"/sel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try: shutil.move(str(path), str(dst))
            except Exception: pass
            st.rerun()

    st.subheader(t("trash_mgr"))
    trash_files = sorted((TRASH_DIR/"sales").glob("*"))
    trash_names = [p.name for p in trash_files]
    if trash_names:
        ts1, ts2 = st.columns(2)
        to_restore = ts1.selectbox("Seç (restore)" if st.session_state.lang=="tr" else "Select (restore)", trash_names, key="restore_sel")
        if ts1.button(t("restore_sel")):
            src = TRASH_DIR/"sales"/to_restore
            dst = UPLOAD_DIR/"sales"/to_restore
            try: shutil.move(str(src), str(dst))
            except Exception: pass
            st.rerun()
        if ts2.button(t("empty_trash")):
            for p in trash_files:
                try: os.remove(p)
                except: pass
            st.rerun()

# =========================
#  REPORTS
# =========================
elif choice == "Raporlar":
    st.header("📊 Reports")

    # --- Şube Bazlı Stok Tablosu ---
    branch_q = """
        SELECT p.name AS Product,
               m.branch AS Branch,
               SUM(CASE WHEN m.type='IN' THEN m.quantity ELSE 0 END) -
               SUM(CASE WHEN m.type='OUT' THEN m.quantity ELSE 0 END) AS Current_Stock
        FROM products p
        JOIN movements m ON p.id = m.product_id
        GROUP BY p.name, m.branch
    """
    st.subheader("Branch-based Stock Levels")
    st.dataframe(pd.read_sql(branch_q, conn), use_container_width=True)

    # --- Genel Stok Tablosu ---
    stock_q = """
        SELECT p.name AS Product,
               SUM(CASE WHEN m.type='IN'  THEN m.quantity ELSE 0 END) -
               SUM(CASE WHEN m.type='OUT' THEN m.quantity ELSE 0 END) AS Current_Stock
        FROM products p
        LEFT JOIN movements m ON p.id = m.product_id
        GROUP BY p.id
    """
    st.subheader("Overall Stock Status")
    st.dataframe(pd.read_sql(stock_q, conn), use_container_width=True)

    # --- En Çok Satan Ürünler Tablosu ---
    top_q = """
        SELECT p.name AS Product, SUM(l.quantity) AS Total_Sold
        FROM order_lines l
        JOIN products p ON l.product_id = p.id
        GROUP BY p.name
        ORDER BY Total_Sold DESC
        LIMIT 10
    """
    st.subheader("Top Selling Products")
    st.dataframe(pd.read_sql(top_q, conn), use_container_width=True)

    # --- Grafik 1: Şube Bazlı Stok ---
    st.subheader("Branch Stock Chart")
    branch_df = pd.read_sql(branch_q, conn)
    if not branch_df.empty:
        st.bar_chart(branch_df.set_index("Product")["Current_Stock"])

    # --- Grafik 2: Günlük Satışlar ---
    st.subheader("Daily Sales Chart")
    sales_q = """
        SELECT o.date AS Date,
               SUM(l.quantity * l.unit_price) AS Daily_Sales
        FROM orders o
        JOIN order_lines l ON o.id = l.order_id
        GROUP BY o.date
        ORDER BY o.date
    """
    df_sales_chart = pd.read_sql(sales_q, conn)
    if not df_sales_chart.empty:
        st.line_chart(df_sales_chart.set_index("Date"))

# =========================
#  IMPORT HISTORY
# =========================
elif choice==t("menu_imports"):
    st.header(t("imports_header"))
    his = pd.read_sql("SELECT id, kind, filename, ts FROM imports ORDER BY ts DESC", conn)
    st.dataframe(localize_df(his), use_container_width=True)
    st.download_button(t("imports_download"), df_to_excel_bytes(his,"Imports"), file_name="imports.xlsx")
    sel = st.selectbox(t("imports_select"), his["id"].tolist() if not his.empty else [])
    if st.button(t("imports_undo")):
        if sel:
            cur.execute("DELETE FROM order_lines WHERE import_id=?", (sel,))
            cur.execute("DELETE FROM movements   WHERE import_id=?", (sel,))
            cur.execute("DELETE FROM orders      WHERE import_id=?", (sel,))
            cur.execute("DELETE FROM imports     WHERE id=?", (sel,))
            conn.commit()
            st.success(t("imports_done").format(x=sel))
            st.rerun()