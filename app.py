from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from datetime import datetime, timedelta
import os
import uuid
import json
import requests
import traceback
from werkzeug.utils import secure_filename

app = Flask(__name__)
application = app
app.secret_key = 'allison-electronics-secret-2026'
app.permanent_session_lifetime = timedelta(days=7)

# ================================================================
# ===== CONFIGURATION =====
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
except:
    UPLOAD_FOLDER = '/tmp/static/uploads'
    STATIC_FOLDER = '/tmp/static'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(STATIC_FOLDER, exist_ok=True)

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
# ===== DATA LOADING - WORKS ON BOTH LOCAL AND VERCEL =====
# ================================================================

def load_orders():
    """Load orders - Supabase on Vercel, JSON on local"""
    
    # On Vercel: ALWAYS use Supabase
    if IS_VERCEL:
        try:
            print("📤 Vercel: Loading orders from Supabase...")
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/orders?select=*&order=created_at.desc",
                headers=SUPABASE_HEADERS,
                timeout=10
            )
            if response.status_code == 200:
                orders = response.json()
                if isinstance(orders, list):
                    print(f"✅ Loaded {len(orders)} orders from Supabase")
                    return orders
            print(f"⚠️ Supabase returned: {response.status_code}")
            return []
        except Exception as e:
            print(f"❌ Error loading orders: {e}")
            return []
    
    # Local: Load from JSON
    try:
        if os.path.exists('orders.json'):
            with open('orders.json', 'r') as f:
                orders = json.load(f)
                if orders and isinstance(orders, list):
                    print(f"✅ Loaded {len(orders)} orders from JSON")
                    return orders
        return []
    except Exception as e:
        print(f"❌ Error loading orders: {e}")
        return []

def load_products():
    """Load products - Supabase on Vercel, JSON on local"""
    
    # On Vercel: ALWAYS use Supabase
    if IS_VERCEL:
        try:
            print("📤 Vercel: Loading products from Supabase...")
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/products?select=*",
                headers=SUPABASE_HEADERS,
                timeout=5
            )
            if response.status_code == 200:
                products = response.json()
                if isinstance(products, list):
                    print(f"✅ Loaded {len(products)} products from Supabase")
                    return products
            return []
        except Exception as e:
            print(f"❌ Error loading products: {e}")
            return []
    
    # Local: Load from JSON
    try:
        if os.path.exists('products.json'):
            with open('products.json', 'r') as f:
                products = json.load(f)
                if products and isinstance(products, list):
                    print(f"✅ Loaded {len(products)} products from JSON")
                    return products
        # Create sample products
        products = [
            {"id": "1", "name": "iPhone 15 Pro Max", "price": 150000, "cost_price": 120000, "image": "", "category": "Phones", "description": "Latest iPhone", "rating": 4.8, "reviews": 120, "badge": "Best Seller", "stock": 50, "original_price": 165000, "specs": []},
            {"id": "2", "name": "MacBook Pro M3", "price": 250000, "cost_price": 200000, "image": "", "category": "Laptops", "description": "Powerful laptop", "rating": 4.9, "reviews": 85, "badge": "New", "stock": 30, "original_price": 280000, "specs": []}
        ]
        with open('products.json', 'w') as f:
            json.dump(products, f, indent=2)
        return products
    except Exception as e:
        print(f"❌ Error loading products: {e}")
        return []

def load_bundles():
    """Load bundles"""
    try:
        if os.path.exists('bundles.json'):
            with open('bundles.json', 'r') as f:
                bundles = json.load(f)
                if bundles and isinstance(bundles, list):
                    return bundles
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

