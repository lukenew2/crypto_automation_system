# Prerequisites

- AWS account with AWS CLI setup on your machine. To do this correctly follow this video: (https://www.youtube.com/watch?v=CjKhQoYeR4Q)
- TradingView strategy(s)

# Use Cases

1. Automate multiple cryptocurrency TradingView strategies.
2. Automate portfolio allocation across different TradingView strategies.

# Features

This trade automation system uses a serverless approach so we only pay for what we use.  And in our case this will always fall under AWS free tier.

- **AWS Chalice** - A framework for quickly deploying serverless applications.  And since our application is invoked less than 1 million times a month it is **completely free**!  This is plenty enough for our application.
- **DynamoDB** - A serverless database used to store incoming trade signals from TradingView as an intermediary step between receiving trade signals and execution.  As long as you stay under 25GB of storage, 25 Write Capacity Units (WCU), and 25 Read Capacity Units (RCU) this service is also **always free!**  This is enough to handle up to 200 million requests per month so don’t worry we will never come close.
- **AWS Secrets Manager** (Optional) - This is the only paid service the system uses and if we’re going to pay for anything it should be security.  That being said, AWS charges $0.40 per secret per month and we will only need one secret that stores our exchange’s API keys.   The system is designed using Secrets Manager so I’ll leave it to the reader to reconfigure it using another storage method if they desire.
- **CCXT** - A library used to connect and trade on cryptocurrency exchanges in a unified format.  This allows us to easily extend the automation system to different exchanges.  Current exchange support:
    - Gemini
- **CI/CD** - Separation of production and development environments allows us to continually integrate and develop the system without affecting what’s deployed in production.

# Application Design

This application relies on TradingView to generate trading signals from a strategy (or multiple strategies) and sends them via web-hooks to a REST API (**AWS Chalice**).  The API has two functions:

1. Processes incoming trade signals and stores them in a NoSQL database (**DynamoDB**). 
    1. If the incoming trade signal is a **stop loss**, the application immediately executes a sell order instead of writing the trade to the database.
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

From here on forward I’m assuming that you have the AWS CLI set up properly so we can create your AWS resources from the command line.  

## DynamoDB

First, you’ll create your database that will store incoming trade signals from TradingView.  Make note of the **table name.** This field can be changed to whatever you want.  For example, if you want to have separate tables for dev/prod you can add a -dev or -prod to the end of the name.

If you’re on Linux/OS run the following in the terminal:

```bash
$ aws dynamodb create-table \
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
$ aws dynamodb create-table ^
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
```

Take note of the **TableArn** field and copy the value to your clipboard.  Now, open the file *crypto_automation_system/crypto_bot/.chalice/policy-prod.json* and paste the TableArn value inside the **DynamoDB** Resource field.  It should look something like this:

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

This gives your automation system permission to read/write to the database so whenever TradingView sends signals to your application you will be able to write the signals to the table.

Next, open *crypto_automation_system/crypto_bot/.chalice/config.json* and paste the table name in the field **TABLE_NAME**. If you’re creating two tables, one for dev/prod, you would put the respective name in the respective stage.  Your file should look something like this:

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
        "TABLE_NAME": "tradesignals-dev",
        "SECRET_NAME": "YOUR-API-SECRET",
        "SANDBOX": "True"
      }
    },
    "prod": {
      "api_gateway_stage": "prod",
      "autogen_policy": false,
      "iam_policy_file": "policy-prod.json",
      "environment_variables": {
        "TABLE_NAME": "tradesignals-prod",
        "SECRET_NAME": "YOUR-API-SECRET",
        "SANDBOX": "False"
      }
    }
  }
}
```

And boom!  You’ve created your DynamoDB table and given your application the required permissions and configurations.

**Developer Note**: If you’re using the dev environment, you will also need to modify the policy-dev.json file in a similar way as we did the policy-prod.json file above.

## Generate API Keys

Next, you need to give your application access to your trading account.  You do this by generating API keys on your exchange, storing those keys in AWS Secrets Manager, and giving your application sufficient permission to retrieve said keys.   

Generating API keys is different for every exchange.  For instructions, google how to generate API keys on your exchange.  **Important** - your keys only need sufficient permissions to view account balances and create orders.  It is best practice to give your keys minimum permissions required.  Once you have your keys store them in a safe place.  

## Secrets Manager

Now that you have your API keys for your exchange, You’ll securely store them in AWS Secrets Manager and give your application permission to retrieve them.  

1. Open the Secrets Manager console at  https://console.aws.amazon.com/secretsmanager/
2. Choose **Store a new secret**.
3. On the **Choose secret type** page, do the following:
    1. For **Secret type**, choose **Other type of secret**.
    2. In **Key/value pairs**, enter your secret in JSON **Key/value** pairs as shown below.
    
    ```json
    {
        "api-key": "YOUR-API-KEY",
        "api-secret": "YOUR-API-SECRET"
    }
    ```
    
    You do not need to change anything else on this page.  Choose next.
    
4. On the **Configure secret** page, do the following:
    1. Enter a descriptive **Secret name** and **Description**. Secret names must contain 1-512 Unicode characters.  Take note of the secret name.  We will use it later.
    2. Choose next
5. On the **Review** page, review your secret details, and then choose **Store**.
    
    Secrets Manager returns to the list of secrets. If your new secret doesn't appear, choose the refresh button.
    
6. Click on your newly created secret and copy the **Secret ARN** to your clipboard.  Open *crypto_automation_system/crypto_bot/.chalice/policy-prod.json* and paste the Secret ARN value inside the **Secrets Manager Resource field**.  It should look something like this:
    
    ```json
          {
            "Action": [
              "secretsmanager:GetSecretValue"
            ],
            "Resource": [
              "arn:aws:secretsmanager:us-east-1:111122223333:secret:secretname"
            ],
            "Effect": "Allow"
          }
    ```
    
7. Now, open *crypto_automation_system/crypto_bot/.chalice/config.json* and paste your secret name in the field **SECRET_NAME** within the prod stage.  It should look something like this:
    
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
            "SECRET_NAME": "secretname-dev",
            "SANDBOX": "True"
          }
        },
        "prod": {
          "api_gateway_stage": "prod",
          "autogen_policy": false,
          "iam_policy_file": "policy-prod.json",
          "environment_variables": {
            "TABLE_NAME": "tradesignals",
            "SECRET_NAME": "secretname-prod",
            "SANDBOX": "False"
          }
        }
      }
    }
    ```
    

