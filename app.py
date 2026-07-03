from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, Response
from datetime import datetime, timedelta
import os
import uuid
import json
import requests
import traceback
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
application = app
app.secret_key = 'allison-electronics-secret-2026'
app.permanent_session_lifetime = timedelta(days=7)

# ================================================================
# ===== VERCEL READ-ONLY FILESYSTEM COMPATIBILITY =====
# ================================================================

IS_VERCEL = 'VERCEL' in os.environ or 'NOW' in os.environ

if IS_VERCEL:
    UPLOAD_FOLDER = '/tmp/static/uploads'
    STATIC_FOLDER = '/tmp/static'
    JSON_FOLDER = '/tmp'
else:
    UPLOAD_FOLDER = 'static/uploads'
    STATIC_FOLDER = 'static'
    JSON_FOLDER = '.'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = '/tmp/static/uploads'
    STATIC_FOLDER = '/tmp/static'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)

app.static_folder = STATIC_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================================================================
# ===== VERCEL BLOB STORAGE =====
# ================================================================

USE_BLOB = False
BLOB_STORE = None

try:
    # Try to import Vercel Blob Storage
    from vercel_blob import BlobStore
    BLOB_STORE = BlobStore()
    USE_BLOB = True
    print("✅ Vercel Blob Storage enabled!")
except ImportError:
    print("⚠️ Vercel Blob not available - using local storage")
except Exception as e:
    print(f"⚠️ Error initializing Blob: {e}")

def get_json_path(filename):
    """Get the correct path for JSON files"""
    if USE_BLOB:
        return filename  # Blob uses filename directly
    return os.path.join(JSON_FOLDER, filename)

def load_json(file_path):
    """Load JSON from Blob or local file"""
    try:
        # Try Blob first if available
        if USE_BLOB and BLOB_STORE:
            try:
                data = BLOB_STORE.get(file_path)
                if data:
                    return json.loads(data)
            except Exception as e:
                print(f"Blob read error for {file_path}: {e}")
        
        # Fallback to local file
        full_path = get_json_path(file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                return json.load(f)
        
        # Create sample products if products.json doesn't exist
        if file_path == 'products.json':
            sample_products = [
                {
                    "id": "1",
                    "name": "iPhone 15 Pro Max",
                    "price": 150000,
                    "cost_price": 120000,
                    "image": "https://via.placeholder.com/300x300/000/fff?text=iPhone",
                    "category": "Phones",
                    "description": "Latest iPhone with amazing features",
                    "rating": 4.8,
                    "reviews": 120,
                    "badge": "Best Seller",
                    "stock": 50,
                    "original_price": 165000,
                    "specs": ["6.7\" Display", "48MP Camera", "A17 Pro Chip"]
                },
                {
                    "id": "2",
                    "name": "MacBook Pro M3",
                    "price": 250000,
                    "cost_price": 200000,
                    "image": "https://via.placeholder.com/300x300/000/fff?text=MacBook",
                    "category": "Laptops",
                    "description": "Powerful laptop for professionals",
                    "rating": 4.9,
                    "reviews": 85,
                    "badge": "New",
                    "stock": 30,
                    "original_price": 280000,
                    "specs": ["14\" Display", "M3 Chip", "16GB RAM"]
                },
                {
                    "id": "3",
                    "name": "Samsung Galaxy S24",
                    "price": 120000,
                    "cost_price": 95000,
                    "image": "https://via.placeholder.com/300x300/000/fff?text=Samsung",
                    "category": "Phones",
                    "description": "Premium Android phone",
                    "rating": 4.7,
                    "reviews": 95,
                    "badge": "Trending",
                    "stock": 40,
                    "original_price": 135000,
                    "specs": ["6.8\" Display", "200MP Camera", "Snapdragon 8 Gen 3"]
                },
                {
                    "id": "4",
                    "name": "AirPods Pro 2",
                    "price": 35000,
                    "cost_price": 25000,
                    "image": "https://via.placeholder.com/300x300/000/fff?text=AirPods",
                    "category": "Accessories",
                    "description": "Premium wireless earbuds",
                    "rating": 4.6,
                    "reviews": 200,
                    "badge": "Best Seller",
                    "stock": 100,
                    "original_price": 40000,
                    "specs": ["Active Noise Cancellation", "Spatial Audio"]
                }
            ]
            save_json(file_path, sample_products)
            return sample_products
        
        # Create empty file for others
        save_json(file_path, [])
        return []
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []

def save_json(file_path, data):
    """Save JSON to Blob or local file"""
    try:
        # Try Blob first if available
        if USE_BLOB and BLOB_STORE:
            try:
                BLOB_STORE.put(file_path, json.dumps(data))
                print(f"✅ Saved to Blob: {file_path}")
                return True
            except Exception as e:
                print(f"Blob write error for {file_path}: {e}")
        
        # Fallback to local file
        full_path = get_json_path(file_path)
        with open(full_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved to local: {file_path}")
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False

# ================================================================
# ===== SUPABASE CONFIGURATION =====
# ================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://hzqrdwerkgfmfaufabjr.supabase.co")
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', "sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ===== DATABASE CONNECTION =====
DB_CONNECTED = False
DB_TYPE = 'json'

def test_supabase_connection():
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=count",
            headers=SUPABASE_HEADERS,
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

try:
    if test_supabase_connection():
        DB_CONNECTED = True
        DB_TYPE = 'supabase'
        print("✅ Supabase connected!")
    else:
        print("⚠️ Supabase connection failed - using JSON storage (OFFLINE MODE)")
except Exception as e:
    print(f"⚠️ Supabase error: {e}")
    print("📁 OFFLINE MODE - Using JSON storage")

# ================================================================
# ===== DATABASE FUNCTIONS =====
# ================================================================

def load_products():
    """Load all products from Supabase or JSON"""
    if DB_CONNECTED:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/products?select=*",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    save_json('products.json', data)  # Backup to Blob/local
                    return data
                if isinstance(data, dict) and 'items' in data:
                    save_json('products.json', data['items'])
                    return data['items']
                return data
        except Exception as e:
            print(f"Error loading products from Supabase: {e}")
    
    # Fallback to JSON (Blob or local)
    return load_json('products.json')

def load_product_by_id(product_id):
    """Load a single product by ID"""
    if DB_CONNECTED:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data:
                    return data[0]
        except:
            pass
    products = load_products()
    for product in products:
        if str(product.get('id')) == str(product_id):
            return product
    return None

def load_products_by_category(category):
    """Load products by category"""
    if DB_CONNECTED:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/products?category=eq.{category}",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
    products = load_products()
    return [p for p in products if p.get('category') == category]

def load_bundles():
    """Load all bundles from Supabase or JSON"""
    if DB_CONNECTED:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/bundles?select=*",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    save_json('bundles.json', data)
                    return data
                if isinstance(data, dict) and 'items' in data:
                    save_json('bundles.json', data['items'])
                    return data['items']
                return data
        except Exception as e:
            print(f"Error loading bundles: {e}")
    
    return load_json('bundles.json')

def get_cart():
    """Get cart from session"""
    cart = session.get('cart', {})
    if isinstance(cart, list):
        new_cart = {}
        for item_id in cart:
            new_cart[item_id] = new_cart.get(item_id, 0) + 1
        session['cart'] = new_cart
        session.modified = True
        return new_cart
    if not isinstance(cart, dict):
        session['cart'] = {}
        session.modified = True
        return {}
    return cart

def save_product_to_db(product_data):
    """Save product to Supabase or JSON"""
    product_copy = dict(product_data)
    
    if DB_CONNECTED:
        try:
            check = requests.get(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_copy.get('id')}",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if check.status_code == 200 and check.json():
                response = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_copy.get('id')}",
                    headers=SUPABASE_HEADERS,
                    json=product_copy,
                    timeout=5
                )
            else:
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/products",
                    headers=SUPABASE_HEADERS,
                    json=product_copy,
                    timeout=5
                )
            print(f"✅ Product saved to Supabase: {product_copy.get('id')}")
            
            # Also save to Blob/local as backup
            products = load_products()
            found = False
            for p in products:
                if str(p.get('id')) == str(product_copy.get('id')):
                    p.update(product_copy)
                    found = True
                    break
            if not found:
                products.append(product_copy)
            save_json('products.json', products)
            
            return response.status_code in [200, 201, 204]
        except Exception as e:
            print(f"Error saving product to Supabase: {e}")
            return save_product_to_json_only(product_copy)
    else:
        return save_product_to_json_only(product_copy)

