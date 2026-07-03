from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from datetime import datetime, timedelta
import os
import uuid
import json
import requests
import traceback
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)
application = app
app.secret_key = 'allison-electronics-secret-2026'
app.permanent_session_lifetime = timedelta(days=7)

# ================================================================
# ===== CONFIGURATION =====
# ================================================================

IS_VERCEL = 'VERCEL' in os.environ or 'NOW' in os.environ

# Force print to see what's happening
print(f"🔵 Running on: {'VERCEL' if IS_VERCEL else 'LOCAL'}")

if IS_VERCEL:
    UPLOAD_FOLDER = '/tmp/static/uploads'
    STATIC_FOLDER = '/tmp/static'
else:
    UPLOAD_FOLDER = 'static/uploads'
    STATIC_FOLDER = 'static'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)
except:
    pass

app.static_folder = STATIC_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===== SUPABASE CONFIG =====
SUPABASE_URL = "https://hzqrdwerkgfmfaufabjr.supabase.co"
SUPABASE_KEY = "sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ================================================================
# ===== TEST CONNECTION ON STARTUP =====
# ================================================================

def test_supabase_connection():
    """Test if Supabase is reachable"""
    try:
        print("🔍 Testing Supabase connection...")
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/orders?select=count",
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        print(f"📤 Supabase test: status {response.status_code}")
        if response.status_code == 200:
            print("✅ Supabase connected successfully!")
            return True
        else:
            print(f"❌ Supabase returned: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

# Test connection on startup
CONNECTION_OK = test_supabase_connection()

# ================================================================
# ===== DATA FUNCTIONS =====
# ================================================================

def load_orders():
    """Load orders from Supabase with detailed logging"""
    try:
        print("📤 FETCHING orders from Supabase...")
        url = f"{SUPABASE_URL}/rest/v1/orders?select=*&order=created_at.desc"
        print(f"📤 URL: {url}")
        
        response = requests.get(
            url,
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        
        print(f"📤 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"✅ Loaded {len(data)} orders")
                if len(data) > 0:
                    print(f"📦 Sample order: {data[0].get('order_id')}")
                return data
            else:
                print(f"⚠️ Unexpected data type: {type(data)}")
                return []
        else:
            print(f"❌ Supabase error: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}")
            return []
    except Exception as e:
        print(f"❌ Error loading orders: {e}")
        traceback.print_exc()
        return []

def load_products():
    """Load products from Supabase with detailed logging"""
    try:
        print("📤 FETCHING products from Supabase...")
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=*",
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        
        print(f"📤 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"✅ Loaded {len(data)} products")
                return data
            else:
                print(f"⚠️ Unexpected data type: {type(data)}")
                return []
        else:
            print(f"❌ Supabase error: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error loading products: {e}")
        return []

def load_bundles():
    """Load bundles from Supabase"""
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/bundles?select=*",
            headers=SUPABASE_HEADERS,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
        return []
    except:
        return []

def get_cart():
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

# ================================================================
# ===== ANALYTICS =====
# ================================================================

def get_sales_analytics():
    """Calculate revenue, profit, and sales analytics"""
    try:
        orders = load_orders()
        products = load_products()
        
        print(f"📊 Analytics - Orders: {len(orders) if orders else 0}")
        print(f"📊 Analytics - Products: {len(products) if products else 0}")
        
        if not orders:
            orders = []
        if not products:
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
        customer_data = {}
        
        for order in orders:
            try:
                if order.get('status') == 'cancelled':
                    continue
                
                customer = order.get('customer', {})
                if isinstance(customer, str):
                    try:
                        customer = json.loads(customer)
                    except:
                        customer = {}
                if isinstance(customer, list):
                    customer = customer[0] if customer else {}
                if not isinstance(customer, dict):
                    customer = {}
                
                items = order.get('items', [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except:
                        items = []
                if not isinstance(items, list):
                    items = []
                
                source = order.get('source', 'web')
                if source == 'pos':
                    pos_orders_count += 1
                else:
                    web_orders_count += 1
                
                customer_name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
                if customer_name not in customer_data:
                    customer_data[customer_name] = {
                        'name': customer_name,
                        'email': customer.get('email', '') if isinstance(customer, dict) else '',
                        'phone': customer.get('phone', '') if isinstance(customer, dict) else '',
                        'orders': 0,
                        'total_spent': 0
                    }
                customer_data[customer_name]['orders'] += 1
                customer_data[customer_name]['total_spent'] += order.get('total', 0)
                
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
                    
            except Exception as order_error:
                print(f"⚠️ Error processing order: {order_error}")
                continue
        
        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'total_orders': total_orders,
            'total_items_sold': total_items_sold,
            'pos_orders_count': pos_orders_count,
            'web_orders_count': web_orders_count,
            'total_customers': len(customer_data),
            'monthly_data': {},
            'product_sales': {},
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
            'customer_data': {}
        }

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
    products = load_products()
    products_dict = {}
    for p in products:
        if p and 'id' in p and p.get('category') == category_name:
            products_dict[str(p['id'])] = p
    return render_template('category.html',
        products=products_dict,
        category_name=category_name,
        CATEGORIES=get_all_categories()
    )

@app.route('/product/<product_id>')
def product_detail(product_id):
    products = load_products()
    product = None
    for p in products:
        if str(p.get('id')) == str(product_id):
            product = p
            break
    
    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('index'))
    
    related = [p for p in products if p.get('category') == product.get('category') and str(p.get('id')) != product_id][:4]
    
    related_dict = {}
    for r in related:
        if r and 'id' in r:
            related_dict[str(r['id'])] = r
    
    return render_template('product.html',
        product=product,
        related=related_dict
    )

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
        
        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
                
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
        
        if not order_items:
            return jsonify({'success': False, 'message': 'No valid items in cart'}), 400
        
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
        
        # Save to Supabase
        import json as json_module
        supabase_order = {
            'order_id': order_data.get('order_id'),
            'items': json_module.dumps(order_data.get('items', [])),
            'subtotal': order_data.get('subtotal', 0),
            'shipping': order_data.get('shipping', 0),
            'total': order_data.get('total', 0),
            'status': order_data.get('status', 'pending'),
            'source': order_data.get('source', 'web'),
            'created_at': order_data.get('created_at', datetime.utcnow().isoformat()),
            'customer': json_module.dumps(order_data.get('customer', {}))
        }
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/orders",
            headers=SUPABASE_HEADERS,
            json=supabase_order,
            timeout=10
        )
        
        if response.status_code in [200, 201, 204]:
            session['cart'] = {}
            session.modified = True
            
            return jsonify({
                'success': True,
                'order_id': order_id,
                'total': total,
                'message': 'Order placed successfully!'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to save order'}), 500
            
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
    orders = load_orders()
    products = load_products()
    return jsonify({
        'success': True,
        'products': len(products),
        'orders': len(orders),
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'vercel' if IS_VERCEL else 'local',
        'connection_ok': CONNECTION_OK
    })

@app.route('/api/products')
def api_products():
    return jsonify(load_products())

@app.route('/api/orders')
def api_orders():
    return jsonify(load_orders())

@app.route('/cart-count', methods=['GET'])
def cart_count():
    try:
        cart = get_cart()
        count = sum(cart.values()) if cart and isinstance(cart, dict) else 0
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

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
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin_login'))
    
    try:
        products = load_products()
        orders = load_orders()
        bundles = load_bundles()
        cart = get_cart()
        analytics = get_sales_analytics()
        
        customer_list = {}
        pos_count = 0
        web_count = 0
        
        for order in orders:
            customer = order.get('customer', {})
            if isinstance(customer, str):
                try:
                    customer = json.loads(customer)
                except:
                    customer = {}
            if isinstance(customer, list):
                customer = customer[0] if customer else {}
            
            source = order.get('source', 'web')
            if source == 'pos':
                pos_count += 1
            else:
                web_count += 1
            
            name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
            if name not in customer_list:
                customer_list[name] = {
                    'name': name,
                    'email': customer.get('email', '') if isinstance(customer, dict) else '',
                    'phone': customer.get('phone', '') if isinstance(customer, dict) else '',
                    'orders': 0,
                    'total_spent': 0
                }
            customer_list[name]['orders'] += 1
            customer_list[name]['total_spent'] += order.get('total', 0)
        
        customers = list(customer_list.values())
        customers.sort(key=lambda x: x['orders'], reverse=True)
        
        stats = {
            'total_products': len(products),
            'total_bundles': len(bundles),
            'total_cart_items': sum(cart.values()) if cart else 0,
            'low_stock': len([p for p in products if p.get('stock', 0) < 10]),
            'total_orders': len(orders),
            'pending_orders': len([o for o in orders if o.get('status') == 'pending']),
            'pos_orders': pos_count,
            'web_orders': web_count,
            'total_revenue': analytics.get('total_revenue', 0),
            'total_profit': analytics.get('total_profit', 0),
            'total_items_sold': analytics.get('total_items_sold', 0),
            'total_customers': len(customers),
            'db_mode': 'online' if CONNECTION_OK else 'offline'
        }
        
        return render_template('admin.html',
            products=products,
            bundles=bundles,
            orders=orders,
            customers=customers,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=CONNECTION_OK
        )
        
    except Exception as e:
        print(f"❌ Admin dashboard error: {e}")
        traceback.print_exc()
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
                'db_mode': 'offline'
            },
            DB_CONNECTED=False
        )

@app.route('/admin/pos')
def admin_pos():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin_login'))
    
    products = load_products()
    customers = []
    
    orders = load_orders()
    customer_list = {}
    for order in orders:
        customer = order.get('customer', {})
        if isinstance(customer, str):
            try:
                customer = json.loads(customer)
            except:
                customer = {}
        if isinstance(customer, list):
            customer = customer[0] if customer else {}
        
        name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
        if name not in customer_list and name != 'Unknown':
            customer_list[name] = {
                'name': name,
                'email': customer.get('email', '') if isinstance(customer, dict) else '',
                'phone': customer.get('phone', '') if isinstance(customer, dict) else '',
                'orders': 0,
                'total_spent': 0
            }
        if name in customer_list:
            customer_list[name]['orders'] += 1
            customer_list[name]['total_spent'] += order.get('total', 0)
    
    customers = list(customer_list.values())
    customers.sort(key=lambda x: x['orders'], reverse=True)
    
    return render_template('pos.html',
        products=products,
        customers=customers,
        DB_CONNECTED=CONNECTION_OK
    )

@app.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        if not data or not data.get('items'):
            return jsonify({'success': False, 'message': 'No items in order'}), 400
        
        order_id = f"POS-{uuid.uuid4().hex[:8].upper()}"
        
        order_data = {
            'order_id': order_id,
            'items': data.get('items', []),
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
        
        # Save to Supabase
        import json as json_module
        supabase_order = {
            'order_id': order_data.get('order_id'),
            'items': json_module.dumps(order_data.get('items', [])),
            'subtotal': order_data.get('subtotal', 0),
            'shipping': order_data.get('shipping', 0),
            'total': order_data.get('total', 0),
            'status': order_data.get('status', 'confirmed'),
            'source': order_data.get('source', 'pos'),
            'created_at': order_data.get('created_at', datetime.utcnow().isoformat()),
            'customer': json_module.dumps(order_data.get('customer', {}))
        }
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/orders",
            headers=SUPABASE_HEADERS,
            json=supabase_order,
            timeout=10
        )
        
        if response.status_code not in [200, 201, 204]:
            return jsonify({'success': False, 'message': 'Failed to save order'}), 500
        
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
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        analytics = get_sales_analytics()
        return jsonify(analytics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/revenue')
def admin_api_revenue():
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

@app.route('/admin/upload-image', methods=['POST'])
def upload_image():
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
        return jsonify({'success': False, 'message': 'Invalid file type'}), 400

@app.route('/admin/products', methods=['POST'])
def admin_products():
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
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=SUPABASE_HEADERS,
            json=product_data,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            return jsonify({'success': True, 'message': 'Product saved successfully!', 'product': product_data})
        else:
            return jsonify({'success': False, 'message': 'Error saving product'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/products/<product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        response = requests.delete(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=SUPABASE_HEADERS,
            timeout=5
        )
        if response.status_code in [200, 204]:
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Failed to delete'})
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
        
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
            headers=SUPABASE_HEADERS,
            json={'status': new_status},
            timeout=5
        )
        
        if response.status_code in [200, 204]:
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Failed to update status'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ================================================================
# ===== DEBUG ROUTES =====
# ================================================================

@app.route('/debug')
def debug():
    """Check data in Supabase"""
    try:
        orders = load_orders()
        products = load_products()
        return jsonify({
            'orders_count': len(orders),
            'products_count': len(products),
            'sample_order': orders[0] if orders else None,
            'sample_product': products[0] if products else None,
            'is_vercel': IS_VERCEL,
            'connection_ok': CONNECTION_OK,
            'supabase_url': SUPABASE_URL
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/test-data')
def test_data():
    """Test data loading"""
    try:
        orders = load_orders()
        products = load_products()
        analytics = get_sales_analytics()
        
        return jsonify({
            'success': True,
            'orders_count': len(orders),
            'products_count': len(products),
            'revenue': analytics.get('total_revenue', 0),
            'customers': analytics.get('total_customers', 0),
            'sample_order': orders[0] if orders else None
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/raw-orders')
def raw_orders():
    """Show raw orders from Supabase"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/orders?select=*&limit=10",
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            return jsonify({
                'count': len(response.json()),
                'orders': response.json()
            })
        return jsonify({'error': f'Status: {response.status_code}'})
    except Exception as e:
        return jsonify({'error': str(e)})

# ================================================================
# ===== RUN APP =====
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("📱 PRICE POINT - Premium Electronics Shop")
    print("="*60)
    print(f"🌍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    print(f"🔗 Supabase Connection: {'✅ OK' if CONNECTION_OK else '❌ FAILED'}")
    
    # Test data loading
    orders = load_orders()
    products = load_products()
    print(f"\n📊 Products: {len(products) if products else 0}")
    print(f"📊 Orders: {len(orders) if orders else 0}")
    print("="*60)
    
    print("\n🚀 Starting server...")
    print("📍 http://localhost:5000")
    print("🔑 Login: admin / electronics2026")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
