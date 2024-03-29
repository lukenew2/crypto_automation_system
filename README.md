# Prerequisites

* AWS account with AWS CLI setup on your machine.  To do this correctly follow this video: (https://www.youtube.com/watch?v=CjKhQoYeR4Q)

# Use Cases

1. Automate multiple cryptocurrency TradingView strategies.
2. Automate complex interactions across differenct strategies.

# Features

This trade automation system uses a serverless approach so you only pay for what you use.  And in our case this will always fall under AWS free tier.

- **AWS Chalice** - A framework for quickly deploying serverless applications.  And since our application is invoked less than 1 million times a month it is **completely free**!
- **DynamoDB** - A serverless database used to store incoming trade signals from TradingView as an intermediary step between receiving trade signals and execution.  As long as you stay under 25GB of storage, 25 Write Capacity Units (WCU), and 25 Read Capacity Units (RCU) this service is also **always free!**  This is enough to handle up to 200 million requests per month.
- **AWS Secrets Manager** (Optional) - This is the only paid service the system uses and if you’re going to pay for anything it should be security.  That being said, AWS charges $0.40 per secret per month and you will only need one secret that stores your exchange’s API keys.   The system is designed using Secrets Manager so I’ll leave it to the reader to reconfigure it using another storage method if they desire.
- **CCXT** - A library used to connect and trade on cryptocurrency exchanges in a unified format.  This allows us to easily extend the automation system to different exchanges.  Current exchange support:
    - Gemini
- **CI/CD** - Separation of production and development environments allows us to continually integrate and develop the system without affecting what’s deployed to production.

# Application Design

This application relies on TradingView to generate trading signals from a strategy (or multiple strategies) and sends them via web-hooks to a REST API (**AWS Chalice**).  The API has two functions:

1. Processes incoming trade signals and stores them in a NoSQL database (**DynamoDB**). 
2. Invokes a **lambda** function at a fixed interval that executes trades based on if there were any recent trading signals stored in the database. (*Note: the interval should be the same as the timeframe the trading strategies trade on.*)

To execute trades, the lambda function connects to the exchange via API, gathering required account data, and places the order(s).

![trade_automation_system](img/trade_automation_system.png)

# Getting Started

## Project setup

To get started go ahead and clone the repository in your local workspace by running the following command:

```bash
$ git clone https://github.com/lukenew2/crypto_auto_trading.git
```

Navigate your terminal inside the project directory and create a new virtual environment with python 3.10 and install both requirements.txt files.  

- requirements.txt - Installs chalice and pytest used for application deployment and unit testing respectively.
- crypto_bot/requirements.txt - Installs packages used within application.

```bash
$ python3.10 -m venv venv310
$ . venv310/bin/activate
$ pip install -r requirements.txt
$ pip install -r crypto_bot/requirements.txt
```

From here on forward I’m assuming that you have the AWS CLI set up properly so we can create our AWS resources from the command line.  

## DynamoDB

First, we’ll create our database that will store incoming trade signals from TradingView.  Make note of the **table name.** This field can be changed to whatever you want to call your table.  For example, if you want to have separate tables for dev/prod you can add a -dev or -prod to the end of the name.

In the terminal run if you’re on Linux/OS:

```bash
aws dynamodb create-table \
    --table-name tradesignals \
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

Or if you’re on Windows:

```bash
aws dynamodb create-table ^
    --table-name tradesignals ^
    --attribute-definitions ^
        AttributeName=ticker,AttributeType=S ^
        AttributeName=create_ts,AttributeType=S ^
    --key-schema ^
        AttributeName=ticker,KeyType=HASH ^
        AttributeName=create_ts,KeyType=RANGE ^
    --provisioned-throughput ^
        ReadCapacityUnits=5,WriteCapacityUnits=5 ^
    --table-class STANDARD
```

You should get an output that looks something like this:

```json
{
    "TableDescription": {
        "AttributeDefinitions": [
            {
                "AttributeName": "ticker",
                "AttributeType": "S"
            },
            {
                "AttributeName": "create_ts",
                "AttributeType": "S"
            }
        ],
        "TableName": "tradesignals",
        "KeySchema": [
            {
                "AttributeName": "ticker",
                "KeyType": "HASH"
            },
            {
                "AttributeName": "create_ts",
                "KeyType": "RANGE"
            }
        ],
        "TableStatus": "CREATING",
        "CreationDateTime": "2023-03-29T12:11:43.379000-04:00",
        "ProvisionedThroughput": {
            "NumberOfDecreasesToday": 0,
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        },
        "TableSizeBytes": 0,
        "ItemCount": 0,
        "TableArn": "arn:aws:dynamodb:us-east-1:111122223333:table/tradesignals",
        "TableId": "60abf404-1839-4917-a89b-a8b0ab2a1b87",
        "TableClassSummary": {
            "TableClass": "STANDARD"
        }
    }
}
}
```

Take note of the field **TableArn** and copy the value to your clipboard.  Now, open the file crypto_automation_system/crypto_bot/.chalice/policy-prod.json and paste the TableArn value you copied inside the **DynamoDB** Resource field.  It should look something like this:

```json
      {
        "Action": [
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ],
        "Resource": [
          "arn:aws:dynamodb:us-east-1:111122223333:table/tradesignals"
        ],
        "Effect": "Allow"
      },
```

This gives our automation system permission to read/write to the database so whenever TradingView sends signals to our application we will be able to write the signals to the table.

Next, open crypto_automation_system/crypto_bot/.chalice/config.json and paste the table name in the field **TABLE_NAME**. If you’re creating two tables one for dev/prod you would put the respective name in the respective stage.  Your file should look something like this:

```json
{
  "version": "2.0",
  "app_name": "crypto_bot",
  "environment_variables": {
    "EXCHANGE_NAME": "gemini"
  },
  "stages": {
    "dev": {
      "api_gateway_stage": "dev",
      "autogen_policy": false,
      "iam_policy_file": "policy-dev.json",
      "environment_variables": {
        "TABLE_NAME": "tradesignals",
        "SECRET_NAME": "YOUR_SECRET_NAME"
      }
    },
    "prod": {
      "api_gateway_stage": "prod",
      "autogen_policy": false,
      "iam_policy_file": "policy-prod.json",
      "environment_variables": {
        "TABLE_NAME": "tradesignals",
        "SECRET_NAME": "YOUR_SECRET_NAME"
      }
    }
  }
}
```

And boom!  You’ve created your DynamoDB table and given your application the required permissions and configurations.

## Secrets Manager

## Deployment

## Testing

## TradingView Web-hooks
