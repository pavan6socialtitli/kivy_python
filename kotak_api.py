# api/kotak_api.py
from neo_api_client import NeoAPI
from datetime import datetime, timedelta
import pandas as pd
from dateutil.relativedelta import relativedelta
import math
from kivy.storage.jsonstore import JsonStore
import json

class KotakAPI:
    active_api_sessions = {}

    def __init__(self):
        self.client = None
        self.client_id = None
        self.logged_in = False
        self.active_api_sessions = {}
#        self.store = JsonStore('api_sessions.json')
#        self.load_active_sessions()

    def simulate_login(self):
        # Simulate a successful login
        self.logged_in = True
        print("Simulated login successful")

    def get_positions(self):
        # For testing, return some dummy positions
        return [
            {"symbol": "NIFTY21JUN15000CE", "quantity": 50, "pnl": 2500},
            {"symbol": "BANKNIFTY21JUN35000PE", "quantity": 25, "pnl": -1200},
        ]

    def get_trade_book(self):
        # For testing, return some dummy trades
        return [
            {"symbol": "NIFTY21JUN15000CE", "transaction_type": "BUY", "quantity": 50, "price": 100},
            {"symbol": "BANKNIFTY21JUN35000PE", "transaction_type": "SELL", "quantity": 25, "price": 150},
        ]


#    def load_active_sessions(self):
#        if self.store.exists('active_api_sessions'):
#            stored_sessions = self.store.get('active_api_sessions')
#            for client_id, session_data in stored_sessions.items():
#                expiry_time = datetime.fromisoformat(session_data['expiry_time'])
#                if datetime.now() < expiry_time:
#                    self.active_api_sessions[client_id] = {
#                        'api_instance': session_data['api_instance'],
#                        'expiry_time': expiry_time
#                    }

    def initiate_login(self, consumer_key, secret_key, mobile_number, login_password):
        self.client_id = consumer_key  # Assuming consumer_key is unique for each client
         # Check for None values
        if None in (consumer_key, secret_key, mobile_number, login_password):
            raise ValueError("All login parameters must be provided")
        print(f"consumer_key: {consumer_key}, secret_key: {secret_key}, mobile_number: {mobile_number}, login_password: {'*' * len(login_password)}")

        try:
            self.client = NeoAPI(consumer_key=consumer_key, consumer_secret=secret_key, environment='prod')
            response = self.client.login(mobilenumber=mobile_number, password=login_password)
            if response and 'data' in response and 'token' in response['data']:                
                return True  # This should indicate if OTP was sent successfully
            else:
                print(f"Unexpected response format: {response}")
                return False
        except Exception as e:
            print(f"Error during login initiation: {str(e)}")
            raise

    def complete_login(self, otp):
        if not self.client:
            raise Exception("Login not initiated. Please call initiate_login first.")
         
        try:
            # Ensure OTP is a string
            otp_str = str(otp)
            print(f"Sending OTP to Kotak API: {otp_str}")  # Debug print

            login_response = self.client.session_2fa(OTP=otp_str)
            print(f"Received response from Kotak API: {login_response}")  # Debug print
            if login_response['data']['token']:
                self.active_api_sessions[self.client_id] = {
                    'api_instance': self.client,
                    'expiry_time': datetime.now() + timedelta(hours=12)
                }
                self.logged_in = True
#                self.save_active_api()
                return True
            return False
        except Exception as e:
            print(f"Error during OTP verification: {str(e)}")
            raise

    def is_logged_in(self):
        return self.logged_in

    def save_active_api(self):
        for client_id, session_data in self.active_api_sessions.items():
            self.store.put(client_id,
                        api_instance=session_data['api_instance'],
                        expiry_time=session_data['expiry_time'].isoformat())
        print("Active API details saved successfully")

    def get_active_session(self, client_id):
        session = self.active_api_sessions.get(client_id)
        if session and datetime.now() < session['expiry_time']:
            return session['api_instance']
        elif session:
            # Session expired, remove it
            del self.active_api_sessions[client_id]