def get_sales_analytics():
    try:
        orders = load_orders()
        products = load_products()
        
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
        
        monthly_data = {}
        product_sales = {}
        customer_data = {}
        
        for order in orders:
            if order.get('status') == 'cancelled':
                continue
            
            customer = order.get('customer', {})
            if isinstance(customer, str):
                try:
                    customer = json.loads(customer)
                except:
                    customer = {}
            
            items = order.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except:
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
                if source == 'pos':
                    monthly_data[order_date]['pos_orders'] += 1
                else:
                    monthly_data[order_date]['web_orders'] += 1
            
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
        
        # Save to JSON (local only, Vercel saves to Supabase)
        if not IS_VERCEL:
            orders = load_orders()
            if not isinstance(orders, list):
                orders = []
            orders.insert(0, order_data)
            with open('orders.json', 'w') as f:
                json.dump(orders, f, indent=2)
        
        # Update stock
        for updated_product in products_to_update:
            if not IS_VERCEL:
                products = load_products()
                for p in products:
                    if str(p.get('id')) == str(updated_product.get('id')):
                        p['stock'] = updated_product.get('stock')
                        break
                with open('products.json', 'w') as f:
                    json.dump(products, f, indent=2)
        
        session['cart'] = {}
        session.modified = True
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'total': total,
            'message': 'Order placed successfully!'
        })
            
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
        'products': len(products),
        'orders': len(orders),
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'vercel' if IS_VERCEL else 'local',
        'mode': 'vercel' if IS_VERCEL else 'local'
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
            'db_mode': 'vercel' if IS_VERCEL else 'local'
        }
        
        return render_template('admin.html',
            products=products,
            bundles=bundles,
            orders=orders,
            customers=customers,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=IS_VERCEL
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
                'db_mode': 'vercel' if IS_VERCEL else 'local'
            },
            DB_CONNECTED=IS_VERCEL
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
        DB_CONNECTED=IS_VERCEL
    )

@app.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        order_id = f"POS-{uuid.uuid4().hex[:8].upper()}"
        
        # Update stock for products
        products = load_products()
        product_lookup = {str(p.get('id')): p for p in products}
        
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
        
        # On Vercel, update stock in memory only (Supabase will handle it)
        if not IS_VERCEL:
            save_json_file('products.json', products)
        
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
        
        # Save order
        if IS_VERCEL:
            # On Vercel, save to Supabase
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
            requests.post(
                f"{SUPABASE_URL}/rest/v1/orders",
                headers=SUPABASE_HEADERS,
                json=supabase_order,
                timeout=5
            )
        else:
            orders = load_orders()
            if not isinstance(orders, list):
                orders = []
            orders.insert(0, order_data)
            with open('orders.json', 'w') as f:
                json.dump(orders, f, indent=2)
        
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
    return jsonify(get_sales_analytics())

@app.route('/admin/api/revenue')
def admin_api_revenue():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    analytics = get_sales_analytics()
    return jsonify({
        'total_revenue': analytics.get('total_revenue', 0),
        'total_profit': analytics.get('total_profit', 0),
        'total_orders': analytics.get('total_orders', 0),
        'total_items_sold': analytics.get('total_items_sold', 0)
    })

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
        
        products = load_products()
        found = False
        for p in products:
            if str(p.get('id')) == str(product_data.get('id')):
                p.update(product_data)
                found = True
                break
        if not found:
            products.append(product_data)
        
        # On local, save to JSON
        if not IS_VERCEL:
            with open('products.json', 'w') as f:
                json.dump(products, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Product saved successfully!', 'product': product_data})
    except Exception as e:
        print(f"Error saving product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/products/<product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        products = load_products()
        products = [p for p in products if str(p.get('id')) != str(product_id)]
        if not IS_VERCEL:
            with open('products.json', 'w') as f:
                json.dump(products, f, indent=2)
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
        
        orders = load_orders()
        for order in orders:
            if order.get('order_id') == order_id:
                order['status'] = new_status
                break
        
        if not IS_VERCEL:
            with open('orders.json', 'w') as f:
                json.dump(orders, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/debug-data')
def debug_data():
    orders = load_orders()
    products = load_products()
    return jsonify({
        'orders_count': len(orders),
        'products_count': len(products),
        'sample_order': orders[0] if orders else None,
        'is_vercel': IS_VERCEL,
        'mode': 'vercel' if IS_VERCEL else 'local'
    })

# ================================================================
# ===== RUN APP =====
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("📱 PRICE POINT - Premium Electronics Shop")
    print("="*60)
    print(f"🌍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    print(f"📊 Mode: {'Supabase (Vercel)' if IS_VERCEL else 'JSON (Local)'}")
    
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
