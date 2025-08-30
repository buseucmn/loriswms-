import streamlit as st
import sqlite3
import pandas as pd

# Kullanıcı bilgileri
USERS = {
    "admin": "1234",   # yönetici
    "personel": "0000" # çalışan
}
# Login kontrolü
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.subheader("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if username in USERS and USERS[username] == password:
            st.session_state.logged_in = True
            st.session_state.user = username
            st.success(f"Welcome {username}!")
            st.rerun()
        else:
            st.error("Wrong username or password")
    st.stop()

# --- Veritabanı bağlantısı ---
conn = sqlite3.connect("test.db", check_same_thread=False)

# --- Column1 hesaplama fonksiyonu ---
def get_cost(product_name, fallback_cost):
    row_cost = conn.execute(
        "SELECT cost FROM products WHERE name=?", (product_name,)
    ).fetchone()
    if row_cost is not None and row_cost[0] is not None:
        return row_cost[0]
    return pd.to_numeric(fallback_cost, errors="coerce") if fallback_cost is not None else 0


st.title("📦 Loris Perfume - Mini WMS")

if st.session_state.user == "admin":
    menu = ["Ürünler", "Stok Hareketleri", "Satışlar", "Raporlar"]
else:
    menu = ["Stok Hareketleri"]# Logout butonu
if st.sidebar.button("Çıkış Yap"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

choice = st.sidebar.selectbox("Menü", menu)
from datetime import date   # ⬅️ Bunu dosyanın en üstüne ekle (importların yanına)

if choice == "Ürünler":
    st.header("Ürün Listesi")

    # Excel yükleme butonu
    uploaded_file = st.file_uploader("📂 Excel'den Ürün ve Stok Yükle", type=["xls", "xlsx"])
    if uploaded_file:
        df_new = pd.read_excel(uploaded_file)
        df_new.columns = df_new.columns.str.strip()  # başlıklardaki boşlukları temizle
        df_new.rename(columns={"Product name": "Product Name"}, inplace=True)  # olası küçük-büyük farkını düzelt
        for c in ["Cost", "Price", "Shelf Price", "Stock"]:
            df_new[c] = pd.to_numeric(df_new[c], errors="coerce").fillna(0)   # sayısal yap, boşsa 0


        # Excel kolonlarını göster (hata kontrolü için)ƒ
        #st.write("Excel kolonları:", list(df_new.columns))

        for _, row in df_new.iterrows():
            # ürün var mı kontrol et
            cur = conn.cursor()
            cur.execute("SELECT id FROM products WHERE name=?", (row["Product Name"],))
            result = cur.fetchone()
            if result:
                product_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO products(name, unit, cost, price, shelf_price) VALUES(?,?,?,?,?)",
                    (row["Product Name"], row["Unit"], row["Cost"], row["Price"], row["Shelf Price"])
                )
                product_id = cur.lastrowid

            # stok hareketi ekle (ilk giriş)
            cur.execute(
                "INSERT INTO movements(product_id, date, type, quantity, note, branch) VALUES(?,?,?,?,?,?)",
                (product_id, str(date.today()), "IN", row["Stock"], "Excel Upload", "Main Warehouse")
            )
            conn.commit()

        st.success("Excel’den veriler başarıyla yüklendi ✅")

    # Ürünleri veritabanından oku ve hesaplamaları yap
    q = """
    SELECT 
        p.id,
        p.name AS Ürün_Adı,
        p.unit AS Ürün_Türü,
        p.cost AS Alış_Fiyatı,
        p.price AS Satış_Fiyatı,
        p.shelf_price AS Raf_Fiyatı,

        -- stok girişleri
        IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='IN'),0) AS Stok_Giriş,

        -- stok çıkışları
        IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='OUT'),0) AS Stok_Çıkış,

        -- mevcut stok = giriş - çıkış
        (
            IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='IN'),0)
            - IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='OUT'),0)
        ) AS Mevcut_Stok,

        -- alış toplam
        (
            (
                IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='IN'),0)
                - IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='OUT'),0)
            ) * p.cost
        ) AS Alış_Toplam,

        -- satış toplam
        (
            (
                IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='IN'),0)
                - IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='OUT'),0)
            ) * p.price
        ) AS Satış_Toplam,

        -- raf satış toplam
        (
            (
                IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='IN'),0)
                - IFNULL((SELECT SUM(m.quantity) FROM movements m WHERE m.product_id = p.id AND m.type='OUT'),0)
            ) * p.shelf_price
        ) AS Raf_Satış_Toplam

    FROM products p
    ORDER BY p.name
    """

    df = pd.read_sql(q, conn)
    st.dataframe(df, use_container_width=True)


elif choice == "Stok Hareketleri":
    st.header("Stok Hareketleri")

    q = """
    SELECT 
        m.id,
        p.id AS product_id,
        p.name AS Ürün,
        m.date AS Tarih,
        m.type AS Hareket_Tipi,
        m.quantity AS Miktar,
        m.note AS Notlar,
        m.branch AS Şube
    FROM movements m
    JOIN products p ON p.id = m.product_id
    ORDER BY p.id, m.date, m.id
    """
    df = pd.read_sql(q, conn)
    df["Tarih"] = pd.to_datetime(df["Tarih"])

    # IN = +, OUT = - olacak şekilde Etki sütunu
    df["Etki"] = df.apply(
        lambda r: r["Miktar"] if r["Hareket_Tipi"] == "IN" else -r["Miktar"],
        axis=1
    )

    # Ürün bazında sıralama ve kümülatif stok hesabı
    df = df.sort_values(["product_id", "Tarih", "id"])
    df["Toplam_Stok"] = df.groupby("product_id")["Etki"].cumsum()

    # Görünümü tersten sırala (en yeni hareketler yukarıda olsun)
    df = df.sort_values(["Tarih", "id"], ascending=[False, False])

    # Tabloyu göster
    st.dataframe(
        df[["Ürün","Tarih","Hareket_Tipi","Miktar","Notlar","Şube","Toplam_Stok"]],
        use_container_width=True
    )

elif choice == "Satışlar":
    st.header("📊 Sales")

    uploaded_sales = st.file_uploader("📂 Upload Sales Excel", type=["xls", "xlsx", "xlsm"])
    import openpyxl
    import pandas as pd

    # hangi sheet'ler var diye kontrol et
    xls = pd.ExcelFile(uploaded_sales)
    st.write("Excel içindeki sheet isimleri:", xls.sheet_names)

    if uploaded_sales:
        # 1) Doğru sheet'i bul
        df_sales = None
        for cand in ["Sales", "Satışlar", "Satislar", "SATISLAR", "Satişlar"]:
            try:
                df_sales = pd.read_excel(uploaded_sales, sheet_name=cand)
                break
            except Exception:
                continue
        if df_sales is None:
            df_sales = pd.read_excel(uploaded_sales, sheet_name=0)  # fallback: ilk sheet

        # 2) Kolon adlarını normalize et
        df_sales.columns = df_sales.columns.astype(str).str.strip()
        df_sales.rename(
            columns={
                "Product name": "Product Name",
                "product name": "Product Name",
                "Sale_Price": "Sale Price",
                "sale price": "Sale Price",
                "sale_price": "Sale Price",
                "piece": "Piece",
            },
            inplace=True,
        )

        # 3) Zorunlu kolonlar yoksa ekle
        required_defaults = {
            "Date": pd.NaT,
            "Customer": "",
            "Product Name": "",
            "Sale Price": 0,
            "Piece": 0,
            "Cash": 0,
            "Card": 0,
            "Note": 0,  # Note başta yoksa 0
        }
        for col, default in required_defaults.items():
            if col not in df_sales.columns:
                df_sales[col] = default

        # 4) Sayısal kolonları dönüştür
        for c in ["Sale Price", "Piece", "Cash", "Card", "Note"]:
            df_sales[c] = pd.to_numeric(df_sales[c], errors="coerce").fillna(0)

        # 5) NOTE (VLOOKUP benzeri): Note boş/0 ise DB’den cost çek
        products_df = pd.read_sql("SELECT name, cost FROM products", conn)
        cost_map = dict(zip(products_df["name"], products_df["cost"]))
        df_sales.loc[df_sales["Note"] == 0, "Note"] = (
            df_sales["Product Name"].map(cost_map).fillna(0)
        )

        # 6) Payment Type
        df_sales["Payment_Type"] = df_sales.apply(
            lambda r: "Cash" if r["Cash"] != 0 else ("Card" if r["Card"] != 0 else ""),
            axis=1,
        )

        # 7) Hesaplamalar
        df_sales["Total_Cash"] = df_sales.apply(
            lambda r: r["Piece"] * r["Sale Price"] if r["Payment_Type"] == "Cash" else 0,
            axis=1,
        )
        df_sales["Total_Card"] = df_sales.apply(
            lambda r: r["Piece"] * r["Sale Price"] if r["Payment_Type"] == "Card" else 0,
            axis=1,
        )
        df_sales["General_Total"] = df_sales["Total_Cash"] + df_sales["Total_Card"]
        df_sales["Column1"] = df_sales["Note"] * df_sales["Piece"]

        # 8) SQL'e kaydet
        cur = conn.cursor()
        for _, row in df_sales.iterrows():
            cur.execute("SELECT id FROM products WHERE name=?", (row["Product Name"],))
            result = cur.fetchone()
            if result:
                product_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO products(name, unit, cost, price, shelf_price) VALUES(?,?,?,?,?)",
                    (
                        row["Product Name"],
                        "Adet",
                        float(row["Note"]),
                        float(row["Sale Price"]),
                        float(row["Sale Price"]),
                    ),
                )
                product_id = cur.lastrowid

            d = pd.to_datetime(row["Date"], errors="coerce")
            date_str = d.date().isoformat() if not pd.isna(d) else str(date.today())

            cur.execute(
                "INSERT INTO orders(customer, date, status, payment_type) VALUES(?,?,?,?)",
                (str(row["Customer"]), date_str, "Completed", row["Payment_Type"]),
            )
            order_id = cur.lastrowid

            cur.execute(
                "INSERT INTO order_lines(order_id, product_id, quantity, unit_price) VALUES(?,?,?,?)",
                (order_id, product_id, float(row["Piece"]), float(row["Sale Price"])),
            )

            cur.execute(
                "INSERT INTO movements(product_id, date, type, quantity, note, branch) VALUES(?,?,?,?,?,?)",
                (product_id, date_str, "OUT", float(row["Piece"]), "Sale Excel Upload", "Main Warehouse"),
            )

        conn.commit()

        # 9) Tabloyu göster
        st.dataframe(
            df_sales[
                [
                    "Date",
                    "Customer",
                    "Product Name",
                    "Piece",
                    "Sale Price",
                    "Cash",
                    "Card",
                    "Payment_Type",
                    "Total_Cash",
                    "Total_Card",
                    "General_Total",
                    "Note",
                    "Column1",
                ]
            ],
            use_container_width=True,
        )
        st.success("✅ Sales Excel işlendi, Note Products’tan dolduruldu (VLOOKUP), tüm hesaplamalar tamam.")

