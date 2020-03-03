# -*- coding:utf-8 -*-

# Copyright xmuspeech (Author: Snowdar 2019-05-29)

import sys, os
import math
import random
import logging
import shutil
import numpy as np
import pandas as pd

import torch

# Logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def to_bool(variable):
    """Transform string to bool if variable is not bool
    """
    if not isinstance(variable, bool):
        if not isinstance(variable, str):
            raise TypeError("variable is not str or bool type")
        else:
            return True if variable == 'true' or variable == 'True' else False
    else:
        return variable


def auto_select_model_device(model, use_gpu, gpu_id="", benchmark=False):
    """ Auto select device (cpu/GPU) for model
    @use_gpu: bool or 'true'/'false' string
    """
    model.cpu()
    
    use_gpu = to_bool(use_gpu)
    benchmark = to_bool(benchmark)

    if use_gpu :
        if gpu_id == "":
            logger.info("The use_gpu is true and gpu_id is not specified, so select gpu device automatically.")
            import libs.support.GPU_Manager as gpu
            gm = gpu.GPUManager()
            gpu_id = gm.auto_choice()
        else:
            logger.info("The use_gpu is true and gpu_id is specified to {0}".format(gpu_id))

        torch.cuda.set_device(int(gpu_id))
        torch.backends.cudnn.benchmark = benchmark

        model.cuda()

    return model


def to_device(device_object, tensor):
    """
    Select device for non-parameters tensor w.r.t model or tensor which has been specified a device.
    """
    if isinstance(device_object, torch.nn.Module):
        device = next(device_object.parameters()).device
    elif isinstance(device_object, torch.Tensor):
        device = device_object.device

    return tensor.to(device)


def get_device(model):
    assert isinstance(model, torch.nn.Module)
    device = next(model.parameters()).device
    return device


def get_tensors(tensor_sets):
    """Get a single tensor list from a nested tensor_sets list/tuple object,
    such as transforming [(tensor1,tensor2),tensor3] to [tensor1,tensor2,tensor3]
    """
    tensors = []
    
    for this_object in tensor_sets:
        # Only tensor
        if isinstance(this_object, torch.Tensor):
            tensors.append(this_object)
        elif isinstance(this_object, list) or isinstance(this_object, tuple):
            tensors.extend(get_tensors(this_object))

    return tensors


def for_device_free(function):
    """
    A decorator to make class-function with input-tensor device-free
    Used in libs.nnet.framework.TopVirtualNnet
    """
    def wrapper(self, *tensor_sets):
        transformed = []

        for tensor in get_tensors(tensor_sets):
            transformed.append(to_device(self, tensor))

        return function(self, *transformed)

    return wrapper


def create_model_from_py(model_blueprint, model_creation=""):
    """ Used in pipeline/train.py and pipeline/onestep/extract_emdeddings.py and it makes config of nnet
    more free with no-change of training and other common scripts.

    @model_blueprint: string type, a *.py file path which includes the instance of nnet, such as examples/xvector.py
    @model_creation: string type, a command to create the model class according to the class declaration 
                     in model_blueprint, such as using 'Xvector(40,2)' to create an Xvector nnet.
                     Note, it will return model_module if model_creation is not given, else return model.
    """
    sys.path.insert(0, os.path.dirname(model_blueprint))
    model_module_name = os.path.basename(model_blueprint).split('.')[0]
    model_module = __import__(model_module_name)

    if model_creation == "":
        return model_module
    else:
        model = eval("model_module.{0}".format(model_creation))
        return model

def write_nnet_config(model_blueprint:str, model_creation:str, nnet_config:str):
    dataframe = pd.DataFrame([model_blueprint, model_creation], index=["model_blueprint", "model_creation"])
    dataframe.to_csv(nnet_config, header=None, sep=";")
    logger.info("Save nnet_config to {0} done.".format(nnet_config))


def read_nnet_config(nnet_config:str):
    logger.info("Read nnet_config from {0}".format(nnet_config))
    # Use ; sep to avoid some problem in spliting.
    dataframe = pd.read_csv(nnet_config, header=None, index_col=0, sep=";")
    model_blueprint = dataframe.loc["model_blueprint", 1]
    model_creation = dataframe.loc["model_creation", 1]

    return model_blueprint, model_creation


def create_model_dir(model_dir:str, model_blueprint:str, stage=-1):
    if not os.path.exists("{0}/log".format(model_dir)):
        os.makedirs("{0}/log".format(model_dir))

    # Just change the path of blueprint so that use the copy of blueprint which is in the config directory and it could 
    # avoid unkonw influence from the original blueprint which could be changed possibly before some processes needing 
    # this blueprint, such as pipeline/onestep/extracting_embedings.py
    config_model_blueprint = "{0}/config/{1}".format(model_dir, os.path.basename(model_blueprint))

    if not os.path.exists("{0}/config".format(model_dir)):
        os.makedirs("{0}/config".format(model_dir))

    if stage < 0 and model_blueprint != config_model_blueprint:
        shutil.copy(model_blueprint, config_model_blueprint)
    
    return config_model_blueprint


