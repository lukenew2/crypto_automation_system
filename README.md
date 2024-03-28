# Prerequisites

- AWS Account & AWS CLI (Follow this video to setup AWS correctly: https://www.youtube.com/watch?v=CjKhQoYeR4Q)

# Use Cases

1. Automate multiple cryptocurrency TradingView strategies.
2. Automate complex interactions between strategies (Buy side boost).

# Features

This trade automation system uses a serverless approach so you only pay for what you use.  And in our case this will always fall under AWS free tier.

- **AWS Chalice** - A framework for quickly deploying serverless applications.  And since our application is invoked less than 1 million times a month it is **completely free**!
- **DynamoDB** - A serverless database used to store incoming trade signals from TradingView as an intermediary step between receiving trade signals and execution.  As long as you stay under 25GB of storage, 25 Write Capacity Units (WCU), and 25 Read Capacity Units (RCU) this service is also **always free!**  This is enough to handle up to 200 million requests per month.
- **AWS Secrets Manager** (Optional) - This is the only paid service the system uses and if you’re going to pay for anything it should be security.  That being said, AWS charges 0.40$ per secret per month and you will only need one secret that stores your exchange’s API keys.   The system is designed using Secrets Manager so I’ll leave it to the reader to reconfigure it using another storage method if they desire.
- **CCXT** - A library used to connect and trade on cryptocurrency exchanges in a unified format.  This allows us to easily extend the automation system to different exchanges.  Current exchange support:
    - Gemini
- **CI/CD** - Separation of production and development environments allows us to continually integrate and develop the system without affecting what’s deployed to production.

# Application Design

This application relies on TradingView to generate trading signals from a strategy (or multiple strategies) and sends them via web-hooks to a REST API (**AWS Chalice**).  The API has two functions:

1. Processes incoming trade signals and stores them in a NoSQL database (**DynamoDB**). 
2. Invokes a **lambda** function at a fixed interval that executes trades based on if there were any recent trading signals stored in the database. (*Note: the interval should be the same as the timeframe the trading strategies trade on.*)

To execute trades, the lambda function connects to the exchange via API, gathering required account data, and places the order(s).

![Untitled](img/trade_automation_system.png)

# Getting Started

To get started go ahead and clone the repository in your local workspace by running the following command:

```bash
git clone https://github.com/lukenew2/crypto_auto_trading.git
```

Then create a new virtual environment with python 3.10 and install both requirements.txt files.
