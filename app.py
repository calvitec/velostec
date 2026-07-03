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

# ===== TEMPLATE FILTERS =====
@app.template_filter('format_number')
def format_number_filter(value):
    """Format number with commas"""
    try:
        if value is None:
            return "0"
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return "0"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================================================================
# ===== SUPABASE CONFIG =====
# ================================================================

SUPABASE_URL = "https://hzqrdwerkgfmfaufabjr.supabase.co"
SUPABASE_KEY = "sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ================================================================
# ===== ERROR HANDLERS =====
# ================================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/admin/') or request.path.startswith('/api/'):
        return jsonify({'error': 'Not found', 'message': 'The requested endpoint does not exist'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/admin/') or request.path.startswith('/api/'):
        return jsonify({'error': 'Server error', 'message': 'Something went wrong'}), 500
    return render_template('500.html'), 500

# ================================================================
# ===== DATA FUNCTIONS =====
# ================================================================

def load_orders():
    """Load orders from Supabase"""
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/orders?select=*&order=created_at.desc",
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for order in data:
                    # Parse customer field
                    if isinstance(order.get('customer'), str):
                        try:
                            order['customer'] = json.loads(order['customer'])
                        except:
                            order['customer'] = {}
                    elif isinstance(order.get('customer'), list):
                        order['customer'] = order['customer'][0] if order['customer'] else {}
                    
                    # Parse items field
                    if isinstance(order.get('items'), str):
                        try:
                            order['items'] = json.loads(order['items'])
                        except:
                            order['items'] = []
                    
                    # Ensure proper types
                    if not isinstance(order.get('customer'), dict):
                        order['customer'] = {}
                    if not isinstance(order.get('items'), list):
                        order['items'] = []
                    if order.get('total') is None:
                        order['total'] = 0
                    if order.get('subtotal') is None:
                        order['subtotal'] = 0
                
                return data
        return []
    except Exception as e:
        print(f"Error loading orders: {e}")
        return []

def load_products():
    """Load products from Supabase"""
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=*",
            headers=SUPABASE_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # Ensure all products have required fields
                for product in data:
                    if product.get('price') is None:
                        product['price'] = 0
                    if product.get('stock') is None:
                        product['stock'] = 0
                    if product.get('cost_price') is None:
                        product['cost_price'] = 0
                return data
        return []
    except Exception as e:
        print(f"Error loading products: {e}")
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

def save_order_to_supabase(order_data):
    """Save order to Supabase"""
    try:
        supabase_order = {
            'order_id': order_data.get('order_id'),
            'items': json.dumps(order_data.get('items', [])),
            'subtotal': float(order_data.get('subtotal', 0)),
            'shipping': float(order_data.get('shipping', 0)),
            'total': float(order_data.get('total', 0)),
            'status': order_data.get('status', 'pending'),
            'source': order_data.get('source', 'web'),
            'created_at': order_data.get('created_at', datetime.utcnow().isoformat()),
            'customer': json.dumps(order_data.get('customer', {}))
        }
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/orders",
            headers=SUPABASE_HEADERS,
            json=supabase_order,
            timeout=10
        )
        return response.status_code in [200, 201, 204]
    except Exception as e:
        print(f"Error saving order: {e}")
        return False

def update_product_stock(product_id, new_stock):
    """Update product stock in Supabase"""
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=SUPABASE_HEADERS,
            json={'stock': int(new_stock)},
            timeout=5
        )
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"Error updating stock: {e}")
        return False

def get_cart():
    """Get cart from session with proper initialization"""
    try:
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
    except Exception as e:
        print(f"Error getting cart: {e}")
        return {}

# ================================================================
# ===== ANALYTICS =====
# ================================================================

