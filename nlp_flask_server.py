import sys
import os
from numpy.lib.arraysetops import isin
from argparse import ArgumentParser
sys.path.insert(1, './tendims')
sys.path.insert(2, './complexity')
sys.path.insert(3, './sentiment')
sys.path.insert(4, './empathy')

import logging
import json
import numpy as np
import wget
import pickle
import oyaml as yaml

from flask import Flask, request, redirect , jsonify, send_file, send_from_directory, safe_join, abort
from flask.json import JSONEncoder
from flask_cors import CORS
from flask_socketio import SocketIO, send, emit
import uuid
import pandas as pd
from cryptography.fernet import Fernet

from complexity import ComplexityClassifier
from sentiment import SentimentClassifier
from success import SuccessPredictor
from tendims import TenDimensionsClassifier
from empathy import empathy_processing
from werkzeug.utils import secure_filename
from werkzeug.datastructures import  FileStorage

from dh_encryption import DiffieHellman, decrypt_data, encrypt_data, decrypt_file, encrypt_file

import sys
import urllib
import urllib.request
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)

class Engine():
    class Models:
        All = "all"
        Sentiment = "sentiment"
        TenDims = "tendims"
        Success = "success"
        Complexity = "complexity"
        Empathy = "empathy"     

    def register_model(self, model_name, model_fun):
        self.models_map[model_name] = model_fun
    
    def get_model_methods(self, model_name):
        fun_list = []
        if model_name == Engine.Models.All:
            fun_list = list(self.models_map.values())
        else:
            fun_list = self.models_map[model_name]
        return fun_list

    def __init__(self, logger, load_ten_dims=True):
        self.models_map = {}
        self.ip_keys_dict = {}
        self.using_encryption = True
        self.no_key_error_msg = 'Connection is not secure, request a shared key first'
        self.wrong_key_error_msg = 'The shared key is not the same'
        self.dh = DiffieHellman()
                
        #### Complexity Models ####
        logger.info('Loading complexity models...')
        self.ic_model_file = 'complexity/models/Vocab+FullPOS_xbgoost.model'
        self.liwc_dictionary_file = 'complexity/data/LIWC2007_English100131.dic'
        self.model_complexity = ComplexityClassifier(self.ic_model_file, self.liwc_dictionary_file)
        self.register_model(Engine.Models.Complexity, self.get_complexity)
        logger.info('Complexity models loaded')
        #####################
        
        # #### Ten Dimensions Models ####
        if load_ten_dims:
            logger.info('Loading tenDims models...')
            self.models_dir = 'tendims/models/lstm_trained_models'
            self.embeddings_dir = 'tendims/embeddings'  # change urls to embeddings dir
            self.success_model_file = 'tendims/models/meeting_success/xgboost_10dims_success_prediction_model_v0.81.dat'
            # Success is not available
            self.model_tendim = TenDimensionsClassifier(models_dir=self.models_dir, embeddings_dir=self.embeddings_dir)
            self.success_predictor = SuccessPredictor(self.success_model_file) # Sucess prediction
            self.register_model(Engine.Models.TenDims, self.get_ten_dims)
            logger.info('Tend dims models loaded')
        #####################

        # self.empathy_model_file = './empathy/models/Vocab+FullPOS+LIWCtrained_XGboost_model_99perc.pickle'
        # self.empathy_ic_model_file = './empathy/models/Vocab+FullPOS_xbgoost.pickle'
        # self.empathy_scorer = empathy_processing.EmpathyScorer(self.empathy_model_file, self.empathy_ic_model_file)
        # self.register_model(Engine.Models.Empathy, self.empathyIC_from_texts)
        #####################

        #### Sentiment Models ####
        logger.info('Loading sentiment model...')
        self.model_sentim = SentimentClassifier()
        self.register_model(Engine.Models.Sentiment, self.get_sentiment)
        logger.info('Sentiment models loaded')
        #####################    
    

    def generate_keys(self, ip_address, logger):        
        self.ip_keys_dict[ip_address] = {}
        client_private_key, client_public_key = self.dh.get_private_key(), self.dh.gen_public_key()
        server_private_key, server_public_key = self.dh.get_private_key(), self.dh.gen_public_key()
        self.ip_keys_dict[ip_address]["client"] = {"private_key": client_private_key, "public_key": client_public_key}
        self.ip_keys_dict[ip_address]["server"] = {"private_key": server_private_key, "public_key": server_public_key}
        return {"private_key": client_private_key, "public_key": client_public_key, 'server_public_key':server_public_key}

    def generate_shared_keys(self, ip_address, local_private_key, remote_public_key, logger):
        client_shared_key = DiffieHellman.gen_shared_key_static(local_private_key, remote_public_key)
        server_shared_key = DiffieHellman.gen_shared_key_static(self.ip_keys_dict[ip_address]["server"]["private_key"], self.ip_keys_dict[ip_address]["server"]["public_key"])
        self.ip_keys_dict[ip_address]["client"]["shared_key"] = client_shared_key
        self.ip_keys_dict[ip_address]["server"]["shared_key"] = server_shared_key
        return client_shared_key
    
    # https://dev.to/ruppysuppy/implementing-end-to-end-encryption-in-your-cross-platform-app-3a2k
    # https://dev.to/ruppysuppy/implementing-end-to-end-encryption-in-your-cross-platform-app-part-2-cgg
    def check_request_key(self, ip_address, logger):    
        if ip_address not in self.ip_keys_dict:
            logger.error(self.no_key_error_msg)
            return 400, self.no_key_error_msg
        elif "shared_key" not in self.ip_keys_dict[ip_address]["server"] or "shared_key" not in self.ip_keys_dict[ip_address]["client"]:
            logger.error(self.wrong_key_error_msg)
            return 400, self.wrong_key_error_msg
        return 200, None


    def encrypt_decrypt_file(self, ip_address, folder, filename, logger, new_prefix="", decrypt=False):
        code, error_text = self.check_request_key(ip_address, logger)
        if code >= 400:
            return code, error_text        
        try:
            with open(os.path.join(folder, filename), 'rb') as enc_file:
                file_data = enc_file.read()
            if self.using_encryption:
                temp_filename = new_prefix+'_temp_file_data.csv'
                client_shared_key = self.ip_keys_dict[ip_address]["client"]["shared_key"]  
                if decrypt:
                    new_data = decrypt_file(file_data, client_shared_key)
                else:
                    new_data = encrypt_file(file_data, client_shared_key)
                with open(os.path.join(folder, temp_filename), 'wb') as dec_file:
                    dec_file.write(new_data) 
                try:
                    os.remove(os.path.join(folder, filename))    
                except:
                    print(f"Error removing file {filename}")   
                filename = temp_filename 
                if decrypt:
                    logger.debug(f"\n\nReceived encrypted File, decrypted using {ip_address} key {client_shared_key}")
                else:
                    logger.debug(f"\n\nFile Encrypted using {ip_address} key {client_shared_key}")
            else:
                logger.debug(f"\n\n: Received non encrypted File from {ip_address}")
            return 200, filename
        except Exception as e:
            error_text = f"\n\n Something went wrong while decrypting/encrypting the file {filename}: {e}"
            logger.error(error_text)
            return 400, error_text

    def get_decrypted_text(self, ip_address, text, method, logger):
        code, error_text = self.check_request_key(ip_address, logger)
        if code >= 400:
            return code, error_text        
        try:
            if engine.using_encryption:
                client_shared_key = engine.ip_keys_dict[ip_address]["client"]["shared_key"] 
                text = decrypt_data(text, client_shared_key)
                logger.debug(f"\n\n{method}: Received encrypted Text, decrypted using {ip_address} key {client_shared_key}: {text}")
            else:
                logger.debug(f"\n\n{method}: Received plain Text from {ip_address}: {text}")
            return 200, text
        except Exception as e:
            error_text = f"\n\n{method}: Something went wrong while getting the request's text {e}"
            logger.error(error_text)
            return 400, error_text

    def get_ten_dims(self, text, logger):  
        if USE_TEN_DIMS:
            # you can give in input one string of text
            # dimensions = None extracts all dimensions
            tendim_scores = engine.model_tendim.compute_score(text, dimensions=None)
            success_probability = engine.success_predictor.predict_success(tendim_scores)
            tendim_scores['success'] = float(success_probability)
        else:        
            tendim_scores = {'conflict': 0, 'fun': 0, 'identity': 0, 'knowledge': 0, 'power': 0, 'romance': 0, 'similarity': 0, 'status': 0, 'support': 0, 'trust': 0}
            tendim_scores['success'] = 0
        return tendim_scores
        
    def get_sentiment(self, text, logger):  
        return self.model_sentim.get_sentiment(text)
    
    def get_complexity(self, text, logger):  
        return self.model_complexity.get_complexity(text)
    
    def get_empathy(self, text, logger):
        avg_empathy, avg_ic, scored_text_list = engine.empathy_scorer.empathyIC_from_texts(text)
        return {'Average_Empathy': avg_empathy , 'Average_IC':avg_ic}

    def calculate_stats(self, texts, text_ids, stat_method, logger):
        if not isinstance(stat_method, list):
            stat_method = [stat_method]
        returnAll = []
        for txt, txt_id in zip(texts,text_ids):
            return_data = {}
            return_data["server_text_id"] = txt_id
            # return_data["server_text_data"] = str(txt)
            for stat_fun in stat_method:
                return_data.update(stat_fun(txt, logger))
            returnAll.append(return_data)
        return returnAll        

    def call_model_from_text(self, ip_address, text, no_encryption, method, logger):
        try:
            logger.debug(f"Text Getting decrypted text")     
            if not isinstance(text, list):
                text = [text]      

            retCode = 200        
            if not no_encryption:
                retCode, text = engine.get_decrypted_text(ip_address, text, method, logger)

            if retCode == 200:
                text_id = range(0, len(text))
                ret = engine.calculate_stats(text, text_id, self.get_model_methods(method), logger)
                return ret, retCode
            else:
                error_msg = f"\n\nText {method}: Something went wrong while calculating {method} stats. Code: {retCode}"
                logger.error(f"Error {retCode}\n{error_msg}\n{text}")
                return {"message": error_msg, "error_info":text, "status": retCode}, retCode
        except Exception as e:
            logger.error(f"Exception in Text {method}:{e}")
            return {"message": f"Internal Server Error in Text {method}", "error_info":str(e), "status": 500}, 500

    def call_model_from_request(self, flask_request, method, logger):
        try:   
            text = flask_request.form.getlist('text')
            if len(text) <= 0:
                text = [flask_request.form.get('text')]

            no_encryption = flask_request.form.get('no_encryption', False)
            retCode = 200
            if not no_encryption:
                retCode, text = engine.get_decrypted_text(flask_request.remote_addr, text, method, logger)   

            text_id = flask_request.form.getlist('id')
            if len(text_id) <= 0:
                text_id = [flask_request.form.get('id')]

            logger.info(f"Text stats request from {flask_request.remote_addr}. Encrypted: {not no_encryption}. List len: {len(text)}") 
            if retCode == 200:
                ret = engine.calculate_stats(text, text_id, self.get_model_methods(method), logger)
                return ret, retCode
            else:
                error_msg = f"\n\nRequest {method}: Something went wrong while calculating {method} stats. Code: {retCode}"
                logger.error(f"Error {retCode}\n{error_msg}\n{text}")
                return {"message": error_msg, "error_info":text, "status": retCode}, retCode
        except Exception as e:
            logger.error(f"Exception in Request {method}:{e}")
            return {"message": f"Internal Server Error in Request {method}", "error_info":str(e), "status": 500}, 500
            
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 

