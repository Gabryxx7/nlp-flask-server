## Flask NLP microservice

** **NOTE: Empathy, TenDims success and Complexity are NOT currently available** **


It is not uncommon that researchers or data scientists need to run some ML tool, and often it's multiple people in the same team.
So I spent some time whipping up a decently-structured and modular Flask-based server that can receive:
- A single string
- A list of strings
- A file with a specified text column

I am no security expert so I did what I could and so the server supports:
- E2EE encryption with a Diffie-Hellman key-exchange
- The encryption works on both files and strings
- The data is encrypted with a "simple" XOR algorithm, nothing too fancy

At the moment, this server implemented the following `GET` end-points:
- `/request-keys`: It returns a pair private and public key
- `/request-shared-key` Given a `local_private_key` and a `remote_public_key` it returns a `shared_key`

The ML models can be called through these `POST` end-points:
- `/getStats`: Calculates scores from all the available ML end-points for the text (or list of texts) in `text` and their ids in `text_id`
- `/getStatsFile`: Same as above but for files. Need to specify a `txt_col_name`
- `/tenDimensions`:  Calculates the TenDimensions [link to github repo](https://github.com/lajello/tendimensions) for the text (or list of texts) in `text` and their ids in `text_id`
- `/complexity`:  Calculates Integrative Complexity (IC), from the paper "The Languge of Dialogue is Complex" from Alexander Robertson, Luca Maria Aielloand Daniele Quercia [ARXIV link](https://arxiv.org/abs/1906.02057/), made publicly available at [https://social-dynamics.net/ic/](https://social-dynamics.net/ic/) and LIWC scores (from python packages `liwc` and `nltk`) for the text (or list of texts) in `text` and their ids in `text_id`
- `/sentiment`:  Calculates the sentiment scores through [FlairNLP](https://github.com/flairNLP/flair) for the text (or list of texts) in `text` and their ids in `text_id`
- `/empathy`:  Calculates the Empathy as from the paper "The Language of Situational Empathy" from Ke Zhou, Luca Maria Aiello, Sanja Scepanovic, Daniele Quercia, Sara Konrath [link](https://dl.acm.org/doi/10.1145/3449087) for the text (or list of texts) in `text` and their ids in `text_id`

At the moment the complexity and the empathy models are not publicly availabe.

The TenDimensions embeddings need to be downloaded from:
1. `Word2Vec`: the file `GoogleNews-vectors-negative300.wv` should be placed in the directory `embeddings/word2vec`. Download it from: https://code.google.com/archive/p/word2vec/
2. `Fasttext`: the file `wiki-news-300d-1M-subword.wv` should be placed in the directory `embeddings/fasttext`. Download it from: https://fasttext.cc/docs/en/english-vectors.html
3. `GloVe`: the file `wiki-news-300d-1M-subword.wv` should be placed in the directory `embeddings/fasttext`. Download it from: https://fasttext.cc/docs/en/english-vectors.html


I started implementing a socket-based communication but it's not working yet.

## How to run the server
Running the server is fairly simple:
1. Copy one of the yaml config files `config5000.yaml` for instance, it should look something like:
```yaml
upload_folder: "./upload_files_5000/"
ip: "0.0.0.0"
port: 5000
use_ten_dims: False
log_filename: "flask_5000.log"
```
2. run the flask app as `sudo python nlp_flask_server.py -c config5000.yaml`.
You can also run this with gunicorn as: `sudo gunicorn3 --preload -b 0.0.0.0:5000 wsgi:app`

You can run this as a service:
`sudo nohup sudo sudo python nlp_flask_server.py -c config5000.yaml &`
or
`sudo nohup sudo gunicorn3 --preload -b 0.0.0.0:5000 wsgi:app &`

If you then want to kill it from the background:
call:
`ps -ef | grep python`
or
`ps -ef | grep gun`
find the Procedd ID (PID) and then
`sudo kill [PID]` or `sudo pkill -P [PID]`

Gunicorn might have issues if you pass the argument `-c config5000.yaml`
So if using gunicorn I'd suggest to just remove the argument parsing part and load a known yaml config file instead.

## How to run the client
The client is even simpler. I wrapped everything in a class ready to be used in `nlp_flask_client.py`. The client is ready to send:

- Text
- List of texts
- Dataframes
- Files

Encrypt them, send them to the server. Receive the response, decrypt it and store it.
The client is also multi-threaded and can automatically split the dataframe in chunks to be sent out to the server.
It will automatically append the result to the dataframe, no need to specify the columns. It will automatically add any new column and keep the original ones. The output is a COPY of the original dataframe, not an updated dataframe.

1. Check `analyse_data.py` and change it to your needs

## How to add new models
This was the main point of this project. I wanted this to be easy to update and to add new pre-trained models to the server.
The process is fairly simple:

1. Add your new model code and import it in the `nlp_flask_server.py`
2. In the `Engine` class, add the model file loading code in the constructor
3. Add the model name in the `Models` class
4. Register the model's prediction function in the Engine class as:
```python
self.register_model(Engine.Models.ModelName, self.model.get_prediction)
```

Or alternatively, if your model needs multiple calls and some data wrangling, you can write a middle-ware function in the Engine class and register it as:

```python
self.register_model(Engine.Models.ModelName, self.get_prediction)
```
5. Add a middle function in the `Engine` class that calls your model for a text string. Something like:


Make sure that the method you register returns a dictionary (not a list). As the result dictionary will update itself from the values returned from the model.

6. Add a new `@app.route("/whatever", methods=['POST'])` and define a new function underneath with code that looks like this:

```python
ret_data, code = engine.call_model_from_request(request, Engine.Models.ModelName, app.logger)
```

7. And that's it! Restart the server and test it out from the client!