def get_sales_analytics():
    """Calculate revenue, profit, and sales analytics"""
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
        customer_data = {}
        monthly_data = {}
        product_sales = {}
        
        for order in orders:
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
            
            # Customer tracking
            customer_name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
            if customer_name != 'Unknown':
                if customer_name not in customer_data:
                    customer_data[customer_name] = {
                        'name': customer_name,
                        'email': customer.get('email', ''),
                        'phone': customer.get('phone', ''),
                        'orders': 0,
                        'total_spent': 0
                    }
                customer_data[customer_name]['orders'] += 1
                customer_data[customer_name]['total_spent'] += float(order.get('total', 0))
            
            # Monthly tracking
            created_at = order.get('created_at', '')
            month = created_at[:7] if created_at else datetime.utcnow().strftime('%Y-%m')
            if month not in monthly_data:
                monthly_data[month] = {
                    'orders': 0,
                    'items': 0,
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0
                }
            monthly_data[month]['orders'] += 1
            
            for item in items:
                product_id = str(item.get('product_id', ''))
                quantity = int(item.get('quantity', 1))
                price = float(item.get('price', 0))
                item_total = float(item.get('total', price * quantity))
                
                product = product_lookup.get(product_id, {})
                cost_price = float(product.get('cost_price', 0)) if product else 0
                item_cost = cost_price * quantity
                
                total_revenue += item_total
                total_cost += item_cost
                total_profit += (item_total - item_cost)
                total_items_sold += quantity
                
                # Monthly data
                monthly_data[month]['items'] += quantity
                monthly_data[month]['revenue'] += item_total
                monthly_data[month]['cost'] += item_cost
                monthly_data[month]['profit'] += (item_total - item_cost)
                
                # Product sales
                product_name = item.get('name', 'Unknown Product')
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
            'product_sales': product_sales,
            'customer_data': customer_data
        }
    except Exception as e:
        print(f"Error in analytics: {e}")
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
    try:
        cart = get_cart()
        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        bundles = load_bundles()
        
        # Create lookups
        product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}
        bundle_lookup = {str(b.get('id')): b for b in bundles if b and b.get('id')}
        
        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            
            # Check if it's a product
            product = product_lookup.get(str(item_id))
            if product:
                price = float(product.get('price', 0))
                item_total = price * quantity
                cart_items.append({
                    'id': str(item_id),
                    'name': str(product.get('name', 'Product')),
                    'price': price,
                    'image': str(product.get('image', '')),
                    'type': 'product',
                    'quantity': quantity,
                    'item_total': item_total,
                    'stock': int(product.get('stock', 0)),
                    'description': str(product.get('description', '')),
                    'specs': product.get('specs', [])
                })
                subtotal += item_total
                total_items += quantity
                continue
            
            # Check if it's a bundle
            bundle = bundle_lookup.get(str(item_id))
            if bundle:
                price = float(bundle.get('price', 0))
                item_total = price * quantity
                cart_items.append({
                    'id': str(item_id),
                    'name': str(bundle.get('name', 'Bundle')),
                    'price': price,
                    'image': str(bundle.get('image', '')),
                    'type': 'bundle',
                    'quantity': quantity,
                    'item_total': item_total,
                    'products': bundle.get('products', [])
                })
                subtotal += item_total
                total_items += quantity
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        return render_template('cart.html',
            cart_items=cart_items,
            subtotal=subtotal,
            shipping=shipping,
            total=total,
            total_items=total_items
        )
    except Exception as e:
        print(f"Cart error: {e}")
        traceback.print_exc()
        flash('Error loading cart', 'danger')
        return redirect(url_for('index'))

@app.route('/add-to-cart/<item_id>', methods=['POST'])
def add_to_cart(item_id):
    """Add item to cart - returns JSON"""
    try:
        cart = get_cart()
        products = load_products()
        bundles = load_bundles()
        
        # Check if product exists
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
        
        # Check if bundle exists
        bundle_exists = False
        for b in bundles:
            if str(b.get('id')) == str(item_id):
                bundle_exists = True
                break
        
        if not product and not bundle_exists:
            return jsonify({
                'success': False, 
                'message': 'Item not found'
            })
        
        # Add to cart
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
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/update-cart/<item_id>/<action>', methods=['POST'])
def update_cart_item(item_id, action):
    """Update cart item - returns JSON"""
    try:
        cart = get_cart()
        products = load_products()
        bundles = load_bundles()
        
        # Create lookups
        product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}
        bundle_lookup = {str(b.get('id')): b for b in bundles if b and b.get('id')}
        
        if action == 'increase':
            product = product_lookup.get(str(item_id))
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
        
        # Recalculate totals
        subtotal = 0
        for iid, qty in cart.items():
            product = product_lookup.get(str(iid))
            if product:
                subtotal += float(product.get('price', 0)) * qty
            else:
                bundle = bundle_lookup.get(str(iid))
                if bundle:
                    subtotal += float(bundle.get('price', 0)) * qty
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        # Get item price for response
        item_price = 0
        product = product_lookup.get(str(item_id))
        if product:
            item_price = float(product.get('price', 0))
        else:
            bundle = bundle_lookup.get(str(item_id))
            if bundle:
                item_price = float(bundle.get('price', 0))
        
        return jsonify({
            'success': True,
            'quantity': cart.get(item_id, 0) if item_id in cart else 0,
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'total_items': sum(cart.values()),
            'item_total': item_price * cart.get(item_id, 0) if item_id in cart else 0
        })
    except Exception as e:
        print(f"Error updating cart: {e}")
        traceback.print_exc()
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
    try:
        cart = get_cart()
        if not cart:
            flash('Your cart is empty', 'warning')
            return redirect(url_for('index'))
        
        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        bundles = load_bundles()
        
        product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}
        bundle_lookup = {str(b.get('id')): b for b in bundles if b and b.get('id')}
        
        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            
            product = product_lookup.get(str(item_id))
            if product:
                price = float(product.get('price', 0))
                item_total = price * quantity
                cart_items.append({
                    'id': item_id,
                    'name': product.get('name', 'Product'),
                    'price': price,
                    'image': product.get('image', ''),
                    'type': 'product',
                    'quantity': quantity,
                    'item_total': item_total
                })
                subtotal += item_total
                total_items += quantity
                continue
            
            bundle = bundle_lookup.get(str(item_id))
            if bundle:
                price = float(bundle.get('price', 0))
                item_total = price * quantity
                cart_items.append({
                    'id': item_id,
                    'name': bundle.get('name', 'Bundle'),
                    'price': price,
                    'image': bundle.get('image', ''),
                    'type': 'bundle',
                    'quantity': quantity,
                    'item_total': item_total
                })
                subtotal += item_total
                total_items += quantity
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        return render_template('checkout.html',
            cart_items=cart_items,
            subtotal=subtotal,
            shipping=shipping,
            total=total,
            total_items=total_items
        )
    except Exception as e:
        print(f"Checkout error: {e}")
        traceback.print_exc()
        flash('Error loading checkout', 'danger')
        return redirect(url_for('index'))