parser = ArgumentParser()
parser.add_argument('-c', nargs='?', const="config.yaml", type=str)
args = parser.parse_args()
config_filename = args.c
# config_filename = "config5000.yaml"
global config
try:
    config = yaml.safe_load(open(config_filename))
except:
    config = {}

UPLOAD_FOLDER = config.get("upload_folder", './uploaded_files/')
ALLOWED_EXTENSIONS = config.get("allowed_extensions", {'csv', 'txt', 'dat', 'json'})
IP = config.get("ip", "0.0.0.0")
PORT = config.get("port", 5000)
USE_TEN_DIMS = config.get("use_ten_dims", True)
LOG_FILENAME = config.get("log_filename", "flask_log.log")

app = Flask(__name__)
with open(LOG_FILENAME, 'w'):
    pass
handler = logging.FileHandler(LOG_FILENAME)  # Create the file logger
app.logger.addHandler(handler)             # Add it to the built-in logger
app.logger.setLevel(logging.DEBUG)         # Set the log level to debug
app.json_encoder = CustomJSONEncoder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)
engine = Engine(app.logger, USE_TEN_DIMS)


@app.route("/request-keys", methods=["GET"])
def request_keys():
    method = "Request Keys"
    try:
        retCode = 200
        ip_address = request.remote_addr
        keys_dict = engine.generate_keys(ip_address, app.logger)
        keys_dict["status"] = retCode
        return jsonify(keys_dict), retCode
    except Exception as e:
        app.logger.error(f"Exception in {method}:{e}")
        return jsonify({"message": f"Internal Server Error in {method}", "error_info":str(e), "status": 500}), 500

