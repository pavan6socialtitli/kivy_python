# screens/strategy_screen.py
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.button import MDFlatButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.label import MDLabel
from kivy.metrics import dp
from kivy.clock import Clock
import socketio
from functools import partial
import json
import time

class SellDialogContent(MDBoxLayout):
    def __init__(self, stop_loss, take_profit, trailing, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.size_hint_y = None
        self.height = "320dp"
        
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



class StrategyScreen(MDScreen):
    def __init__(self, **kwargs):
        super(StrategyScreen, self).__init__(**kwargs)
#        super().__init__(**kwargs)
        self.index_mapping = {
            "NIFTY": {"pSymbol": "26000", "pExchSeg": "nse_cm", "freez_qty": 1800},
            "BANKNIFTY": {"pSymbol": "26009", "pExchSeg": "nse_cm", "freez_qty": 900},
            "FINNIFTY": {"pSymbol": "26037", "pExchSeg": "nse_cm", "freez_qty": 1800},
            "SENSEX": {"pSymbol": "1", "pExchSeg": "bse_cm", "freez_qty": 1000},
            "MIDCPNIFTY": {"pSymbol": "26074", "pExchSeg": "nse_cm", "freez_qty": 2800}
        }
        self.api_instance = None
        self.option_data = None
        self.lot_sizes = {"BANKNIFTY": 15, "NIFTY": 25, "FINNIFTY": 25, "MIDCPNIFTY": 50, "SENSEX": 10}
        self.option_data = None
        self.consumer_key = None
        self.position_update_event = None
        self.index_dropdown = None
        self.timeframe_dropdown = None
        self.strategy_dropdown = None
        self.index_button = None
        self.timeframe_button = None
        self.strategy_button = None
        self.selected_index = ""
        self.selected_timeframe = ""
        self.selected_strategy = ""
        self.strategy_positions = []
        self.strategy_table = None
        self.sio = None
        self.websocket_connected = False
        self.retry_interval = 60  # Retry every 60 seconds
        self.setup_websocket()
#        self.create_strategy_table()

    def set_api_instance(self, consumer_key):
        print("Setting API instance in StrategyScreen")
        self.consumer_key = consumer_key
        if hasattr(self.kotakapi, 'get_active_session'):
            self.api_instance = self.kotakapi.get_active_session(consumer_key)
        else:
            print("Warning: kotakapi does not have get_active_session method")
            self.api_instance = self.kotakapi  # Fallback to using kotakapi directly

    def create_strategy_table(self):
        if not self.strategy_table:
            self.strategy_table = MDDataTable(
                size_hint=(1, None),
                height=300,  # Adjust as needed
                use_pagination=True,
                background_color_header="#65275d",
                column_data=[
                    ("Strategy", dp(30)),
                    ("Symbol", dp(30)),
                    ("Qty", dp(20)),
                    ("LTP", dp(30)),
                    ("PnL", dp(30)),
                    ("SL", dp(30)),
                    ("TP", dp(30)),
                    ("TSL", dp(30))
                ],
                row_data=[],
                rows_num=5  # Adjust this to show more or fewer rows
            )
            self.strategy_table.bind(on_row_press=self.on_row_press)
            self.ids.strategy_table_container.clear_widgets()
            self.ids.strategy_table_container.add_widget(self.strategy_table)

    def on_row_press(self, instance_table, instance_row):
        try:
            row = self.strategy_table.row_data[(instance_row.index)//6]
            if float(row[2]) > 0:
                self.show_sell_dialog(row[0])
        except Exception as e:
            print(f"Error in on_row_press: {e}")

    def show_index_menu(self, button):
        index_items = [
            {"text": index, "viewclass": "OneLineListItem", "on_release": lambda x=index: self.select_index(x)}
            for index in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]
        ]
        self.index_dropdown = MDDropdownMenu(caller=button, items=index_items, width_mult=4)
        self.index_dropdown.open()

    def show_timeframe_menu(self, button):
        timeframe_items = [
            {"text": tf, "viewclass": "OneLineListItem", "on_release": lambda x=tf: self.select_timeframe(x)}
            for tf in ["1 min", "5 min", "15 min"]
        ]
        self.timeframe_dropdown = MDDropdownMenu(caller=button, items=timeframe_items, width_mult=4)
        self.timeframe_dropdown.open()

    def show_strategy_menu(self, button):
        strategy_items = [
            {"text": strategy, "viewclass": "OneLineListItem", "on_release": lambda x=strategy: self.select_strategy(x)}
            for strategy in ["MACross", "MACD", "BB", "Break", "RSI"]
        ]
        self.strategy_dropdown = MDDropdownMenu(caller=button, items=strategy_items, width_mult=4)
        self.strategy_dropdown.open()

    def select_index(self, index):
        self.selected_index = index
        self.ids.index_button.text = index
        self.index_dropdown.dismiss()

    def select_timeframe(self, timeframe):
        self.selected_timeframe = timeframe
        self.ids.timeframe_button.text = timeframe
        self.timeframe_dropdown.dismiss()

    def select_strategy(self, strategy):
        self.selected_strategy = strategy
        self.ids.strategy_button.text = strategy
        self.strategy_dropdown.dismiss()

    def start_strategy(self):
        if self.selected_index and self.selected_timeframe and self.selected_strategy:
            if len(self.strategy_positions) >= 3:
                self.ids.strategy_status.text = "Strategy Status: Max limit reached (3)"
                return
#            combined_strategy = f"{self.selected_index}_{self.selected_timeframe}_{self.selected_strategy}"
            combined_strategy = f"{self.selected_index}_{self.selected_timeframe}_{self.selected_strategy}".replace(' ', '_')
            new_strategy = {
                'combined_strategy': combined_strategy,
                'index': self.selected_index,
                'timeframe': self.selected_timeframe,
                'strategy': self.selected_strategy,
                'symbol': None,
                'token': None,
                'fund': float(self.ids.fund.text or 0),
                'net_quantity': 0,
                'ltp': 0,
                'pnl': 0,
                'new_pnl': 0,
                'stop_loss': 0,
                'take_profit': 0,
                'trail': 0,
                'new_stop_loss': 0,
                'trail_diff': 0
            }
            self.strategy_positions.append(new_strategy)
            self.update_strategy_table()
            self.ids.strategy_status.text = f"Strategy Status: {self.selected_strategy} started"
        else:
            self.ids.strategy_status.text = "Strategy Status: Please select all options"

    def stop_strategy(self):
        if self.selected_index and self.selected_timeframe and self.selected_strategy:
            remove_strategy = next((pos for pos in self.strategy_positions 
                            if pos['strategy'] == self.selected_strategy and pos['index'] == self.selected_index 
                            and pos['timeframe'] == self.selected_timeframe), None)
            if remove_strategy:
                self.strategy_positions.remove(remove_strategy)
                self.update_strategy_table()
                self.ids.strategy_status.text = f"Strategy Status: {self.selected_strategy} stopped"
            else:
                self.ids.strategy_status.text = "Strategy Status: Selected strategy not found"
        else:
            self.ids.strategy_status.text = "Strategy Status: Please select all options"


    def update_strategy_table(self):
        self.strategy_positions.sort(key=lambda x: abs(float(x['net_quantity'])), reverse=True)  # Sort positions by absolute value of net_quantity in descending order
        if not self.strategy_table:
            self.create_strategy_table()
        if self.strategy_table:
            self.strategy_table.row_data = [
                (
                    f"{pos['combined_strategy']}",
                    pos['symbol'] or '-',
                    str(pos['net_quantity']),
                    f"{pos['ltp']:.2f}",
                    f"{pos['new_pnl']:.2f}",
                    f"{pos['stop_loss']:.2f}",
                    f"{pos['take_profit']:.2f}",
                    f"{pos['new_stop_loss']:.2f}"
                )
                for pos in self.strategy_positions
            ]

    def stop_all_strategies(self):
        self.stop_live_updates()
        self.strategy_positions.clear()
        self.update_strategy_table()
        self.ids.strategy_status.text = "Strategy Status: All strategies stopped"

    def setup_websocket(self):
        self.sio = socketio.Client()
        
        @self.sio.on('connect')
        def on_connect():
            print("Connected to strategy server")
            self.websocket_connected = True
            self.update_connection_status()

        @self.sio.on('disconnect')
        def on_disconnect():
            print("Disconnected from strategy server")
            self.websocket_connected = False
            self.update_connection_status()

        @self.sio.on('strategy_signal')
        def on_strategy_signal(data):
            try:
    #            print(f"Received signal: {data}")
                signal_data = json.loads(data)
                combined_strategy = f"{signal_data['Index']}_{signal_data['TimeFrame']}_{signal_data['Strategy']}".replace(' ', '_')
                if combined_strategy in [pos['combined_strategy'] for pos in self.strategy_positions]:
                    Clock.schedule_once(partial(self.process_strategy_signal, signal_data))
    #            Clock.schedule_once(partial(self.process_strategy_signal, data))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Received data: {data}")
            except Exception as e:
                print(f"Error processing strategy signal: {e}")
                print(f"Received data: {data}")


        self.attempt_websocket_connection()

    def attempt_websocket_connection(self, dt=None):
        if not self.websocket_connected:
            try:
#                self.sio.connect('http://localhost:5000')
                self.sio.connect('ws://ec2-3-91-75-20.compute-1.amazonaws.com:3000')
                print("Successfully connected to strategy server")
                self.websocket_connected = True
                self.update_connection_status()
            except Exception as e:
                print(f"Failed to connect to strategy server: {e}")
                print(f"Will retry in {self.retry_interval} seconds")
                Clock.schedule_once(self.attempt_websocket_connection, self.retry_interval)

    def update_connection_status(self):
        if hasattr(self.ids, 'connection_status'):
            self.ids.connection_status.text = f"Connected to Strategy Server" if self.websocket_connected else "Not connected to strategy server"

    def process_strategy_signal(self, data, dt):
        strategy = data.get('Strategy')
        index = data.get('Index')
        signal = data.get('Signal')
        timeframe = data.get('TimeFrame')
#        combined_strategy = f"{index}_{timeframe}_{strategy}"
        combined_strategy = f"{index}_{timeframe}_{strategy}".replace(' ', '_')
        # Find the corresponding strategy position
        position = next((pos for pos in self.strategy_positions 
                     if pos['combined_strategy'] == combined_strategy), None)

        if position:
            # Execute the trade
            option = "Call" if signal == "LONG" else "Put"
            trade_action = "LONG"
            symbol = self.get_closest_options(index, option)
            token = self.get_token_from_option_data(symbol)
            print(f"symbol: {symbol} & Token: {token}")
            index_info = self.index_mapping[index]
            lot_size = self.lot_sizes.get(index, 1)
            if token['instrument_token'] not in self.subscribed_symbols:
                self.subscribe_new_symbol(token['instrument_token'], token['exchange_segment'])
            # Retry mechanism for getting a valid current price
            max_retries = 3
            for _ in range(max_retries):
                current_price = self.get_current_price(token['instrument_token'])
                if current_price is not None and current_price > 0:
                    break
                time.sleep(1)  # Wait for 1 second before retrying
            if current_price is None or current_price == 0:
                self.show_error_dialog(f"Unable to get valid price for {symbol}")
                return
            available_fund = self.load_account_balance()
            strategy_fund = float(position['fund'])
            fund = min(available_fund, strategy_fund)
            lots = int((fund / current_price) // lot_size)
            print(f"current_price: {current_price}, available_fund: {available_fund}, strategy_fund: {strategy_fund}, lots: {lots}")
            if lots > 0:
                data = {
                    'symbol': symbol,
                    'exchange_segment': token['exchange_segment'],
                    'action': signal,
                    'lots': lots,
                    'freez_qty': index_info['freez_qty'],
                    'lot_size': lot_size
                }
                symbol, order_qty, investment = self.kotakapi.manual_buy_sell(self.consumer_key, data)
                if symbol and order_qty > 0:
                    position['symbol'] = symbol
                    position['net_quantity'] = order_qty
                    position['pnl'] = investment
                    position['token'] = token['instrument_token']
                    self.load_positions()
                    self.update_strategy_table()             # Update strategy table
                    self.stop_live_updates()
                    if self.strategy_positions:  # Only start updates if there are active strategies
                        self.position_update_event = Clock.schedule_interval(self.update_live_data, 1)
                    else:
                        self.show_error_dialog("No Strategy Subscribed")
                else:
                    self.show_error_dialog(f"Order not executed for signal: {position['combined_strategy']}")
            else:
                self.show_error_dialog(f"Alloted Fund {fund} is less than required for strategy execution")


    def stop_live_updates(self):
        if self.position_update_event:
            self.position_update_event.cancel()
            self.position_update_event = None

    def update_live_data(self, dt):
#        print("Live Updated Started")
        if not self.strategy_table:
            return
        for index, position in enumerate(self.strategy_positions):
            if float(position['net_quantity']) <= 0:
                continue  # Skip closed positions
            symbol = position['symbol']
            current_price = self.get_current_price(position['token'])
#            print("current_price:", current_price)

            if current_price is not None and current_price != position['ltp'] and float(position['net_quantity']) > 0:
#                position['ltp'] = current_price
                new_pnl = float(position['pnl']) + float(int(position['net_quantity']) * current_price)
                position['new_pnl'] = new_pnl

                # Check for stop loss and take profit
                stop_loss = position.get('stop_loss', 0)
                take_profit = position.get('take_profit', 0)
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

                self.strategy_table.update_row(
                    self.strategy_table.row_data[index],  # old row data
                    [position['combined_strategy'], position['symbol'], str(position['net_quantity']), f"{float(current_price):.2f}", f"{float(new_pnl):.2f}", f"{float(position.get('stop_loss', 0)):.2f}", f"{float(position.get('take_profit', 0)):.2f}", f"{float(position.get('new_stop_loss', 0)):.2f}"],  # new row data
                )


    def execute_sell(self, position):
        symbol = position['symbol']
        net_quantity = position['net_quantity']
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
        for update_position in self.strategy_positions:
            if update_position['combined_strategy'] == position['combined_strategy']:
                update_position['net_quantity'] = float(0)
                update_position['pnl'] = update_position['new_pnl']
                update_position['stop_loss'] = float(0)
                update_position['take_profit'] = float(0)

        self.update_strategy_table()
        self.load_positions()  # Refresh positions after a successful sell


    def dismiss_sell_dialog(self, *args):
        if self.sell_dialog:
            self.sell_dialog.dismiss()

    def show_sell_dialog(self, combined_strategy):
        try:
            position = next((pos for pos in self.strategy_positions 
                    if pos['combined_strategy'] == combined_strategy), None)

            if not position:
                print(f"Error: Position for {combined_strategy} not found")
                return
            
            index = self.extract_index_from_symbol(position['symbol'])
            lot_size = self.lot_sizes.get(index, 1)
            max_lots = int(float(position['net_quantity'])) // lot_size
            stop_loss = position.get('stop_loss', 0)
            take_profit = position.get('take_profit', 0)
            trailing = position.get('trail', 0)

            print(f"Position : {position}")
            content = SellDialogContent(stop_loss, take_profit, trailing)
            self.sell_dialog = None
            if not self.sell_dialog:
                self.sell_dialog = MDDialog(
                    title=f"Manage {combined_strategy}",
                    type="custom",
                    content_cls=content, 
                    buttons=[
                        MDFlatButton(
                            text="CANCEL",
                            on_release=self.dismiss_sell_dialog
                        ),
                        MDFlatButton(
                            text="UPDATE/SELL",
                            on_release=lambda x: self.update_or_sell_position(combined_strategy)
                        ),
                    ],
                )
            else:
                self.sell_dialog.content_cls = content
                self.sell_dialog.title = f"Manage {combined_strategy}"

            content.sell_all_checkbox.active = False   #  Ensure the checkbox is not checked by default
            content.stop_loss_input.text = str(stop_loss) if stop_loss else "" # Display current stop loss
            content.take_profit_input.text = str(take_profit) if take_profit else "" # Display current take profit
            self.sell_dialog.open()
        except Exception as e:
            print(f"Error in show_sell_dialog: {e}")            

    def update_or_sell_position(self, combined_strategy):
        try:
            # 1. Check if position is available
            position = next((pos for pos in self.strategy_positions if pos['combined_strategy'] == combined_strategy), None)
            index = self.extract_index_from_symbol(position['symbol'])
            lot_size = self.lot_sizes.get(index, 1)            
            max_lots = int(float(position['net_quantity'])) // lot_size
#            position_index = next((index for index, pos in enumerate(self.strategy_positions) if pos['combined_strategy'] == combined_strategy), None)
            if not position:
                print(f"Error: Position for {combined_strategy} not found")
                self.dismiss_sell_dialog()
                return          
            content = self.sell_dialog.content_cls
            sell_all = content.sell_all_checkbox.active
#            lots_to_sell = int(content.quantity_input.text.strip() or 0)
            new_stop_loss = float(content.stop_loss_input.text.strip() or 0)
            new_take_profit = float(content.take_profit_input.text.strip() or 0)
            new_trail = float(content.trailing_input.text.strip() or 0)
            # 2. Check if sell all checkbox is ticked
            if sell_all:
                self.execute_sell(position)
                self.dismiss_sell_dialog()
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
                print(f"Updated {combined_strategy} - Stop Loss Updated: {position['stop_loss']}, Take Profit Updated: {position['take_profit']}")
                self.update_strategy_table()
            self.dismiss_sell_dialog()
        except Exception as e:
            print(f"Error in update_or_sell_position: {e}")
            self.dismiss_sell_dialog()


    def get_closest_options(self, index, option):
        if not self.option_data or index not in self.option_data:
            return
        index_info = self.index_mapping[index]
        current_price = self.get_current_price(index_info["pSymbol"])
#        current_price = 50092
        if current_price is None or current_price==0:
            return
        options = self.option_data[index]['options']
        # Find closest call option
        if option == 'Call':
            closest_call = min(
                (opt for opt in options if opt['pOptionType'] == 'CE'),
                key=lambda x: abs(float(x['StrikePrice']) - current_price),
                default=None
            )
            return closest_call['pTrdSymbol']
        if option == 'Put':
            # Find closest put option
            closest_put = min(
                (opt for opt in options if opt['pOptionType'] == 'PE'),
                key=lambda x: abs(float(x['StrikePrice']) - current_price),
                default=None
            )
            return closest_put['pTrdSymbol']

    def load_account_balance(self):
        try:
            if hasattr(self.kotakapi, 'get_balance'):
                balance = self.kotakapi.get_balance(self.consumer_key)
                return balance
            elif self.api_instance:
                f = self.api_instance.limits(segment="ALL", exchange="ALL",product="ALL")
                balance = float(f['Net'])
                return balance
            else:
                self.show_error_dialog("Warning: No get_balance method found")            
        except Exception as e:
            print(f"Error fetching account balance: {e}")
            self.show_error_dialog("Failed to fetch account balance. Please try again.")

    def get_current_price(self, symbol):
#        return self.parent.ids.trading_screen.current_prices.get(symbol, 0)
        return self.current_prices.get(symbol, 0)

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

    def on_enter(self):
        # This method is called when the screen is entered
        if not self.websocket_connected:
            self.attempt_websocket_connection()

    def on_leave(self):
        if self.sio:
            self.sio.disconnect()
