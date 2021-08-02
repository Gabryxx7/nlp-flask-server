from nlp_flask_client import NLPClient
import pandas as pd

csv_filename = "messaging_data.csv"
data_df = pd.read_csv(csv_filename)

IP = "127.0.0.1" # Local
PORT = 5000 # Always running

multi_threaded=True
multi_messages=True
threads_no=100
calls_per_loop = 1000
rows_per_call = 15

client = NLPClient(IP, PORT)
 # this will send a file, get a new one and save it on the disk
# client.analyse_file(csv_filename, "msg_text")
 # this will send the dataframe text rows one by one, get its stats back and return an update dataframe AND also write everything to 
 # a csv file
# out = client.analyse_dataframe(data_df, 'msg_text', multi_threaded, multi_messages, threads_no, rows_per_call)
# out.to_csv("pandas_stats_result.csv", index=False)

res = client.get_text_stats("Hey just testing this out", no_encryption=False)
print(res)
res = client.get_text_stats("Hey just testing this out", no_encryption=True)
print(res)