def save_product_to_json_only(product_data):
    """Save product to JSON file only (fallback)"""
    products = load_products()
    found = False
    for p in products:
        if str(p.get('id')) == str(product_data.get('id')):
            p.update(product_data)
            found = True
            break
    if not found:
        products.append(product_data)
    save_json('products.json', products)
    print(f"✅ Product saved to JSON: {product_data.get('id')}")
    return True

def update_product_stock(product_id, quantity):
    """Update product stock after order"""
    products = load_products()
    for p in products:
        if str(p.get('id')) == str(product_id):
            current_stock = p.get('stock', 0)
            p['stock'] = max(0, current_stock - quantity)
            save_product_to_db(p)
            return True
    return False

# ================================================================
# ===== ORDER FUNCTIONS =====
# ================================================================

def load_orders():
    """Load all orders from Supabase or JSON"""
    supabase_orders = []
    if DB_CONNECTED:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/orders?select=*&order=created_at.desc",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    supabase_orders = data
                    print(f"✅ Loaded {len(data)} orders from Supabase")
        except Exception as e:
            print(f"Error loading orders from Supabase: {e}")

    json_orders = load_json('orders.json')
    if not isinstance(json_orders, list):
        json_orders = []

    # Merge orders
    merged = {}
    for order in json_orders:
        oid = order.get('order_id')
        if oid:
            merged[oid] = order
    for order in supabase_orders:
        oid = order.get('order_id')
        if oid:
            merged[oid] = order

    all_orders = list(merged.values())
    all_orders.sort(key=lambda o: o.get('created_at', ''), reverse=True)
    return all_orders

