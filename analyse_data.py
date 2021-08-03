from nlp_flask_client import NLPClient
import pandas as pd

csv_filename = "messaging_data.csv"
data_df = pd.read_csv(csv_filename)

IP = "127.0.0.1" # Local
PORT = 5000 # Always running

multi_threaded=True
multi_messages=True
threads_no=20
rows_per_call = 13

client = NLPClient(IP, PORT)

# Testing with a single string
res = client.get_text_stats("Hey just testing this out", no_encryption=False)
print(res)
res = client.get_text_stats("Hey just testing this out", no_encryption=True)
print(res)


# this will send a file, get a new one and save it on the disk
# client.analyse_file(csv_filename, "msg_text")

# this will send the dataframe text rows one by one, get its stats back and return an update dataframe AND also write everything to a csv file
out = client.analyse_dataframe(client.slice_df(data_df, rows_amount=500), 'msg_text', True, True, threads_no, rows_per_call)
# out = client.analyse_dataframe(client.slice_df(data_df, rows_amount=500), 'msg_text', True, False, threads_no, rows_per_call)
# out = client.analyse_dataframe(client.slice_df(data_df, rows_amount=500), 'msg_text', False, True, threads_no, rows_per_call)
# out = client.analyse_dataframe(client.slice_df(data_df, rows_amount=500), 'msg_text', False, False, threads_no, rows_per_call)

# out.to_csv("pandas_stats_result.csv", index=False)

