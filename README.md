# Crypto Automation System
Welcome to my trading automation system! Designed specifically for traders with strategies developed in TradingView, this system streamlines the transition from manual to automated execution. By eliminating emotional bias, ensuring consistent execution, and maintaining constant connectivity, our system empowers you to optimize your trading strategies with greater efficiency and confidence—all while keeping your private keys secure and minimizing costs to less than $1 a month.

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
First, open `strategy_config.json` and adjust the values next to each percentage to reflect your desired allocation split. Ensure the top-level key matches the symbol in TradingView. For example, if your strategy is based on SOLUSDT in TradingView, the key should also be SOLUSDT.

## Increment Percent
Next, open `app.py` and locate lines 28 and 56, where a parameter called `increment_pct` is set to a float. Adjust this value as needed to ensure your limit orders are filled promptly (e.g. 0.001 is .1%).

**Line 28:**

`order = trade_execution.execute_long_stop(exchange, trade_out, increment_pct=0.001)`

**Line 56:**

`orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=0.001)`

## Execution Strategy
To switch between multi-strategy allocation and buy-side boost, edit line 56 in `app.py` as follows:

**Multi-Strategy Allocation:**

`orders = trade_execution.multi_strategy_allocation(exchange, trades, increment_pct=0.001)`

**Buy-Side Boost:** 

`orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=0.001)`

## Important Guidelines
This section is to go over important guidelines to ensure the system works as intended.
- The account should be **solely** used for trading automated strategies **on the same timeframe**. 
- Ensure all trades are closed in the account before activating the system, as open trades will disrupt account value calculations.
- For similar reasons as above, avoid using this account for external crypto transfers. All strategies must start fresh, either with no trades at all or with the last trade fully closed.
- Configured percentages in `strategy_config.json` should not exceed 98%, leaving 2% available for fees.
- If using Buy-Side Boost, ensure that configured percentages in `strategy_config.json` are not the same, allowing for proper calculation of trade precedence.

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
# Clone the Repository & Install Dependencies 
To get started, clone the repository to your local workspace by running the following command:

```shell
$ git clone https://github.com/lukenew2/crypto_automation_system.git
```

Next, navigate to the project directory in your terminal, create a virtual environment using Python 3.10, and install the required dependencies from both `requirements.txt` files:

- `requirements.txt`: Installs Chalice for deployment and Pytest for unit testing.
- `crypto_bot/requirements.txt`: Installs packages used within the application.

```shell
$ python3.10 -m venv venv310
$ . venv310/bin/activate
$ pip install -r requirements.txt
$ pip install -r crypto_bot/requirements.txt
```
With the dependencies installed, you're ready to create your AWS resources and configure the automation system.
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

---
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

---

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
## Assign Permissions
Next, we’ll configure the automation system to interact with your newly created AWS resources. Follow these steps:
1. Open the file located at `./crypto_bot/.chalice/config.json`.
1. On **line 23**, replace `"YOUR_TABLE_NAME"` with the name of your DynamoDB table name. It should look like this:
    
    `"TABLE_NAME": "crypto_automation_table",`
	
1. On **line 24**, replace `"YOUR_SECRET_NAME"` with the name of the secret that stores your API keys. It should look like this:
    
    `"SECRET_NAME": "exchange_api_keys",`

**Note:** This file defines two stages: `prod` and `dev`. The `dev` stage is used for development and connects to your exchange’s sandbox environment. In this guide, we’ll only focus on the `prod` stage.
## Deploy the System
With your automation system set up and configured, the next step is to deploy the system using AWS Chalice. Chalice simplifies the process of deploying Python applications to AWS Lambda, allowing you to create and manage serverless applications easily.

Before deploying, ensure you're in the root directory of your project (where your `crypto_bot` folder is located), and run the following command:

```shell
$ chalice deploy --stage prod
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
$ chalice delete --stage prod
Deleting Rest API: abcd4kwyl4
Deleting function aws:arn:lambda:region:123456789:crpyto_bot-prod
Deleting IAM Role crpyto_bot-prod
```
## Perform Testing
## Configure TradingView Strategies