def save_order_to_db(order_data):
    """Save order to Supabase and JSON backup"""
    # Always save to Blob/local first (works offline)
    json_saved = save_order_to_json(order_data)

    if DB_CONNECTED:
        try:
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/orders",
                headers=SUPABASE_HEADERS,
                json=order_data,
                timeout=5
            )
            print(f"Supabase response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print(f"✅ Order saved to Supabase: {order_data.get('order_id')}")
                return True
            else:
                print(f"❌ Supabase save failed ({response.status_code}), JSON backup saved")
                return json_saved
        except Exception as e:
            print(f"❌ Error saving order to Supabase: {e}")
            return json_saved
    else:
        return json_saved

def save_order_to_json(order_data):
    """Save order to JSON file - WORKS OFFLINE + BLOB"""
    try:
        orders = load_json('orders.json')
        if not isinstance(orders, list):
            orders = []
        
        orders = [o for o in orders if o.get('order_id') != order_data.get('order_id')]
        orders.insert(0, order_data)
        
        save_json('orders.json', orders)
        print(f"✅ Order saved to JSON/Blob: {order_data.get('order_id')}")
        return True
    except Exception as e:
        print(f"❌ Failed to save order: {e}")
        return False

# ================================================================
# ===== HELPER FUNCTIONS =====
# ================================================================

def get_category_icon(category):
    icons = {
        'Phones': 'fa-mobile-screen',
        'Laptops': 'fa-laptop',
        'Accessories': 'fa-headphones',
        'Wearables': 'fa-watch',
        'Audio': 'fa-music',
        'Televisions': 'fa-tv',
        'Gaming': 'fa-gamepad',
        'Tablets': 'fa-tablet'
    }
    return icons.get(category, 'fa-box')

def get_all_categories():
    return {
        'Phones': 'fa-mobile-screen',
        'Laptops': 'fa-laptop',
        'Accessories': 'fa-headphones',
        'Wearables': 'fa-watch',
        'Audio': 'fa-music',
        'Televisions': 'fa-tv',
        'Gaming': 'fa-gamepad',
        'Tablets': 'fa-tablet'
    }

# ================================================================
# ===== REVENUE & PROFIT ANALYTICS =====
# ================================================================

def get_sales_analytics():
    """Calculate revenue, profit, and sales analytics"""
    try:
        orders = load_orders()
        products = load_products()
        
        if not orders or not isinstance(orders, list):
            orders = []
        if not products or not isinstance(products, list):
            products = []
        
        product_lookup = {}
        for p in products:
            if p and p.get('id'):
                product_lookup[str(p.get('id'))] = p
        
        total_revenue = 0
        total_cost = 0
        total_profit = 0
        total_orders = len(orders)
        total_items_sold = 0
        pos_orders_count = 0
        web_orders_count = 0
        
        monthly_data = {}
        product_sales = {}
        customer_data = {}
        
        for order in orders:
            if order.get('status') == 'cancelled':
                continue
            
            if order.get('source') == 'pos':
                pos_orders_count += 1
            else:
                web_orders_count += 1
            
            customer = order.get('customer', {})
            customer_name = customer.get('name', 'Unknown')
            if customer_name not in customer_data:
                customer_data[customer_name] = {
                    'name': customer_name,
                    'email': customer.get('email', ''),
                    'phone': customer.get('phone', ''),
                    'orders': 0,
                    'total_spent': 0
                }
            customer_data[customer_name]['orders'] += 1
            customer_data[customer_name]['total_spent'] += order.get('total', 0)
                
            order_date = order.get('created_at', '')[:7]
            if order_date and order_date not in monthly_data:
                monthly_data[order_date] = {
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0,
                    'orders': 0,
                    'items': 0,
                    'pos_orders': 0,
                    'web_orders': 0
                }
            
            if order_date:
                monthly_data[order_date]['orders'] += 1
                if order.get('source') == 'pos':
                    monthly_data[order_date]['pos_orders'] += 1
                else:
                    monthly_data[order_date]['web_orders'] += 1
            
            items = order.get('items', [])
            for item in items:
                product_id = str(item.get('product_id', ''))
                quantity = item.get('quantity', 1)
                price = item.get('price', 0)
                item_total = item.get('total', price * quantity)
                
                product = product_lookup.get(product_id, {})
                cost_price = product.get('cost_price', 0) if product else 0
                item_cost = cost_price * quantity
                
                total_revenue += item_total
                total_cost += item_cost
                total_profit += (item_total - item_cost)
                total_items_sold += quantity
                
                if order_date:
                    monthly_data[order_date]['revenue'] += item_total
                    monthly_data[order_date]['cost'] += item_cost
                    monthly_data[order_date]['profit'] += (item_total - item_cost)
                    monthly_data[order_date]['items'] += quantity
                
                product_name = item.get('name', 'Unknown')
                if product_name not in product_sales:
                    product_sales[product_name] = {
                        'quantity': 0,
                        'revenue': 0,
                        'cost': 0,
                        'profit': 0
                    }
                product_sales[product_name]['quantity'] += quantity
                product_sales[product_name]['revenue'] += item_total
                product_sales[product_name]['cost'] += item_cost
                product_sales[product_name]['profit'] += (item_total - item_cost)
        
        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'total_orders': total_orders,
            'total_items_sold': total_items_sold,
            'pos_orders_count': pos_orders_count,
            'web_orders_count': web_orders_count,
            'total_customers': len(customer_data),
            'monthly_data': monthly_data,
            'product_sales': dict(sorted(product_sales.items(), key=lambda x: x[1]['profit'], reverse=True)[:10]),
            'all_product_sales': product_sales,
            'customer_data': customer_data
        }
    except Exception as e:
        print(f"❌ Error in get_sales_analytics: {e}")
        traceback.print_exc()
        return {
            'total_revenue': 0,
            'total_cost': 0,
            'total_profit': 0,
            'total_orders': 0,
            'total_items_sold': 0,
            'pos_orders_count': 0,
            'web_orders_count': 0,
            'total_customers': 0,
            'monthly_data': {},
            'product_sales': {},
            'all_product_sales': {},
            'customer_data': {}
        }

# ================================================================
# ===== ROUTES =====
# ================================================================

@app.route('/')
def index():
    products_list = load_products()
    bundles_list = load_bundles()
    
    products_dict = {}
    for p in products_list:
        if p and 'id' in p:
            products_dict[str(p['id'])] = p
    
    bundles_dict = {}
    for b in bundles_list:
        if b and 'id' in b:
            bundles_dict[str(b['id'])] = b
    
    best_sellers = [p for p in products_list if p.get('badge') == 'Best Seller']
    new_arrivals = [p for p in products_list if p.get('badge') == 'New']
    trending = [p for p in products_list if p.get('badge') == 'Trending']
    
    categories = {}
    for p in products_list:
        cat = p.get('category', 'Other')
        if cat not in categories:
            categories[cat] = {
                'name': cat,
                'icon': get_category_icon(cat),
                'count': 0
            }
        categories[cat]['count'] += 1
    
    return render_template('shop.html',
        products=products_dict,
        all_products=products_dict,
        bundles=bundles_dict,
        best_sellers=best_sellers,
        new_arrivals=new_arrivals,
        trending=trending,
        categories=categories,
        CATEGORIES=get_all_categories()
    )

@app.route('/category/<category_name>')
def category_page(category_name):
    products = load_products_by_category(category_name)
    products_dict = {}
    for p in products:
        if p and 'id' in p:
            products_dict[str(p['id'])] = p
    return render_template('category.html',
        products=products_dict,
        category_name=category_name,
        CATEGORIES=get_all_categories()
    )