@app.route("/request-shared-key", methods=["GET"])
def request_shared_key():
    method = "Request Shared Key"
    try:
        retCode = 200
        ip_address = request.remote_addr
        try:
            local_private_key = request.args.get("local_private_key")
            remote_public_key = request.args.get("remote_public_key")
            client_shared_key = engine.generate_shared_keys(ip_address, local_private_key, remote_public_key, app.logger)
        except Exception as e:
            retCode = 400
            return jsonify({"message": "Invalid shared key", "error_info":str(e), "status": retCode}), retCode
        return jsonify({"shared_key": client_shared_key, "status": retCode}), retCode
    except Exception as e:
        app.logger.error(f"Exception in {method}:{e}")
        return jsonify({"message": f"Internal Server Error in {method}", "error_info":str(e), "status": 500}), 500
    

@app.route("/getStats", methods=['POST'])
def getStats():
    ret_data, code = engine.call_model_from_request(request, Engine.Models.All, app.logger)
    return jsonify(ret_data), code

@app.route("/getStatsFile", methods=['POST'])
def getStatsFile():
    no_encryption = str(request.form.get('no_encryption')) != "False" # No clue why the boolean is returned as a string... But just in case I converted it to a string every time
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"message": f"No file submitted", "error_info":f"No file submitted", "status": 400}), 400
    file = request.files['file']
    # If the user does not select a file, the browser submits an empty file without a filename.
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)                
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        if not no_encryption:
            code, filename = engine.encrypt_decrypt_file(request.remote_addr, UPLOAD_FOLDER, filename, app.logger, new_prefix="decrypted", decrypt=True)
    
    txt_col = request.form["txt_col_name"]    
        
    amount = int(request.form.get("amount", 0))   
    data_df = pd.read_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))    
    except:
        print(f"Error removing file {filename}")
    # remove file
    data_df["idx"] = range(0,len(data_df))
    app.logger.info(f"File stats request from {request.remote_addr}. Encrypted: {not no_encryption}. Row col: {txt_col}, limit: {amount}, rows: {len(data_df)}") 
    output_filename = os.path.splitext(filename)[0]
    output_filename = UPLOAD_FOLDER+output_filename+"_pandas_res.csv"
    initialized = False
    for index, row in data_df.iterrows():
        ret_data, code = engine.call_model_from_text(request.remote_addr, str(row[txt_col]), True, Engine.Models.All, app.logger)
        if code == 200 :
            for key, value in ret_data[0].items():
                if not initialized:
                    data_df[key] = 0 if type(value) == int or float else ""
                    initialized = True
                data_df.at[index, key] = value
        else:
            app.logger.error(f"{ret_data}\t{index}\t{row[txt_col]}")
        if amount > 0 and index >= amount:
            break
    data_df.to_csv(output_filename)
    if not no_encryption:
        code, output_filename = engine.encrypt_decrypt_file(request.remote_addr, UPLOAD_FOLDER, output_filename, app.logger, new_prefix="encrypted", decrypt=False)
    try:
        return send_file(output_filename, attachment_filename=output_filename+"_pandas_res.csv")
    except Exception as e:
        app.logger.error(f"Exception in files stats:{e}")
        return jsonify({"message": f"Internal Server Error in files stats", "error_info":str(e), "status": 500}), 500

