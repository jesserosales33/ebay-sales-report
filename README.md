# eBay Sales Report Generator

A Streamlit app that generates comprehensive sales reports from your eBay account, combining data from the eBay Fulfillment and Finances APIs.

## Features

- 📊 Real-time sales data aggregation
- 💰 Automatic calculation of fees, taxes, and payouts
- 🔄 Auto-refreshing OAuth2 tokens (no re-authentication needed)
- 📥 Multi-item order support with accurate totals
- 🎯 Filterable by fulfillment status
- 📥 Export to CSV
- 📅 Customizable date range (1-365 days)

## Data Included

- Sale Amount (feeBasisAmount from all items)
- Shipping Cost
- Shipping Label Cost
- Total Fees (eBay fees + promotional/ad fees)
- Tax Collected
- Order details and fulfillment status

## Prerequisites

- Python 3.8+
- eBay Developer Account with API credentials
- Active eBay seller account

## Setup Instructions

### 1. Get eBay API Credentials

1. Go to [eBay Developer Portal](https://developer.ebay.com/)
2. Create an app in your Developer Account
3. Get your:
   - **Client ID**
   - **Client Secret**
   - **RuName (Redirect URI)**
4. Enable these scopes:
   - `https://api.ebay.com/oauth/api_scope/sell.fulfillment`
   - `https://api.ebay.com/oauth/api_scope/sell.finances`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