def draw_list_to_png(list_x, list_y, out_png_file, color='r', marker=None, dpi=256):
    """ Draw a piture for some values.
    """
    import matplotlib.pyplot as plt
    plt.figure()
    plt.plot(list_x, list_y, color=color, marker=marker)
    plt.savefig(out_png_file, dpi=dpi)
    plt.close()


def read_file_to_list(file_path, every_bytes=10000000):
    list = []
    with open(file_path, 'r') as reader :
            while True :
                lines = reader.readlines(every_bytes)
                if not lines:
                    break
                for line in lines:
                    list.append(line)
    return list


def write_list_to_file(this_list, file_path, mod='w'):
    """
    @mod: could be 'w' or 'a'
    """
    if not isinstance(this_list,list):
        this_list = [this_list]

    with open(file_path, mod) as writer :
        writer.write('\n'.join(str(x) for x in this_list))
        writer.write('\n')


def save_checkpoint(checkpoint_path, **kwargs):
    """Save checkpoint to file for training. Generally, The checkpoint includes
        epoch:<int>
        iter:<int>
        model_path:<string>
        optimizer:<optimizer.state_dict>
        lr_scheduler:<lr_scheduler.state_dict>
    """
    state_dict = {}
    state_dict.update(kwargs)
    torch.save(state_dict, checkpoint_path)


def format(x, str):
    """To hold on the None case when formating float to string.
    @x: a float value or None or any others, should be consistent with str
    @str: a format such as {:.2f}
    """
    if x is None:
        return "-"
    else:
        return str.format(x)


def set_all_seed(seed=None):
    """This is refered to https://github.com/lonePatient/lookahead_pytorch/blob/master/tools.py.
    """
    if seed is not None:
        random.seed(seed)
        os.environ['PYTHONHASHSEED'] = str(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # some cudnn methods can be random even after fixing the seed
        # unless you tell it to be deterministic
        torch.backends.cudnn.deterministic = True


def key_to_value(adict, key, return_none=True):
    assert isinstance(adict, dict)

    if key in adict.keys():
        return adict[key]
    elif return_none:
        return None
    else:
        return key


def assign_params_dict(default_params:dict, params:dict, force_check=False, support_unknow=False):
    # Should keep force_check=False to use support_unknow
    default_keys = set(default_params.keys())

    if force_check:
        for key in param.keys():
            if key not in default_keys:
                raise ValueError("The params key {0} is not in default params".format(key))

    # Do default params <= params if they have the same key
    params_keys = set(params.keys())
    for k, v in default_params.items():
        if k in params_keys:
            if isinstance(v, type(params[k])):
                default_params[k] = params[k]
            elif isinstance(v, float) and isinstance(params[k], int):
                default_params[k] = params[k] * 1.0
            elif v is None or params[k] is None:
                default_params[k] = params[k]
            else:
                raise ValueError("The value type of default params [{0}] is "
                "not equal to [{1}] of params for k={2}".format(type(default_params[k]), type(params[k]), k))

    # Support unknow keys
    if not force_check and support_unknow:
        for key in params.keys():
            if key not in default_keys:
                default_params[key] = params[key]

    return default_params


def split_params(params:dict):
    params_split = {"public":{}} 
    params_split_keys = params_split.keys()
    for k, v in params.items():
        if len(k.split(".")) == 2:
            name, param = k.split(".")
            if name in params_split_keys:
                params_split[name][param] = v
            else:
                params_split[name] = {param:v}
        elif len(k.split(".")) == 1:
            params_split["public"][k] = v
        else:
            raise ValueError("Expected only one . in key, but got {0}".format(k))

    return params_split


def auto_str(value, auto=True):
    if isinstance(value, str) and auto:
        return "'{0}'".format(value)
    else:
        return str(value)

def iterator_to_params_str(iterator, sep=",", auto=True):
    return sep.join(auto_str(x, auto) for x in iterator)

def dict_to_params_str(dict, auto=True, connect="=", sep=","):
    params_list = []
    for k, v in dict.items():
        params_list.append(k+connect+auto_str(v, auto))
    return iterator_to_params_str(params_list, sep, False)


def read_log_csv(csv_path:str):
    dataframe = pd.read_csv(csv_path).drop_duplicates(["epoch", "iter"], keep="last", inplace=True)
    return dataframe


