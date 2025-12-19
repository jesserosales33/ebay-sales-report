import streamlit as st
import requests
import csv
from datetime import datetime, timedelta
import pandas as pd
import os
import json
import base64
import re
import time
import urllib.parse

# eBay credentials
CLIENT_ID = 'JesseRos-ExcelTes-PRD-26e40085e-763030ed'
CLIENT_SECRET = 'PRD-6e716ceec704-3a31-4c41-8ac0-3286'
REDIRECT_URI = 'Jesse_Rosales-JesseRos-ExcelT-zfumxhpu'
TOKEN_FILE = "ebay_tokens.json"

def load_tokens():
    """Load tokens from file"""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def save_tokens(tokens):
    """Save tokens to file"""
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)

def extract_code_from_url(url):
    """Extract authorization code from URL"""
    match = re.search(r'[?&]code=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def exchange_code_for_tokens(code):
    """Exchange authorization code for access and refresh tokens"""
    # URL decode the code
    code = urllib.parse.unquote(code)
    
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_credentials = base64.b64encode(credentials.encode()).decode()
    response = requests.post(
        'https://api.ebay.com/identity/v1/oauth2/token',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64_credentials}'
        },
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
    )
    if response.status_code == 200:
        tokens = response.json()
        tokens['expires_at'] = time.time() + tokens['expires_in'] - 60
        save_tokens(tokens)
        return tokens
    else:
        st.error(f"Status Code: {response.status_code}")
        st.error(f"Response: {response.text}")
        st.error(f"Code used: {code}")
        return None

def refresh_tokens(refresh_token):
    """Refresh the access token using refresh token"""
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_credentials = base64.b64encode(credentials.encode()).decode()
    response = requests.post(
        'https://api.ebay.com/identity/v1/oauth2/token',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64_credentials}'
        },
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    )
    if response.status_code == 200:
        tokens = response.json()
        tokens['expires_at'] = time.time() + tokens['expires_in'] - 60
        save_tokens(tokens)
        return tokens
    else:
        return None

def get_access_token(tokens):
    """Get valid access token, refresh if needed"""
    if not tokens:
        return None
    if time.time() > tokens['expires_at']:
        tokens = refresh_tokens(tokens['refresh_token'])
        if tokens:
            return tokens['access_token']
        else:
            return None
    return tokens['access_token']

