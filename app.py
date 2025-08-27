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
if choice == "Ürünler":
    st.header("Ürün Listesi")

    # Excel yükleme butonu
    uploaded_file = st.file_uploader("📂 Excel'den Ürün ve Stok Yükle", type=["xls", "xlsx"])
    if uploaded_file:
        df_new = pd.read_excel(uploaded_file)

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
                (product_id, str(date.today()), "IN", row["Stock"], "Excel Yükleme", "Main Warehouse")
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

    # Tarihi datetime tipine çevir
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
    st.header("Satışlar")

    q = """
    SELECT 
        o.date AS Date,
        o.customer AS Customer,
        p.name AS Product_Name,
        (
            IFNULL(SUM(CASE WHEN m.type='IN' THEN m.quantity ELSE 0 END),0)
            - IFNULL(SUM(CASE WHEN m.type='OUT' THEN m.quantity ELSE 0 END),0)
        ) AS Current_Stock,
        l.unit_price AS Sale_Price,
        CASE WHEN o.payment_type = 'Cash' THEN (l.quantity * l.unit_price) ELSE 0 END AS Cash,
        CASE WHEN o.payment_type = 'Card' THEN (l.quantity * l.unit_price) ELSE 0 END AS Card,
        l.quantity AS Piece,
        CASE WHEN o.payment_type = 'Cash' THEN (l.quantity * l.unit_price) ELSE 0 END AS Total_Cash,
        CASE WHEN o.payment_type = 'Card' THEN (l.quantity * l.unit_price) ELSE 0 END AS Total_Card,
        (l.quantity * l.unit_price) AS General_Total
    FROM orders o
    JOIN order_lines l ON o.id = l.order_id
    JOIN products p ON l.product_id = p.id
    LEFT JOIN movements m ON m.product_id = p.id
    GROUP BY o.id, l.id
    ORDER BY o.date DESC
    """

    st.dataframe(pd.read_sql(q, conn))


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