#            self.save_active_api()
        return None

    def logout(self, client_id):
        if client_id in self.active_api_sessions:
            del self.active_api_sessions[client_id]
#            self.save_active_api()
        self.logged_in = False
        self.client = None

    def get_balance(self, client_id):
        session = self.get_active_session(client_id)
        f = session.limits(segment="ALL", exchange="ALL",product="ALL")
        fund = float(f['Net'])
        return fund
    # Add more API methods as needed

    def get_position_data(self, client_id):
        session = self.get_active_session(client_id)
        try:
            response = session.positions()
            if response['stat'] != 'Ok':
                raise Exception(f"Failed to fetch positions: {response['stat']}")
            
            positions = response['data']
            formatted_positions = []

            for pos in positions:
                total_buy_qty = float(pos['cfBuyQty']) + float(pos['flBuyQty'])
                total_sell_qty = float(pos['cfSellQty']) + float(pos['flSellQty'])
                net_qty = total_buy_qty - total_sell_qty

                total_buy_amt = float(pos['cfBuyAmt']) + float(pos['buyAmt'])
                total_sell_amt = float(pos['cfSellAmt']) + float(pos['sellAmt'])

                comb_multiplier = (float(pos['multiplier']) * 
                                   float(pos['genNum']) / float(pos['genDen']) * 
                                   float(pos['prcNum']) / float(pos['prcDen']))
                pnl = round((total_sell_amt - total_buy_amt), int(pos['precision']))

                formatted_positions.append({
                    'symbol': pos['trdSym'],
                    'token': pos['tok'],
                    'net_quantity': net_qty,
                    'pnl': pnl,
                    'ltp': 0,
                    'total_buy_amt': total_buy_amt,
                    'total_sell_amt': total_sell_amt,
                    'comb_multiplier': comb_multiplier,
                    'precision': int(pos['precision'])
                })

            return formatted_positions

        except Exception as e:
            print(f"Error fetching position data: {e}")
            return []


    #Function to Get Current Price of Symbol
    def get_current_quote(self, client_id, token):
        session = self.get_active_session(client_id)
        def on_message(message):
            print('[Res]: ', message)
            if message['type'] == 'quotes':
                global current_prices
                current_prices = message
        def on_error(message):
            print('[OnError]: ', message)
        session.on_message = on_message  # called when message is received from websocket
        session.on_error = on_error  # called when any error or exception occurs in code or websocket
        session.on_close = None  # called when websocket connection is closed
        session.on_open = None  # called when websocket successfully connects

        try:
            session.quotes(instrument_tokens = [token], quote_type="ltp", isIndex=False)
            return float(current_prices['data'][0]['ltp'])
        except Exception as e:
            print("Exception when calling get Quote api->quotes: %s\n" % e)
            return None

    def invested_amount(self, client_id, order_ids):
        try:
            session = self.get_active_session(client_id)
            order_bk = session.order_report()
            if order_bk["stat"]=="Ok":
                order_book = order_bk['data']
            else:
                return None, None
            investment = 0
            order_qty = 0
            print(order_ids)
            for orderno in order_ids:
                for dictionary in order_book:
                    if orderno in dictionary['nOrdNo'] and 'complete' in dictionary['ordSt']:
                        investment += (float(dictionary['avgPrc'])*int(dictionary['fldQty']))
                        order_qty += int(dictionary['fldQty'])
            return int(order_qty), float(investment)
        except Exception as e:
            print(f"Error getting invested_amount for {order_ids}:", e)
            return None, None

    #Check if Order present before exiting
    def check_order(self, client_id, order_ids):
        try:
            session = self.get_active_session(client_id)
            order_bk = session.order_report()
            order_book = order_bk['data']
            order_qty = 0
            print(order_ids)
            for orderno in order_ids:
                for dictionary in order_book:
                    if orderno in dictionary['nOrdNo'] and 'complete' in dictionary['ordSt']:
                        order_qty += int(dictionary['fldQty'])
            return int(order_qty)
        except Exception as e:
            print(f"Error getting order status for {order_ids}:", e)
            return None


    #3 Use this funtion to buy Call / Put by Manual Action
    def manual_buy_sell(self, client_id, data):
        session = self.get_active_session(client_id)
        symbol = str(data['symbol'])  # Ensure Symbol is a string
        action = str(data['action'])  # Ensure action is a string
        exchange_segment = str(data['exchange_segment'])
        lots = float(data.get('lots', 0))
        freez_qty = float(data.get('freez_qty', 0))
        lot_size = float(data.get('lot_size', 0))
        freez_lot = math.floor(freez_qty / lot_size)

        if action == 'LONG':
            transaction_type = 'B'
        elif action == 'SHORT':
            transaction_type = 'S'
            quantity = float(data.get('quantity', 0))  # Use .get() with a default value

        order_id = []

        try:
            if lots > freez_lot:
                Full_lot_order = math.floor(lots/freez_lot)
                Partial_lot_order = math.floor((lots - (Full_lot_order*freez_lot)))               
                for flo in range(Full_lot_order):
                    order_response = session.place_order(exchange_segment=exchange_segment, product="NRML", price="", order_type="MKT", quantity=str(freez_qty), validity="DAY", 
                                                            trading_symbol=symbol, transaction_type=transaction_type, amo="NO", disclosed_quantity="0", market_protection="0", pf="N", trigger_price="0", tag=None)
                    if order_response['stat'] == 'Ok':
                        print("Trade executed:", order_response)
                        order_id.append(order_response['nOrdNo'])
                if Partial_lot_order > 0:
                    order_response = session.place_order(exchange_segment=exchange_segment, product="NRML", price="", order_type="MKT", quantity=str(Partial_lot_order*lot_size), validity="DAY", 
                                                            trading_symbol=symbol, transaction_type=transaction_type, amo="NO", disclosed_quantity="0", market_protection="0", pf="N", trigger_price="0", tag=None)
                    if order_response['stat'] == 'Ok':
                        print("Trade executed:", order_response)
                        order_id.append(order_response['nOrdNo'])
            elif lots > 0:
                order_response = session.place_order(exchange_segment=exchange_segment, product="NRML", price="", order_type="MKT", quantity=str(math.floor(lots*lot_size)), validity="DAY", 
                                                            trading_symbol=symbol, transaction_type=transaction_type, amo="NO", disclosed_quantity="0", market_protection="0", pf="N", trigger_price="0", tag=None)
                if order_response['stat'] == 'Ok':
                    print("Trade executed:", order_response)
                    order_id.append(order_response['nOrdNo'])

            order_qty, investment = self.invested_amount(client_id, order_id)
            if order_qty is None and investment is None:
                return None, None, None
            if action == 'LONG':
                order_qty = order_qty
                investment = -1 * investment
            elif action == 'SHORT':
                order_qty = -1 * order_qty
                investment = investment

            return symbol, order_qty, investment

        except Exception as e:
            print("Error executing trade:", e)
            return None, None, None


    def get_tradebook_data(self, client_id):
        try:
            session = self.get_active_session(client_id)
            response = session.order_report()
            if response['stat'] != 'Ok':
                raise Exception(f"Failed to fetch positions: {response['stat']}")
            
            formatted_orderbook = []
            if response["stat"]=="Ok":
                order_book = response['data']
            else:
                return None, None
            for pos in order_book:
                if 'complete' in pos['ordSt']:
                    investment = (float(pos['avgPrc'])*int(pos['fldQty']))
                    order_qty = int(pos['fldQty'])
                    formatted_orderbook.append({
                        'symbol': pos['trdSym'],
                        'token': pos['tok'],
                        'quantity': order_qty,
                        'investment': investment,
                        'OrdNo': pos['nOrdNo'],
                        'ordSt': pos['ordSt'],
                        'avgPrc': pos['avgPrc'],
                        'ordDtTm': pos['ordDtTm']
                    })
            return formatted_orderbook
        except Exception as e:
            print(f"Error fetching order book data: {e}")
            return []