def get_ebay_complete_sales_report(access_token, days_back=90):
    """
    Retrieves complete sales data combining Fulfillment and Finances APIs.
    """
    
    # Step 1: Get orders from Fulfillment API
    fulfillment_url = "https://api.ebay.com/sell/fulfillment/v1/order"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    fulfillment_params = {
        "limit": 200,
        "fieldGroups": "TAX_BREAKDOWN"
    }
    
    try:
        response = requests.get(fulfillment_url, headers=headers, params=fulfillment_params)
        response.raise_for_status()
        fulfillment_data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching Fulfillment API: {e}")
        return None
    
    # Create lookup dictionary from Fulfillment API
    fulfillment_lookup = {}
    if "orders" in fulfillment_data:
        for order in fulfillment_data["orders"]:
            order_id = order.get("orderId", "N/A")
            
            pricing = order.get("pricingSummary", {})
            delivery_cost = pricing.get("deliveryCost", {}).get("value", "0")
            
            # Get fulfillment status - using orderFulfillmentStatus
            fulfillment_status = order.get("orderFulfillmentStatus", "N/A")
            
            item_titles = []
            for line_item in order.get("lineItems", []):
                title = line_item.get("title", "N/A")
                item_titles.append(title)
            
            fulfillment_lookup[order_id] = {
                "shipping_cost": delivery_cost,
                "item_titles": item_titles,
                "fulfillment_status": fulfillment_status
            }
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    start_date_str = start_date.strftime('%Y-%m-%dT00:00:01.000Z')
    end_date_str = end_date.strftime('%Y-%m-%dT23:59:59.000Z')
    
    label_start_date = start_date - timedelta(days=1)
    label_end_date = end_date + timedelta(days=7)
    label_start_date_str = label_start_date.strftime('%Y-%m-%dT00:00:01.000Z')
    label_end_date_str = label_end_date.strftime('%Y-%m-%dT23:59:59.000Z')
    
    finances_url = "https://apiz.ebay.com/sell/finances/v1/transaction"
    
    # Step 2: Get shipping label costs
    shipping_label_lookup = {}
    shipping_label_params = {
        "limit": 1000,
        "filter": [
            f"transactionType:{{SHIPPING_LABEL}}",
            f"transactionDate:[{label_start_date_str}..{label_end_date_str}]"
        ]
    }
    
    try:
        response = requests.get(finances_url, headers=headers, params=shipping_label_params)
        response.raise_for_status()
        shipping_label_data = response.json()
        
        if "transactions" in shipping_label_data:
            for transaction in shipping_label_data["transactions"]:
                order_id = transaction.get("orderId")
                label_amount = transaction.get("amount", {}).get("value", "0")
                if order_id:
                    shipping_label_lookup[order_id] = label_amount
                    
    except requests.exceptions.RequestException as e:
        pass
    
    # Step 3: Get sales transactions
    sales_params = {
        "limit": 1000,
        "filter": [
            f"transactionType:{{SALE}}",
            f"transactionDate:[{start_date_str}..{end_date_str}]"
        ]
    }
    
    try:
        response = requests.get(finances_url, headers=headers, params=sales_params)
        response.raise_for_status()
        finances_data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching Finances API: {e}")
        return None
    
    # Step 4: Get promotional fees
    promo_fee_lookup = {}
    promo_params = {
        "limit": 1000,
        "filter": f"transactionType:{{NON_SALE_CHARGE}}"
    }
    
    try:
        response = requests.get(finances_url, headers=headers, params=promo_params)
        response.raise_for_status()
        promo_data = response.json()
        
        if "transactions" in promo_data:
            for transaction in promo_data["transactions"]:
                if transaction.get("feeType") == "AD_FEE":
                    references = transaction.get("references", [])
                    promo_amount = transaction.get("amount", {}).get("value", "0")
                    
                    for ref in references:
                        if ref.get("referenceType") == "ORDER_ID":
                            order_id = ref.get("referenceId")
                            if order_id:
                                promo_fee_lookup[order_id] = promo_amount
                                break
    except requests.exceptions.RequestException as e:
        pass
    
    # Step 5: Combine data
    combined_sales = []
    
    if "transactions" in finances_data:
        for transaction in finances_data["transactions"]:
            order_id = transaction.get("orderId", "N/A")
            transaction_date = transaction.get("transactionDate", "N/A")
            
            total_fees = transaction.get("totalFeeAmount", {}).get("value", "0")
            # Get ebayCollectedTaxAmount
            tax_amount = transaction.get("ebayCollectedTaxAmount", {}).get("value", "0")
            
            # Get feeBasisAmount from orderLineItems - sum all items
            sale_amount = 0
            order_line_items = transaction.get("orderLineItems", [])
            if order_line_items:
                for line_item in order_line_items:
                    item_amount = float(line_item.get("feeBasisAmount", {}).get("value", "0"))
                    sale_amount += item_amount
            
            fulfillment_info = fulfillment_lookup.get(order_id, {})
            item_titles = fulfillment_info.get("item_titles", ["N/A"])
            shipping_cost = fulfillment_info.get("shipping_cost", "0")
            fulfillment_status = fulfillment_info.get("fulfillment_status", "N/A")
            
            shipping_label_cost = shipping_label_lookup.get(order_id, "0")
            promo_fee = promo_fee_lookup.get(order_id, "0")
            
            item_title = ", ".join(item_titles) if item_titles else "N/A"
            
            combined_sales.append({
                "Date Sold": transaction_date,
                "Order ID": order_id,
                "Item Title": item_title,
                "Fulfillment Status": fulfillment_status,
                "Sale Amount": float(sale_amount),
                "Shipping Cost": float(shipping_cost),
                "Shipping Label Cost": float(shipping_label_cost),
                "Total Fees": float(total_fees) + float(promo_fee),
                "Tax Collected": float(tax_amount)
            })
    
    return combined_sales

# Streamlit UI
st.set_page_config(page_title="eBay Sales Report", layout="wide")
st.title("📊 eBay Sales Report Generator")

st.markdown("---")

# Sidebar for inputs
st.sidebar.header("Settings")

# Load tokens
tokens = load_tokens()