@app.route("/tenDimensions", methods=['POST'])
def tenDimensions():
    ret_data, code = engine.call_model_from_request(request, Engine.Models.TenDims, app.logger)
    return jsonify(ret_data), code
            
@app.route("/complexity", methods=['POST'])
def complexity():
    ret_data, code = engine.call_model_from_request(request, Engine.Models.Complexity, app.logger)
    return jsonify(ret_data), code

@app.route("/sentiment", methods=['POST'])
def sentiment():
    ret_data, code = engine.call_model_from_request(request, Engine.Models.Sentiment, app.logger)
    return jsonify(ret_data), code
        
@app.route("/empathy", methods=['GET'])
def empathy():
    ret_data, code = engine.call_model_from_request(request, Engine.Models.Sentiment, app.logger)
    return jsonify(ret_data), code

@socketio.on('json')
def handle_json(json):
    app.logger.info('received json: ' + str(json))
    # data = engine.call_model(json, "All", app.logger)
    send(json.dumps({"test":0}), json=True)

@socketio.on('message')
def handle_message(message):
    app.logger.info('received message: ' + str(message))
    send(message)

if __name__ == '__main__':
    CORS(app)
    app.run(host="0.0.0.0",port=5000,threaded=True)
    socketio.run(app)
    app.run()

# Run gunicorn
# sudo nohup sudo gunicorn3 --workers 30 --timeout 0 --bind 0.0.0.0:5000 wsgi:app &
# sudo nohup sudo gunicorn3 --threads 100 --timeout 0 --bind 0.0.0.0:5000 wsgi:app &
# sudo pkill -P [PID]
# ps -ef | grep gun