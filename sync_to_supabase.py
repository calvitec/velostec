import requests
import json
from datetime import datetime

SUPABASE_URL = "https://hzqrdwerkgfmfaufabjr.supabase.co"
SUPABASE_KEY = "sb_publishable_tnBOmCO7EFfIoXfNjEH_Tg_D7WX-zld"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Load local data
with open('products.json', 'r') as f:
    products = json.load(f)

try:
    with open('orders.json', 'r') as f:
        orders = json.load(f)
        if not orders:
            print("⚠️ orders.json is empty!")
            orders = []
except:
    orders = []

print(f"📦 Found {len(products)} products and {len(orders)} orders to sync...")

# ===== SYNC PRODUCTS =====
synced_products = 0
for product in products:
    try:
        # Check if exists
        check = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{product.get('id')}",
            headers=headers,
            timeout=5
        )
        if check.status_code == 200 and check.json():
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{product.get('id')}",
                headers=headers,
                json=product,
                timeout=5
            )
        else:
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/products",
                headers=headers,
                json=product,
                timeout=5
            )
        if response.status_code in [200, 201, 204]:
            synced_products += 1
            print(f"✅ Synced product: {product.get('name')}")
        else:
            print(f"❌ Failed product: {product.get('name')} - {response.text}")
    except Exception as e:
        print(f"❌ Error syncing product {product.get('name')}: {e}")

print(f"✅ Synced {synced_products}/{len(products)} products")

# ===== SYNC ORDERS =====
if orders:
    synced_orders = 0
    for i, order in enumerate(orders):
        try:
            print(f"\n📝 Processing order {i+1}/{len(orders)}: {order.get('order_id', 'NO_ID')}")
            
            # Format for Supabase
            supabase_order = {
                'order_id': order.get('order_id'),
                'items': json.dumps(order.get('items', [])),
                'subtotal': order.get('subtotal', 0),
                'shipping': order.get('shipping', 0),
                'total': order.get('total', 0),
                'status': order.get('status', 'pending'),
                'source': order.get('source', 'web'),
                'created_at': order.get('created_at', datetime.utcnow().isoformat()),
                'customer': json.dumps(order.get('customer', {}))
            }
            
            # Check if exists
            check = requests.get(
                f"{SUPABASE_URL}/rest/v1/orders?order_id=eq.{supabase_order['order_id']}",
                headers=headers,
                timeout=5
            )
            
            if check.status_code == 200 and check.json():
                response = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/orders?order_id=eq.{supabase_order['order_id']}",
                    headers=headers,
                    json=supabase_order,
                    timeout=5
                )
                if response.status_code in [200, 204]:
                    synced_orders += 1
                    print(f"✅ Updated order: {supabase_order['order_id']}")
                else:
                    print(f"❌ Failed to update: {response.text}")
            else:
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/orders",
                    headers=headers,
                    json=supabase_order,
                    timeout=5
                )
                if response.status_code in [200, 201]:
                    synced_orders += 1
                    print(f"✅ Inserted order: {supabase_order['order_id']}")
                else:
                    print(f"❌ Failed to insert: {response.text}")
                    
        except Exception as e:
            print(f"❌ Error syncing order: {e}")
    
    print(f"\n✅ Synced {synced_orders}/{len(orders)} orders")
else:
    print("⚠️ No orders to sync")

# ===== CHECK RESULTS =====
print("\n" + "="*60)
print("📊 VERIFYING DATA IN SUPABASE")
print("="*60)

# Check products
response = requests.get(
    f"{SUPABASE_URL}/rest/v1/products?select=count",
    headers=headers
)
if response.status_code == 200:
    data = response.json()
    if isinstance(data, list):
        print(f"📦 Products in Supabase: {len(data)}")
    else:
        print(f"📦 Products in Supabase: {data}")

# Check orders
response = requests.get(
    f"{SUPABASE_URL}/rest/v1/orders?select=count",
    headers=headers
)
if response.status_code == 200:
    data = response.json()
    if isinstance(data, list):
        print(f"📦 Orders in Supabase: {len(data)}")
    else:
        print(f"📦 Orders in Supabase: {data}")

# Count customers
response = requests.get(
    f"{SUPABASE_URL}/rest/v1/orders?select=customer",
    headers=headers
)
if response.status_code == 200:
    orders_data = response.json()
    customers = set()
    for o in orders_data:
        customer = o.get('customer', {})
        if isinstance(customer, str):
            try:
                customer = json.loads(customer)
            except:
                customer = {}
        if customer.get('name'):
            customers.add(customer['name'])
    print(f"👥 Customers in Supabase: {len(customers)}")

print("="*60)
print("🎉 Sync complete!")