# Check if we need to authenticate
if not tokens:
    st.sidebar.warning("⚠️ Authentication Required")
    st.sidebar.markdown("**Step 1:** Click the link below to authorize:")
    auth_url = f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=https://api.ebay.com/oauth/api_scope/sell.fulfillment https://api.ebay.com/oauth/api_scope/sell.finances"
    st.sidebar.markdown(f"[Authorize eBay Access]({auth_url})")
    
    st.sidebar.markdown("**Step 2:** Paste the full redirect URL here:")
    redirect_url = st.sidebar.text_input("Redirect URL", type="password")
    
    if redirect_url:
        code = extract_code_from_url(redirect_url)
        if code:
            with st.spinner("Authenticating..."):
                tokens = exchange_code_for_tokens(code)
            if tokens:
                st.sidebar.success("✓ Authenticated successfully!")
                st.rerun()
            else:
                st.sidebar.error("Failed to authenticate. Check error messages above.")
        else:
            st.sidebar.error("Could not find authorization code in URL.")
else:
    # Show token status
    st.sidebar.success("✓ Authenticated")
    
    # Get valid access token (will refresh if needed)
    access_token = get_access_token(tokens)
    
    if not access_token:
        st.sidebar.error("Token refresh failed. Please re-authenticate.")
        if st.sidebar.button("Re-authenticate"):
            os.remove(TOKEN_FILE)
            st.rerun()
    else:
        # Show time until token expires
        expires_at = tokens.get('expires_at', 0)
        time_remaining = expires_at - time.time()
        hours_remaining = int(time_remaining / 3600)
        st.sidebar.caption(f"Token expires in {hours_remaining}h")
        
        days_back = st.sidebar.slider("Days to look back", min_value=1, max_value=365, value=90)
        
        # Initialize session state for report data
        if "report_data" not in st.session_state:
            st.session_state.report_data = None
        
        # Main area
        if st.button("Generate Report", key="generate"):
            with st.spinner("Fetching data from eBay..."):
                sales_data = get_ebay_complete_sales_report(access_token, days_back)
            
            if sales_data:
                st.session_state.report_data = sales_data
        
        # Display report if data exists
        if st.session_state.report_data:
            df = pd.DataFrame(st.session_state.report_data)
            
            # Format date column to mm/dd/yyyy
            df['Date Sold'] = pd.to_datetime(df['Date Sold']).dt.strftime('%m/%d/%Y')
            
            # Reorder columns
            df = df[['Date Sold', 'Order ID', 'Item Title', 'Fulfillment Status', 'Sale Amount', 'Shipping Cost', 'Shipping Label Cost', 'Total Fees', 'Tax Collected']]
            
            # Get fulfillment statuses for filter
            fulfillment_statuses = sorted(df['Fulfillment Status'].unique())
            
            # Add filter to sidebar
            st.sidebar.markdown("---")
            st.sidebar.header("Filters")
            selected_status = st.sidebar.multiselect(
                "Fulfillment Status",
                options=fulfillment_statuses,
                default=fulfillment_statuses
            )
            
            # Apply filter
            filtered_df = df[df['Fulfillment Status'].isin(selected_status)]
            
            # Calculate totals on filtered data
            total_sales = filtered_df['Sale Amount'].sum()
            total_fees = filtered_df['Total Fees'].sum()
            total_tax = filtered_df['Tax Collected'].sum()
            total_shipping_labels = filtered_df['Shipping Label Cost'].sum()
            total_payout = total_sales - total_fees - total_shipping_labels
            
            # Display metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Sales", f"${total_sales:.2f}")
            with col2:
                st.metric("Total Fees", f"${total_fees:.2f}")
            with col3:
                st.metric("Shipping Labels", f"${total_shipping_labels:.2f}")
            with col4:
                st.metric("Tax Collected", f"${total_tax:.2f}")
            with col5:
                st.metric("💰 Total Seller Payout", f"${total_payout:.2f}")
            
            st.markdown("---")
            
            # Display table
            st.subheader("Sales Data")
            st.dataframe(filtered_df, use_container_width=True)
            
            # Download CSV
            csv = filtered_df.to_csv(index=False)
            filename = f"ebay_sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=filename,
                mime="text/csv"
            )

st.markdown("---")
st.markdown("*eBay Sales Report Generator - Data pulled from Finances and Fulfillment APIs*")