@app.route('/product/<product_id>')
def product_detail(product_id):
    product = load_product_by_id(product_id)
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('index'))
    
    related = [p for p in load_products_by_category(product.get('category')) 
               if str(p.get('id')) != product_id][:4]
    
    related_dict = {}
    for r in related:
        if r and 'id' in r:
            related_dict[str(r['id'])] = r
    
    return render_template('product.html',
        product=product,
        related=related_dict
    )

# ================================================================
# ===== IMAGE UPLOAD ROUTE =====
# ================================================================

@app.route('/admin/upload-image', methods=['POST'])
def upload_image():
    """Upload product image"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        image_url = f"/static/uploads/{filename}"
        return jsonify({
            'success': True, 
            'url': image_url,
            'message': 'Image uploaded successfully!'
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400

# ================================================================
# ===== CART ROUTES =====
# ================================================================

@app.route('/cart')
def cart_page():
    cart = get_cart()
    cart_items = []
    subtotal = 0
    total_items = 0
    products = load_products()
    bundles = load_bundles()
    
    for item_id, quantity in cart.items():
        if quantity <= 0:
            continue
        
        product = None
        for p in products:
            if str(p.get('id')) == str(item_id):
                product = p
                break
        
        if product:
            item_total = product.get('price', 0) * quantity
            cart_items.append({
                'id': item_id,
                'name': product.get('name', 'Product'),
                'price': product.get('price', 0),
                'image': product.get('image', ''),
                'type': 'product',
                'quantity': quantity,
                'item_total': item_total,
                'stock': product.get('stock', 0),
                'description': product.get('description', ''),
                'specs': product.get('specs', [])
            })
            subtotal += item_total
            total_items += quantity
            continue
        
        for bundle in bundles:
            if str(bundle.get('id')) == str(item_id):
                item_total = bundle.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id,
                    'name': bundle.get('name', 'Bundle'),
                    'price': bundle.get('price', 0),
                    'image': bundle.get('image', ''),
                    'type': 'bundle',
                    'quantity': quantity,
                    'item_total': item_total,
                    'products': bundle.get('products', [])
                })
                subtotal += item_total
                total_items += quantity
                break
    
    shipping = 0 if subtotal >= 50000 else 800
    total = subtotal + shipping
    
    return render_template('cart.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        total_items=total_items
    )

@app.route('/add-to-cart/<item_id>', methods=['POST'])
def add_to_cart(item_id):
    try:
        cart = get_cart()
        products = load_products()
        bundles = load_bundles()
        
        product = None
        for p in products:
            if str(p.get('id')) == str(item_id):
                product = p
                break
        
        if product:
            current_qty = cart.get(item_id, 0)
            if current_qty >= product.get('stock', 0):
                return jsonify({
                    'success': False,
                    'message': 'Not enough stock available!'
                })
        
        bundle_exists = False
        for b in bundles:
            if str(b.get('id')) == str(item_id):
                bundle_exists = True
                break
        
        if not product and not bundle_exists:
            return jsonify({'success': False, 'message': 'Item not found'})
        
        cart[item_id] = cart.get(item_id, 0) + 1
        session['cart'] = cart
        session.modified = True
        
        total_items = sum(cart.values())
        return jsonify({
            'success': True,
            'message': 'Added to cart!',
            'count': total_items,
            'quantity': cart[item_id]
        })
    except Exception as e:
        print(f"Error adding to cart: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/update-cart/<item_id>/<action>', methods=['POST'])
def update_cart_item(item_id, action):
    try:
        cart = get_cart()
        products = load_products()
        
        if action == 'increase':
            product = None
            for p in products:
                if str(p.get('id')) == str(item_id):
                    product = p
                    break
            
            if product:
                current = cart.get(item_id, 0)
                if current >= product.get('stock', 0):
                    return jsonify({
                        'success': False,
                        'message': 'Not enough stock available!'
                    })
            
            cart[item_id] = cart.get(item_id, 0) + 1
            
        elif action == 'decrease':
            if item_id in cart:
                if cart[item_id] <= 1:
                    del cart[item_id]
                else:
                    cart[item_id] -= 1
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        
        elif action == 'remove':
            if item_id in cart:
                del cart[item_id]
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})
        
        session['cart'] = cart
        session.modified = True
        
        subtotal = 0
        products = load_products()
        bundles = load_bundles()
        
        for iid, qty in cart.items():
            for p in products:
                if str(p.get('id')) == str(iid):
                    subtotal += p.get('price', 0) * qty
                    break
            else:
                for b in bundles:
                    if str(b.get('id')) == str(iid):
                        subtotal += b.get('price', 0) * qty
                        break
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        item_price = 0
        for p in products:
            if str(p.get('id')) == str(item_id):
                item_price = p.get('price', 0)
                break
        else:
            for b in bundles:
                if str(b.get('id')) == str(item_id):
                    item_price = b.get('price', 0)
                    break
        
        return jsonify({
            'success': True,
            'quantity': cart.get(item_id, 0),
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'total_items': sum(cart.values()),
            'item_total': item_price * cart.get(item_id, 0)
        })
    except Exception as e:
        print(f"Error updating cart: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/remove-from-cart/<item_id>', methods=['POST'])
def remove_from_cart(item_id):
    try:
        cart = get_cart()
        if item_id in cart:
            del cart[item_id]
            session['cart'] = cart
            session.modified = True
            return jsonify({
                'success': True,
                'message': 'Removed from cart!',
                'count': sum(cart.values())
            })
        return jsonify({'success': False, 'message': 'Item not in cart'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ================================================================
# ===== CHECKOUT & ORDERS =====
# ================================================================

@app.route('/checkout')
def checkout_page():
    cart = get_cart()
    if not cart:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('index'))
    
    cart_items = []
    subtotal = 0
    total_items = 0
    products = load_products()
    bundles = load_bundles()
    
    for item_id, quantity in cart.items():
        if quantity <= 0:
            continue
        
        product = None
        for p in products:
            if str(p.get('id')) == str(item_id):
                product = p
                break
        
        if product:
            item_total = product.get('price', 0) * quantity
            cart_items.append({
                'id': item_id,
                'name': product.get('name', 'Product'),
                'price': product.get('price', 0),
                'image': product.get('image', ''),
                'type': 'product',
                'quantity': quantity,
                'item_total': item_total
            })
            subtotal += item_total
            total_items += quantity
            continue
        
        for bundle in bundles:
            if str(bundle.get('id')) == str(item_id):
                item_total = bundle.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id,
                    'name': bundle.get('name', 'Bundle'),
                    'price': bundle.get('price', 0),
                    'image': bundle.get('image', ''),
                    'type': 'bundle',
                    'quantity': quantity,
                    'item_total': item_total
                })
                subtotal += item_total
                total_items += quantity
                break
    
    shipping = 0 if subtotal >= 50000 else 800
    total = subtotal + shipping
    
    return render_template('checkout.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        total_items=total_items
    )

@app.route('/place-order', methods=['POST'])
def place_order():
    try:
        cart = get_cart()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty'})
        
        if request.is_json:
            data = request.get_json()
        else:
            data = {
                'customer_name': request.form.get('customer_name', 'Customer'),
                'customer_email': request.form.get('customer_email', 'customer@example.com'),
                'customer_phone': request.form.get('customer_phone', 'N/A'),
                'customer_address': request.form.get('customer_address', 'N/A')
            }
        
        subtotal = 0
        products = load_products()
        bundles = load_bundles()
        order_items = []
        products_to_update = []
        
        for item_id, quantity in cart.items():
            item_found = False
            for p in products:
                if str(p.get('id')) == str(item_id):
                    current_stock = p.get('stock', 0)
                    if current_stock < quantity:
                        return jsonify({
                            'success': False,
                            'message': f'Not enough stock for {p.get("name")}. Available: {current_stock}'
                        }), 400
                    
                    item_total = p.get('price', 0) * quantity
                    subtotal += item_total
                    order_items.append({
                        'product_id': item_id,
                        'name': p.get('name'),
                        'price': p.get('price', 0),
                        'quantity': quantity,
                        'total': item_total,
                        'type': 'product'
                    })
                    item_found = True
                    
                    current_stock = p.get('stock', 0)
                    new_stock = max(0, current_stock - quantity)
                    p['stock'] = new_stock
                    products_to_update.append(dict(p))
                    break
            
            if not item_found:
                for b in bundles:
                    if str(b.get('id')) == str(item_id):
                        item_total = b.get('price', 0) * quantity
                        subtotal += item_total
                        order_items.append({
                            'product_id': item_id,
                            'name': b.get('name'),
                            'price': b.get('price', 0),
                            'quantity': quantity,
                            'total': item_total,
                            'type': 'bundle'
                        })
                        break
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        order_id = f"ELEC-{uuid.uuid4().hex[:8].upper()}"
        
        customer_name = data.get('customer_name', 'Customer')
        customer_email = data.get('customer_email', 'customer@example.com')
        customer_phone = data.get('customer_phone', 'N/A')
        customer_address = data.get('customer_address', 'N/A')
        
        order_data = {
            'order_id': order_id,
            'items': order_items,
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'status': 'pending',
            'source': 'web',
            'created_at': datetime.utcnow().isoformat(),
            'customer': {
                'name': customer_name,
                'email': customer_email,
                'phone': customer_phone,
                'address': customer_address
            }
        }
        
        print(f"📦 Order data: {json.dumps(order_data, indent=2)}")
        
        if save_order_to_db(order_data):
            print(f"📦 Reducing stock for {len(products_to_update)} items...")
            
            for updated_product in products_to_update:
                save_product_to_db(updated_product)
                print(f"✅ Stock updated: {updated_product.get('name')} → {updated_product.get('stock')}")
            
            session['cart'] = {}
            session.modified = True
            
            return jsonify({
                'success': True,
                'order_id': order_id,
                'total': total,
                'message': 'Order placed successfully!'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to save order. Please try again.'}), 500
            
    except Exception as e:
        print(f"❌ Error placing order: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/order-confirmation/<order_id>')
def order_confirmation(order_id):
    return render_template('confirmation.html', order_id=order_id)

@app.route('/clear-cart', methods=['POST'])
def clear_cart():
    session['cart'] = {}
    session.modified = True
    return jsonify({'success': True, 'message': 'Cart cleared'})

# ================================================================
# ===== API ROUTES =====
# ================================================================

@app.route('/api/status')
def api_status():
    return jsonify({
        'database': DB_TYPE,
        'connected': DB_CONNECTED,
        'products': len(load_products()),
        'bundles': len(load_bundles()),
        'orders': len(load_orders()),
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'vercel' if IS_VERCEL else 'local',
        'mode': 'online' if DB_CONNECTED else 'offline',
        'blob_storage': USE_BLOB
    })

@app.route('/api/products')
def api_products():
    products = load_products()
    return jsonify(products)

@app.route('/api/products/<product_id>')
def api_product(product_id):
    product = load_product_by_id(product_id)
    if product:
        return jsonify(product)
    return jsonify({'error': 'Product not found'}), 404

@app.route('/api/orders')
def api_orders():
    orders = load_orders()
    return jsonify(orders)

@app.route('/api/orders/<order_id>')
def api_order(order_id):
    orders = load_orders()
    for order in orders:
        if order.get('order_id') == order_id:
            return jsonify(order)
    return jsonify({'error': 'Order not found'}), 404

@app.route('/test-order-api')
def test_order_api():
    test_order = {
        'order_id': 'TEST-123',
        'items': [{'name': 'Test', 'price': 1000, 'quantity': 1, 'total': 1000}],
        'subtotal': 1000,
        'shipping': 0,
        'total': 1000,
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat(),
        'customer': {'name': 'Test', 'email': 'test@test.com', 'phone': '123', 'address': '123 St'}
    }
    
    result = save_order_to_db(test_order)
    return jsonify({
        'success': result,
        'order': test_order,
        'db_connected': DB_CONNECTED,
        'db_type': DB_TYPE,
        'blob_storage': USE_BLOB
    })

# ================================================================
# ===== ADMIN ROUTES =====
# ================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'electronics2026':
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard with proper error handling"""
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin_login'))
    
    try:
        products = load_products()
        bundles = load_bundles()
        cart = get_cart()
        orders = load_orders()
        analytics = get_sales_analytics()
        
        customer_list = {}
        pos_count = 0
        web_count = 0
        
        for order in orders:
            if order.get('source') == 'pos':
                pos_count += 1
            else:
                web_count += 1
            
            if order.get('customer') and order['customer'].get('name'):
                name = order['customer']['name']
                if name not in customer_list:
                    customer_list[name] = {
                        'name': name,
                        'email': order['customer'].get('email', ''),
                        'phone': order['customer'].get('phone', ''),
                        'orders': 0,
                        'total_spent': 0
                    }
                customer_list[name]['orders'] += 1
                customer_list[name]['total_spent'] += order.get('total', 0)
        
        customers = list(customer_list.values())
        customers.sort(key=lambda x: x['orders'], reverse=True)
        
        if products is None or not isinstance(products, list):
            products = []
        if orders is None or not isinstance(orders, list):
            orders = []
        if bundles is None or not isinstance(bundles, list):
            bundles = []
        if cart is None or not isinstance(cart, dict):
            cart = {}
        
        stats = {
            'total_products': len(products),
            'total_bundles': len(bundles),
            'total_cart_items': sum(cart.values()),
            'low_stock': len([p for p in products if p.get('stock', 0) < 10]),
            'total_orders': len(orders),
            'pending_orders': len([o for o in orders if o.get('status') == 'pending']),
            'pos_orders': pos_count,
            'web_orders': web_count,
            'total_revenue': analytics.get('total_revenue', 0),
            'total_profit': analytics.get('total_profit', 0),
            'total_items_sold': analytics.get('total_items_sold', 0),
            'total_customers': len(customers),
            'db_mode': 'online' if DB_CONNECTED else 'offline',
            'blob_storage': USE_BLOB
        }
        
        return render_template('admin.html',
            products=products,
            bundles=bundles,
            orders=orders,
            customers=customers,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=DB_CONNECTED
        )
        
    except Exception as e:
        print(f"❌ Admin dashboard error: {e}")
        flash('Error loading admin dashboard', 'danger')
        
        return render_template('admin.html',
            products=[],
            bundles=[],
            orders=[],
            customers=[],
            pos_count=0,
            analytics={},
            stats={
                'total_products': 0,
                'total_bundles': 0,
                'total_cart_items': 0,
                'low_stock': 0,
                'total_orders': 0,
                'pending_orders': 0,
                'pos_orders': 0,
                'web_orders': 0,
                'total_revenue': 0,
                'total_profit': 0,
                'total_items_sold': 0,
                'total_customers': 0,
                'db_mode': 'offline',
                'blob_storage': False
            },
            DB_CONNECTED=DB_CONNECTED
        )

