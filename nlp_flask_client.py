import requests
import pandas as pd
import numpy as np
from pathlib import Path
import json
import utils
import csv
import datetime
import concurrent.futures
import socket
from dh_encryption import DiffieHellman, decrypt_data, encrypt_data, decrypt_file, encrypt_file
from io import BytesIO

# using the generated key

# https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04
# https://python-socketio.readthedocs.io/en/latest/server.html#standard-threads
# https://medium.com/swlh/implement-a-websocket-using-flask-and-socket-io-python-76afa5bbeae1

# https://www.techbeamers.com/python-tutorial-write-multithreaded-python-server/

# https://medium.com/hackernoon/3x-faster-than-flask-8e89bfbe8e4f

class NLPClient():
    def __init__(self, server_ip, server_port, keys_url="request-keys", request_shared_key="request-shared-key", stats_url="getStats", file_stats_url="getStatsFile", socket_port=-1):
        self.server_ip = server_ip
        self.server_port = server_port
        self.base_url =  f"http://{self.server_ip}:{self.server_port}"
        print(f"\nSERVER URL: {self.base_url}")
        self.keys_url = f"{self.base_url}/{keys_url}"
        self.shared_key_url = f"{self.base_url}/{request_shared_key}"
        self.keys = None
        self.stats_url = f"{self.base_url}/{stats_url}"
        self.file_stats_url = f"{self.base_url}/{file_stats_url}"
        self.socket = self.init_socket(self.server_ip, self.server_port) if socket_port < 0 else self.init_socket(self.server_ip, self.socket_port)
        self.write_csv_headers = True
        self.output_df = None
        self.add_df_cols = True
        self.csv_writer = None
        self.write_csv_headers = True
        self.request_keys()

    def request_keys(self, keys_url=None, shared_key_url=None):
        keys_url = self.keys_url if keys_url is None else keys_url
        shared_key_url = self.shared_key_url if shared_key_url is None else shared_key_url
        try:
            keys_data = requests.get(keys_url).json()
            print(f"Keys: {keys_data}")
            keys_params = {"local_private_key": keys_data["private_key"], "remote_public_key": keys_data["public_key"]}
            try:            
                shared_key_data = requests.get(shared_key_url, params=keys_params).json()
                keys_params.update(shared_key_data)
                self.keys = keys_params
                print(f"Shared Key: {shared_key_data}")
                return keys_params
            except Exception as e:
                print(f"Error requesting shared keys on {shared_key_url}:: {e}")
                return None
        except Exception as e:
            print(f"Error requesting keys on {keys_url}: {e}")
            return None

    def init_socket(self, socket_ip, socket_port):                
        sock = None
        try:            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        
            sock.connect((socket_ip, socket_port))
        except Exception as e:
            print(f"Could not create socket on {socket_ip}:{socket_port}: {e}")

    def socket_receive_json(self, s, msglen=10000):
        fragments = []
        while True: 
            chunk = s.recv(msglen)
            if not chunk: 
                break
            fragments.append(chunk)
        return json.loads("".join(fragments))

    def socket_send_json(self, s, msg, msglen=10000):
        totalsent = 0
        while totalsent < msglen:
            sent = s.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
    def socket_send_all_json(self, s, payload):
        socket.sendall(json.dumps(payload).encode('utf-8'))

    def get_text_stats(self, text_data, no_encryption=False, index_list=None):        
        if not no_encryption:
            text_data = encrypt_data(text_data, self.keys["shared_key"])
        if index_list is not None:
            payload={'text': text_data, 'id': index_list, "no_encryption":no_encryption}
        else:
            payload={'text': text_data, "no_encryption":no_encryption}
        try:          
            if self.socket is None:
                response = requests.post(self.stats_url, data=payload)
                # print(response.text)
                data = response.json()
                # print(f"Req: {data}")
            else:
                # socket_send(socket, json.dumps(payload).encode('utf-8'))
                # print(f"Sending Socket data")
                self.socket_send_all_json(payload)
                data = self.socket_receive_json(self.socket)
                # print(f"Received Socket: {data}")
            return data
        except Exception as e:
            print(f"Exception getting text stats: {e}")
            raise e

    def get_df_rows_stats(self, index_list, row_list, text_col_name, total_rows, no_encryption=False):   
        index_list = index_list if isinstance(index_list, list) else [index_list] 
        row_list = row_list if isinstance(row_list, list) else [row_list] 
        text_list = [row[text_col_name] for row in row_list]
        a = datetime.datetime.now()
        data = self.get_text_stats(text_list, no_encryption, index_list)
        b = datetime.datetime.now()    
        print(f"Index Range: {index_list[0]} - {index_list[len(index_list)-1]} / {total_rows}, Elapsed: {(b-a)}, Time: {utils.formatted_now(sepDate='/', sepTime=':', sep=' ')}")
        self.add_to_df(data, index_list)
        self.add_to_csv(data, row_list)

    def add_to_df(self, data_list, index_list):
        for index, data in zip(index_list, data_list):
            for key, value in data.items():
                if self.add_df_cols:
                    self.output_df[key] = 0 if type(value) == int or float else ""
                    self.add_df_cols = False
                self.output_df.at[index, key] = value

    def add_to_csv(self, data_list, row_list):    
        print(data_list[0])
        for data, row in zip(data_list, row_list):
            if self.write_csv_headers:
                print(f"CSV File Headers Written")
                self.csv_writer.writerow(list(data.keys())+self.output_df_cols)
                self.write_csv_headers = False                
            csv_row = list(data.values())
            for val in row:
                csv_row.append(val)
            # csv_row.append(row["idx"])
            self.csv_writer.writerow(csv_row)

    def slice_df(self, data_df, txt_type_col=None, txt_type_filter=None, rows_amount=None):
        sliced_df = data_df
        if txt_type_filter is not None and txt_type_col is not None:
            sliced_df = data_df[data_df[txt_type_col] == txt_type_filter]
        elif rows_amount is not None and rows_amount > 0:
            sliced_df = data_df.iloc[0:rows_amount]
        return sliced_df

    def encrypt_decrypt_file(self, input_filename, new_prefix="", decrypt=False):   
        new_file_name = new_prefix+'temp_file.csv'   
        file_handle = open(input_filename, 'rb')
        file_data = file_handle.read()
        file_handle.close()
        if decrypt:
            new_data = decrypt_file(file_data, self.keys["shared_key"])
        if decrypt:
            new_data = encrypt_file(file_data, self.keys["shared_key"])
        with open(new_file_name, 'wb') as new_f:
            new_f.write(new_data) 
        return new_file_name
        
    def analyse_file(self, input_filename, txt_col_name="text", limit_rows=0, no_encryption=False): 
        start = datetime.datetime.now()
        if not no_encryption:
            input_filename = self.encrypt_decrypt_file(input_filename, new_prefix="encrypted", decrypt=False)

        file_to_send=open(input_filename, 'rb') 
        payload={'txt_col_name': txt_col_name, "amount":limit_rows, "no_encryption":no_encryption}
        res = requests.post(self.file_stats_url, files={'file': file_to_send}, data=payload)    
        file_to_send.close()
        output_filename = "stats_"+Path(input_filename).stem+".csv"
        with open(output_filename, "wb") as f_res:
            f_res.write(res.content)
        if not no_encryption:
            output_filename = self.encrypt_decrypt_file(output_filename, new_prefix="decrypted", decrypt=False)        
        end = datetime.datetime.now()
        print(f"{utils.formatted_now(sepDate='/', sepTime=':', sep=' ')}\tFile Analysis Completed\t Execution Time: {end-start}")

    def analyse_dataframe(self, data_df, text_col_name, multi_threaded=True, multi_messages=True, threads_no=100, rows_per_call=10, no_encryption=False):    
        start = datetime.datetime.now()
        prefix = "mt_" if multi_threaded else "st_"
        prefix += "mr_" if multi_messages else "sr_"
        prefix += "rq_" if self.socket is None else "sk_"
        rows_per_call = rows_per_call if multi_messages else 1
        threads_no = threads_no if multi_threaded else 1
        output_file = open(prefix+"stats_result.csv", 'w', newline='', encoding='utf-8')
        self.output_df = data_df.copy()
        self.add_df_cols = True
        self.csv_writer = csv.writer(output_file, delimiter=',', quoting=csv.QUOTE_ALL)
        self.write_csv_headers = True       
        self.output_df["idx"] = range(0,len(self.output_df))
        self.output_df_cols = list(self.output_df.columns.values)
        
        total_rows = self.output_df.shape[0]
        total_rows_processed = 0

        print(f"{utils.formatted_now(sepDate='/', sepTime=':', sep=' ')}\tStarting Dataframe Analysis {'Multi' if multi_threaded else 'Single'}-Thread, {'Multi' if multi_messages else 'Single'}-Message, {'Requests' if socket is None else 'Socket'}, Rows per call [{rows_per_call}], Simultaneous calls [{threads_no}]. Total Rows: {total_rows}")
        res = []
        indeces = []
        rows = []
        if multi_threaded:
            with concurrent.futures.ThreadPoolExecutor() as executor: # optimally defined number of threads
                for index, row in self.output_df.iterrows():
                    try:
                        if row["idx"] <= 0:
                            processed_rows = 1
                            total_rows_processed += processed_rows
                            res.append(executor.submit(self.get_df_rows_stats, index, row, text_col_name, total_rows, no_encryption))
                            print(f"Waiting for FIRST future to init data, rows per call: {1}, calls sent: {len(res)}, total rows sent {processed_rows}, total rows processed {total_rows_processed}/{total_rows}, Index: {row['idx']}")
                            concurrent.futures.wait(res)
                            res = []
                        else:
                            if multi_messages:
                                indeces.append(index)
                                rows.append(row)     
                                if len(rows) >= rows_per_call:
                                    res.append(executor.submit(self.get_df_rows_stats, indeces, rows, text_col_name, total_rows, no_encryption))
                                    # print(f"Call {len(res)}, Packed {indeces}, Total: {len(indeces)}")
                                    indeces = []
                                    rows = []
                            else:
                                res.append(executor.submit(self.get_df_rows_stats, index, row, text_col_name, total_rows, no_encryption))

                            if len(res) >= threads_no:
                                processed_rows = (len(res)*rows_per_call)
                                total_rows_processed += processed_rows
                                print(f"Waiting for futures, rows per call: {rows_per_call}, calls sent: {len(res)}, total rows sent {processed_rows}, total rows processed {total_rows_processed}/{total_rows}, Index: {row['idx']}")
                                concurrent.futures.wait(res)
                                res = []
                    except Exception as e:
                        print(f"Error processing row {index}: {e}")
                if multi_messages and len(indeces) > 0:
                    processed_rows = (len(res)*rows_per_call)
                    total_rows_processed += processed_rows
                    res.append(executor.submit(self.get_df_rows_stats, indeces, rows, text_col_name, total_rows, no_encryption))
                    print(f"Waiting for last futures, rows per call: {rows_per_call}, calls sent: {len(res)}, total rows sent {processed_rows}, total rows processed {total_rows_processed}/{total_rows}")
                    concurrent.futures.wait(res)
                    res = []
        else:
            for index, row in self.output_df.iterrows():
                try:
                    if multi_messages:
                        indeces.append(index)
                        rows.append(row)                      
                        if len(rows) >= rows_per_call:
                            self.get_df_rows_stats(indeces, rows, text_col_name, total_rows, no_encryption)
                            indeces = []
                            rows = []
                    else:
                        self.get_df_rows_stats(index, row, text_col_name, total_rows, no_encryption)
                except Exception as e:
                    print(f"Error processing row {index}: {e}")
            if multi_messages and len(indeces) > 0:
                self.get_df_rows_stats(indeces, rows, text_col_name, total_rows, no_encryption)

        # print(result_df)
        output_file.close()
        end = datetime.datetime.now()
        print(f"{utils.formatted_now(sepDate='/', sepTime=':', sep=' ')}\tAnalysis Completed {'Multi' if multi_threaded else 'Single'}-Thread, {'Multi' if multi_messages else 'Single'}-Message, {'Requests' if socket is None else 'Socket'}, Rows per call [{rows_per_call}], Simultaneous calls [{threads_no}]. Total Rows: {total_rows}\t Execution Time: {end-start}")
        return self.output_df

