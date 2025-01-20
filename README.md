# Crypto Automation System
Welcome to my trading automation system! Designed specifically for traders with strategies developed in TradingView, this system streamlines the transition from manual to automated execution. By eliminating emotional bias, ensuring consistent execution, and maintaining constant connectivity, our system empowers you to optimize your trading strategies with greater efficiency and confidence—all while keeping your private keys secure and minimizing costs to less than $1 a month.

## Table of Contents
- [Crypto Automation System](#crypto-automation-system)
- [System Design](#system-design)
  - [TradingView](#tradingview)
  - [AWS Chalice](#aws-chalice)
  - [AWS DynamoDB](#aws-dynamodb)
  - [AWS Secrets Manager](#aws-secrets-manager)
- [Trade Execution](#trade-execution)
  - [Portfolio Allocation](#portfolio-allocation)
  - [Execution Strategies](#execution-strategies)
    - [Multi-Strategy Allocation](#multi-strategy-allocation)
    - [Buy-Side Boost](#buy-side-boost)
- [Usage](#usage)
  - [Allocation Split](#allocation-split)
  - [Increment Percent](#increment-percent)
  - [Execution Strategy](#execution-strategy)
  - [Important Guidelines](#important-guidelines)
- [Getting Started](#getting-started)
  - [AWS Account Setup & Configuration](#aws-account-setup--configuration)
  - [Clone the Repository & Install UV](#clone-the-repository--install-uv)
  - [Create DynamoDB Table](#create-dynamodb-table)
  - [Obtain & Store API Keys](#obtain--store-api-keys)
  - [User Configurations](#user-configurations)
  - [Deploy the System](#deploy-the-system)
  - [Perform Testing](#perform-testing)
  - [Configure TradingView Strategies](#configure-tradingview-strategies)
  
# System Design
So, how does it work? Our system seamlessly integrates four key components: TradingView, AWS Chalice, AWS DynamoDB, and AWS Secrets Manager.

## TradingView
- **Function**: Hosts your custom trading strategies, defining when to buy or sell an asset and specifying the trading timeframe. All strategies must operate on the same timeframe.
- **Alerts**: Sends custom payloads via webhooks to designated endpoints whenever an alert is triggered.

## AWS Chalice
- **Function**: Simplifies the development and deployment of our *REST API* and *Lambda Function*, handling the logic for processing and executing trade signals.
- **REST API**: Receives incoming trade signals from TradingView and stores them in DynamoDB. If the signal is a stop loss, the trade is executed immediately; otherwise, it is saved for further processing.
- **Lambda Function**: Executes trades based on signals stored in DynamoDB. It is triggered on the same timeframe as your TradingView strategy. For instance, if your strategy operates on an 8-hour timeframe, the Lambda function is invoked every 8 hours, 1 minute after the hour, to check for and act upon any trade signals.
- **Pricing**: Completely free; we stay comfortably within the AWS free tier limits, which allows for up to 1 million invocations per month at no cost.

## AWS DynamoDB
- **Function**: Serves as an intermediary database to store processed trades, enabling precise account allocation and advanced trade execution strategies, such as buy-side boost. Without this intermediary, we would be restricted to processing trade signals sequentially, which becomes a bottleneck when multiple signals occur simultaneously.
- **Pricing**: Completely free; we comfortably operate within DynamoDB's free tier limits, which provide up to 25 WCUs and RCUs per month at no cost.

## AWS Secrets Manager
- **Function**: Securely stores sensitive information, such as exchange API keys.
- **Pricing**: $0.30 per month per secret. This is the only paid service we use, and the investment in security is well worth it.

![trade_automation_system](img/trade_automation_system.png)

# Trade Execution
In this section, we’ll provide a detailed overview of how our system executes trades and allocates the correct percentage to each strategy, including the two key execution strategies: multi-strategy execution and buy-side boost. We’ll also cover important guidelines to ensure the system operates as intended.

Our system executes trades using **limit orders** because some exchange APIs don't support market orders, and maker fees are often significantly lower than taker fees. However, we make our limit orders behave like market orders by adjusting the order price based on the last traded price of the market, plus or minus a defined **increment percent**, depending on whether it's a buy or sell order. It's important to adjust this **increment percentage** according to your account value to ensure your limit orders function effectively as market orders.

## Portfolio Allocation
Our system automatically handles portfolio allocation to each strategy based on user-defined percentages set in the `strategy_config.json` file. 

**Important:** Configured percentages should not add up to more than 98%. We reserve 2% of the account to ensure there's always cash available for fees.

## Execution Strategies
There are two execution strategies available: Multi-Strategy Allocation and Buy-Side Boost.

### Multi-Strategy Allocation
This execution strategy ensures the defined percentage in `strategy_config.json` is used when executing on the strategy.

**How does it work?**
- When there are no active trades, it's fairly simple: We take the total account value in USD and multiply it by the specified percentage to determine the allocation for a given strategy.
- However, when you're already in a trade and need to allocate for the next trade signal, things get a bit more complex: But the idea remains the same—we calculate the total account value in USD and multiply it by the strategy's percentage.
- The challenge is that to accurately determine the account value, we first need to figure out how much USD was originally allocated to all active trades. This means calculating the account's value before factoring in any unrealized gains. This is handled in our function `get_total_usd()`.

This ensures that our system precisely allocates to each strategy as intended. 

### Buy-Side Boost
This advanced execution strategy is the most efficient way to allocate capital to multiple strategies. The idea is that instead of only using a portion of your account, you should use all of your account and reallocate as more trades are entered. 

To understand how this works, let's introduce a concept called **trade precedence**. Trade precedence is determined based on the incoming and active trades, meaning we reassess which trade has precedence every time a strategy is triggered to enter the market. The strategy with trade precedence receives the otherwise available capital of your account.

**Otherwise Available Capital** is calculated by summing the percentages in `strategy_config.json` assigned to strategies that are not currently active.

**Important:** Ensure that configured percentages are not the same so trade precedence can be correctly determined.

Let’s walk through an example to clarify this concept. Suppose we have defined the following allocation percentages for three strategies:
- BTC/USD: 0.2
- ETH/USD: 0.25
- SOL/USD: 0.5

Now suppose we have the following sequence of trades: 
1. BTC/USD Buy
2. ETH/USD Buy
3. BTC/USD Sell & ETH/USD Sell
4. BTC/USD Buy & SOL/USD Buy
5. BTC/USD Sell & SOL/USD Sell 

At step 1, since BTC/USD is the only incoming trade and we have no active trades, it receives trade precedence. Because BTC/USD has trade precedence, we allocate both the BTC/USD percentage and the Otherwise Available Capital percentage, which is 0.2 + 0.75 = 0.95. Therefore, we buy BTC/USD with 95% of our account value.

At step 2, we need to determine which trade has precedence between the incoming trade (ETH/USD) and the active trade (BTC/USD). Since ETH/USD has a higher allocation percentage than BTC/USD, it receives trade precedence. To adjust, we sell a portion of our BTC/USD position so that its allocation matches the defined percentage of 0.2.

After the sell, we allocate 0.25 to ETH/USD, plus the Otherwise Available Capital percentage, which is now 0.5. This means we purchase ETH/USD using 75% of our total account value. Our portfolio is now composed of 20% BTC and 75% ETH.

At step 3, we sell our entire BTC/USD and ETH/USD positions.

At step 4, we determine trade precedence between the two incoming trades (BTC/USD and SOL/USD). SOL/USD receives precedence due to its higher defined allocation percentage. As a result, we allocate 20% of our portfolio to BTC/USD and 75% to SOL/USD.

At step 5, we sell our entire positions in BTC/USD and SOL/USD.

**Important:** To ensure buy-side boost functions as intended, avoid having ties between the defined allocation percentages in `strategy_config.json`.

# Usage
In this section, I’ll guide you through the essential user configurations, including setting your portfolio allocation split, choosing your execution strategy, and reviewing guidelines to ensure the system functions as intended.

## Allocation Split
First, open `trading_automation_system/chalicelib/strategy_config.json` and adjust the values next to each percentage to reflect your desired allocation split. Ensure the top-level key matches the symbol in TradingView. For example, if your strategy is based on SOLUSDT in TradingView, the key should also be SOLUSDT.

## Execution Strategy
To switch between multi-strategy allocation and buy-side boost, edit line 86 in `app.py` as follows:

**Multi-Strategy Allocation:**

`orders = trade_execution.multi_strategy_allocation(exchange, trades, increment_pct=INCREMENT_PCT)`

**Buy-Side Boost:** 

`orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=INCREMENT_PCT)`

## Important Guidelines
For optimal performance, please follow these key guidelines:

### Account Management
- Dedicate this trading account exclusively to automated strategies operating on the same timeframe
- Keep your account clean by fully closing all trades for each strategy
    - A fully closed trade example: Buy 1 SOL → Sell 1 SOL
    - An incomplete trade example: Buy 1 SOL → Sell 0.5 SOL
- Avoid manual trading or external transfers in this account, as they can interfere with position tracking

### Portfolio Allocation
- Keep total strategy allocations at or below 98% in strategy_config.json
    - The remaining 2% is reserved for trading fees
    - Example: If you have three strategies, they might be allocated as 40%, 30%, and 28%

### Buy-Side Boost Configuration
When using Buy-Side Boost, trade priority is determined by:
1. Highest allocation percentage first
2. Alphabetical order for strategies with equal allocation
    - Example: If both "BTC" and "ETH" strategies are allocated 30%, "BTC" takes precedence

**Note**: Accurate position tracking and account value calculations depend on following these guidelines strictly.

# Getting Started
To set up the automation system on your own machine, we'll follow these steps:
1. AWS Account Setup & Configuration
2. Clone the Repository & Install Dependencies
3. Create DynamoDB Table
4. Obtain & Store API Keys
5. Assign Permissions
6. Deploy the System
7. Perform Testing
8. Configure TradingView Strategies
## AWS Account Setup & Configuration
To begin, you'll need to create an AWS account and set up the AWS CLI to interact with your account via the command line. For a detailed walkthrough, refer to this guide: [AWS Account & CLI Setup](https://youtu.be/CjKhQoYeR4Q?si=yrVoZYg3SKRq28og).
## Clone the Repository & Install UV 
First, install uv - a fast Python package installer and resolver. You can install it using curl:

```shell
# On macOS or Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

Next, clone the repository:

```shell
$ git clone https://github.com/lukenew2/crypto_automation_system.git
```
With the repo cloned and uv installed, you're ready to create your AWS resources and configure the automation system.

## Create DynamoDB Table
You can create a DynamoDB table using either the AWS Console or the AWS CLI. 

**Important:** Ensure both Write Capacity Units (WCUs) and Read Capacity Units (RCUs) are set to 5. This keeps you well within the AWS free tier limit of 25 WCUs and RCUs per month.
### Option 1: Using the AWS Management Console
1. **Sign in to the AWS Management Console**  
    - Go to the [DynamoDB dashboard](https://console.aws.amazon.com/dynamodb).
2. **Create a New Table**
    - Click on **"Create table"**.
    - Enter a **Table name**. For example, `crypto_automation_table`.
    - Set the **Partition key** to `ticker` and the **Range key** to `create_ts`. Both should be set to **String** as their data type.
3. **Adjust Read/Write Capacity Settings**
    - Scroll down to **Capacity mode**.
    - Select **"Provisioned"**.
    - Set both **Read capacity units (RCU)** and **Write capacity units (WCU)** to **5**
4. **Create the Table**
    - Click **Create table** at the bottom of the page.
    - Your table will be created and ready for use in your automation system.

### Option 2: Using the AWS CLI
You can also create the DynamoDB table via the AWS CLI with the following command. This will create a table named `crypto_automation_table` with the partition key `ticker` and the range key `create_ts`, both of which are set to String (`S`), and WCUs/RCUs set to 5.
```
$ aws dynamodb create-table \
    --table-name crypto_automation_table \
    --attribute-definitions \
        AttributeName=ticker,AttributeType=S \
        AttributeName=create_ts,AttributeType=S \
    --key-schema \
        AttributeName=ticker,KeyType=HASH \
        AttributeName=create_ts,KeyType=RANGE \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --table-class STANDARD
```

Make sure to note the table name because we'll need it later to reference the table in your automation system.
## Obtain & Store API Keys
To connect your exchange to the automation system, follow your exchange's instructions for generating API keys. These keys usually consist of an **API Key** and a **Secret Key**. Make sure to generate the necessary permissions for trading (Read and Trade, but typically leave Withdraw disabled for security).

Once you have your API keys, securely store them in **AWS Secrets Manager** by following these steps:
### Step 1: Access AWS Secrets Manager
1. Log in to your **AWS Management Console**.
2. Navigate to **Secrets Manager** by searching for it in the search bar.
### Step 2: Create a New Secret
1. Click **Store a new secret**.
2. Select **Other type of secret**.
3. Enter your **API Key** and **Secret Key** as key-value pairs:
    - Key: `api-key`, Value: your API key
    - Key: `api-secret`, Value: your secret key
4. Click **Next**.
### Step 3: Name and Configure the Secret
1. Give your secret a name, such as `exchange_api_keys`.
2. Optionally, add a description to identify it.
### Step 4: Store the Secret
1. Click **Next** to configure any additional settings or leave them as default.
2. Finally, click **Store** to securely save your API keys.

Be sure to take note of the secret name because in the next section we’ll configure the automation system to access and interact with our AWS resources.
## User Configurations
This section will help you customize the `trading_automation_system/.chalice/config.json` file for your crypto trading bot. This configuration file is crucial for connecting your bot to the correct exchange, setting up your trading preferences, and managing your development and production environments.

### Development vs Production
The configuration file defines two separate environments (stages): dev and prod. Here's what each one is for:
**Development** (dev)
    - Used for testing and development
    - Connects to exchange's sandbox/testnet environment
    - Uses simulated trading with fake money
    - Perfect for testing new strategies or system changes
    - Set to "SANDBOX": "True" automatically
    - You can safely ignore this section if you're only planning to trade with real funds
**Production** (prod)
    - Used for real trading with actual funds
    - Connects to the exchange's main trading environment
    - Set to "SANDBOX": "False" for live trading
    - **This is the environment you'll configure for actual trading**

### Global Settings
```json
{
    "version": "2.0",
    "app_name": "crypto_bot",
    "environment_variables": {
        "EXCHANGE_NAME": "YOUR_EXCHANGE_NAME",
        "QUOTE_CURRENCY": "USD",
        "INCREMENT_PCT": "0.001"
    }
}
```
#### How to Configure Global Settings
1. **EXCHANGE_NAME**: Replace YOUR_EXCHANGE_NAME with your exchange's identifier
    - For Binance: Use "binance"
    - For Bybit: Use "bybit"
    - For Gemini: Use "gemini"
2. **QUOTE_CURRENCY**: Set this to the currency you'll use for purchasing
    - Common options: "USD", "USDT", "USDC"
    - Example: If trading on Binance with USDC, use "USDC"
3. **INCREMENT_PCT**: This ensures your limit orders are filled promptly
    - Default is "0.001" (0.1%)
    - Increase for larger account values
    - Example: "0.002" for 0.2% increment

### Environment-Specific Settings
The configuration has two environments: dev and prod. Each environment has its own settings:
```json
"stages": {
    "dev": {
        "api_gateway_stage": "dev",
        "autogen_policy": false,
        "iam_policy_file": "policy-dev.json",
        "environment_variables": {
            "TABLE_NAME": "YOUR_TABLE_NAME",
            "SECRET_NAME": "YOUR_SECRET_NAME",
            "SANDBOX": "True"
        }
    },
    "prod": {
        "api_gateway_stage": "prod",
        "autogen_policy": false,
        "iam_policy_file": "policy-prod.json",
        "environment_variables": {
            "TABLE_NAME": "YOUR_TABLE_NAME",
            "SECRET_NAME": "YOUR_SECRET_NAME",
            "SANDBOX": "False"
        }
    }
}
```

#### How to Configure Environment Settings
For both dev and prod environments:

1. **TABLE_NAME**: Replace YOUR_TABLE_NAME with your DynamoDB table name
    - Example: "crypto_trading_signals"
    - Use different names for dev and prod if you want separate tables
    - Example dev: "crypto_trading_signals_dev"
    - Example prod: "crypto_trading_signals_prod"
2. **SECRET_NAME**: Replace YOUR_SECRET_NAME with your AWS Secrets Manager secret name
    - Example: "exchange_api_keys"
    - Use different names for dev and prod environments
    - Example dev: "exchange_api_keys_dev"
    - Example prod: "exchange_api_keys_prod"

## Deploy the System
With your automation system set up and configured, the next step is to deploy the system using AWS Chalice. Chalice simplifies the process of deploying Python applications to AWS Lambda, allowing you to create and manage serverless applications easily.

Before deploying, ensure you're in the root directory of your project (where your `crypto_bot` folder is located), and run the following command:

```shell
$ uv run chalice deploy --stage prod
Creating deployment package.
Creating IAM role: crpyto_bot-prod
Creating lambda function: crpyto_bot-prod
Creating Rest API
Resources deployed:
  - Lambda ARN: arn:aws:lambda:us-west-2:12345:function:crpyto_bot-prod
  - Rest API URL: https://abcd.execute-api.us-west-2.amazonaws.com/api/
```
This will package and deploy the entire application to AWS. During the deployment process, Chalice will:

- Deploy your application to **AWS Lambda**.
- Set up an **API Gateway**.
- Assign the appropriate permissions based on your `config.json` file.
- Deploy the resources associated with the production environment (`prod` stage).

If you need to delete your application at any point, you can use the following command:

```shell
$ uv run chalice delete --stage prod
Deleting Rest API: abcd4kwyl4
Deleting function aws:arn:lambda:region:123456789:crpyto_bot-prod
Deleting IAM Role crpyto_bot-prod
```
## Perform Testing
In this section, we’ll test the REST API endpoint to ensure trade signals can be written to the database. Then, we’ll test the Lambda function by invoking it and checking for the appropriate messages in the logs.
### Testing the REST API

To confirm that the REST API is functioning properly, we’ll send a test request using **Insomnia**, a tool for testing APIs.

#### Step 1: Set Up Insomnia
1. Download and install **Insomnia** if you don’t have it installed already.
2. Open Insomnia and create a new **Request**.
3. Select **POST** as the request type and enter your **API Gateway URL** adding `receive_trade_signals` to the end (e.g., `https://abcd.execute-api.us-west-2.amazonaws.com/prod/receive_trade_signals`).

#### Step 2: Configure the Request Body
1. Under the **Body** tab in Insomnia, select **JSON** and input a test payload. For example:
```JSON
{
	"time": "2024-08-10T02:30:02Z",
	"ticker": "BTCUSD",
	"order_action": "buy",
	"order_price": "67656.77",
	"order_comment": "long"
}
```

2. Make sure your payload structure matches what the API expects (in this case, a trade signal).

#### Step 3: Send the Request
1. Click **Send** in Insomnia to submit the request.
2. Check the response to ensure the API is accepting and processing the request properly. A successful response might return a `200 OK` status, confirming that the trade signal was sent to the system.

#### Step 4: Verify the Data in DynamoDB
1. Log in to the **AWS Console** and navigate to **DynamoDB**.
2. Open your table and check the entries to confirm that the trade signal  has been written to the database.
### Testing the Lambda Function
Now, we’ll test the Lambda function directly to ensure that it processes the trade signals correctly.

#### Step 1: Invoke the Lambda Function**
1. Open the **AWS Console** and go to **AWS Lambda**.
2. Find your Lambda function (e.g., `crypto_bot-prod-execute_trade_signals`) and click on it.
3. Click **Test** to create a test event, using a similar payload as the one below:
```JSON
{
  "id": "9dbbc12b-0e1a-4c90-9929-e5475c68e9e4",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "account": "123456789012",
  "time": "2019-10-08T16:53:06Z",
  "region": "us-west-2",
  "resources": [
    "arn:aws:lambda:us-west-2:12345:function:crpyto_bot-prod-execute_trade_signals"
  ],
  "detail": {},
  "version": ""
}
```
4. Click **Test** again to invoke the function.

#### Step 2: Check the Logs
1. In the **AWS Console**, navigate to **CloudWatch** and locate the log group for your Lambda function.
2. Review the logs and confirm that the following message appears (time shouldn't match):  
    `"crypto_bot - INFO - No trade signals at 2024-09-09 16:00:00+00:00"`.
## Configure TradingView Strategies
Finally, we can configure our TradingView strategies to send webhooks to our Rest API.
#### Step 1: Get Your API Endpoint
Copy your **API Gateway URL** from Chalice adding `receive_trade_signals` to the end (e.g., `https://abcd.execute-api.us-west-2.amazonaws.com/prod/receive_trade_signals`).
#### Step 2: Set Up a TradingView Alert
1. Open your strategy in **TradingView**.
2. Click the **Alerts** icon and select **Create Alert**.
#### Step 3: Configure Webhook & Message
1. In the **Webhook URL** field, paste your **API Gateway URL**.
2. Set the **Message** field to the following JSON:
```JSON
{
    "time": "{{timenow}}",
    "ticker": "{{ticker}}",
    "order_action": "{{strategy.order.action}}",
    "order_price": "{{strategy.order.price}}",
    "order_comment": "{{strategy.order.comment}}"
}
```