@app.route('/admin/pos')
def admin_pos():
    """POS system for admin to create orders for customers"""
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin_login'))
    
    products = load_products()
    customers = []
    
    orders = load_orders()
    customer_list = {}
    for order in orders:
        if order.get('customer') and order['customer'].get('name'):
            name = order['customer']['name']
            if name not in customer_list:
                customer_list[name] = {
                    'name': name,
                    'email': order['customer'].get('email', ''),
                    'phone': order['customer'].get('phone', ''),
                    'orders': 0,
                    'total_spent': 0
                }
            customer_list[name]['orders'] += 1
            customer_list[name]['total_spent'] += order.get('total', 0)
    
    customers = list(customer_list.values())
    customers.sort(key=lambda x: x['orders'], reverse=True)
    
    return render_template('pos.html',
        products=products,
        customers=customers,
        DB_CONNECTED=DB_CONNECTED
    )

@app.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    """Place order from POS system - WORKS OFFLINE + BLOB"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        order_id = f"POS-{uuid.uuid4().hex[:8].upper()}"

        products = load_products()
        product_lookup = {str(p.get('id')): p for p in products}

        items = []
        products_to_update = []

        for item in data.get('items', []):
            product_id = str(item.get('product_id'))
            quantity = item.get('quantity', 1)

            product = product_lookup.get(product_id)
            if product:
                current_stock = product.get('stock', 0)
                if current_stock < quantity:
                    return jsonify({
                        'success': False,
                        'message': f'Not enough stock for {product.get("name")}. Available: {current_stock}'
                    }), 400
                product['stock'] = max(0, current_stock - quantity)
                products_to_update.append(dict(product))

            items.append({
                'product_id': item.get('product_id'),
                'name': item.get('name'),
                'price': item.get('price'),
                'quantity': quantity,
                'total': item.get('total'),
                'type': 'product'
            })
        
        order_data = {
            'order_id': order_id,
            'items': items,
            'subtotal': data.get('subtotal', 0),
            'shipping': data.get('shipping', 0),
            'total': data.get('total', 0),
            'status': 'confirmed',
            'source': 'pos',
            'created_at': datetime.utcnow().isoformat(),
            'customer': {
                'name': data.get('customer_name', 'Walk-in Customer'),
                'email': data.get('customer_email', 'walkin@example.com'),
                'phone': data.get('customer_phone', 'N/A'),
                'address': data.get('customer_address', 'In-store purchase')
            }
        }
        
        if not save_order_to_db(order_data):
            return jsonify({'success': False, 'message': 'Failed to save order'}), 500

        for updated_product in products_to_update:
            save_product_to_db(updated_product)
            print(f"✅ Stock updated: {updated_product.get('name')} → {updated_product.get('stock')}")

        analytics = get_sales_analytics()

        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Order placed successfully!',
            'analytics': analytics,
            'stats': {
                'total_revenue': analytics.get('total_revenue', 0),
                'total_profit': analytics.get('total_profit', 0),
                'total_orders': analytics.get('total_orders', 0),
                'total_items_sold': analytics.get('total_items_sold', 0),
                'pos_orders_count': analytics.get('pos_orders_count', 0),
                'web_orders_count': analytics.get('web_orders_count', 0)
            }
        })
            
    except Exception as e:
        print(f"❌ POS Order error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/analytics')
def admin_api_analytics():
    """API endpoint for sales analytics"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        analytics = get_sales_analytics()
        return jsonify(analytics)
    except Exception as e:
        print(f"Error in analytics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/revenue')
def admin_api_revenue():
    """API endpoint for revenue data"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        analytics = get_sales_analytics()
        return jsonify({
            'total_revenue': analytics.get('total_revenue', 0),
            'total_profit': analytics.get('total_profit', 0),
            'total_orders': analytics.get('total_orders', 0),
            'total_items_sold': analytics.get('total_items_sold', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/products', methods=['POST'])
def admin_products():
    """Handle product creation/update via AJAX"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        product_data = {
            'id': request.form.get('id'),
            'name': request.form.get('name'),
            'price': float(request.form.get('price', 0)),
            'cost_price': float(request.form.get('cost_price', 0)) or 0,
            'image': request.form.get('image'),
            'category': request.form.get('category'),
            'description': request.form.get('description'),
            'rating': float(request.form.get('rating', 4.0)),
            'reviews': int(request.form.get('reviews', 0)),
            'badge': request.form.get('badge', ''),
            'stock': int(request.form.get('stock', 0)),
            'original_price': float(request.form.get('original_price', 0)) or None,
            'specs': request.form.get('specs', '').split(',') if request.form.get('specs') else []
        }
        
        if save_product_to_db(product_data):
            return jsonify({'success': True, 'message': 'Product saved successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Error saving product'}), 500
    except Exception as e:
        print(f"Error saving product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/products/<product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        if DB_CONNECTED:
            response = requests.delete(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code in [200, 204]:
                return jsonify({'success': True})
        
        products = load_products()
        if isinstance(products, list):
            products = [p for p in products if str(p.get('id')) != str(product_id)]
        else:
            products = []
        save_json('products.json', products)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/orders/<order_id>/status', methods=['POST'])
def admin_update_order_status(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        new_status = request.json.get('status')
        if not new_status:
            return jsonify({'success': False, 'message': 'Status required'}), 400
        
        if DB_CONNECTED:
            try:
                response = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
                    headers=SUPABASE_HEADERS,
                    json={'status': new_status},
                    timeout=5
                )
                if response.status_code in [200, 204]:
                    orders = load_orders()
                    if isinstance(orders, list):
                        for order in orders:
                            if order.get('order_id') == order_id:
                                order['status'] = new_status
                                break
                        save_json('orders.json', orders)
                    return jsonify({'success': True})
            except:
                pass
        
        orders = load_orders()
        if isinstance(orders, list):
            for order in orders:
                if order.get('order_id') == order_id:
                    order['status'] = new_status
                    break
        save_json('orders.json', orders)
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/cart-count', methods=['GET'])
def cart_count():
    """Get cart count for header"""
    try:
        cart = get_cart()
        count = sum(cart.values()) if cart and isinstance(cart, dict) else 0
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'count': 0})

