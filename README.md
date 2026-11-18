# Simplified Marketplace - Project 5

A full-stack Django e-commerce marketplace featuring a modern responsive UI, relational data modeling, vendor isolation in Django Admin, session-based shopping carts, atomic checkout transactions, a RESTful API with nested serializers, and all 5 optional portfolio challenges.

---

## 🚀 Key Features

### Core Architecture
- **Modern Responsive UI:** Clean storefront interface built with CSS Grid/Flexbox, real-time stock badges, toast notifications, and interactive category/price filters powered by Vanilla JavaScript `fetch()` and `localStorage`.
- **Vendor Isolation in Admin:** Custom `ModelAdmin` (`get_queryset`, `get_exclude`, `save_model`) ensures each seller views and manages only their own products.
- **Session-Based Shopping Cart:** Visitors can browse the catalog and add products to their cart without logging in (`request.session`), persisting across authentication.
- **Atomic Checkout (`transaction.atomic`):** Validates stock across all items before persisting changes, creates orders and order items, decrements inventory atomically, and clears the cart only upon success.
- **Historical Price Snapshot:** `ItemPedido` stores `preco_unitario` at the time of purchase so future product price changes never alter past orders.

### Extra Portfolio Challenges Implemented
- **Product Reviews (`Avaliacao`):** Authenticated buyers can submit ratings (1–5 stars) and comments via `POST /api/avaliacoes/` only for products they have actually purchased (`ItemPedido` verification).
- **Sandbox Payment Gateway:** `POST /api/pedidos/<id>/pagar/` simulates payment authorization using environment-configured sandbox keys (`PAYMENT_SANDBOX_KEY`) before transitioning order status from `ABERTO` to `PAGO`.
- **API Filtering:** `GET /api/produtos/` supports dynamic query parameters (`?categoria=<id>`, `?preco_min=<value>`, `?preco_max=<value>`) via custom `get_queryset()`, integrated directly into the storefront filter bar.
- **Vendor Sales Dashboard (`/painel-vendedor/`):** Aggregates units sold and revenue per product and per category using Django ORM `annotate()`, `aggregate()`, and `Sum()`.
- **Production-Ready Configuration:** Environment variable management via `python-dotenv` and `dj-database-url` supporting SQLite locally and PostgreSQL (Supabase) in production.

---

## 🛠️ Tech Stack

- **Backend:** Python 3, Django, Django REST Framework
- **Frontend:** HTML5, CSS3, Vanilla JavaScript (`fetch`, `localStorage`)
- **Database:** SQLite (Development) / PostgreSQL via `dj-database-url` (Production)
- **Testing:** Django `TestCase` & DRF `APIClient` (23 automated unit & integration tests)

---

## 📡 API Endpoints & Usage Examples

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/produtos/` | Public | List products (supports `?categoria=`, `?preco_min=`, `?preco_max=`) |
| `POST` | `/api/produtos/` | Authenticated | Create a new product automatically bound to the seller |
| `POST` | `/api/pedidos/` | Authenticated | Create a nested order atomically ignoring client-sent prices |
| `POST` | `/api/pedidos/<id>/pagar/` | Authenticated | Process sandbox payment and mark order as `PAGO` |
| `GET / POST` | `/api/avaliacoes/` | Public / Buyer | List reviews or submit a review (verified buyers only) |

### Example Request (`POST /api/pedidos/`)

```json
{
  "itens": [
    {
      "produto": 1,
      "quantidade": 1
    }
  ]
}
```

### Example Response (`201 Created`)

```json
{
  "id": 1,
  "status": "ABERTO",
  "criado_em": "2026-11-18T13:07:00Z",
  "itens": [
    {
      "produto": 1,
      "quantidade": 1,
      "preco_unitario": "39.99"
    }
  ]
}
```

---

## 📸 Screenshots

### 1. Storefront Catalog & Dynamic Filters
![Storefront Catalog & Dynamic Filters](image.png)
*Displays the responsive product grid with category badges, live stock availability indicators, and interactive category/price filters connected to `/api/produtos/` via JavaScript `fetch()`.*

### 2. Session-Based Shopping Cart
![Session-Based Shopping Cart](image-1.png)
*Displays the itemized shopping cart table with unit prices, quantities, subtotals, order total, and authentication prompt preserving the visitor's session cart before checkout.*

---

## 📦 Getting Started

1. **Clone the repository:**
   ```bash
   git clone <YOUR_REPOSITORY_URL>
   cd marketplace
   ```

2. **Create and activate a virtual environment:**
   - **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   PAYMENT_SANDBOX_KEY=sk_test_marketplace_2026
   # DATABASE_URL=postgres://user:password@host:5432/dbname
   ```

5. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create an administrator account:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

---

## 🧪 Automated Tests

The project includes **23 automated tests** (`loja/tests.py`) covering every functional requirement and edge case:

* **Admin Isolation (`AdminTest` & `AdminFluxoTest`):** Verifies that sellers only list, create, and manage their own products in Django Admin.
* **Session Cart & Login Flow (`CarrinhoTest` & `LoginTest`):** Confirms anonymous cart storage, `POST`-only protection when adding items, and cart persistence across user authentication.
* **Atomic Checkout & Historical Pricing (`CheckoutTest`):** Validates stock deduction, full transaction rollback on insufficient stock or mid-transaction failures (`transaction.atomic`), and immutability of historical `preco_unitario`.
* **REST API & Extra Challenges (`APITest` & `DesafiosExtrasTest`):** Tests public product reads, authenticated nested order creation ignoring client-sent prices, query parameter filtering (`categoria`, `preco_max`), verified-buyer product reviews, sandbox payment confirmation, and vendor sales aggregations (`aggregate` / `Sum`).

Run the entire test suite with:

```bash
python manage.py test -v 2
```

---

## 👩‍💻 Author

Developed by **Nicole** (2026)