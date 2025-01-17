import os
import logging
import traceback
from decimal import Decimal
from chalice import Chalice, Cron
from chalicelib import utils, aws_clients, trade_processing, trade_execution

app = Chalice(app_name="trading_automation_system")
app.log.setLevel(logging.DEBUG)

TABLE_NAME = os.environ.get("TABLE_NAME")
SECRET_NAME = os.environ.get("SECRET_NAME")
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME")
SANDBOX = utils.get_env_var("SANDBOX")
QUOTE_CURRENCY = os.environ.get("QUOTE_CURRENCY")
INCREMENT_PCT = Decimal(os.environ.get("INCREMENT_PCT"))

def process_stop_loss(stop_loss_trade):
    """Handle stop loss trade execution."""
    try:
        exchange = trade_execution.Exchange(EXCHANGE_NAME, QUOTE_CURRENCY)
        exchange.connect(SECRET_NAME, sandbox=SANDBOX)
        app.log.debug(f"Successfully connected to exchange: {EXCHANGE_NAME}")

        order = trade_execution.execute_long_stop(exchange, stop_loss_trade, increment_pct=INCREMENT_PCT)
        app.log.info(f"Successfully executed stop loss order: {order}")
    except Exception as e:
        error_msg = f"Failed to execute stop loss: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        app.log.error(error_msg)
        raise
    
def save_trade_to_db(trade):
    """Save trade signal to DynamoDB."""
    try:
        dynamodb_manager = aws_clients.DynamoDBManager()
        table = dynamodb_manager.get_table(TABLE_NAME)
        app.log.debug(f"Established connection to {TABLE_NAME} database")

        table.put_item(Item=trade)
        app.log.info(f"Trade on {trade['ticker']} at {trade['create_ts']} saved to database.")
    except Exception as e:
        error_msg = f"Failed to save trade to DynamoDB: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        app.log.error(error_msg)
        raise

# REST API Endpoint
@app.route("/receive_trade_signals", methods=["POST"])
def receive_trade_signals():
    """Receives trade signal via post request and executes stop loss or writes it to database."""
    trade_in = app.current_request.json_body
    app.log.debug(f"Trade Signal Received: {trade_in}")

    trade_out = trade_processing.preprocess_trade_signal(trade_in)
    app.log.debug(f"Trade Signal Processed: {trade_out}")

    if "stop" in trade_out.get("order_comment").lower():
        return process_stop_loss(trade_out)
    return save_trade_to_db(trade_out)

# Scheduled Lambda Function 
@app.schedule(Cron("1", "0,8,16", "*", "*", "?", "*"))
def execute_trade_signals(event):
    """
    Execute pending trade signals retrieved from the database.

    This function runs on a scheduled basis (at 00:01, 08:01, and 16:01 UTC) to process
    trade signals stored in DynamoDB. For each valid trade signal, it connects to the
    specified exchange and executes orders with a small price increment to account
    for market movement.
    """
    try:
        utcnow = utils.get_utc_now_rounded()
        trades = trade_processing.get_all_recent_signals(
            cutoff_time=utcnow, 
            table_name=TABLE_NAME
        )
        if not trades:
            app.log.info(f"No trade signals at {utcnow}")
            return 
    
        app.log.debug(f"Successfully retrieved trade signals from database: {trades}")
        exchange = trade_execution.Exchange(EXCHANGE_NAME, QUOTE_CURRENCY)
        exchange.connect(SECRET_NAME, sandbox=SANDBOX)
        app.log.debug(f"Successfully connected to exchange: {EXCHANGE_NAME}")

        orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=INCREMENT_PCT)
        if orders:
            app.log.info(f"Successfully placed order(s): {orders}")
    except Exception as e:
        error_msg = f"Failed to execute trade signals: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        app.log.error(error_msg)