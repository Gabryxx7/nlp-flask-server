from datetime import datetime

def dt_to_ts(datetime_str):
    # datetime_str = '2018-06-29 08:15:27.243860'
    datetime_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    return datetime.timestamp(datetime_obj)

def ts_to_dt(ts):
    return datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')

def formatted_now(sepDate="_", sepTime="_", sep="_"):
    return datetime.now().strftime('%Y{0}%m{0}%d{2}%H{1}%M{1}%S'.format(sepDate, sepTime, sep))

def get_conversation_type_string(conversation):
    convo_type = ""
    if "is_channel" in conversation.keys() and conversation["is_channel"]:
        if conversation["is_private"]:
            convo_type = "private channel"
        else:
            convo_type = "public_channel"
    elif "is_group" in conversation.keys() and conversation["is_group"]:
        convo_type = "group"
    elif "is_im" in conversation.keys() and conversation["is_im"]:
        convo_type = "im"
    elif "is_mpim" in conversation.keys() and conversation["is_mpim"]:
        convo_type = "mpim"
    # elif conversation["is_group"]:
    #     convo_type = "group"
    return convo_type

def get_conversation_name(conversation, users_list=None):
    convo_name = ""
    try:
        convo_name = conversation["name"]
    except KeyError as e:
        convo_name = conversation["user"]
        if users_list:
            convo_name = users_list[conversation["user"]]
    return convo_name

def print_dict_keys(dict):
    print(list(dict.keys()))