# ================================================================
# ===== DATA IMPORT/EXPORT ROUTES =====
# ================================================================

@app.route('/export-local-data')
def export_local_data():
    """Export local JSON data for migration"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = {
        'products': load_json('products.json'),
        'orders': load_json('orders.json'),
        'bundles': load_json('bundles.json'),
        'analytics': get_sales_analytics(),
        'blob_storage': USE_BLOB
    }
    
    return jsonify(data)

@app.route('/import-data', methods=['POST'])
def import_data():
    """Import data to Vercel - POST JSON"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        messages = []
        
        if 'products' in data and data['products']:
            save_json('products.json', data['products'])
            messages.append(f"✅ Imported {len(data['products'])} products")
            
            if DB_CONNECTED:
                for product in data['products']:
                    try:
                        check = requests.get(
                            f"{SUPABASE_URL}/rest/v1/products?id=eq.{product.get('id')}",
                            headers=SUPABASE_HEADERS,
                            timeout=5
                        )
                        if check.status_code == 200 and check.json():
                            requests.patch(
                                f"{SUPABASE_URL}/rest/v1/products?id=eq.{product.get('id')}",
                                headers=SUPABASE_HEADERS,
                                json=product,
                                timeout=5
                            )
                        else:
                            requests.post(
                                f"{SUPABASE_URL}/rest/v1/products",
                                headers=SUPABASE_HEADERS,
                                json=product,
                                timeout=5
                            )
                    except Exception as e:
                        print(f"Error syncing product: {e}")
        
        if 'orders' in data and data['orders']:
            save_json('orders.json', data['orders'])
            messages.append(f"✅ Imported {len(data['orders'])} orders")
            
            if DB_CONNECTED:
                for order in data['orders']:
                    try:
                        requests.post(
                            f"{SUPABASE_URL}/rest/v1/orders",
                            headers=SUPABASE_HEADERS,
                            json=order,
                            timeout=5
                        )
                    except Exception as e:
                        print(f"Error syncing order: {e}")
        
        if 'bundles' in data and data['bundles']:
            save_json('bundles.json', data['bundles'])
            messages.append(f"✅ Imported {len(data['bundles'])} bundles")
        
        if not messages:
            messages.append("⚠️ No data to import")
        
        return jsonify({
            'success': True,
            'message': ' | '.join(messages),
            'products': len(data.get('products', [])),
            'orders': len(data.get('orders', [])),
            'blob_storage': USE_BLOB
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/import-page')
def import_page():
    """Simple import page - works on Vercel"""
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin_login'))
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Import Data - Price Point</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; padding: 40px; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1 { color: #1a1a2e; margin-bottom: 10px; }
            p { color: #666; margin-bottom: 30px; }
            .step { background: #f8f9fa; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid #3b82f6; }
            .step h3 { color: #1a1a2e; margin-bottom: 10px; }
            .step ol { padding-left: 20px; color: #333; }
            .step ol li { margin-bottom: 8px; }
            .code-block { background: #1a1a2e; color: #e2e8f0; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 13px; overflow-x: auto; margin: 10px 0; white-space: pre-wrap; word-wrap: break-word; }
            textarea { width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-family: monospace; font-size: 14px; min-height: 200px; resize: vertical; }
            textarea:focus { outline: none; border-color: #3b82f6; }
            .btn { padding: 12px 30px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
            .btn-primary { background: #3b82f6; color: white; }
            .btn-primary:hover { background: #2563eb; transform: translateY(-2px); }
            .btn-success { background: #22c55e; color: white; }
            .btn-success:hover { background: #16a34a; transform: translateY(-2px); }
            .btn-outline { background: transparent; border: 2px solid #e2e8f0; color: #475569; }
            .btn-outline:hover { background: #f1f5f9; }
            .flex { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
            .mb-10 { margin-bottom: 10px; }
            label { font-weight: 600; display: block; margin-bottom: 5px; color: #1a1a2e; }
            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
            .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
            .badge-success { background: #dcfce7; color: #166534; }
            .badge-info { background: #dbeafe; color: #1e40af; }
            .badge-warning { background: #fef3c7; color: #92400e; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📥 Import Data to Vercel</h1>
            <p>Copy your local data and import it to this Vercel deployment</p>
            
            <div class="step">
                <h3>📋 Current Data Status</h3>
                <div class="grid-2">
                    <div>
                        <p><strong>Products:</strong> <span class="badge badge-info">{{ products|length }}</span></p>
                        <p><strong>Orders:</strong> <span class="badge badge-info">{{ orders|length }}</span></p>
                    </div>
                    <div>
                        <p><strong>Mode:</strong> 
                            {% if DB_CONNECTED %}
                            <span class="badge badge-success">🟢 Online</span>
                            {% else %}
                            <span class="badge badge-warning">🔴 Offline</span>
                            {% endif %}
                        </p>
                        <p><strong>Blob Storage:</strong> 
                            {% if blob_storage %}
                            <span class="badge badge-success">✅ Enabled</span>
                            {% else %}
                            <span class="badge badge-warning">⚠️ Disabled</span>
                            {% endif %}
                        </p>
                        <p><strong>Revenue:</strong> KSh {{ analytics.total_revenue|default(0)|int }}</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <h3>Step 1: Get your local data</h3>
                <ol>
                    <li>Go to your <strong>local</strong> Price Point at <code>http://localhost:5000/export-local-data</code></li>
                    <li>Copy the entire JSON response</li>
                </ol>
                <div class="code-block"># On your local machine, visit:
http://localhost:5000/export-local-data</div>
            </div>
            
            <div class="step">
                <h3>Step 2: Paste your data here</h3>
                <form method="POST" action="{{ url_for('import_data') }}">
                    <div class="mb-10">
                        <label>Products Data (from products.json)</label>
                        <textarea name="products_data" placeholder='[{"id": "1", "name": "iPhone", ...}]'></textarea>
                    </div>
                    <div class="mb-10">
                        <label>Orders Data (from orders.json)</label>
                        <textarea name="orders_data" placeholder='[{"order_id": "ELEC-123", ...}]'></textarea>
                    </div>
                    <button type="submit" class="btn btn-success">📥 Import Data</button>
                </form>
            </div>
            
            <div class="step">
                <h3>Step 3: Or use the API directly</h3>
                <div class="code-block">curl -X POST {{ request.host_url }}import-data \
  -H "Content-Type: application/json" \
  -d @data.json</div>
            </div>
            
            <div class="flex">
                <a href="/admin" class="btn btn-outline">← Back to Admin</a>
                <a href="/admin/pos" class="btn btn-primary">🛒 Go to POS</a>
            </div>
        </div>
    </body>
    </html>
    ''', 
    products=load_products(), 
    orders=load_orders(), 
    analytics=get_sales_analytics(), 
    DB_CONNECTED=DB_CONNECTED,
    blob_storage=USE_BLOB
    )

# ================================================================
# ===== DEBUG ROUTE =====
# ================================================================

@app.route('/debug')
def debug():
    """Debug endpoint to check file system"""
    import os
    return jsonify({
        'is_vercel': IS_VERCEL,
        'json_folder': JSON_FOLDER,
        'blob_storage': USE_BLOB,
        'files_in_json_folder': os.listdir(JSON_FOLDER) if os.path.exists(JSON_FOLDER) else [],
        'orders_json_exists': os.path.exists(get_json_path('orders.json')),
        'products_json_exists': os.path.exists(get_json_path('products.json')),
        'db_connected': DB_CONNECTED,
        'mode': 'online' if DB_CONNECTED else 'offline',
        'cwd': os.getcwd()
    })

# ================================================================
# ===== RUN APP =====
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("📱 PRICE POINT - Premium Electronics Shop")
    print("="*60)
    print(f"📁 Database: {DB_TYPE}")
    print(f"🔗 Connected: {'✅ YES' if DB_CONNECTED else '❌ NO (OFFLINE MODE)'}")
    print(f"🌍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    print(f"📁 JSON Folder: {JSON_FOLDER}")
    print(f"💾 Blob Storage: {'✅ ENABLED' if USE_BLOB else '❌ DISABLED'}")
    print("💰 Prices in Kenyan Shillings (KES)")
    print("="*60)
    
    products = load_products()
    bundles = load_bundles()
    orders = load_orders()
    print(f"\n📊 Products: {len(products) if products else 0}")
    print(f"📊 Bundles: {len(bundles) if bundles else 0}")
    print(f"📊 Orders: {len(orders) if orders else 0}")
    print("="*60)
    
    analytics = get_sales_analytics()
    print(f"\n💰 Total Revenue: KSh {analytics.get('total_revenue', 0):,.0f}")
    print(f"📈 Total Profit: KSh {analytics.get('total_profit', 0):,.0f}")
    print(f"📦 Total Orders: {analytics.get('total_orders', 0)}")
    print("="*60)
    
    print("\n🚀 Starting server...")
    print("📍 http://localhost:5000")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