And Kaboom!  You’ve created a secret to securely store your exchange’s API keys and gave your application sufficient permissions to access the keys.  

**Developer Note:** Most exchanges offer a sandbox environment that provides the same functionality as the actual exchange to enable testing in your application without affecting your actual account.  If you have API keys for your exchange’s sandbox, you can create another secret in AWS Secrets Manager to store the sandbox’s API keys.  Copy the Secret Name within the dev stage of our config.json file and the Secret ARN in the policy-dev.json file.

## Deployment

Open *crypto_automation_system/crypto_bot/chalicelib/strategy_config.json* and adjust how much of your portfolio you want to allocate to each strategy by adjusting the “**percentage**” field to your desired allocation.  (**Important**: the values must not add to more than 0.98 to ensure you have enough for fees).

```json
{
    "BTCUSD": {
        "symbol": "BTC/USD",
        "currency": "BTC",
        "percentage": 0.20,
        "stop_loss": 0.03
    },
    "ETHUSD": {
        "symbol": "ETH/USD",
        "currency": "ETH",
        "percentage": 0.25,
        "stop_loss": 0.03
    },
    "ADAUSD": {
        "symbol": "ADA/USD",
        "currency": "ADA",
        "percentage": 0,
        "stop_loss": 0.20
    },
    "SOLUSD": {
        "symbol": "SOL/USD",
        "currency": "SOL",
        "percentag*": 0.53,
        "stop_loss": 0.066
    }
}
```

To deploy, navigate your terminal inside the crypto_bot directory run `chalice deploy --stage prod`:

```bash
$ chalice deploy --stage prod
Creating deployment package.
Creating IAM role: crpyto_bot-prod
Creating lambda function: crpyto_bot-prod
Creating Rest API
Resources deployed:
  - Lambda ARN: arn:aws:lambda:us-west-2:12345:function:crpyto_bot-prod
  - Rest API URL: https://abcd.execute-api.us-west-2.amazonaws.com/api/
```
Make note of the Rest API URL.  You will need it to setup TradingView to send alerts to your application.

If you need to delete your application for whatever reason you can run `chalice delete --stage prod`:
```bash
$ chalice delete --stage prod
Deleting Rest API: abcd4kwyl4
Deleting function aws:arn:lambda:region:123456789:crpyto_bot-prod
Deleting IAM Role crpyto_bot-prod
```

## Testing

Now that your application is deployed you can test it using the AWS console. (*Note: this won't trigger any trades on your account since the time field is in the past.*)

1. In AWS search **Lambda** and in the left side bar choose **functions**.  You should see two functions:
    1. **crypto_bot-prod** writes incoming trade signals to your database
    2. **crypto_bot-prod-execute_trade_signals** executes trades signals stored in the database.
2. Click on the function **crypto_bot-prod** and choose **Test**.
3. Choose **create new event.**
4. In the **Event JSON** editor paste the JSON below

```json
{
  "time": "2024-04-04T16:00:02Z",
  "ticker": "BTCUSD",
  "order_action": "buy",
  "order_price": "67656.77",
  "order_comment": "long"
}
```

5. **Choose Test.**  Wait a few seconds and you should see a green check for **successful execution.**
6. Now go back and click on the function **crypto_bot-prod-execute_trade_signals** and choose **Test.**
7. Choose **create new event.**
8. In the **Event JSON** editor paste the JSON below

```json
{
  "id": "9dbbc12b-0e1a-4c90-9929-e5475c68e9e4",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "account": "123456789012",
  "time": "2019-10-08T16:53:06Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:lambda:us-east-1:111122223333:function:crypto_bot-prod-execute_trade_signals"
  ],
  "detail": {},
  "version": ""
}
```

9. **Choose Test.**  Wait a few seconds and you should see a green check for **successful execution.**

## TradingView Web-hooks

Last step is to configure your strategy in TradingView to send alerts to your new REST API Endpoint.  Create a new alert off your strategy and in the message paste the JSON below:

```json
{
    "time": "{{timenow}}",
    "ticker": "{{ticker}}",
    "order_action": "{{strategy.order.action}}",
    "order_price": "{{strategy.order.price}}",
    "order_comment": "{{strategy.order.comment}}"
}
```

And then in the notifications select Webhook URL and paste your REST API’s endpoint with receive_trade_signals after the slash.  It should look something like this:

```
https://abcd.execute-api.us-west-2.amazonaws.com/prod/receive_trade_signals
```