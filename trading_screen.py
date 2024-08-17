from kivymd.uix.screen import MDScreen
#from kivy.properties import ObjectProperty
from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.anchorlayout import AnchorLayout
from kivymd.uix.textfield import MDTextField
from kivy.metrics import dp, sp
from functools import partial
from kivy.clock import Clock
#import threading
from threading import Thread, Lock
import pandas as pd
import pytz
from datetime import datetime, timedelta
import json
import os
import time
from kivymd.uix.button import MDFlatButton
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.button import MDFloatingActionButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.uix.label import Label
from kivy.properties import NumericProperty
from kivymd.uix.card import MDSeparator
import random
from kivy.uix.anchorlayout import AnchorLayout
from kivy.utils import platform


def get_storage_path():
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except ImportError:
            # Fallback if running in desktop environment
            return os.path.dirname(os.path.abspath(__file__))
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_master_file(client):
    df = pd.DataFrame()
    current_date = datetime.now(pytz.timezone('Asia/Kolkata')).date()
    max_date = current_date + timedelta(days=7)
    segment = ['NFO', 'BFO']
    for seg in segment:
        url = client.scrip_master(exchange_segment=seg)
        d = pd.read_csv(url)
        d.columns = [c.strip() for c in d.columns.values.tolist()]
        column = ['pSymbol', 'pExchSeg', 'pSymbolName', 'pTrdSymbol', 'pInstType', 'lExpiryDate', 'lLotSize', 'pOptionType', 'dStrikePrice;', 'lFreezeQty']
        d = d[column]
        
        if seg in ['NFO', 'CDS']:
            d['ExpiryDate'] = pd.to_datetime(d['lExpiryDate'].astype(int) + 315513000, unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.date
        elif seg in ['BFO', 'MCX']:
            d['ExpiryDate'] = pd.to_datetime(d['lExpiryDate'].astype(int), unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.date
        d['StrikePrice'] = d['dStrikePrice;'] / 100
        d['pSymbolName'] = d['pSymbolName'].replace('BSXOPT', 'SENSEX')
#        d = d[(d['pSymbolName'].isin(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']))].copy() #Keep only  options of relevant index
        d = d[(d['pSymbolName'].isin(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX'])) & 
              (d['ExpiryDate'] >= current_date) & (d['ExpiryDate'] <= max_date)].copy()
        d = d.sort_values('ExpiryDate')
        d = d.drop_duplicates(subset=['pSymbolName', 'StrikePrice', 'pOptionType'], keep='first')
        df = pd.concat([df, d], ignore_index=True)
    # Drop unused columns
    df = df.drop(columns=['lExpiryDate', 'dStrikePrice;'])
    print("Master script downlaoded")
    return df

def fetch_master_file_with_retry(client, max_retries=3, retry_delay=5):
    for attempt in range(max_retries):
        try:
            return get_master_file(client)
        except Exception as e:
            print(f"Error fetching master file (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise Exception("Failed to fetch master file after multiple attempts")

def extract_option_data(df):
    option_data = {}
    for index in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
        index_data = df[df['pSymbolName'] == index]
        option_data[index] = {
            'expiry_dates': sorted(index_data['ExpiryDate'].unique().tolist()),
            'strike_prices': sorted(index_data['StrikePrice'].unique().tolist()),
            'options': index_data.to_dict('records')
        }
    return option_data

def save_option_data(option_data):
     storage_path = get_storage_path()
     with open(f'{storage_path}/option_data.json', 'w') as f:
        json.dump({
            'date': datetime.now(pytz.timezone('Asia/Kolkata')).date().isoformat(),
            'data': option_data
        }, f, default=str)

def load_option_data():
    storage_path = get_storage_path()
    filename = f'{storage_path}/option_data.json'
    if not os.path.exists(filename):
        return None
    with open(filename, 'r') as f:
        saved_data = json.load(f)
    saved_date = datetime.fromisoformat(saved_data['date']).date()
    current_date = datetime.now(pytz.timezone('Asia/Kolkata')).date()
    if saved_date < current_date:
        return None  # Data is outdated
    return saved_data['data']

class SellDialogContent(MDBoxLayout):
    def __init__(self, quantity, stop_loss, take_profit, trailing, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.size_hint_y = None
        self.height = "320dp"
        
        self.quantity_input = MDTextField(
            hint_text=f"Enter lots to sell (max {quantity})",
            input_filter="int",
            size_hint_y=None,
            height="48dp"
        )
        self.add_widget(self.quantity_input)

        self.stop_loss_input = MDTextField(
            hint_text="Stop Loss",
            input_filter="float",
            text=str(stop_loss) if stop_loss else "",
            size_hint_y=None,
            height="48dp"
        )
        self.add_widget(self.stop_loss_input)

        self.take_profit_input = MDTextField(
            hint_text="Take Profit",
            input_filter="float",
            text=str(take_profit) if take_profit else "",
            size_hint_y=None,
            height="48dp"
        )
        self.add_widget(self.take_profit_input)

        self.trailing_input = MDTextField(
            hint_text="Trailing Stop Loss",
            input_filter="float",
            text=str(trailing) if trailing else "",
            size_hint_y=None,
            height="48dp"
        )
        self.add_widget(self.trailing_input)

        checkbox_layout = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height="48dp",
            spacing="12dp"
        )
        checkbox_layout.add_widget(MDLabel(text="Sell All Immediately"))
        self.sell_all_checkbox = MDCheckbox(
            size_hint=(None, None),
            size=(48, 48),
            pos_hint={'center_x': .5, 'center_y': .5}
        )
        checkbox_layout.add_widget(self.sell_all_checkbox)
        self.add_widget(checkbox_layout)

class TradingScreen(MDScreen):
    def __init__(self, **kwargs):
        print("Initializing TradingScreen")  # Debug statement
        super(TradingScreen, self).__init__(**kwargs)
        self.index_mapping = {
            "NIFTY": {"pSymbol": "26000", "pExchSeg": "nse_cm", "freez_qty": 1800},
            "BANKNIFTY": {"pSymbol": "26009", "pExchSeg": "nse_cm", "freez_qty": 900},
            "FINNIFTY": {"pSymbol": "26037", "pExchSeg": "nse_cm", "freez_qty": 1800},
            "SENSEX": {"pSymbol": "1", "pExchSeg": "bse_cm", "freez_qty": 1000},
            "MIDCPNIFTY": {"pSymbol": "26074", "pExchSeg": "nse_cm", "freez_qty": 2800}
        }
        self.api_instance = None
        self.option_data = None
        self.subscribed_symbols = set()
        self.current_prices = {}
        self.positions = []  # Store positions data
        self.websocket_thread = None
        self.refresh_interval = 1  # Adjust as needed
        self.ui_update_event = None
        self.lot_sizes = {"BANKNIFTY": 15, "NIFTY": 25, "FINNIFTY": 25, "MIDCPNIFTY": 50, "SENSEX": 10}
        self.index_dropdown = None
        self.option_dropdown = None
        self.call_option_dropdown = None
        self.put_option_dropdown = None
        self.position_update_event = None
        self.index_update_event = None
        self.position_table = None        
        self.position_row_indices = {}  # To keep track of row indices for each symbol
        self.sell_dialog = None
        self.position_widgets = {}
        self.positions_table = None
        self.price_lock = Lock()

    def set_api_instance(self, consumer_key):
        print("Setting API instance in TradingScreen")
        self.consumer_key = consumer_key
#        self.api_instance  = self.kotakapi.get_active_session(consumer_key)
        if hasattr(self.kotakapi, 'get_active_session'):
            self.api_instance = self.kotakapi.get_active_session(consumer_key)
        else:
            print("Warning: kotakapi does not have get_active_session method")
            self.api_instance = self.kotakapi  # Fallback to using kotakapi directly
        print(f"API instance type: {type(self.api_instance)}")
        print(f"Consumer key: {self.consumer_key}")
        self.load_option_data()
        self.start_websocket()
        self.setup_index_dropdown()
        self.load_positions()

    def on_enter(self):
        print("On_Enter: Entering TradingScreen")
        if self.api_instance and not self.option_data:
            print("Loading option data")
            self.load_option_data()
        if not self.websocket_thread or not self.websocket_thread.is_alive():
            print("On_Enter: Starting websocket")
#            self.start_websocket()            
#        self.refresh_data()
        self.setup_index_dropdown()

    def refresh_data(self):
        self.load_positions() # Manual refresh

    def show_index_menu(self):
        if not self.index_dropdown:
            self.setup_index_dropdown()
            self.index_dropdown.open()
        elif self.index_dropdown:
            self.index_dropdown.open()
        else:
            print("Index dropdown is not initialized.")

    def show_option_menu(self, option):
        if self.ids.index_button.text == "Select Index":
            self.show_error_dialog("Please select an index first.")
            return
        if not hasattr(self, 'call_option_dropdown') or not hasattr(self, 'put_option_dropdown'):
            self.update_option_dropdown(self.ids.index_button.text)
        if option == "Call":
            self.call_option_dropdown.open()
        elif option == "Put":
            self.put_option_dropdown.open()
        else:
            self.show_error_dialog("Option dropdown is not available. Make sure an index is selected first.")

    def load_option_data(self):
        self.option_data = load_option_data()
#        print(self.option_data)
        if self.option_data is None:
            print("Option data not found or outdated. Fetching new data...")
            try:
                df = fetch_master_file_with_retry(self.api_instance)
                self.option_data = extract_option_data(df)
                save_option_data(self.option_data)
                print("Fetched and saved new option data")
            except Exception as e:
                print(f"Failed to fetch new option data: {e}")
                self.show_error_dialog("Failed to fetch option data. Please try again later.")
        else:
            print("Loaded current option data from file")
        self.setup_index_dropdown()

    def load_account_info(self):
        try:
            if hasattr(self.kotakapi, 'get_balance'):
                balance = self.kotakapi.get_balance(self.consumer_key)
            elif self.api_instance:
                f = self.api_instance.limits(segment="ALL", exchange="ALL",product="ALL")
                balance = float(f['Net'])
            else:
                print("Warning: No get_balance method found. Using mock balance.")            
#            balance = 52000
            self.ids.available_funds.text = f"Available Funds: ₹{balance:,.2f}"
        except Exception as e:
            print(f"Error fetching account balance: {e}")
            self.show_error_dialog("Failed to fetch account balance. Please try again.")

    def setup_index_dropdown(self):
        print("Setting up index dropdown")
        indices = list(self.index_mapping.keys())
        print(f"indices: {indices}")
        menu_items = [
            {
                "text": index,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=index: self.on_index_select(x),
            } for index in indices
        ]
        self.index_dropdown = MDDropdownMenu(
            caller=self.ids.index_button,
            items=menu_items,
            width_mult=4,
        )

    def on_index_select(self, index):
        self.ids.index_button.text = index
        self.index_dropdown.dismiss()
        self.update_option_dropdown(index)
        self.populate_closest_options(index)
        if not self.index_update_event:
            self.index_update_event = Clock.schedule_interval(self.update_index_and_option_prices, 1)

    def update_option_dropdown(self, index):
        if not self.option_data:
            self.load_option_data()
        print(index)
        index_info = self.index_mapping[index]
        current_price = self.get_current_price(index_info["pSymbol"])
#        current_price = 24600
        if current_price is None:
            print(f"Unable to get current price for {index}")
            return
        if (not self.option_data) or (index not in self.option_data):
            print(index)
            print(f"No option data available for {index}")
            return
        index_options = self.option_data[index]['options']
        current_date = datetime.now(pytz.timezone('Asia/Kolkata')).date()
        if index in ['BANKNIFTY', 'SENSEX']:
            range = 300
        elif index in['NIFTY','FINNIFTY'] :
            range = 150
        else:
            range = 100
        filtered_call_options = [
            opt for opt in index_options
#            if datetime.strptime(opt['ExpiryDate'], '%Y-%m-%d').date() >= current_date and
            if abs(float(opt['StrikePrice']) - float(current_price)) <= range and opt['pOptionType'] == 'CE'
        ]
        sorted_call_options = sorted(filtered_call_options, key=lambda x: float(x['StrikePrice']))
        call_menu_items = [
            {
#                "text": f"{opt['pTrdSymbol']} - {opt['ExpiryDate']} - {opt['StrikePrice']}",
                "text": f"{opt['StrikePrice']}",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=opt: self.on_option_select(x),
            } for opt in sorted_call_options
        ]
        self.call_option_dropdown = MDDropdownMenu(
            caller=self.ids.call_option_button,
            items=(call_menu_items),
            width_mult=4,
        )

        filtered_put_options = [
            opt for opt in index_options
#            if datetime.strptime(opt['ExpiryDate'], '%Y-%m-%d').date() >= current_date and
            if abs(float(opt['StrikePrice']) - float(current_price)) <= range and opt['pOptionType'] == 'PE'
        ]
        sorted_put_options = sorted(filtered_put_options, key=lambda x: float(x['StrikePrice']))
        put_menu_items = [
            {
#                "text": f"{opt['pTrdSymbol']} - {opt['ExpiryDate']} - {opt['StrikePrice']}",
                "text": f"{opt['StrikePrice']}",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=opt: self.on_option_select(x),
            } for opt in sorted_put_options
        ]
        self.put_option_dropdown = MDDropdownMenu(
            caller=self.ids.put_option_button,
            items=(put_menu_items),
            width_mult=4,
        )

#        for opt in filtered_call_options + filtered_put_options:         # Subscribe to live data for filtered options
#            self.subscribe_new_symbol(opt['pSymbol'], opt['pExchSeg'])



    def populate_closest_options(self, index):
        if not self.option_data or index not in self.option_data:
            return

        index_info = self.index_mapping[index]
        current_price = self.get_current_price(index_info["pSymbol"])
        if current_price is None:
            return

        options = self.option_data[index]['options']
        current_date = datetime.now(pytz.timezone('Asia/Kolkata')).date()
#        valid_options = [opt for opt in options if datetime.strptime(opt['ExpiryDate'], '%Y-%m-%d').date() >= current_date] # Filter options for the current date or later
        # Find closest call option
        closest_call = min(
            (opt for opt in options if opt['pOptionType'] == 'CE'),
            key=lambda x: abs(float(x['StrikePrice']) - current_price),
            default=None
        )
        # Find closest put option
        closest_put = min(
            (opt for opt in options if opt['pOptionType'] == 'PE'),
            key=lambda x: abs(float(x['StrikePrice']) - current_price),
            default=None
        )
        if closest_call:
            self.ids.call_option_button.text = closest_call['pTrdSymbol']
            self.subscribe_new_symbol(closest_call['pSymbol'], closest_call['pExchSeg'])
            self.update_option_info(closest_call)
        if closest_put:
            self.ids.put_option_button.text = closest_put['pTrdSymbol']
            self.subscribe_new_symbol(closest_put['pSymbol'], closest_put['pExchSeg'])
            self.update_option_info(closest_put)

    def on_option_select(self, option):
        if option['pOptionType'] == 'CE':
            self.ids.call_option_button.text = option['pTrdSymbol']
            self.call_option_dropdown.dismiss()
            self.update_option_info(option)
            self.subscribe_new_symbol(option['pSymbol'], option['pExchSeg'])
#            self.update_fund_required()
        elif option['pOptionType'] == 'PE':
            self.ids.put_option_button.text = option['pTrdSymbol']
            self.put_option_dropdown.dismiss()
            self.update_option_info(option)
            self.subscribe_new_symbol(option['pSymbol'], option['pExchSeg'])
#            self.update_fund_required()


    def update_option_info(self, option):
        if option['pOptionType'] == 'CE':
            self.ids.call_details.text = (
                f"Expiry: {option['ExpiryDate']}\n"
                f"Strike: {option['StrikePrice']}\n"
                f"Lot Size: {option['lLotSize']}"
            )
        elif option['pOptionType'] == 'PE':
            self.ids.put_details.text = (
                f"Expiry: {option['ExpiryDate']}\n"
                f"Strike: {option['StrikePrice']}\n"
                f"Lot Size: {option['lLotSize']}"
            )

    def get_current_price_new(self, token):
        return float(self.current_prices.get(token, 0))

    def get_current_price(self, symbol):
        price = self.current_prices.get(symbol)
        if price is not None:
            try:
                return float(price)
            except ValueError:
                print(f"Invalid price value for {symbol}: {price}")
        # If no price is available, return 0
#        print(f"No price available for {symbol}, returning 0")
        return 0
    
    def subscribe_to_index(self, index):
        if index in self.index_mapping:
            index_info = self.index_mapping[index]
            token = {"instrument_token": index_info["pSymbol"], "exchange_segment": index_info["pExchSeg"]}
            self.subscribe_symbol(token, is_index=True)
        else:
            print(f"Unknown index: {index}")

    def get_token_from_option_data(self, option):
        for index, data in self.option_data.items():
            for opt in data['options']:
                if opt['pTrdSymbol'] == option:
                    return {"instrument_token": opt['pSymbol'], "exchange_segment": opt['pExchSeg']}
        return None  # Return None if the option is not found

    def subscribe_new_symbol(self, symbol, exchange_segment):
        if symbol not in self.subscribed_symbols:
            token = {"instrument_token": symbol, "exchange_segment": exchange_segment}
            try:
                self.api_instance.subscribe(instrument_tokens=[token])
                self.subscribed_symbols.add(symbol)
                print(f"Subscribed to new symbol: {symbol}")
            except Exception as e:
                print(f"Error subscribing to {symbol}: {e}")

    def unsubscribe_symbol(self, instrument_token):
        if instrument_token in self.subscribed_symbols:
            token = self.subscribed_symbols[instrument_token]
            self.api_instance.un_subscribe(instrument_tokens=[token])
            del self.subscribed_symbols[instrument_token]
            print(f"Unsubscribed from {instrument_token}")
        else:
            print(f"Symbol {instrument_token} was not subscribed")

    def clear_all_subscriptions(self):
        tokens_to_unsubscribe = list(self.subscribed_symbols.values())
        if tokens_to_unsubscribe:
            self.api_instance.un_subscribe(instrument_tokens=tokens_to_unsubscribe)
        self.subscribed_symbols.clear()
        print("All subscriptions cleared")

    def get_subscribed_symbols(self):
        return list(self.subscribed_symbols.keys())

    def start_websocket(self):
        def on_message(message):
            for i in message['data']:
                if 'tk' in i and 'ltp' in i:
                    self.current_prices[i['tk']] = float(i['ltp'])
        def on_error(error):
            print(f"WebSocket error: {error}")
        def on_close(message):
            print("WebSocket connection closed", message)
        def on_open(message):
            print("WebSocket connection opened", message)

        self.api_instance.on_message = on_message
        self.api_instance.on_error = on_error
        self.api_instance.on_close = on_close
        self.api_instance.on_open = on_open

        # Prepare initial subscription tokens
        initial_tokens = [
            {"instrument_token": info['pSymbol'], "exchange_segment": info['pExchSeg']}
            for info in self.index_mapping.values()
        ]

        def start_subscription():
            try:
                self.api_instance.subscribe(instrument_tokens=initial_tokens)
                for token in initial_tokens:
                    self.subscribed_symbols.add(token['instrument_token'])
                print(f"Subscribed to indices: {', '.join(self.index_mapping.keys())}")
            except Exception as e:
                print(f"Error in initial subscription: {e}")

        # Start the WebSocket connection and initial subscription in a thread
        self.websocket_thread = Thread(target=start_subscription)
        self.websocket_thread.daemon = True
        self.websocket_thread.start()

    def extract_index_from_symbol(self, symbol):
        index_mapping = {
            "BANKNIFTY": "BANKNIFTY",
            "NIFTY": "NIFTY",
            "FINNIFTY": "FINNIFTY",
            "MIDCPNIFTY": "MIDCPNIFTY",
            "SENSEX": "SENSEX"
        }
        for index in index_mapping:
            if symbol.startswith(index):
                return index_mapping[index]
        return None

    def buy_sell_option(self, option, action):
        if option == "Call":
            if self.ids.call_option_button.text == "Select Call Option":
                return
            lots = int(self.ids.call_lots.text or 1)
            symbol = self.ids.call_option_button.text
        elif option == "Put":
            if self.ids.put_option_button.text == "Select Put Option":
                return
            lots = int(self.ids.put_lots.text or 1)
            symbol = self.ids.put_option_button.text

#        index = self.ids.index_button.text
        index = self.extract_index_from_symbol(symbol)
        lot_size = self.lot_sizes.get(index, 1)
#        quantity = lots * lot_size
        token = self.get_token_from_option_data(symbol)
#        current_price = self.get_current_price(token['instrument_token'])

        if index not in self.index_mapping:
            self.show_error_dialog(f"Invalid index: {index}")
            return
        index_info = self.index_mapping[index]
        data = {
            'symbol': symbol,
            'exchange_segment': token['exchange_segment'],
            'action': action,
            'lots': lots,
            'freez_qty': index_info['freez_qty'],
            'lot_size':lot_size
        }
        symbol, order_qty, investment = self.kotakapi.manual_buy_sell(self.consumer_key, data)
        if symbol and order_qty > 0:
            print(f"Bought {order_qty} of {symbol} for {investment:,.2f}")
            self.load_positions()  # Refresh positions after a successful buy
            if action == 'LONG':
                self.show_success_dialog(f"Successfully bought {order_qty} of {symbol} for ₹{investment:,.2f}")
            elif action == 'SHORT':
                self.show_success_dialog(f"Successfully sold {order_qty} of {symbol} for ₹{investment:,.2f}")

        else:
            self.show_error_dialog("Order execution failed. Please try again.")

    def create_positions_table(self):
        if not self.positions_table:
            self.positions_table = MDDataTable(
                size_hint=(1, None),
                height=400,  # Adjust as needed
                use_pagination=True,
                background_color_header="#65275d",
#                check = True,
                column_data=[
                    ("Symbol", dp(40)),
                    ("Qty", dp(20)),
                    ("LTP", dp(30)),
                    ("PnL", dp(30)),
                    ("SL", dp(30)),
                    ("TP", dp(30)),
                    ("TSL", dp(30))
                ],
                row_data=[],
                rows_num=10  # Adjust this to show more or fewer rows
            )
#            self.positions_table.bind(on_check_press=self.on_check_press)
            self.positions_table.bind(on_row_press=self.on_row_press)
            self.ids.positions_container.clear_widgets()
            self.ids.positions_container.add_widget(self.positions_table)

    def on_check_press(self, instance_table, current_row):
        try:
            self.show_sell_dialog(current_row[0], current_row[1])
        except Exception as e:
            print(f"Error in on_row_press: {e}")

    def on_row_press(self, instance_table, instance_row):
        try:
            row = self.positions_table.row_data[(instance_row.index)//6]
            self.show_sell_dialog(row[0], row[1])
        except Exception as e:
            print(f"Error in on_row_press: {e}")

    def update_total_pnl(self):
        total_pnl = 0  # Initialize total PnL
        total_pnl = sum(float(pos['new_pnl']) for pos in self.positions)
        # Optionally, you can change the color of the Total_PnL label based on its value
        if total_pnl > 0:
            self.ids.Total_PnL.text = f"Profit: ₹{total_pnl:.2f}" # Update the Total_PnL label
            self.ids.Total_PnL.theme_text_color = "Custom"
            self.ids.Total_PnL.text_color = [0, 1, 0, 1]  # Green color
        elif total_pnl < 0:
            self.ids.Total_PnL.text = f"Loss: ₹{total_pnl:.2f}" # Update the Total_PnL label
            self.ids.Total_PnL.theme_text_color = "Custom"
            self.ids.Total_PnL.text_color = [1, 0, 0, 1]  # Red color
 
    def update_positions_display(self):
        if not self.positions_table:
            self.create_positions_table()
        self.positions_table.row_data = [
            (
                pos['symbol'],
                str(pos['net_quantity']),
                f"{float(pos['ltp']):.2f}",
                f"{float(pos['new_pnl']):.2f}",
                f"{float(pos.get('stop_loss', 0)):.2f}",
                f"{float(pos.get('take_profit', 0)):.2f}",
                f"{float(pos.get('new_stop_loss', 0)):.2f}"
            )
            for pos in self.positions
        ]
        self.update_total_pnl()    

    def update_live_data(self, dt):
        if not self.positions_table:
            return
        updated = False
        for index, position in enumerate(self.positions):
            if float(position['net_quantity']) <= 0:
                continue  # Skip closed positions
            symbol = position['symbol']
            
            current_price = self.get_current_price(position['token'])
            if current_price is not None and current_price != position['ltp']:
                position['ltp'] = current_price
#                new_pnl = float(position['pnl']) + float(int(position['net_quantity']) * current_price)
                position['new_pnl'] = float(position['pnl']) + float(int(position['net_quantity']) * current_price)
                updated = True

                # Check for stop loss and take profit
                stop_loss = position.get('stop_loss', 0)
                take_profit = position.get('take_profit', 0)
#                print(f"Update_live_data- Symbol: {symbol}, LTP: {current_price}, PnL: {position['new_pnl']}, SL: {position.get('stop_loss', 0)}, TP: {position.get('take_profit', 0)}")
                trail = position.get('trail', 0)
                trail_diff = position.get('trail_diff', 0)
                new_stop_loss = position.get('new_stop_loss', 0)
                if trail > 0 and stop_loss > 0 and (current_price > new_stop_loss):
                    factor = int(float(current_price - trail_diff - stop_loss)//trail)
                    if factor > 1:
                        trail_stop_loss = float(stop_loss + (factor * trail))
                        if trail_stop_loss > new_stop_loss:
                            position['new_stop_loss'] = trail_stop_loss

                if (float(new_stop_loss) > 0 and current_price <= float(new_stop_loss)) or (float(take_profit) > 0 and current_price >= float(take_profit)):
                    self.execute_sell(symbol, abs(position['net_quantity']))
                
                self.positions_table.update_row(
                    self.positions_table.row_data[index],  # old row data
                    [position['symbol'], str(position['net_quantity']), f"{float(position['ltp']):.2f}", f"{float(position['new_pnl']):.2f}", f"{float(position.get('stop_loss', 0)):.2f}", f"{float(position.get('take_profit', 0)):.2f}", f"{float(position.get('new_stop_loss', 0)):.2f}"],  # new row data
                )

#        if updated:
#            self.update_positions_display()  # Refresh the entire table
        self.update_total_pnl()  


    def dismiss_sell_dialog(self, *args):
        if self.sell_dialog:
            self.sell_dialog.dismiss()

    def show_sell_dialog(self, symbol, available_qty):
        try:
            index = self.extract_index_from_symbol(symbol)
            lot_size = self.lot_sizes.get(index, 1)
            max_lots = int(float(available_qty)) // lot_size

            position = next((pos for pos in self.positions if pos['symbol'] == symbol), None)
            if not position:
                print(f"Error: Position for {symbol} not found")
                return
            stop_loss = position.get('stop_loss', 0)
            take_profit = position.get('take_profit', 0)
            trailing = position.get('trail', 0)

            print(f"Position : {position}")
            content = SellDialogContent(max_lots, stop_loss, take_profit, trailing)
            self.sell_dialog = None
            if not self.sell_dialog:
                self.sell_dialog = MDDialog(
                    title=f"Manage {symbol}",
                    type="custom",
                    content_cls=content, 
                    buttons=[
                        MDFlatButton(
                            text="CANCEL",
                            on_release=self.dismiss_sell_dialog
                        ),
                        MDFlatButton(
                            text="UPDATE/SELL",
                            on_release=lambda x: self.update_or_sell_position(symbol, max_lots)
                        ),
                    ],
                )
            else:
                self.sell_dialog.content_cls = content
                self.sell_dialog.title = f"Manage {symbol}"

            content.sell_all_checkbox.active = False   #  Ensure the checkbox is not checked by default
            content.stop_loss_input.text = str(stop_loss) if stop_loss else "" # Display current stop loss
            content.take_profit_input.text = str(take_profit) if take_profit else "" # Display current take profit
            self.sell_dialog.open()
        except Exception as e:
            print(f"Error in show_sell_dialog: {e}")            

    def update_or_sell_position(self, symbol, max_lots):
        try:
            # 1. Check if position is available
            position = next((pos for pos in self.positions if pos['symbol'] == symbol), None)
            position_index = next((index for index, pos in enumerate(self.positions) if pos['symbol'] == symbol), None)
            if not position:
                print(f"Error: Position for {symbol} not found")
                self.dismiss_sell_dialog()
                return          
            content = self.sell_dialog.content_cls
            sell_all = content.sell_all_checkbox.active
            lots_to_sell = int(content.quantity_input.text.strip() or 0)
            new_stop_loss = float(content.stop_loss_input.text.strip() or 0)
            new_take_profit = float(content.take_profit_input.text.strip() or 0)
            new_trail = float(content.trailing_input.text.strip() or 0)
            index = self.extract_index_from_symbol(symbol)
            lot_size = self.lot_sizes.get(index, 1)

            # 2. Check if sell all checkbox is ticked
            if sell_all:
                self.execute_sell(symbol, float(max_lots*lot_size))
                self.dismiss_sell_dialog()
                return
            # 3. If lots to sell entered, sell them first
            if lots_to_sell > 0:
                self.execute_sell(symbol, float(lots_to_sell*lot_size))
                self.dismiss_sell_dialog() # No need to update stop loss or take profit here as load_positions will refresh everything
                return
            # 4 & 5. Update stop loss and take profit if entered
            updated = False
            if new_stop_loss > 0 and new_stop_loss != position.get('stop_loss'):
                position['stop_loss'] = new_stop_loss
                position['new_stop_loss'] = new_stop_loss
                if new_trail > 0 and new_trail != position.get('trail'):
                    position['trail'] = new_trail
                    position['trail_diff'] = position['ltp'] - new_stop_loss
                updated = True
            if new_take_profit > 0 and new_take_profit != position.get('take_profit'):
                position['take_profit'] = new_take_profit
                updated = True
            if updated:
                print(f"Updated {symbol} - Stop Loss Updated: {position['stop_loss']}, Take Profit Updated: {position['take_profit']}")
                self.update_positions_display()
            self.dismiss_sell_dialog()
        except Exception as e:
            print(f"Error in update_or_sell_position: {e}")
            self.dismiss_sell_dialog()


    def execute_sell(self, symbol, net_quantity):
        index = self.extract_index_from_symbol(symbol)
        token = self.get_token_from_option_data(symbol)
        lot_size = self.lot_sizes.get(index, 1)
        index_info = self.index_mapping[index]
        lots = int(float(net_quantity) // lot_size)
        data = {
            'symbol': symbol,
            'exchange_segment': token['exchange_segment'],
            'action': 'SHORT',
            'lots': lots,
            'freez_qty': index_info['freez_qty'],
            'lot_size': lot_size
        }
        print("Execute_Sell", data)
        try:
            symbol, order_qty, investment = self.kotakapi.manual_buy_sell(self.consumer_key, data)
            if symbol:
                print(f"Sold {order_qty} of {symbol} for {investment:,.2f}")
                self.show_success_dialog(f"Successfully sold {order_qty} of {symbol} for ₹{investment:,.2f}")
            else:
                self.show_error_dialog("Sell order execution failed. Please try again.")
        except Exception as e:
            print(f"Error executing sell: {e}")
            self.show_error_dialog("Error executing sell. Please try again.")
        self.dismiss_sell_dialog()
        self.load_positions()  # Refresh positions after a successful sell

    def load_positions(self):
        self.load_account_info()
        net_quantity = 0
        try:
#            new_positions = [{'symbol': 'BANKNIFTY2480751400PE', 'token': '50201', 'net_quantity': 100, 'pnl': -2.25, 'ltp': 10, 'total_buy_amt': 5477.25, 'total_sell_amt': 5475.0, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'BANKNIFTY2480751400CE', 'token': '50197', 'net_quantity': 300, 'pnl': -5.25, 'ltp': 30, 'total_buy_amt': 5743.5, 'total_sell_amt': 5738.25, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'FINNIFTY2480623450PE', 'token': '48262', 'net_quantity': 0.0, 'pnl': -3.75, 'ltp': 50, 'total_buy_amt': 3746.25, 'total_sell_amt': 3742.5, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'MIDCPNIFTY2480512700PE', 'token': '43799', 'net_quantity': 0.0, 'pnl': 20.0, 'ltp': 60, 'total_buy_amt': 3450.0, 'total_sell_amt': 3470.0, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'SENSEX2480281100PE', 'token': '844415', 'net_quantity': 0.0, 'pnl': 53.5, 'ltp': 70, 'total_buy_amt': 33498.0, 'total_sell_amt': 33551.5, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'SENSEX2480281000PE', 'token': '844273', 'net_quantity': 0.0, 'pnl': 2468.5, 'ltp': 80, 'total_buy_amt': 42861.5, 'total_sell_amt': 45330.0, 'comb_multiplier': 1.0, 'precision': 2}, {'symbol': 'SENSEX2480281000CE', 'token': '844157', 'net_quantity': 0.0, 'pnl': -5133.0, 'ltp': 0, 'total_buy_amt': 40203.0, 'total_sell_amt': 35070.0, 'comb_multiplier': 1.0, 'precision': 2}]
            new_positions = self.kotakapi.get_position_data(self.consumer_key)
            print("Position Loaded:", new_positions)
#            if new_positions and self.positions != new_positions:
            if new_positions:
                # Add default values for stop_loss and take_profit
                for position in new_positions:
                    position['stop_loss'] = 0
                    position['take_profit'] = 0
                    position['trail'] = 0
                    position['new_stop_loss'] = 0
                    position['trail_diff'] = 0
                    position['new_pnl'] = position['pnl']      
                new_positions.sort(key=lambda x: abs(float(x['net_quantity'])), reverse=True)  # Sort positions by absolute value of net_quantity in descending order
                self.positions = new_positions
                net_quantity = sum(float(pos['net_quantity']) for pos in self.positions)
            self.update_positions_display()
            # Start or restart the regular updates
            if self.position_update_event:
                self.position_update_event.cancel()
            if net_quantity > 0:
#                print("Net_Qty", net_quantity)
                self.position_update_event = Clock.schedule_interval(self.update_live_data, 1)
        except Exception as e:
            print(f"Error fetching position data: {e}")
            self.show_error_dialog("Failed to fetch positions. Please try again.")
#        finally:
#            self.ids.loading_spinner.active = False

    def update_index_and_option_prices(self, dt):
        # Update index price
        selected_index = self.ids.index_button.text
        lot_size = self.lot_sizes.get(selected_index, 1)
        if selected_index != "Select Index":
            index_info = self.index_mapping.get(selected_index)
            if index_info:
                index_price = self.get_current_price(index_info["pSymbol"])
                if index_price is not None:
                    self.ids.index_price.text = f"Index Price: ₹{index_price:,.2f}"
                else:
                    self.ids.index_price.text = "Index Price: N/A"
            else:
                self.ids.index_price.text = "Index Price: N/A"

        # Update option price
        selected_call_option = self.ids.call_option_button.text
        if selected_call_option != "Select Call Option":
            token = self.get_token_from_option_data(selected_call_option)
            call_option_price = self.get_current_price(token['instrument_token'])
            lots = int(self.ids.call_lots.text or 1)
            if call_option_price is not None:
                self.ids.call_price.text = f"Call Price: ₹{call_option_price:,.2f}"
                self.ids.call_fund_required.text = f"Fund Required: ₹{(call_option_price * lots * lot_size):,.2f}"
            else:
                self.ids.call_price.text = "Call Price: N/A"
                self.ids.call_fund_required.text = "Fund Required: N/A"
        else:
            self.ids.call_price.text = "Call Price: -"
            self.ids.call_fund_required.text = "Fund Required: -"

        selected_put_option = self.ids.put_option_button.text
        if selected_put_option != "Select Put Option":
            token = self.get_token_from_option_data(selected_put_option)
            put_option_price = self.get_current_price(token['instrument_token'])
            lots = int(self.ids.put_lots.text or 1)
            if put_option_price is not None:
                self.ids.put_price.text = f"Put Price: ₹{put_option_price:,.2f}"
                self.ids.put_fund_required.text = f"Fund Required: ₹{(put_option_price * lots * lot_size):,.2f}"
            else:
                self.ids.put_price.text = "Put Price: N/A"
                self.ids.put_fund_required.text = "Fund Required: N/A"
        else:
            self.ids.put_price.text = "Put Price: -"
            self.ids.put_fund_required.text = "Fund Required: -"

    def show_error_dialog(self, message):
        dialog = MDDialog(
            title="Error",
            text=message,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())]

        )
        dialog.open()

    def show_success_dialog(self, message):
        dialog = MDDialog(
            title="Success",
            text=message,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())]
        )
        dialog.open()

    def on_leave(self):
        if self.api_instance:
            self.api_instance.close()


