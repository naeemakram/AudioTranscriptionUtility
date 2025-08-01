import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import threading
import tkinter as tk
from openai import OpenAI

# API Configuration - BULLETPROOF Setup
client = OpenAI(
    api_key=
    """
)

BARS = 50
RUN_INTERVAL_SECONDS = 30
running = False


def test_openai_connection():
    """Test OpenAI connection before starting the system"""
    try:
        print("🧪 Testing OpenAI connection...")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role":
                "system",
                "content":
                "You are a professional currency trader who uses Meta Trader 5."
            }, {
                "role": "user",
                "content": "Can we test connection?"
            }],
            max_tokens=2000,
            temperature=0.1)
        print("✅ OpenAI connection successful!")
        return True
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        return False


def safe_mt5_shutdown():
    """Close MetaTrader5 connection safely."""
    try:
        if mt5.is_initialized():
            mt5.shutdown()
            print("MT5 connection shut down successfully.")
    except Exception as e:
        print(f"Error shutting down MT5: {e}")


def get_market_data(symbol):
    """Get historical market data from MetaTrader5."""
    try:
        if not mt5.initialize():
            print("❌ Failed to initialize MT5")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(
                f"❌ Symbol {symbol} not found. Trying alternative formats...")
            alternatives = [f"{symbol}.m", f"#{symbol}", f"{symbol}.raw"]
            for alt in alternatives:
                if mt5.symbol_info(alt):
                    symbol = alt
                    print(f"✅ Found symbol as: {symbol}")
                    break
            else:
                print(
                    f"❌ Symbol {symbol} not available. Try EURUSD, GBPUSD, or USDJPY"
                )
                return None

        if not mt5.symbol_select(symbol, True):
            print(f"❌ Failed to select symbol {symbol}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, BARS)
        if rates is None or len(rates) == 0:
            print(f"❌ No M1 data available for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f"✅ Got {len(df)} M1 bars for {symbol}")
        return df
    except Exception as e:
        print(f"❌ Data error for {symbol}: {e}")
        return None


def prepare_market_data_for_gpt(df, symbol_name):
    """Prepare market data for GPT analysis."""
    if df is None or df.empty:
        return "No market data available for analysis."

    df_summary = df[['time', 'open', 'high', 'low', 'close',
                     'tick_volume']].tail(BARS)
    data_string = f"Market data for {symbol_name} (last {len(df_summary)} bars):\n"

    for index, row in df_summary.iterrows():
        digits = 5
        if mt5.symbol_info(symbol_name):
            digits = mt5.symbol_info(symbol_name).digits
        data_string += (f"Time: {row['time'].strftime('%Y-%m-%d %H:%M')}, "
                        f"Open: {row['open']:.{digits}f}, "
                        f"High: {row['high']:.{digits}f}, "
                        f"Low: {row['low']:.{digits}f}, "
                        f"Close: {row['close']:.{digits}f}, "
                        f"Volume: {int(row['tick_volume'])}\n")

    data_string += (
        "\nAnalyze this data for a 1-minute trade. "
        "Provide decision (BUY/SELL/WAIT) and confidence (0-100%). "
        "Format: DECISION: [BUY/SELL/WAIT], CONFIDENCE: [X]%")
    return data_string


def get_gpt_decision(market_data_df, symbol_name):
    """Get trading decision from GPT with multiple model fallback."""
    models_to_try = ["gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]

    for model in models_to_try:
        try:
            prompt_text = prepare_market_data_for_gpt(market_data_df,
                                                      symbol_name)
            print(f"Trying {model} for {symbol_name}...")

            response = client.chat.completions.create(model=model,
                                                      messages=[{
                                                          "role":
                                                          "user",
                                                          "content":
                                                          prompt_text
                                                      }],
                                                      max_tokens=100,
                                                      temperature=0.1)

            gpt_raw_response = response.choices[0].message.content.strip(
            ).upper()
            print(f"✅ {model} Response: {gpt_raw_response}")

            # Parse response
            decision = "WAIT"
            confidence = 0.0

            if "DECISION:" in gpt_raw_response and "CONFIDENCE:" in gpt_raw_response:
                try:
                    parts = gpt_raw_response.split("DECISION:")[1].split(
                        ", CONFIDENCE:")
                    decision_part = parts[0].strip()
                    confidence_part = parts[1].strip().replace('%', '')

                    if decision_part in ['BUY', 'SELL', 'WAIT']:
                        decision = decision_part
                        confidence = float(confidence_part)

                    confidence = np.clip(confidence, 0, 100)
                except Exception as parse_error:
                    print(f"⚠️ Parse error: {parse_error}")
                    if "BUY" in gpt_raw_response:
                        decision = "BUY"
                    elif "SELL" in gpt_raw_response:
                        decision = "SELL"
                    confidence = 50.0
            else:
                if "BUY" in gpt_raw_response:
                    decision = "BUY"
                elif "SELL" in gpt_raw_response:
                    decision = "SELL"
                confidence = 50.0

            # Format final decision
            if decision == "BUY" and confidence >= 70:
                return f"🔥 STRONG BUY ({model}) - {confidence:.1f}%"
            elif decision == "SELL" and confidence >= 70:
                return f"🔥 STRONG SELL ({model}) - {confidence:.1f}%"
            elif decision == "WAIT" or confidence < 50:
                return f"⏳ WAIT ({model}) - {confidence:.1f}%"
            else:
                return f"✅ {decision} ({model}) - {confidence:.1f}%"

        except Exception as e:
            print(f"❌ {model} failed: {str(e)[:100]}")
            continue

    return "❌ All AI models failed - Check API connection"


def update_gui_safe(widget, **kwargs):
    """Safe GUI update from any thread."""
    try:
        widget.after(0, lambda: widget.config(**kwargs))
    except Exception as e:
        print(f"GUI update error: {e}")


def trading_analysis_loop(symbol, output_label, time_label, score_label,
                          quality_label):
    """Main trading analysis loop."""
    global running

    if not mt5.initialize():
        update_gui_safe(output_label, text="❌ MT5 connection failed", fg="red")
        return

    signal_counter = 0

    try:
        while running:
            current_time = time.strftime("%H:%M:%S")
            update_gui_safe(time_label, text=f"🕐 Time: {current_time}")

            market_data = get_market_data(symbol)
            if market_data is None:
                update_gui_safe(output_label,
                                text=f"❌ {symbol}: No data available",
                                fg="orange")
                time.sleep(RUN_INTERVAL_SECONDS)
                continue

            update_gui_safe(score_label,
                            text="AI Analysis in Progress...",
                            fg="cyan")
            update_gui_safe(quality_label,
                            text="Awaiting AI Decision...",
                            fg="yellow")

            trading_decision = get_gpt_decision(market_data, symbol)
            signal_counter += 1

            if "STRONG BUY" in trading_decision:
                signal_color = "lime"
            elif "STRONG SELL" in trading_decision:
                signal_color = "red"
            elif "WAIT" in trading_decision:
                signal_color = "orange"
            else:
                signal_color = "yellow"

            update_gui_safe(output_label,
                            text=f"{symbol}: {trading_decision}",
                            fg=signal_color)
            print(f"🎯 SIGNAL #{signal_counter}: {trading_decision}")

            time.sleep(RUN_INTERVAL_SECONDS)

    except Exception as e:
        update_gui_safe(output_label,
                        text=f"❌ System Error: {str(e)[:40]}",
                        fg="red")
        print(f"❌ Critical error: {e}")
    finally:
        pass


def start_trading_system(symbol_entry, output_label, time_label, score_label,
                         quality_label, start_button, stop_button):
    """Start the trading system."""
    global running

    # Test API connection first
    if not test_openai_connection():
        update_gui_safe(output_label,
                        text="❌ OpenAI API connection failed!",
                        fg="red")
        return

    trading_symbol = symbol_entry.get().upper().strip()
    if not trading_symbol:
        update_gui_safe(output_label,
                        text="⚠️ Please enter a trading symbol",
                        fg="orange")
        return

    if running:
        update_gui_safe(output_label,
                        text="⚠️ System already running",
                        fg="orange")
        return

    if not mt5.initialize():
        update_gui_safe(output_label, text="❌ MT5 connection failed", fg="red")
        return

    running = True
    update_gui_safe(start_button, state="disabled")
    update_gui_safe(stop_button, state="normal")
    update_gui_safe(output_label, text="🚀 AI System starting...", fg="white")

    analysis_thread = threading.Thread(target=trading_analysis_loop,
                                       args=(trading_symbol, output_label,
                                             time_label, score_label,
                                             quality_label))
    analysis_thread.daemon = True
    analysis_thread.start()

    print(f"🚀 AI Trading system started for {trading_symbol}")


def stop_trading_system(start_button, stop_button, output_label):
    """Stop the trading system."""
    global running

    if running:
        running = False
        update_gui_safe(start_button, state="normal")
        update_gui_safe(stop_button, state="disabled")
        update_gui_safe(output_label,
                        text="⏹️ Trading system stopped",
                        fg="yellow")
        print("⏹️ Trading system stopped")
    else:
        update_gui_safe(output_label,
                        text="⚠️ System not running",
                        fg="orange")


# GUI Setup
root = tk.Tk()
root.title("🤖 AI Trading System - Multi-Model GPT Analysis")
root.geometry("700x570")
root.configure(bg="black")

main_title = tk.Label(
    root,
    text="🔥 AI Trading System with Multi-Model GPT Analysis 🔥",
    fg="cyan",
    bg="black",
    font=("Arial", 18, "bold"))
main_title.pack(pady=15)

subtitle = tk.Label(root,
                    text="Auto-Fallback: GPT-4 Turbo → GPT-4 → GPT-3.5 Turbo",
                    fg="gold",
                    bg="black",
                    font=("Arial", 11))
subtitle.pack(pady=5)

input_section = tk.Frame(root, bg="black")
input_section.pack(pady=15)

symbol_label = tk.Label(input_section,
                        text="Enter Trading Symbol:",
                        fg="white",
                        bg="black",
                        font=("Arial", 13))
symbol_label.pack()

symbol_input = tk.Entry(input_section,
                        font=("Arial", 13),
                        width=12,
                        justify='center')
symbol_input.pack(pady=8)
symbol_input.insert(0, "EURUSD")

time_display = tk.Label(root,
                        text="🎯 Multi-Model AI System Ready",
                        fg="gray",
                        bg="black",
                        font=("Arial", 11))
time_display.pack(pady=2)

score_display = tk.Label(root,
                         text="AI Analysis Status: Idle",
                         fg="cyan",
                         bg="black",
                         font=("Arial", 11))
score_display.pack(pady=3)

quality_display = tk.Label(root,
                           text="Confidence: N/A",
                           fg="yellow",
                           bg="black",
                           font=("Arial", 11))
quality_display.pack(pady=3)

main_output = tk.Label(
    root,
    text="Enter symbol and start - AI will analyze with model fallback",
    fg="white",
    bg="black",
    font=("Arial", 15, "bold"))
main_output.pack(pady=25)

control_section = tk.Frame(root, bg="black")
control_section.pack(pady=15)

start_button = tk.Button(control_section,
                         text="🚀 Start Multi-Model AI Trading",
                         font=("Arial", 13),
                         bg="green",
                         fg="white",
                         width=28)
start_button.pack(side=tk.LEFT, padx=8)

stop_button = tk.Button(control_section,
                        text="⏹️ Stop System",
                        font=("Arial", 13),
                        bg="red",
                        fg="white",
                        width=15,
                        state="disabled")
stop_button.pack(side=tk.LEFT, padx=8)

start_button.config(command=lambda: start_trading_system(
    symbol_input, main_output, time_display, score_display, quality_display,
    start_button, stop_button))
stop_button.config(command=lambda: stop_trading_system(
    start_button, stop_button, main_output))

info_section = tk.Frame(root, bg="black")
info_section.pack(pady=15)

info_line1 = tk.Label(info_section,
                      text="🎯 Strong Buy/Sell = AI High Confidence Signal",
                      fg="lime",
                      bg="black",
                      font=("Arial", 10))
info_line1.pack()

info_line2 = tk.Label(info_section,
                      text="⏳ Wait = AI Low Confidence or No Clear Signal",
                      fg="orange",
                      bg="black",
                      font=("Arial", 10))
info_line2.pack()

info_line3 = tk.Label(
    root,
    text="🔄 Auto-Fallback: Tries GPT-4 Turbo → GPT-4 → GPT-3.5 Turbo",
    fg="cyan",
    bg="black",
    font=("Arial", 10))
info_line3.pack(pady=2)

info_line4 = tk.Label(
    info_section,
    text=
    f"⚡ Updates every {RUN_INTERVAL_SECONDS} seconds | Multi-Model AI Analysis",
    fg="gold",
    bg="black",
    font=("Arial", 10))
info_line4.pack()


def on_closing():
    """Ensure system stops and MT5 closes properly."""
    global running

    if running:
        running = False
        print("Stopping trading loop...")
        time.sleep(0.5)

    if root:
        root.destroy()
        print("GUI destroyed.")

    safe_mt5_shutdown()
    print("👋 Application closed")


root.protocol("WM_DELETE_WINDOW", on_closing)

if __name__ == "__main__":
    print("🚀 Multi-Model AI Trading System Starting...")
    print("✅ Your API key is configured")
    print("🔄 Auto-Fallback: GPT-4 Turbo → GPT-4 → GPT-3.5")
    print("✅ Connection test will run before trading")
    print("💡 Make sure MT5 is running and logged in")
    print("💡 Try symbols: EURUSD, GBPUSD, USDJPY")
    root.mainloop()