@app.route('/place-order', methods=['POST'])
def place_order():
    try:
        cart = get_cart()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty'})
        
        # Get data from form or JSON
        if request.is_json:
            data = request.get_json()
        else:
            data = {
                'customer_name': request.form.get('customer_name', 'Customer'),
                'customer_email': request.form.get('customer_email', 'customer@example.com'),
                'customer_phone': request.form.get('customer_phone', 'N/A'),
                'customer_address': request.form.get('customer_address', 'N/A')
            }
        
        # Validate customer name
        if not data.get('customer_name') or data.get('customer_name') == 'Customer':
            return jsonify({'success': False, 'message': 'Please enter your name'}), 400
        
        subtotal = 0
        products = load_products()
        bundles = load_bundles()
        product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}
        bundle_lookup = {str(b.get('id')): b for b in bundles if b and b.get('id')}
        order_items = []
        
        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
                
            product = product_lookup.get(str(item_id))
            if product:
                current_stock = int(product.get('stock', 0))
                if current_stock < quantity:
                    return jsonify({
                        'success': False,
                        'message': f'Not enough stock for {product.get("name")}. Available: {current_stock}'
                    }), 400
                
                price = float(product.get('price', 0))
                item_total = price * quantity
                subtotal += item_total
                order_items.append({
                    'product_id': item_id,
                    'name': product.get('name', 'Product'),
                    'price': price,
                    'quantity': quantity,
                    'total': item_total,
                    'type': 'product'
                })
                
                # Update stock
                new_stock = max(0, current_stock - quantity)
                update_product_stock(item_id, new_stock)
                continue
            
            bundle = bundle_lookup.get(str(item_id))
            if bundle:
                price = float(bundle.get('price', 0))
                item_total = price * quantity
                subtotal += item_total
                order_items.append({
                    'product_id': item_id,
                    'name': bundle.get('name', 'Bundle'),
                    'price': price,
                    'quantity': quantity,
                    'total': item_total,
                    'type': 'bundle'
                })
        
        if not order_items:
            return jsonify({'success': False, 'message': 'No valid items in cart'}), 400
        
        shipping = 0 if subtotal >= 50000 else 800
        total = subtotal + shipping
        
        order_id = f"ELEC-{uuid.uuid4().hex[:8].upper()}"
        
        customer_name = data.get('customer_name', 'Customer').strip()
        customer_email = data.get('customer_email', 'customer@example.com').strip()
        customer_phone = data.get('customer_phone', 'N/A').strip()
        customer_address = data.get('customer_address', 'N/A').strip()
        
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
        
        if save_order_to_supabase(order_data):
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
        print(f"Error placing order: {e}")
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
    try:
        orders = load_orders()
        products = load_products()
        return jsonify({
            'success': True,
            'products': len(products),
            'orders': len(orders),
            'timestamp': datetime.utcnow().isoformat(),
            'environment': 'vercel' if IS_VERCEL else 'local'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/products')
def api_products():
    try:
        return jsonify(load_products())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/products/<product_id>')
def api_product_detail(product_id):
    """Get single product by ID"""
    try:
        products = load_products()
        for p in products:
            if str(p.get('id')) == str(product_id):
                return jsonify(p)
        return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders')
def api_orders():
    try:
        return jsonify(load_orders())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/orders/<order_id>')
def api_order_detail(order_id):
    """Get single order by ID"""
    try:
        orders = load_orders()
        for o in orders:
            if str(o.get('order_id')) == str(order_id):
                return jsonify(o)
        return jsonify({'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cart-count', methods=['GET'])
def cart_count():
    try:
        cart = get_cart()
        count = sum(cart.values()) if cart and isinstance(cart, dict) else 0
        return jsonify({'count': count})
    except Exception as e:
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
        
        # Build customer list
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
            if not isinstance(customer, dict):
                customer = {}
            
            source = order.get('source', 'web')
            if source == 'pos':
                pos_count += 1
            else:
                web_count += 1
            
            name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
            if name and name != 'Unknown':
                if name not in customer_list:
                    customer_list[name] = {
                        'name': name,
                        'email': customer.get('email', '') if isinstance(customer, dict) else '',
                        'phone': customer.get('phone', '') if isinstance(customer, dict) else '',
                        'orders': 0,
                        'total_spent': 0
                    }
                customer_list[name]['orders'] += 1
                customer_list[name]['total_spent'] += float(order.get('total', 0))
        
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
            'db_mode': 'online'
        }
        
        return render_template('admin.html',
            products=products,
            bundles=bundles,
            orders=orders,
            customers=customers,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=True
        )
        
    except Exception as e:
        print(f"Admin dashboard error: {e}")
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
        if not isinstance(customer, dict):
            customer = {}
        
        name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
        if name and name != 'Unknown':
            if name not in customer_list:
                customer_list[name] = {
                    'name': name,
                    'email': customer.get('email', '') if isinstance(customer, dict) else '',
                    'phone': customer.get('phone', '') if isinstance(customer, dict) else '',
                    'orders': 0,
                    'total_spent': 0
                }
            customer_list[name]['orders'] += 1
            customer_list[name]['total_spent'] += float(order.get('total', 0))
    
    customers = list(customer_list.values())
    customers.sort(key=lambda x: x['orders'], reverse=True)
    
    return render_template('pos.html',
        products=products,
        customers=customers,
        DB_CONNECTED=True
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
        
        # Update stock for products
        products = load_products()
        product_lookup = {str(p.get('id')): p for p in products}
        
        for item in data.get('items', []):
            product_id = str(item.get('product_id'))
            quantity = int(item.get('quantity', 1))
            product = product_lookup.get(product_id)
            if product:
                current_stock = int(product.get('stock', 0))
                if current_stock < quantity:
                    return jsonify({
                        'success': False,
                        'message': f'Not enough stock for {product.get("name")}. Available: {current_stock}'
                    }), 400
                new_stock = max(0, current_stock - quantity)
                update_product_stock(product_id, new_stock)
        
        order_data = {
            'order_id': order_id,
            'items': data.get('items', []),
            'subtotal': float(data.get('subtotal', 0)),
            'shipping': float(data.get('shipping', 0)),
            'total': float(data.get('total', 0)),
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
        
        if save_order_to_supabase(order_data):
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
        else:
            return jsonify({'success': False, 'message': 'Failed to save order'}), 500
            
    except Exception as e:
        print(f"POS Order error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/notifications')
def admin_api_notifications():
    """Get notifications for admin"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        orders = load_orders()
        pending = [o for o in orders if o.get('status') == 'pending']
        pending_count = len(pending)
        
        notifications = []
        if pending_count > 0:
            notifications.append({
                'icon': '📦',
                'title': f'{pending_count} pending orders',
                'time': 'Just now'
            })
        
        products = load_products()
        low_stock = [p for p in products if p.get('stock', 0) < 5]
        if low_stock:
            notifications.append({
                'icon': '⚠️',
                'title': f'{len(low_stock)} products low in stock',
                'time': 'Just now'
            })
        
        return jsonify({
            'count': len(notifications),
            'notifications': notifications
        })
    except Exception as e:
        return jsonify({'count': 0, 'notifications': []})

@app.route('/admin/api/top-products')
def admin_api_top_products():
    """Get top selling products"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        orders = load_orders()
        product_sales = {}
        
        for order in orders:
            if order.get('status') == 'cancelled':
                continue
            
            items = order.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except:
                    items = []
            if not isinstance(items, list):
                items = []
            
            for item in items:
                name = item.get('name', 'Unknown')
                revenue = float(item.get('total', 0))
                if name not in product_sales:
                    product_sales[name] = 0
                product_sales[name] += revenue
        
        sorted_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'products': [{'rank': i+1, 'name': name, 'revenue': revenue} for i, (name, revenue) in enumerate(sorted_products)]
        })
    except Exception as e:
        return jsonify({'products': []})

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

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Server is running',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/debug')
def debug():
    """Check data in Supabase"""
    try:
        orders = load_orders()
        products = load_products()
        bundles = load_bundles()
        
        customers = set()
        for order in orders:
            customer = order.get('customer', {})
            if isinstance(customer, str):
                try:
                    customer = json.loads(customer)
                except:
                    customer = {}
            if isinstance(customer, list):
                customer = customer[0] if customer else {}
            if isinstance(customer, dict):
                name = customer.get('name')
                if name:
                    customers.add(name)
        
        return jsonify({
            'orders_count': len(orders),
            'products_count': len(products),
            'bundles_count': len(bundles),
            'customers_count': len(customers),
            'sample_order': orders[0] if orders else None,
            'sample_product': products[0] if products else None,
            'is_vercel': IS_VERCEL
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

@app.route('/load-sample-data', methods=['GET', 'POST'])
def load_sample_data():
    """Load sample products into Supabase for testing"""
    try:
        sample_products = [
            {
                'id': 'iphone_15',
                'name': 'iPhone 15 Pro Max',
                'price': 245000.0,
                'cost_price': 180000.0,
                'category': 'Phones',
                'description': 'Latest Apple flagship with A17 Pro chip',
                'image': 'https://images.unsplash.com/photo-1592286927505-1def25e4c479?w=500',
                'stock': 15,
                'rating': 4.9,
                'reviews': 245,
                'badge': 'Best Seller'
            },
            {
                'id': 'macbook_pro',
                'name': 'MacBook Pro 16"',
                'price': 450000.0,
                'cost_price': 350000.0,
                'category': 'Laptops',
                'description': 'Professional laptop with M3 Max chip',
                'image': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500',
                'stock': 8,
                'rating': 4.8,
                'reviews': 156,
                'badge': 'New'
            },
            {
                'id': 'airpods_pro',
                'name': 'AirPods Pro 2',
                'price': 35000.0,
                'cost_price': 22000.0,
                'category': 'Accessories',
                'description': 'Premium wireless earbuds with ANC',
                'image': 'https://images.unsplash.com/photo-1606841838e0-bf1baf2dc3e9?w=500',
                'stock': 25,
                'rating': 4.7,
                'reviews': 389,
                'badge': 'Trending'
            },
            {
                'id': 'samsung_s24',
                'name': 'Samsung Galaxy S24 Ultra',
                'price': 165000.0,
                'cost_price': 115000.0,
                'category': 'Phones',
                'description': 'Flagship Android phone with advanced camera',
                'image': 'https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=500',
                'stock': 20,
                'rating': 4.6,
                'reviews': 234
            },
            {
                'id': 'ipad_pro',
                'name': 'iPad Pro 12.9"',
                'price': 185000.0,
                'cost_price': 140000.0,
                'category': 'Tablets',
                'description': 'Powerful tablet with M2 chip',
                'image': 'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=500',
                'stock': 12,
                'rating': 4.7,
                'reviews': 198,
                'badge': 'New'
            }
        ]
        
        added = 0
        errors = []
        
        for product in sample_products:
            try:
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/products",
                    headers=SUPABASE_HEADERS,
                    json=product,
                    timeout=5
                )
                if response.status_code in [200, 201]:
                    added += 1
                else:
                    errors.append(f"{product['name']}: {response.status_code}")
            except Exception as e:
                errors.append(f"{product['name']}: {str(e)}")
        
        return jsonify({
            'success': True,
            'added': added,
            'total': len(sample_products),
            'errors': errors,
            'message': f'Loaded {added}/{len(sample_products)} sample products'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/debug-products')
def debug_products():
    """Show all products with detailed info"""
    try:
        products = load_products()
        
        if not products:
            return jsonify({
                'success': False,
                'error': 'No products loaded',
                'message': 'Database may be empty. Try /load-sample-data'
            })
        
        product_list = []
        for p in products:
            product_list.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'price': p.get('price'),
                'stock': p.get('stock'),
                'category': p.get('category'),
                'has_image': bool(p.get('image'))
            })
        
        return jsonify({
            'success': True,
            'total_products': len(products),
            'products': product_list,
            'sample': products[0] if products else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ================================================================
# ===== RUN APP =====
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("📱 PRICE POINT - Premium Electronics Shop")
    print("="*60)
    print(f"🌍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    
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