elif choice == "Raporlar":
     st.subheader("Şube Bazlı Stoklar")
     branch_q = """
        SELECT p.name,
            m.branch,
            SUM(CASE WHEN m.type='IN' THEN m.quantity ELSE 0 END) -
            SUM(CASE WHEN m.type='OUT' THEN m.quantity ELSE 0 END) AS current_stock
        FROM products p
        JOIN movements m ON p.id = m.product_id
        GROUP BY p.name, m.branch
        """
     st.dataframe(pd.read_sql(branch_q, conn))

     st.header("Raporlar")

     st.subheader("Stok Durumu")
     stock_q = """
    SELECT p.name,
           SUM(CASE WHEN m.type='IN'  THEN m.quantity ELSE 0 END) -
           SUM(CASE WHEN m.type='OUT' THEN m.quantity ELSE 0 END) AS current_stock
    FROM products p
    LEFT JOIN movements m ON p.id = m.product_id
    GROUP BY p.id
    """
     st.dataframe(pd.read_sql(stock_q, conn))

     st.subheader("En Çok Satan Ürünler")
     top_q = """
    SELECT p.name, SUM(l.quantity) AS total_sold
    FROM order_lines l
    JOIN products p ON l.product_id = p.id
    GROUP BY p.name
    ORDER BY total_sold DESC
    """
     st.dataframe(pd.read_sql(top_q, conn))
     st.subheader("Günlük Satış Grafiği")
     sales_q = """
    SELECT o.date,
           SUM(l.quantity * l.unit_price) AS daily_sales
    FROM orders o
    JOIN order_lines l ON o.id = l.order_id
    GROUP BY o.date
    ORDER BY o.date
    """
     df_sales = pd.read_sql(sales_q, conn)
     st.line_chart(df_sales.set_index("date"))
