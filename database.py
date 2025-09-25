import sqlite3

def init_db():
    conn = sqlite3.connect('shop.db')
    cur = conn.cursor()

    # Таблица товаров
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            photo TEXT
        )
    """)

    # Таблица заказов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_date TEXT,
            order_time TEXT,
            payment_method TEXT,
            total_amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Таблица элементов заказа (корзина)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)

    # Вставляем тестовые товары, если их нет
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        products = [
            ("Товар 1", 500, "Описание товара 1", "https://via.placeholder.com/300x200.png?text=Товар+1"),
            ("Товар 2", 750, "Описание товара 2", "https://via.placeholder.com/300x200.png?text=Товар+2"),
            ("Товар 3", 1200, "Описание товара 3", "https://via.placeholder.com/300x200.png?text=Товар+3")
        ]
        cur.executemany("INSERT INTO products (name, price, description, photo) VALUES (?, ?, ?, ?)", products)

    conn.commit()
    conn.close()
