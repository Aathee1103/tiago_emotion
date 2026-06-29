import matplotlib
matplotlib.use('TkAgg') # Force interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.dates as mdates

def plot_heart_rate(csv_file):
    try:
        df = pd.read_csv(csv_file, header=None, names=['Time', 'BPM'])
        df['Time'] = pd.to_datetime(df['Time'])
        df = df.sort_values('Time')
        
        plt.figure(figsize=(10, 6))
        plt.plot(df['Time'], df['BPM'], marker='o', linestyle='-', color='b')
        
        plt.title('Heart Rate Over Time')
        plt.xlabel('Time')
        plt.ylabel('Beats Per Minute (BPM)')
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.gcf().autofmt_xdate()
        
        plt.tight_layout()
        plt.show() # This will now open a window
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    plot_heart_rate('heart_rate.csv')